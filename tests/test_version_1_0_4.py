"""Demandes du propriétaire du 2026-11-01 (version 1.0.4)."""
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from mvogmbi_sync import feuillets as fe
from mvogmbi_sync import ria_etats
from mvogmbi_sync.courriel import copie_cachee
from mvogmbi_sync.design import montant_saisi
from mvogmbi_sync.fenetre_paie import paie_dans_le_futur
from mvogmbi_sync.fiches import nom_emplacement
from mvogmbi_sync.utilisateurs import ADMIN, Registre

ETAT = """Account Statement Summary
Marche Exemple Inc. (QC0001)
From 10/23/2026 To 10/26/2026
Previous Balance as of 0.00 0.00 0.00
Date of Last Deposit: 10/21/2026
Amount of Last Deposit: 599.99
Total Balance 82.64 -2,259.75 -2,177.11
Amount to Pay 0.00
Commission
Payment Date 10/2/2026
Commission paid for Sep 2026 10.26
Commission accrued for Oct 2026 14.03
Account Statement Detail
10/23/2026 MT Send 72 CA0000000001 72.64 10.00 3.00 82.64 82.64
10/23/2026 MT Send Total 1 72.64 10.00 3.00 82.64 82.64
10/23/2026 MT Payout 900000002 CM0000000002 -2,259.75 11.03 -2,259.75 -2,177.11
10/23/2026 MT Payout 1 -2,259.75 11.03 -2,259.75 -2,177.11
10/23/2026 Grand Total 2 -2,187.11 10.00 14.03 82.64 -2,259.75 -2,177.11
"""


def test_etat_ria_lu_et_controle():
    e = ria_etats.lire_texte(ETAT)
    assert (e.agence, e.debut, e.fin) == ("QC0001", "2026-10-23", "2026-10-26")
    assert (e.debits, e.credits, e.total) == ("82.64", "-2259.75", "-2177.11")
    assert (e.commission_payee, e.date_paiement_commission, e.commission_courue) == ("10.26", "2026-10-02", "14.03")
    assert [(l.activite, l.mouvement) for l in e.lignes] == [("MT Send", "82.64"), ("MT Payout", "-2259.75")]
    assert e.remarques == [] and e.somme("MT Payout", "commission") == D("11.03")
    with pytest.raises(ValueError):
        ria_etats.lire_texte("Relevé de la caisse")


def test_commission_reconnue_dans_le_releve():
    e = ria_etats.lire_texte(ETAT)
    depot = SimpleNamespace(montant=D("10.26"), date="2026-10-06", cle="R|4")
    autre = SimpleNamespace(montant=D("10.26"), date="2026-11-30", cle="R|9")
    assert ria_etats.commissions_reconnues([autre, depot], [e]) == ["R|4"]


def test_montant_saisi():
    assert montant_saisi("12,50 $") == D("12.50") and montant_saisi("1 234,56") == D("1234.56")
    assert montant_saisi("1,234.56") == D("1234.56")
    with pytest.raises(ValueError, match="Montant invalide"):
        montant_saisi("douze")


def test_verrouillage_apres_trois_mots_de_passe_faux(tmp_path):
    r = Registre(tmp_path)
    r.ajouter("Patron", ADMIN, "secret123456")
    r.ajouter("Jean", "Employé", "secret123456")
    for _ in range(3):
        assert r.verifier("Jean", "faux") is None
    assert r.trouver("Jean").verrouille and r.verifier("Jean", "secret123456") is None
    r.changer_mot_de_passe("Jean", "nouveau12345")  # l'administrateur rouvre le compte
    assert r.verifier("Jean", "nouveau12345") is not None and r.trouver("Jean").echecs == 0
    for _ in range(3):  # le dernier administrateur n'est jamais verrouillé : seulement bloqué un moment
        r.verifier("Patron", "faux")
    assert not r.trouver("Patron").verrouille and r.bloque(r.trouver("Patron"))


def test_jamais_de_paie_dans_le_futur():
    aujourdhui = date(2026, 11, 1)
    assert paie_dans_le_futur(date(2026, 11, 3), date(2026, 11, 18), aujourdhui)
    assert paie_dans_le_futur(date(2026, 10, 20), date(2026, 11, 18), aujourdhui)
    assert paie_dans_le_futur(date(2026, 10, 20), date(2026, 10, 30), aujourdhui) == ""


def test_copie_cachee_et_emplacement():
    assert copie_cachee({"cci": "patron@exemple.test"}) == ["patron@exemple.test"]
    assert copie_cachee({"destinataires": "a@exemple.test, b@exemple.test"}) == ["a@exemple.test"]
    assert nom_emplacement("Primary location for all") == "Emplacement par défaut"
    assert nom_emplacement("Dépôt 2") == "Dépôt 2"


def test_formulaires_livres_conformes_et_copie_gardee(tmp_path):
    for genre, chemin in (("T4", fe.T4_PDF), ("RL-1", fe.RL1_PDF)):
        assert fe.formulaire_conforme(chemin.read_bytes(), genre)
    assert not fe.formulaire_conforme(fe.T4_PDF.read_bytes(), "RL-1")
    copie = tmp_path / "donnees" / "formulaires" / "t4.pdf"  # copie récente : aucun téléchargement
    copie.parent.mkdir(parents=True)
    copie.write_bytes(fe.T4_PDF.read_bytes())
    assert fe.formulaire(tmp_path, "T4") == (copie, "")


def test_formulaires_officiels_remplis():
    pypdf = pytest.importorskip("pypdf")
    pytest.importorskip("fpdf")
    import io

    f = fe.Feuillet(2026, "EXEMPLE JEAN", brut=D("1234.50"), rrq=D("70.00"), impot_quebec=D("90.00"))
    employeur = SimpleNamespace(nom="Marché Exemple", adresse="1 rue", ville="Sherbrooke")
    contenu = fe.pdf_officiels([f], employeur, "123456789RP0001")
    pages = pypdf.PdfReader(io.BytesIO(contenu)).pages
    assert len(pages) == 3  # T4 (feuillets + verso) puis RL-1
    texte = pages[0].extract_text() + pages[2].extract_text()
    assert "1 234" in texte and "123456789RP0001" in texte and "EXEMPLE JEAN" in texte

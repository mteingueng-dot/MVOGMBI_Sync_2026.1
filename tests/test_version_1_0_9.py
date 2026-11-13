"""Version 1.0.9 : états RIA traités dans Sage, promotion en cours annulée, courriel réessayé, en-têtes IMAP lus en une
demande, modification et suppression des articles."""

import smtplib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from email.message import EmailMessage

from mvogmbi_sync import courriel, ria, ria_etats
from mvogmbi_sync import paquet3 as p3
from mvogmbi_sync.paiements_courriel import entetes_en_une_fois
from mvogmbi_sync.robot_fiches_articles import DemandeArticle

TEXTE = """Account Statement
Agence (QC1234)
From 10/01/2026 To 10/07/2026
Previous Balance as of 10/01/2026 0.00 0.00 100.00
Account Statement Detail
10/02/2026 MT Send 111 DOE JOHN 200.00 5.00 1.50 205.00 305.00
10/03/2026 MT Payout 222 SMITH ANA 50.00 0.50 -50.00 255.00
10/03/2026 MT Payout 1 -50.00 255.00
10/04/2026 ACH 333 RIA PAYMENT -255.00 0.00
MT Payout Total -50.00
Total Balance 205.00 -305.00 0.00
"""


def test_lecture_des_lignes_ria():
    e = ria_etats.lire_texte(TEXTE)
    assert e.agence == "QC1234"
    assert [(l.activite, l.reference) for l in e.lignes] == [("MT Send", "111"), ("MT Payout", "222"), ("ACH", "333")]
    envoi = e.lignes[0]
    assert (envoi.montant, envoi.frais, envoi.commission, envoi.mouvement) == ("200.00", "5.00", "1.50", "205.00")
    assert e.lignes[1].mouvement == "-50.00" and e.lignes[2].description == "RIA PAYMENT"


@dataclass
class Mouvement:
    date: str
    montant: Decimal
    description: str


def test_operations_des_etats(tmp_path):
    e = ria_etats.lire_texte(TEXTE, "etat.pdf")
    e.lecture = ria_etats.VERSION_LECTURE
    registre = ria_etats.Registre(tmp_path)
    registre.etats.append(e)
    registre.enregistrer()
    banque = [Mouvement("2026-10-04", Decimal("-50.00"), "Virement Interac Paiement RIA")]
    assert ria_etats.operations_des_etats(tmp_path, banque) == 1  # le versement payé par Interac est sauté
    assert ria_etats.operations_des_etats(tmp_path, banque) == 0  # jamais deux fois
    ops = ria.Registre(tmp_path).operations
    assert [(o.genre, Decimal(o.montant)) for o in ops] == [(ria.ENVOI, Decimal("205.00"))]
    assert ria.Registre(tmp_path).comptes["mode"] == "etats"
    # sans le virement, le versement est payé en espèces
    autre = tmp_path / "autre"
    registre = ria_etats.Registre(autre)
    registre.etats.append(e)
    registre.enregistrer()
    assert ria_etats.operations_des_etats(autre) == 2
    assert {o.genre for o in ria.Registre(autre).operations} == {ria.ENVOI, ria.ESPECES}


class FauxClover:
    def __init__(self, prix):
        self.prix, self.regles = prix, []

    def _get(self, chemin):
        prix = self.prix

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"price": int(prix * 100)}

        return R()

    def regler_prix(self, id_clover, prix):
        self.regles.append((id_clover, prix))


def _promotion(tmp_path, etat):
    registre = p3.Promotions(tmp_path)
    jour = date.today()
    registre.liste.append(p3.Promotion("PR-0001", "ID1", "Plantain", "1.50", (jour - timedelta(days=1)).isoformat(),
                                       (jour + timedelta(days=3)).isoformat(), prix_normal="2.00", etat=etat))
    registre.enregistrer()


def test_annuler_une_promotion_en_cours(tmp_path):
    _promotion(tmp_path, p3.EN_COURS)
    client = FauxClover(Decimal("1.50"))
    p3.annuler_promotion(tmp_path, "PR-0001", client)
    assert client.regles == [("ID1", Decimal("2.00"))]
    assert p3.Promotions(tmp_path).liste[0].etat == p3.ANNULEE
    try:
        p3.annuler_promotion(tmp_path, "PR-0001", client)
        assert False, "une promotion annulée ne s'annule pas deux fois"
    except ValueError:
        pass


def test_promotion_en_cours_dont_le_prix_a_change(tmp_path):
    _promotion(tmp_path, p3.EN_COURS)
    client = FauxClover(Decimal("1.75"))
    texte = p3.annuler_promotion(tmp_path, "PR-0001", client)
    assert client.regles == [] and "laissé" in texte


def test_envoi_reessaye(monkeypatch):
    essais = []

    def une_fois(c, message, delai):
        essais.append(delai)
        if len(essais) < 3:
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed: timed out")

    monkeypatch.setattr(courriel, "_expedier_une_fois", une_fois)
    monkeypatch.setattr("time.sleep", lambda s: None)
    courriel._expedier({}, EmailMessage())
    assert essais == [60, 120, 180]
    essais.clear()
    monkeypatch.setattr(courriel, "_expedier_une_fois",
                        lambda c, m, d: (_ for _ in ()).throw(smtplib.SMTPAuthenticationError(535, b"mot de passe")))
    try:
        courriel._expedier({}, EmailMessage())
        assert False
    except smtplib.SMTPAuthenticationError:
        pass  # erreur de mot de passe : jamais réessayée


def test_entetes_en_une_fois():
    class Boite:
        def __init__(self):
            self.demandes = 0

        def uid(self, commande, uids, parties):
            self.demandes += 1
            assert uids == b"2,10"
            return "OK", [(b"1 (UID 2 BODY[HEADER.FIELDS (MESSAGE-ID)] {30}", b"Message-ID: <a@x>\r\n\r\n"), b")",
                          (b"2 (UID 10 BODY[HEADER.FIELDS (MESSAGE-ID)] {4}", b"\r\n"), b")"]

    boite = Boite()
    assert entetes_en_une_fois(boite, [b"10", b"2"]) == {b"2": "<a@x>", b"10": ""}
    assert boite.demandes == 1 and entetes_en_une_fois(boite, []) == {}


def test_demande_article():
    d = DemandeArticle("modifier", "ESSAI0003", inactif=True)
    assert d.description == "" and d.inactif is True


def test_ancienne_entree_ria_donne_les_nouvelles(tmp_path):
    import json

    from mvogmbi_sync.interface import MENU_GROUPES
    from mvogmbi_sync.utilisateurs import Registre, _renommees

    assert _renommees(["RIA (transferts d'argent)", "tableau"]) == sorted(
        ["Opérations RIA", "États de compte RIA", "Comptes RIA", "tableau"])
    titres = {g: [e[1] for e in entrees if isinstance(e, tuple)] for g, _, entrees in MENU_GROUPES if g}
    # demande du propriétaire du 2026-11-06 : états de compte et comptes RIA dans la rubrique RIA
    assert titres["RIA"] == ["Opérations RIA", "États de compte RIA", "Comptes RIA"]
    assert not {"États de compte RIA", "Comptes RIA"} & set(titres["Comptabilité"])
    assert not any("RIA (transferts" in t for t in titres["Comptabilité"])
    r = Registre(tmp_path)
    r.ajouter("Patron", "Administrateur", "secret123456")
    r.definir_acces("Comptable", ["RIA (transferts d'argent)"], [])
    r.enregistrer()
    relu = Registre(tmp_path)
    assert "Opérations RIA" in relu.fonctions_permises["Comptable"]
    json.loads((tmp_path / "donnees" / "utilisateurs.json").read_text(encoding="utf-8"))

from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.automatique import (AUCUNE_VENTE, BLOQUEE, IMPORTEE, REPORTEE, CompteRendu, EtatJour)
from mvogmbi_sync.courriel import html_compte_rendu, sujet_compte_rendu, texte_compte_rendu


def compte_rendu_succes():
    cr = CompteRendu(fichier="MARCHE.SAI", derniere_avant=date(2026, 10, 20),
                     periode=(date(2026, 10, 21), date(2026, 10, 23)))
    cr.jours = [
        EtatJour(date(2026, 10, 21), IMPORTEE, "", 150, D("2500.00"), D("40.00"), D("2540.00")),
        EtatJour(date(2026, 10, 22), AUCUNE_VENTE),
        EtatJour(date(2026, 10, 23), IMPORTEE, "", 155, D("3139.39"), D("57.83"), D("3197.22")),
    ]
    return cr


def test_courriel_de_succes():
    cr = compte_rendu_succes()
    assert cr.succes
    assert sujet_compte_rendu(cr) == "MVOGMBI_Sync : succès — 2 facture(s) importée(s) du 21/10 au 23/10/2026"
    texte = texte_compte_rendu(cr)
    assert "Période traitée : du 2026-10-21 au 2026-10-23" in texte
    assert "2026-10-22 (jeudi) : Aucune vente" in texte
    assert "2026-10-23 (vendredi) : Facture importée — 155 lignes" in texte
    assert "Total importé : 2 facture(s), 5 737,22 $ taxes comprises" in texte
    page = html_compte_rendu(cr)
    assert "<table" in page and "Facture importée" in page and "5 737,22 $" in page


def test_courriel_avec_jour_bloque():
    cr = compte_rendu_succes()
    cr.jours[2] = EtatJour(date(2026, 10, 23), BLOQUEE, "article Clover non relié à Sage : Colombianas")
    cr.jours.append(EtatJour(date(2026, 10, 24), REPORTEE, "en attente de la correction du 2026-10-23"))
    cr.problemes.append("2026-10-23 : article Clover non relié à Sage : Colombianas")
    assert sujet_compte_rendu(cr) == "MVOGMBI_Sync : 1 point(s) à corriger — 1 facture(s) importée(s)"
    texte = texte_compte_rendu(cr)
    assert "Bloquée" in texte and "Colombianas" in texte and "Reportée à la prochaine exécution" in texte


def test_courriel_sage_a_jour():
    cr = CompteRendu(fichier="MARCHE.SAI", derniere_avant=date(2026, 10, 24))
    assert sujet_compte_rendu(cr) == "MVOGMBI_Sync : Sage est à jour (dernière facture : 2026-10-24)"
    assert "aucune (Sage était déjà à jour)" in texte_compte_rendu(cr)


def test_copie_cc():
    from mvogmbi_sync.courriel import adresses_invalides, preparer_message

    c = {"serveur": "mail.exemple.com", "expediteur": "notification@marchemvogmbi.com",
         "destinataires": "contact@marchemvogmbi.com", "copie": "a@exemple.com; b@exemple.com\nContact@marchemvogmbi.com"}
    message = preparer_message(c, "Sujet", "Corps")
    assert message["To"] == "contact@marchemvogmbi.com"
    assert message["Cc"] == "a@exemple.com, b@exemple.com"  # le destinataire principal n'est pas répété en copie
    assert preparer_message({**c, "copie": ""}, "Sujet", "Corps")["Cc"] is None
    assert adresses_invalides("a@exemple.com, pas-une-adresse, b@exemple") == ["pas-une-adresse", "b@exemple"]

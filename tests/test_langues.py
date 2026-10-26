import ast
from pathlib import Path

from mvogmbi_sync import langues
from mvogmbi_sync.aide import ACCUEIL, FAQ, GUIDE

PAQUET = Path(__file__).resolve().parent.parent / "mvogmbi_sync"


def textes_traduits() -> set[str]:
    """Tous les textes littéraux passés à t(...) dans le code de l'application."""
    trouves = set()
    for fichier in PAQUET.glob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) and noeud.func.id == "t"
                    and noeud.args and isinstance(noeud.args[0], ast.Constant) and isinstance(noeud.args[0].value, str)):
                trouves.add(noeud.args[0].value)
    return trouves


def test_tous_les_textes_ont_une_traduction_anglaise():
    manquants = sorted(textes_traduits() - set(langues.EN))
    assert manquants == [], f"Textes sans traduction anglaise : {manquants}"


def test_etats_et_filtres_traduits():
    from mvogmbi_sync.automatique import (AUCUNE_VENTE, BLOQUEE, DEJA_PRESENTE, ECHEC, IMPORTEE, PRETE, REPORTEE)
    from mvogmbi_sync.page_correspondance import COLONNES, FILTRES

    for texte in [IMPORTEE, PRETE, AUCUNE_VENTE, DEJA_PRESENTE, BLOQUEE, REPORTEE, ECHEC, *FILTRES,
                  *(c[1] for c in COLONNES)]:
        assert texte in langues.EN, texte


def test_t_et_changement_de_langue():
    try:
        langues.definir("en")
        assert langues.t("Enregistrer la configuration") == "Save configuration"
        assert langues.t("connecté à « {nom} »", nom="Marché") == "connected to “Marché”"
        assert langues.t("Texte inconnu") == "Texte inconnu"
        assert langues.jours_semaine()[0] == "Monday"
        langues.definir("xx")
        assert langues.courante() == "fr"
    finally:
        langues.definir("fr")


def test_pages_aide_dans_les_deux_langues():
    for page in (ACCUEIL, FAQ, GUIDE):
        assert set(page) == {"fr", "en"}
        assert [b[0] for b in page["fr"]] == [b[0] for b in page["en"]]  # même structure


def test_courriel_en_anglais():
    from datetime import date
    from decimal import Decimal as D

    from mvogmbi_sync.automatique import AUCUNE_VENTE, IMPORTEE, CompteRendu, EtatJour
    from mvogmbi_sync.courriel import html_compte_rendu, sujet_compte_rendu, texte_compte_rendu

    cr = CompteRendu(fichier="MARCHE.SAI", derniere_avant=date(2026, 10, 20),
                     periode=(date(2026, 10, 21), date(2026, 10, 22)))
    cr.jours = [EtatJour(date(2026, 10, 21), IMPORTEE, "", 150, D("2500.00"), D("40.00"), D("2540.00")),
                EtatJour(date(2026, 10, 22), AUCUNE_VENTE)]
    try:
        langues.definir("en")
        assert sujet_compte_rendu(cr) == "MVOGMBI_Sync: success — 1 invoice(s) imported from 21/10 to 22/10/2026"
        texte = texte_compte_rendu(cr)
        assert "2026-10-21 (Wednesday) : Invoice imported — 150 lines, subtotal $2,500.00" in texte
        assert "Total imported: 1 invoice(s), $2,540.00 including taxes" in texte
        assert "No sales" in html_compte_rendu(cr)
    finally:
        langues.definir("fr")

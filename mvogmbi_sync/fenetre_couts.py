"""Fenêtres « Coûts Clover depuis Sage » (CUMP) et « Comptes Sage à corriger » (table catégorie -> comptes) : les
lignes sont proposées, la personne coche celles à mettre à jour puis lance la mise à jour."""

from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path

from .fenetre_cocher import FenetreACocher
from .langues import t


def _config(racine: Path) -> dict:
    return tomllib.loads((Path(racine) / "config.toml").read_text(encoding="utf-8"))


def _montant(valeur: Decimal | None) -> str:
    return "" if valeur is None else f"{valeur:.2f} $".replace(".", ",")


class FenetreCoutsClover(FenetreACocher):
    def __init__(self, parent, racine: Path):
        from . import couts_clover as cc

        self.racine = Path(racine)

        def valeurs(p):
            ecart = "" if p.cump is None or p.cout_clover is None else f"{p.cump - p.cout_clover:+.2f}".replace(".", ",")
            marge = "" if not p.prix or p.cump is None else f"{(p.prix - p.cump) / p.prix * 100:.0f} %"
            return (p.nom, p.numero_sage, _montant(p.prix), _montant(p.cout_clover), _montant(p.cump), ecart, marge,
                    t(p.etat), t(p.note) if p.note else "")

        def lire():
            propositions, a_jour = cc.lire(self.racine, _config(self.racine))
            return propositions, t("{n} article(s) proposé(s), {a} déjà au coût Sage. Les valeurs aberrantes (grisées) "
                                   "ne peuvent pas être cochées.", n=len(propositions), a=a_jour)

        def traiter(lignes, progression):
            resultats = cc.appliquer(self.racine, lignes, progression)
            erreurs = [f"{p.nom} : {e}" for p, e in resultats if e]
            return t("{n} coût(s) Clover mis à jour.", n=len(resultats) - len(erreurs)) + (
                "\n\n" + t("Non mis à jour :") + "\n" + "\n".join(erreurs[:15]) if erreurs else "")

        super().__init__(
            parent, t("Coûts Clover depuis Sage"),
            t("Le coût moyen (CUMP) de l'article dans Sage remplace le coût Clover. Cochez les lignes à mettre à jour "
              "(clic sur la case, ou barre d'espace sur les lignes sélectionnées), puis lancez la mise à jour. "
              "Jamais de valeur aberrante : CUMP absent, plus de 5 fois le prix de vente ou sous 5 % du prix."),
            [("Article Clover", 300), ("N° Sage", 110), ("Prix de vente", 90), ("Coût Clover", 90),
             ("Coût Sage (CUMP)", 125), ("Écart", 70), ("Marge", 60), ("État", 130), ("Remarque", 260)],
            valeurs, lire, traiter, t("Mettre à jour les coûts Clover"),
            t("Le coût Clover de {n} article(s) sera remplacé par le coût moyen de Sage.\n\nContinuer ?"))


class LigneComptes:
    """Une correction proposée, vue par la liste à cocher."""

    def __init__(self, c):
        self.c = c
        self.permis = True
        self.cochee_par_defaut = "Actif" not in c.changements  # changer le compte d'actif : à décider
        self.etat = "Écart vide" if c.changements == ["Écart"] and not c.actuel[3] else (
            "Compte d'actif différent" if "Actif" in c.changements else "Comptes différents")


class FenetreComptesSage(FenetreACocher):
    def __init__(self, parent, racine: Path):
        from .correspondance import lire_correspondances
        from .creation_articles import TableCategories, comptes_a_corriger, creer_dans_sage, lire_comptes_sage
        from .robot_articles import ArticleACreer

        self.racine = Path(racine)

        def valeurs(l):
            c = l.c
            return (c.numero, c.description, c.categorie, t(c.source), " / ".join(x or "—" for x in c.actuel),
                    " / ".join(c.attendu), ", ".join(t(x) for x in c.changements), t(l.etat))

        def lire():
            config = _config(self.racine)
            corrections, inconnus = comptes_a_corriger(
                lire_comptes_sage(self.racine, config), TableCategories(self.racine),
                lire_correspondances(self.racine / "donnees" / "correspondance_articles.xlsx"))
            return [LigneComptes(c) for c in corrections], t(
                "{n} article(s) Sage dont les comptes ne suivent pas la table ; {i} sans catégorie reconnue. Un "
                "changement du compte d'actif est proposé décoché.", n=len(corrections), i=inconnus)

        def traiter(lignes, progression):
            articles = [ArticleACreer(l.c.numero, l.c.description, *l.c.attendu) for l in lignes]
            resultats = creer_dans_sage(self.racine, _config(self.racine), articles, comptes=True)
            erreurs = [f"{r['numero']} : {' ; '.join(m for m in r['messages'] if m)}" for r in resultats
                       if not r["cree"]]
            return t("{n} article(s) corrigé(s) dans Sage.", n=len(resultats) - len(erreurs)) + (
                "\n\n" + t("Non corrigés :") + "\n" + "\n".join(erreurs[:15]) if erreurs else "")

        super().__init__(
            parent, t("Comptes Sage à corriger"),
            t("Articles de Sage dont un compte (actif, produits, CMV, écart) diffère de la table « Comptes Sage par "
              "catégorie Clover ». Catégorie = celle des articles Clover reliés, sinon celle du compte d'actif. "
              "Cochez les lignes à corriger, puis lancez la correction : l'application ouvre Sage elle-même s'il est "
              "fermé ; s'il est ouvert, ne touchez ni au clavier ni à la souris pendant la correction."),
            [("N° Sage", 120), ("Description Sage", 280), ("Catégorie", 150), ("Selon", 120),
             ("Comptes actuels", 190), ("Comptes de la table", 190), ("À changer", 190), ("État", 180)],
            valeurs, lire, traiter, t("Corriger dans Sage"),
            t("Les comptes de {n} article(s) seront corrigés dans Sage.\n\nContinuer ?"))

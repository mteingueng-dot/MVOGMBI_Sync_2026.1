"""Fenêtre « Prix et marges » (rubrique Articles, demande du propriétaire du 2026-10-29) : articles Clover sous la
marge minimale, prix proposé à cocher, mise à jour des prix dans Clover. Calculs dans prix_marges.py."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import prix_marges as pm
from .design import CARTE
from .langues import t


def _argent(v) -> str:
    return "" if v is None else f"{v:,.2f} $".replace(",", " ").replace(".", ",")


def _pourcent(v) -> str:
    return "" if v is None else f"{v} %".replace(".", ",")


def ouvrir(parent, racine: Path):
    from .fenetre_cocher import FenetreACocher

    racine = Path(racine)
    reglages = {"marge": tk.StringVar(value="25"), "arrondi": tk.StringVar(value=t(pm.ARRONDIS[0])),
                "donnees": None, "relire": True}

    def recalculer(fenetre):
        reglages["relire"] = False  # nouveau calcul sans relire Clover ni Sage
        fenetre.charger()

    def ajouts(fenetre, barre):
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Marge minimale"), background=CARTE).pack(side="left")
        choix = ttk.Combobox(groupe, textvariable=reglages["marge"], values=[str(m) for m in pm.MARGES],
                             state="readonly", width=4)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: recalculer(fenetre))
        tk.Label(groupe, text="%", background=CARTE).pack(side="left")
        groupe = barre.ajouter(barre.groupe(), 12)
        tk.Label(groupe, text=t("Arrondi"), background=CARTE).pack(side="left")
        choix = ttk.Combobox(groupe, textvariable=reglages["arrondi"], values=[t(a) for a in pm.ARRONDIS],
                             state="readonly", width=10)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: recalculer(fenetre))

    def lire():
        import tomllib

        if reglages["relire"] or reglages["donnees"] is None:
            chemin = racine / "config.toml"
            config = tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
            reglages["donnees"] = pm.lire_donnees(racine, config)
        reglages["relire"] = True  # « Actualiser » relit
        d = reglages["donnees"]
        mode = next((a for a in pm.ARRONDIS if t(a) == reglages["arrondi"].get()), pm.ARRONDIS[0])
        marge = int(reglages["marge"].get())
        lignes, correctes = pm.analyser(d["articles"], d["liens"], d["couts"], d["ventes"], marge, mode)
        sous = [l for l in lignes if l.etat == pm.SOUS_MARGE]
        effet = sum((l.effet or 0 for l in sous), 0)
        return lignes, t("{n} article(s) sous {m} % de marge (proposés cochés), {v} à vérifier, {c} à la bonne marge. "
                         "Effet estimé des lignes proposées sur {j} jours de ventes : {e}. Coût = CUMP de Sage "
                         "(sinon coût Clover) ; rien ne change dans Clover sans votre clic.", n=len(sous), m=marge,
                         v=sum(1 for l in lignes if l.etat == pm.A_VERIFIER), c=correctes, j=pm.JOURS_VENTES,
                         e=_argent(effet))

    def traiter(choisies, progression):
        resultats = pm.appliquer(racine, choisies, progression)
        erreurs = [(l, e) for l, e in resultats if e]
        texte = t("{n} prix mis à jour dans Clover (journal : donnees/journal_prix_clover.csv).",
                  n=len(resultats) - len(erreurs))
        if erreurs:
            texte += "\n" + t("Non mis à jour :") + "\n" + "\n".join(f"• {l.nom} : {e}" for l, e in erreurs[:15])
        return texte

    return FenetreACocher(
        parent, t("Prix et marges"),
        t("Articles Clover dont la marge (prix Clover − coût) est sous la marge minimale choisie, avec le prix proposé "
          "(coût / (1 − marge), arrondi). Cochez les prix à changer, puis « Mettre à jour les prix dans Clover »."),
        [("Article Clover", 230), ("Catégorie", 140), ("N° Sage", 95), ("Coût", 80), ("Source du coût", 95),
         ("Prix Clover", 85), ("Marge", 65), ("Prix proposé", 90), ("Marge après", 80), ("Vendu 90 j", 75),
         ("Effet 90 j", 85), ("État", 160), ("Remarque", 220)],
        lambda l: (l.nom, l.categorie, l.numero_sage, _argent(l.cout), t(l.source_cout) if l.source_cout else "",
                   _argent(l.prix), _pourcent(l.marge), _argent(l.nouveau), _pourcent(l.marge_apres),
                   f"{l.vendu.normalize():f}".replace(".", ",") if l.vendu else "", _argent(l.effet), t(l.etat),
                   t(l.note) if l.note else ""),
        lire, traiter, t("Mettre à jour les prix dans Clover"),
        t("Changer le prix de vente de {n} article(s) dans Clover ? Les nouveaux prix s'appliquent tout de suite aux "
          "caisses."), ajouts=ajouts)

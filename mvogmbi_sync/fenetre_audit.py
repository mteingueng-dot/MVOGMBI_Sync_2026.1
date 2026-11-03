"""Administration > « Audit des actions » : table d'audit (audit.py) avec filtres et contrôle de l'intégrité."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from pathlib import Path

from . import audit
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, FenetreOutil, Rangee, apres_frappe
from .export_tableau import bouton_exporter
from .langues import t


class FenetreAudit(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("Audit des actions"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1150x650")
        barre = Rangee(self)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        self.du = tk.StringVar(value=(date.today() - timedelta(days=7)).isoformat())
        self.au = tk.StringVar(value=date.today().isoformat())
        tk.Label(g, text=t("Du"), background=CARTE).pack(side="left", padx=(0, 4))
        ChampDate(g, self.du, fond=CARTE).pack(side="left")
        tk.Label(g, text=t("au"), background=CARTE).pack(side="left", padx=4)
        ChampDate(g, self.au, fond=CARTE).pack(side="left")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Rechercher :"), background=CARTE).pack(side="left", padx=(0, 4))
        self.texte = tk.StringVar()
        champ = tk.Entry(g, textvariable=self.texte, width=26)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher))
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.afficher, fond=CARTE, petit=True), 10)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1100)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=20)
        self.tableau.tag_configure("rompue", background="#fde2e4")
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Audit des actions")))
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        entrees = audit.lire(self.racine)
        rompues = set(audit.verifier(entrees))
        du, au, texte = self.du.get().strip(), self.au.get().strip() + "T99", self.texte.get().strip().casefold()
        choisies = [(i, e) for i, e in enumerate(entrees) if du <= e.moment <= au
                    and (not texte or texte in f"{e.utilisateur} {e.fenetre} {e.action} {e.detail} {e.poste}".casefold())]
        choisies.reverse()  # la plus récente en haut
        remplir(self.tableau, ["Moment", "Utilisateur", "Poste", "Fenêtre", "Action", "Détail"],
                [[e.moment.replace("T", " "), e.utilisateur, e.poste, e.fenetre, e.action, e.detail] for _i, e in choisies],
                {"Moment": 150, "Fenêtre": 220, "Action": 260, "Détail": 300},
                lambda k: ("rompue",) if choisies[k][0] in rompues else (), decroissant=False)
        if rompues:
            self.etat.configure(text=t("⚠ {n} ligne(s) dont l'empreinte ne suit pas : modifiée(s) ou retirée(s) après "
                                       "coup (en rouge).", n=len(rompues)), foreground=ROUGE)
        else:
            self.etat.configure(text=t("{n} action(s) affichée(s) sur {m} ; journal intact (empreintes vérifiées).",
                                       n=len(choisies), m=len(entrees)), foreground=VERT_FONCE if entrees else TEXTE_DOUX)

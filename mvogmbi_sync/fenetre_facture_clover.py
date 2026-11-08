"""Fenêtre « Facture Clover » : la vraie facture d'une commande, relue dans Clover pour vérification (double-clic sur une
anomalie des statistiques, demande du propriétaire du 2026-11-08). Lecture seule ; même contenu que la page web
/facture-clover (facture_clover.py)."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .design import CARTE, ROUGE, TEXTE, TEXTE_DOUX, VERT_FONCE, FenetreOutil, fond_de
from .langues import t


class FenetreFactureClover(FenetreOutil):
    def __init__(self, parent, racine, id_commande: str, points=None):
        super().__init__(parent, background=fond_de(parent))
        self.title(t("Facture Clover"))
        self.geometry("1100x720")
        self.racine, self.id_commande, self.points = racine, id_commande, points
        self.etat = ttk.Label(self, text=t("Lecture de la commande dans Clover…"), foreground=TEXTE_DOUX)
        self.etat.pack(anchor="w", padx=12, pady=(10, 0))
        self.corps = tk.Frame(self, background=fond_de(parent))
        self.corps.pack(fill="both", expand=True, padx=12, pady=8)
        threading.Thread(target=self._lire, daemon=True).start()

    def _lire(self) -> None:
        from .facture_clover import lire

        try:
            facture = lire(self.racine, self.id_commande, self.points)
            self.after(0, lambda: self._afficher(facture))
        except Exception as erreur:  # noqa: BLE001 — Clover injoignable ou commande introuvable
            texte = str(erreur)
            self.after(0, lambda: self.etat.configure(text="✘ " + texte, foreground=ROUGE))

    def _afficher(self, f) -> None:
        from .facture_clover import ENTETES_LIGNES, ENTETES_PAIEMENTS, ENTETES_REMBOURSEMENTS
        from .page_rapports import montant, remplir, tableau_simple

        self.title(t("Facture Clover n° {n}", n=f.numero))
        self.etat.configure(text=t("Lue dans Clover à l'instant (lecture seule)."), foreground=TEXTE_DOUX)
        tk.Label(self.corps, text=f"🧾  {t('Facture Clover n° {n}', n=f.numero)} — {f.moment}",
                 font=("Segoe UI Semibold", 13), foreground=VERT_FONCE, background=fond_de(self.corps),
                 anchor="w").pack(fill="x")
        if f.note:
            tk.Label(self.corps, text="✖  " + t(f.note), background="#fde2e4", foreground=TEXTE, anchor="w",
                     font=("Segoe UI", 9)).pack(fill="x", pady=(4, 0), ipady=3)
        for rangee in ([("Commande", f.numero), ("Employé", f.employe), ("Client", f.client),
                        ("Appareil", f.appareil or "—"), ("État", f.etat), ("Point de vente", f.point_vente or "n° 1")],
                       [(titre, montant(v)) for titre, v in f.totaux]):
            cadre = tk.Frame(self.corps, background=fond_de(self.corps))
            cadre.pack(fill="x", pady=(6, 0))
            for i, (titre, valeur) in enumerate(rangee):
                carte = tk.Frame(cadre, background=CARTE, highlightthickness=1,
                                 highlightbackground="#1b7f3b" if titre == "Montant payé" else "#e2e8e4")
                carte.grid(row=0, column=i, sticky="nsew", padx=3)
                cadre.columnconfigure(i, weight=1, uniform="f")
                tk.Label(carte, text=t(titre), background=CARTE, foreground=TEXTE_DOUX, font=("Segoe UI", 9),
                         anchor="w", wraplength=110, justify="left").pack(fill="x", padx=8, pady=(5, 0))
                tk.Label(carte, text=valeur, background=CARTE, foreground=VERT_FONCE, anchor="w", justify="left",
                         font=("Segoe UI Semibold", 10 if len(valeur) > 18 else 11),
                         wraplength=115).pack(fill="x", padx=8, pady=(0, 5))
        for titre, entetes, lignes, hauteur in (("Articles", ENTETES_LIGNES, f.lignes, 10),
                                                ("Rabais de la commande", ["Rabais", "Valeur"], f.rabais_commande, 3),
                                                ("Paiements", ENTETES_PAIEMENTS, f.paiements, 3),
                                                ("Remboursements", ENTETES_REMBOURSEMENTS, f.remboursements, 3)):
            if not lignes and titre != "Articles":
                continue
            tk.Label(self.corps, text=t(titre), font=("Segoe UI Semibold", 10), foreground=TEXTE,
                     background=fond_de(self.corps), anchor="w").pack(fill="x", pady=(8, 0))
            tableau = tableau_simple(self.corps, min(hauteur, max(1, len(lignes))))
            remplir(tableau, entetes, lignes)

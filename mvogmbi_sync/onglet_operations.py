"""Onglet « Opérations journalières » de la page Rapports (rubrique État, demande du propriétaire du 2026-11-08) :
ventes, achats, encaissements et paiements fournisseurs inscrits dans Sage, jour par jour, avec le moment où
l'application les a traités ; filtres de navigation (période ◀ ▶, types, état, recherche, détail ou par jour).
Calculs dans operations_journalieres.py ; historique Sage lu une fois (10 minutes), partagé avec la recherche."""

from __future__ import annotations

import time
import tkinter as tk
from datetime import date
from tkinter import ttk

from . import operations_journalieres as oj
from .design import TEXTE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee, apres_frappe, fond_de
from .export_tableau import bouton_exporter
from .langues import t

COULEURS = {oj.VENTE: "#e8f5ec", oj.ACHAT: "#fff4d6", oj.ENCAISSEMENT: "#eaf2fb", oj.PAIEMENT: "#fde2e4"}


class OngletOperations(ttk.Frame):
    titre = "Opérations journalières"

    def __init__(self, page, notebook):
        from .page_rapports import tableau_simple

        super().__init__(notebook, padding=(0, 8, 0, 0))
        self.page, self.lu, self.operations = page, False, []
        barre = Rangee(self)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        ttk.Label(g, text=t("Période")).pack(side="left", padx=(0, 4))
        self.periode = tk.StringVar(value=t("Cette semaine"))
        choix = ttk.Combobox(g, textvariable=self.periode, values=[t(p) for p in oj.PERIODES], state="readonly",
                             width=17)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self._periode_choisie())
        Bouton(g, "◀", lambda: self._decaler(-1), petit=True).pack(side="left", padx=(6, 2))
        Bouton(g, "▶", lambda: self._decaler(1), petit=True).pack(side="left", padx=(0, 6))
        du, au = oj.bornes("Cette semaine")
        self.du, self.au = tk.StringVar(value=du.isoformat()), tk.StringVar(value=au.isoformat())
        ttk.Label(g, text=t("Du")).pack(side="left")
        ChampDate(g, self.du).pack(side="left", padx=4)
        ttk.Label(g, text=t("au")).pack(side="left")
        ChampDate(g, self.au).pack(side="left", padx=4)
        Bouton(g, "✔ " + t("Appliquer"), self._dates_tapees, petit=True).pack(side="left", padx=(4, 0))
        g = barre.ajouter(barre.groupe(), 10)
        self.types = {}
        for genre in oj.TYPES:
            self.types[genre] = tk.BooleanVar(value=True)
            ttk.Checkbutton(g, text=t(genre + "s") if genre != oj.PAIEMENT else t("Paiements fournisseurs"),
                            variable=self.types[genre], command=self.afficher).pack(side="left", padx=(0, 6))
        g = barre.ajouter(barre.groupe(), 10)
        ttk.Label(g, text=t("Afficher")).pack(side="left", padx=(0, 4))
        self.vue = tk.StringVar(value=t(oj.VUES[0]))
        liste = ttk.Combobox(g, textvariable=self.vue, values=[t(v) for v in oj.VUES], state="readonly", width=20)
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        ttk.Label(g, text=t("Traitement")).pack(side="left", padx=(10, 4))
        self.etat_choisi = tk.StringVar(value=t(oj.ETATS[0]))
        liste = ttk.Combobox(g, textvariable=self.etat_choisi, values=[t(v) for v in oj.ETATS], state="readonly",
                             width=24)
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        g = barre.ajouter(barre.groupe(), 10)
        ttk.Label(g, text=t("Rechercher :")).pack(side="left", padx=(0, 4))
        self.texte = tk.StringVar()
        champ = ttk.Entry(g, textvariable=self.texte, width=20)
        champ.pack(side="left")
        champ.bind("<KeyRelease>", apres_frappe(champ, self.afficher))
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), lambda: self.actualiser(forcer=True), petit=True), 10)
        self.etat = ttk.Label(self, text=t("Lecture de Sage à l'ouverture de l'onglet…"), foreground=TEXTE_DOUX,
                              padding=(0, 6), wraplength=1100, justify="left")
        self.etat.pack(fill="x")
        self.resume = tk.Label(self, text="", font=("Segoe UI Semibold", 10), foreground=VERT_FONCE,
                               background=fond_de(self), anchor="w", justify="left")
        self.resume.pack(fill="x")
        self.libelle = tk.Label(self, text=t(self.titre), font=("Segoe UI Semibold", 10), foreground=TEXTE,
                                background=fond_de(self), anchor="w")
        self.libelle.pack(fill="x", pady=(4, 0))
        self.tableau = tableau_simple(self, hauteur=16)
        for genre, couleur in COULEURS.items():
            self.tableau.tag_configure(genre, background=couleur)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.libelle.cget("text")))

    # ---------------------------------------------------------------- navigation
    def _bornes(self) -> tuple[date | None, date | None]:
        try:
            return date.fromisoformat(self.du.get().strip()), date.fromisoformat(self.au.get().strip())
        except ValueError:
            return None, None

    def _periode_choisie(self) -> None:
        periode = next((p for p in oj.PERIODES if t(p) == self.periode.get()), oj.PERIODES[-1])
        if periode != "Personnalisée":
            du, au = oj.bornes(periode)
            self.du.set(du.isoformat())
            self.au.set(au.isoformat())
        self.afficher()

    def _decaler(self, sens: int) -> None:
        du, au = self._bornes()
        if du and au:
            du, au = oj.decaler(du, au, sens)
            self.du.set(du.isoformat())
            self.au.set(au.isoformat())
            self.periode.set(t("Personnalisée"))
        self.afficher()

    def _dates_tapees(self) -> None:
        self.periode.set(t("Personnalisée"))
        self.afficher()

    # ---------------------------------------------------------------- lecture et affichage
    def premiere_fois(self) -> None:
        if not self.lu:
            self.actualiser()

    def actualiser(self, forcer: bool = False) -> None:
        from . import rapports

        self.lu = True
        page = self.page
        h = getattr(page, "historique_sage", None)
        if h and not forcer and time.time() - h.get("_lu", 0) < 600:
            self._lu(h)
            return

        def garder(h):
            h["_lu"] = time.time()
            page.historique_sage = h  # partagé avec « Recherche dans l'historique »
            self._lu(h)

        page._lire_sage(rapports.historique, garder, t("Lecture des ventes, achats, encaissements et paiements dans "
                                                       "Sage…"), self.etat)

    def _lu(self, h) -> None:
        self.operations = oj.lire(self.page.racine, h)
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        du, au = self._bornes()
        genres = [g for g, v in self.types.items() if v.get()]
        etat = next((e for e in oj.ETATS if t(e) == self.etat_choisi.get()), oj.ETATS[0])
        ops = oj.filtrer(self.operations, du, au, genres, etat, self.texte.get())
        periode = f"{du} → {au}" if du and au else ""
        self.resume.configure(text="   ".join(f"{t(g)} : {n} — {m:,.2f} $".replace(",", " ").replace(".", ",")
                                              for g, n, m in oj.totaux(ops) if g in genres))
        if self.vue.get() == t(oj.VUES[1]):
            remplir(self.tableau, oj.ENTETES_JOURS, oj.par_jour(ops), {"Date": 100, "Jour": 90})
            self.libelle.configure(text=t("Opérations par jour") + f" — {periode}")
        else:
            remplir(self.tableau, oj.ENTETES, [o.ligne() for o in ops],
                    {"Date": 95, "Type": 140, "Référence": 170, "Facture": 160, "Client / fournisseur": 200,
                     "Montant": 100, "Traité le": 140, "Par": 120, "Origine": 90},
                    lambda i: (ops[i].genre,))
            self.libelle.configure(text=t(self.titre) + f" — {periode}")
        if self.operations:
            app = sum(1 for o in ops if o.traite_le)
            self.etat.configure(text=t("{n} opération(s) affichée(s) ; {a} traitée(s) par l'application, {s} saisie(s) "
                                       "directement dans Sage.", n=len(ops), a=app, s=len(ops) - app))

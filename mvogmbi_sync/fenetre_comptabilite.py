"""Fenêtre « Comptabilité » (demande du propriétaire du 2026-10-29) : âge des comptes, déclaration TPS/TVQ,
prévision de trésorerie, clôture du mois. Calculs dans comptabilite.py ; Sage lu dans un fil (l'application ouvre
Sage elle-même s'il est fermé)."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import ttk

from . import comptabilite as cp
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee
from .export_tableau import bouton_exporter
from .langues import t

ONGLETS = ["Âge des comptes", "Déclaration TPS/TVQ", "Prévision de trésorerie", "Retenues à la source",
           "Suivi des remises", "Budget et écarts", "Clôture du mois"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre"]


def _argent(v) -> str:
    return f"{v:,.2f} $".replace(",", " ").replace(".", ",")


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


class FenetreComptabilite(FenetreOutil):
    def __init__(self, parent, racine: Path, onglet: str = ONGLETS[0]):
        super().__init__(parent)
        self.racine = Path(racine)
        self.config_toml = _config(racine)
        self.title(t("Comptabilité"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1150x660")
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True)
        self.cadres = {}
        for nom, construire in zip(ONGLETS, (self._age, self._taxes, self._tresorerie, self._retenues, self._suivi,
                                             self._budget, self._cloture)):
            cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
            self.onglets.add(cadre, text="  " + t(nom) + "  ")
            self.cadres[nom] = cadre
            construire(cadre)
        self.choisir(onglet)

    def choisir(self, onglet: str) -> None:
        self.onglets.select(self.cadres[onglet])

    # ------------------------------------------------------------------ outils
    def _zone(self, cadre, titre: str):
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        etat = tk.Label(cadre, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                        wraplength=1100)
        etat.pack(fill="x", pady=(6, 0))
        libelle = tk.Label(cadre, text=t(titre), background=CARTE, font=("Segoe UI Semibold", 10), anchor="w")
        libelle.pack(fill="x")
        tableau = tableau_simple(cadre, hauteur=16)
        return barre, etat, libelle, tableau

    def _lire(self, travail, fin, etat: tk.Label, message: str) -> None:
        etat.configure(text=t(message), foreground=TEXTE_DOUX)

        def executer():
            try:
                resultat = travail()
                self.after(0, lambda: fin(resultat))
            except BaseException as exc:  # SystemExit compris (jeton Clover absent)
                texte = str(exc) or type(exc).__name__
                self.after(0, lambda: etat.configure(text="✘ " + texte, foreground=ROUGE))

        threading.Thread(target=executer, daemon=True).start()

    def _sage(self, fonction):
        from .__main__ import lire_sage

        return lire_sage(self.config_toml, fonction, self.config_toml.get("sage_import", {}).get("fichier_entreprise"))

    # ------------------------------------------------------------------ âge des comptes
    def _age(self, cadre) -> None:
        barre, self.etat_age, self.titre_age, self.tableau_age = self._zone(cadre, "Âge des comptes")
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Comptes"), background=CARTE).pack(side="left")
        self.cote = tk.StringVar(value=t("Fournisseurs"))
        choix = ttk.Combobox(groupe, textvariable=self.cote, values=[t("Fournisseurs"), t("Clients")],
                             state="readonly", width=13)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.calculer_age())
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Afficher"), background=CARTE).pack(side="left")
        self.vue_age = tk.StringVar(value=t("Par tiers"))
        choix = ttk.Combobox(groupe, textvariable=self.vue_age, values=[t("Par tiers"), t("Par facture")],
                             state="readonly", width=12)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher_age())
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.calculer_age, fond=CARTE, petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_age, lambda: self.titre_age.cget("text")))
        self.factures_age = None
        self.calculer_age()

    def calculer_age(self) -> None:
        cote = "fournisseurs" if self.cote.get() == t("Fournisseurs") else "clients"

        def fin(factures):
            self.factures_age = (cote, factures)
            self.afficher_age()

        self._lire(lambda: self._sage(lambda b: cp.factures_ouvertes(b, cote, date.today())), fin, self.etat_age,
                   "Lecture des factures ouvertes dans Sage…")

    def afficher_age(self) -> None:
        from .page_rapports import remplir

        if not self.factures_age:
            return
        cote, factures = self.factures_age
        par_tiers = self.vue_age.get() == t("Par tiers")
        if par_tiers:
            lignes = cp.age_par_tiers(factures)
            remplir(self.tableau_age, cp.ENTETES_AGE, lignes, {"Tiers": 260, "Factures": 70},
                    lambda i: ("total",) if lignes[i][0] == "Total" else (), decroissant=False)
        else:
            remplir(self.tableau_age, ["Tiers", "Facture", "Date", "Échéance", "Jours de retard", "Tranche", "Montant dû"],
                    [[f.tiers, f.numero, f.date.isoformat(), f.echeance.isoformat(), max(f.retard, 0), t(f.tranche),
                      f.solde] for f in factures], {"Tiers": 240, "Facture": 160}, decroissant=False)
        self.tableau_age.tag_configure("total", font=("Segoe UI Semibold", 9), background="#e8f3ea")
        retard = sum((f.solde for f in factures if f.retard > 0), cp.Decimal(0))
        self.titre_age.configure(text=t("Âge des comptes {c} au {d}", c=t(cote), d=date.today().isoformat()))
        self.etat_age.configure(text=t("{n} facture(s) ouverte(s), {s} dont {r} en retard. Échéance = date de la "
                                       "facture + jours nets (fiche du tiers dans Sage).", n=len(factures),
                                       s=_argent(sum((f.solde for f in factures), cp.Decimal(0))), r=_argent(retard)),
                                foreground=TEXTE_DOUX)

    # ------------------------------------------------------------------ taxes
    def _taxes(self, cadre) -> None:
        barre, self.etat_taxes, self.titre_taxes, self.tableau_taxes = self._zone(cadre, "Déclaration TPS/TVQ")
        groupe = barre.ajouter(barre.groupe(), 10)
        aujourdhui = date.today()
        fin_mois = aujourdhui.replace(day=1) - timedelta(days=1)
        self.du_taxes, self.au_taxes = tk.StringVar(value=fin_mois.replace(day=1).isoformat()), tk.StringVar(
            value=fin_mois.isoformat())
        tk.Label(groupe, text=t("Période du"), background=CARTE).pack(side="left", padx=(0, 4))
        ChampDate(groupe, self.du_taxes, fond=CARTE).pack(side="left")
        tk.Label(groupe, text=t("au"), background=CARTE).pack(side="left", padx=4)
        ChampDate(groupe, self.au_taxes, fond=CARTE).pack(side="left")
        barre.ajouter(Bouton(barre, "🔍  " + t("Calculer"), self.calculer_taxes, fond=CARTE, petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_taxes, lambda: self.titre_taxes.cget("text")))
        self.etat_taxes.configure(text=t("Choisissez la période de déclaration puis « Calculer »."))

    def calculer_taxes(self) -> None:
        from .page_rapports import remplir

        try:
            du, au = date.fromisoformat(self.du_taxes.get()), date.fromisoformat(self.au_taxes.get())
        except ValueError:
            self.etat_taxes.configure(text="✘ " + t("Dates au format AAAA-MM-JJ."), foreground=ROUGE)
            return

        def travail():
            lignes = self._sage(lambda b: cp.declaration_taxes(b, du, au))
            try:
                clover = cp.taxes_clover(self.racine, du, au)
            except BaseException:
                clover = None
            return lignes, clover

        def fin(resultat):
            lignes, clover = resultat
            remplir(self.tableau_taxes, cp.ENTETES_TAXES, [[l[0], t(l[1]), l[2], l[3]] for l in lignes],
                    {"Taxe": 80, "Nature": 280, "Compte Sage": 320, "Montant": 120},
                    lambda i: ("net",) if lignes[i][1].startswith("Net") else (), decroissant=False)
            self.tableau_taxes.tag_configure("net", font=("Segoe UI Semibold", 9), background="#e8f3ea")
            percues = sum((l[3] for l in lignes if l[1] == "Perçue sur les ventes"), cp.Decimal(0))
            texte = t("Montants de Sage (taxes perçues positives, taxes payées sur les achats négatives). Un net "
                      "négatif est un remboursement à recevoir.")
            if clover is not None:
                texte += "\n" + t("Contrôle : taxes perçues dans Sage {s}, taxes encaissées par Clover {c} (écart {e}).",
                                  s=_argent(percues), c=_argent(clover), e=_argent(percues - clover))
            self.titre_taxes.configure(text=t("Déclaration TPS/TVQ du {d} au {f}", d=du.isoformat(), f=au.isoformat()))
            self.etat_taxes.configure(text=texte, foreground=TEXTE_DOUX)

        self._lire(travail, fin, self.etat_taxes, "Lecture des comptes de taxes dans Sage et des ventes Clover…")

    # ------------------------------------------------------------------ trésorerie
    def _tresorerie(self, cadre) -> None:
        barre, self.etat_tresorerie, self.titre_tresorerie, self.tableau_tresorerie = self._zone(
            cadre, "Prévision de trésorerie")
        barre.ajouter(Bouton(barre, "🔍  " + t("Calculer"), self.calculer_tresorerie, fond=CARTE, petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_tresorerie, lambda: self.titre_tresorerie.cget("text")))
        self.etat_tresorerie.configure(text=t("« Calculer » : 4 semaines à partir d'aujourd'hui."))

    def calculer_tresorerie(self) -> None:
        from .page_rapports import remplir

        def fin(resultat):
            lignes, info = resultat
            remplir(self.tableau_tresorerie, cp.ENTETES_TRESORERIE, lignes, {"Semaine": 190},
                    lambda i: ("negatif",) if lignes[i][-1] < 0 else (), decroissant=False)
            self.tableau_tresorerie.tag_configure("negatif", background="#fde2e4")
            self.titre_tresorerie.configure(text=t("Prévision de trésorerie au {d}", d=date.today().isoformat()))
            self.etat_tresorerie.configure(text=t(
                "Solde de départ : compte de dépôt dans Sage. Entrées : prévision des ventes × {r} (montant encaissé, "
                "taxes comprises, par dollar de ventes nettes les 8 dernières semaines). Factures fournisseurs selon "
                "leur échéance, celles en retard ({e}) dans la 1re semaine. Paies : {p} par semaine (moyenne des 12 "
                "dernières semaines). En rose : solde négatif.", r=f"{info['rapport']:.3f}".replace(".", ","),
                e=_argent(info["en_retard"]), p=_argent(info["paie_semaine"])), foreground=TEXTE_DOUX)

        self._lire(lambda: cp.calculer_tresorerie(self.racine, self.config_toml), fin, self.etat_tresorerie,
                   "Lecture de Clover (prévision des ventes) et de Sage (solde, factures, paies)…")

    # ------------------------------------------------------------------ retenues à la source
    def _retenues(self, cadre) -> None:
        from .page_rapports import tableau_simple

        barre, self.etat_retenues, self.titre_retenues, self.tableau_retenues = self._zone(
            cadre, "Retenues à la source")
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Mois"), background=CARTE).pack(side="left")
        self.mois_retenues = tk.StringVar(value=_mois_proposes()[1])
        choix = ttk.Combobox(groupe, textvariable=self.mois_retenues, values=_mois_proposes(), state="readonly",
                             width=9)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.calculer_retenues())
        barre.ajouter(Bouton(barre, "🔍  " + t("Calculer"), self.calculer_retenues, fond=CARTE, petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_retenues, lambda: self.titre_retenues.cget("text")))
        self.libelle_salaires = tk.Label(cadre, text=t("Salaires et cotisations de l'employeur du mois"),
                                         background=CARTE, font=("Segoe UI Semibold", 10), anchor="w")
        self.libelle_salaires.pack(fill="x", pady=(8, 0))
        self.tableau_salaires = tableau_simple(cadre, hauteur=6)
        self.tableau_retenues.configure(height=10)
        self.etat_retenues.configure(text=t("Choisissez le mois puis « Calculer »."))

    def _suivi(self, cadre) -> None:
        barre, self.etat_suivi, self.titre_suivi, self.tableau_suivi = self._zone(
            cadre, "Suivi des remises des retenues (12 derniers mois)")
        barre.ajouter(Bouton(barre, "🔍  " + t("Calculer"), self.calculer_suivi, fond=CARTE, petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_suivi, lambda: self.titre_suivi.cget("text")))
        self.etat_suivi.configure(text=t("Versements cherchés sur les comptes de retenues (hors paie), du mois suivant "
                                         "jusqu'à 60 jours après l'échéance du 15. « Calculer » lit Sage."))

    def calculer_suivi(self) -> None:
        from .page_rapports import remplir
        from .retenues import A_REMETTRE, EN_RETARD, ENTETES_SUIVI, REMIS_EN_RETARD, alertes, suivi

        def fin(lignes):
            remplir(self.tableau_suivi, ENTETES_SUIVI, [l[:6] + [t(l[6])] for l in lignes],
                    {"Organisme": 220, "État": 160},
                    lambda i: ("retard",) if lignes[i][6] in (EN_RETARD, REMIS_EN_RETARD) else (
                        ("attente",) if lignes[i][6] == A_REMETTRE else ()))
            self.tableau_suivi.tag_configure("retard", foreground=ROUGE)
            self.tableau_suivi.tag_configure("attente", foreground="#9a6700")
            a = alertes(lignes, date.today())
            self.etat_suivi.configure(text=("⚠ " + " ; ".join(a)) if a else t("✔ Aucune remise en retard ni à faire "
                                                                                "dans les 5 prochains jours."),
                                      foreground=ROUGE if a else VERT_FONCE)

        self._lire(lambda: self._sage(lambda b: suivi(b, date.today())), fin, self.etat_suivi,
                   "Lecture des remises dans Sage…")

    def _budget(self, cadre) -> None:
        from .budget import POSTES

        barre, self.etat_budget, self.titre_budget, self.tableau_budget = self._zone(cadre, "Budget et écarts")
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Mois"), background=CARTE).pack(side="left")
        self.mois_budget = tk.StringVar(value=_mois_proposes()[1])
        choix = ttk.Combobox(groupe, textvariable=self.mois_budget, values=_mois_proposes(), state="readonly", width=9)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.charger_budget())
        self.v_budget = {}
        for poste in POSTES:
            g = barre.ajouter(barre.groupe(), 8)
            tk.Label(g, text=t(poste), background=CARTE).pack(side="left", padx=(0, 4))
            self.v_budget[poste] = tk.StringVar()
            ttk.Entry(g, textvariable=self.v_budget[poste], width=10).pack(side="left")
        barre.ajouter(Bouton(barre, "✔  " + t("Enregistrer le budget"), self.enregistrer_budget, "secondaire",
                             fond=CARTE, petit=True), 8)
        g = barre.ajouter(barre.groupe(), 8)
        tk.Label(g, text=t("Croissance (%)"), background=CARTE).pack(side="left", padx=(0, 4))
        self.croissance = tk.StringVar(value="5")
        ttk.Entry(g, textvariable=self.croissance, width=5).pack(side="left")
        barre.ajouter(Bouton(barre, "💡  " + t("Proposer d'après l'an dernier"), self.proposer_budget, "secondaire",
                             fond=CARTE, petit=True), 8)
        barre.ajouter(Bouton(barre, "🔍  " + t("Comparer au réel"), self.comparer_budget, fond=CARTE, petit=True), 8)
        barre.ajouter(bouton_exporter(barre, self.tableau_budget, lambda: self.titre_budget.cget("text")))
        self.etat_budget.configure(text=t("Réel lu dans Sage (produits 4xxx, CMV 50xx, autres charges 51xx-59xx)."))
        self.charger_budget()

    def _mois_budget(self) -> tuple[int, int]:
        a, m = (int(x) for x in self.mois_budget.get().split("-"))
        return a, m

    def charger_budget(self) -> None:
        from .budget import Budget

        valeurs = Budget(self.racine).mois(*self._mois_budget())
        for poste, v in self.v_budget.items():
            v.set(str(valeurs[poste]).replace(".", ",") if valeurs[poste] else "")

    def enregistrer_budget(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Enregistrer le budget"):
            return
        from decimal import Decimal, InvalidOperation

        from .budget import Budget

        try:
            valeurs = {p: Decimal(v.get().replace(" ", "").replace(",", ".") or 0) for p, v in self.v_budget.items()}
        except InvalidOperation:
            self.etat_budget.configure(text="✘ " + t("Montants en chiffres."), foreground=ROUGE)
            return
        Budget(self.racine).definir(*self._mois_budget(), valeurs)
        self.etat_budget.configure(text=t("✔ Budget de {m} enregistré.", m=self.mois_budget.get()),
                                   foreground=VERT_FONCE)

    def proposer_budget(self) -> None:
        from decimal import Decimal

        from .budget import proposer, reel

        annee, mois = self._mois_budget()

        def fin(lignes):
            try:
                croissance = Decimal(self.croissance.get().replace(",", "."))
            except Exception:
                croissance = Decimal(0)
            for poste, v in proposer(reel(lignes, 3), croissance).items():
                self.v_budget[poste].set(str(v))
            self.etat_budget.configure(text=t("Proposé d'après {a}-{m:02d} : vérifiez puis « Enregistrer le budget ».",
                                              a=annee - 1, m=mois), foreground=TEXTE_DOUX)

        self._lire(lambda: self._sage(lambda b: cp.etat_resultats(b, annee, mois)), fin, self.etat_budget,
                   "Lecture de l'état des résultats dans Sage…")

    def comparer_budget(self) -> None:
        from decimal import Decimal

        from .budget import ENTETES_BUDGET, POSTES, Budget, ecarts, reel
        from .page_rapports import remplir

        annee, mois = self._mois_budget()
        budget = Budget(self.racine)

        def travail():
            def lire(b):
                return [reel(cp.etat_resultats(b, annee, m)) for m in range(1, mois + 1)]
            return self._sage(lire)

        def fin(reels):
            cumul_r = {p: sum((r[p] for r in reels), Decimal(0)) for p in POSTES}
            cumul_b = {p: sum((budget.mois(annee, m)[p] for m in range(1, mois + 1)), Decimal(0)) for p in POSTES}
            lignes = ecarts(reels[-1], budget.mois(annee, mois), cumul_r, cumul_b)
            remplir(self.tableau_budget, ENTETES_BUDGET, [[t(l[0])] + l[1:] for l in lignes], {"Poste": 260},
                    decroissant=False)
            self.titre_budget.configure(text=t("Budget et écarts de {m}", m=self.mois_budget.get()))
            self.etat_budget.configure(text=t("Écart = réel − budget ; depuis janvier = cumul de l'année."),
                                       foreground=TEXTE_DOUX)

        self._lire(travail, fin, self.etat_budget, "Lecture de l'état des résultats dans Sage…")

    def calculer_retenues(self) -> None:
        from .page_rapports import remplir
        from .retenues import ENTETES, VACANCES, etat

        annee, mois = (int(x) for x in self.mois_retenues.get().split("-"))

        def fin(resultat):
            lignes, info = resultat
            remplir(self.tableau_retenues, ENTETES, [[t(l[0]), t(l[1])] + l[2:] for l in lignes],
                    {"Organisme": 210, "Compte Sage": 230},
                    lambda i: ("total",) if lignes[i][1] == "Total à remettre" else (
                        ("vacances",) if lignes[i][0] == VACANCES else ()), decroissant=False)
            self.tableau_retenues.tag_configure("total", font=("Segoe UI Semibold", 9), background="#e8f3ea")
            self.tableau_retenues.tag_configure("vacances", foreground="#7d8b81")
            remplir(self.tableau_salaires, ["Compte de charge", "Montant du mois"],
                    info["charges"] + ([["Total", info["salaires"]]] if info["charges"] else []),
                    {"Compte de charge": 320}, decroissant=False)
            self.titre_retenues.configure(text=t("Retenues à la source de {m}", m=f"{annee}-{mois:02d}"))
            remises = info.get("a_remettre", {})
            self.etat_retenues.configure(text=(t("À remettre au plus tard le {d} (remetteur régulier) : ",
                                                 d=info["echeance"].isoformat())
                                               + " ; ".join(f"{t(o)} {_argent(m)}" for o, m in remises.items())
                                               + "\n" + t("Lu dans la comptabilité de Sage (écritures de paie). Le "
                                                          "détail par employé (T4, Relevé 1) demande l'accès en "
                                                          "lecture au module Paie de Sage."))
                                         if remises else t("Aucune paie dans Sage pour ce mois."),
                                         foreground=TEXTE_DOUX)

        self._lire(lambda: self._sage(lambda b: etat(b, annee, mois)), fin, self.etat_retenues,
                   "Lecture des écritures de paie dans Sage…")

    # ------------------------------------------------------------------ clôture
    def _cloture(self, cadre) -> None:
        barre, self.etat_cloture, self.titre_cloture, self.tableau_cloture = self._zone(cadre, "Clôture du mois")
        groupe = barre.ajouter(barre.groupe(), 10)
        precedent = date.today().replace(day=1) - timedelta(days=1)
        self.mois = tk.StringVar(value=f"{precedent:%Y-%m}")
        valeurs = []
        jour = date.today().replace(day=1)
        for _ in range(18):
            jour = (jour - timedelta(days=1)).replace(day=1)
            valeurs.append(f"{jour:%Y-%m}")
        tk.Label(groupe, text=t("Mois"), background=CARTE).pack(side="left")
        choix = ttk.Combobox(groupe, textvariable=self.mois, values=[f"{date.today():%Y-%m}"] + valeurs,
                             state="readonly", width=9)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.calculer_cloture())
        barre.ajouter(Bouton(barre, "🔍  " + t("Vérifier"), self.calculer_cloture, fond=CARTE, petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_cloture, lambda: self.titre_cloture.cget("text")))
        from .page_rapports import tableau_simple

        self.libelle_resultats = tk.Label(cadre, text=t("État des résultats"), background=CARTE,
                                          font=("Segoe UI Semibold", 10), anchor="w")
        self.libelle_resultats.pack(fill="x", pady=(8, 0))
        self.tableau_resultats = tableau_simple(cadre, hauteur=7)
        self.tableau_cloture.configure(height=8)
        self.etat_cloture.configure(text=t("Choisissez le mois puis « Vérifier »."))

    def calculer_cloture(self) -> None:
        from .page_rapports import remplir

        annee, mois = (int(x) for x in self.mois.get().split("-"))

        def fin(resultat):
            controles, resultats = resultat
            remplir(self.tableau_cloture, cp.ENTETES_CLOTURE, [[t(c[0]), t(c[1]), c[2]] for c in controles],
                    {"Contrôle": 380, "État": 110, "Détail": 520},
                    lambda i: ("afaire",) if controles[i][1] == cp.A_FAIRE else (
                        ("fait",) if controles[i][1] == cp.OK else ()), decroissant=False)
            self.tableau_cloture.tag_configure("afaire", background="#fff4d6")
            self.tableau_cloture.tag_configure("fait", background="#e3f1e7")
            remplir(self.tableau_resultats, cp.entetes_resultats(annee, mois),
                    [[t(l[0])] + l[1:] for l in resultats], {"Poste": 300}, decroissant=False)
            nom = f"{t(MOIS[mois - 1])} {annee}"
            self.titre_cloture.configure(text=t("Clôture du mois : {m}", m=nom))
            self.libelle_resultats.configure(text=t("État des résultats : {m}, mois précédent, même mois l'an dernier",
                                                    m=nom))
            a_faire = sum(1 for c in controles if c[1] == cp.A_FAIRE)
            self.etat_cloture.configure(text=t("{n} point(s) à faire avant de clôturer le mois.", n=a_faire)
                                        if a_faire else t("Tous les contrôles sont faits : le mois peut être clôturé."),
                                        foreground=TEXTE_DOUX)

        self._lire(lambda: self._sage(lambda b: (cp.controles_cloture(self.racine, b, annee, mois),
                                                 cp.etat_resultats(b, annee, mois))),
                   fin, self.etat_cloture, "Lecture de Sage et des registres de l'application…")


def _mois_proposes() -> list[str]:
    """Mois en cours puis les 18 précédents (AAAA-MM)."""
    valeurs, jour = [f"{date.today():%Y-%m}"], date.today().replace(day=1)
    for _ in range(18):
        jour = (jour - timedelta(days=1)).replace(day=1)
        valeurs.append(f"{jour:%Y-%m}")
    return valeurs


def ouvrir(parent, racine: Path, onglet: str = ONGLETS[0]) -> FenetreComptabilite:
    return FenetreComptabilite(parent, racine, onglet)

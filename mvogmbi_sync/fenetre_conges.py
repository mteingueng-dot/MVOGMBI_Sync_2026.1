"""Fenêtre « Paie > Jours fériés et congés » (demande du propriétaire du 2026-10-29) : jours fériés de l'année
avec l'indemnité de chaque employé (en heures), saisie des congés, soldes (vacances, maladie). Calculs dans
conges.py ; les heures de férié et de congé payé s'ajoutent aux heures validées envoyées à Sage."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import conges as co
from . import paie_temps as pt
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee
from .export_tableau import bouton_exporter
from .langues import t

ONGLETS = ["Jours fériés", "Congés", "Soldes par employé"]


def _h(v) -> str:
    from .paie import heures

    return heures(v)


class FenetreConges(FenetreOutil):
    def __init__(self, parent, racine: Path, auteur: str = ""):
        super().__init__(parent)
        self.racine, self.auteur = Path(racine), auteur
        self.title(t("Jours fériés et congés"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("1100x640")
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True)
        for nom, construire in zip(ONGLETS, (self._feries, self._conges, self._soldes)):
            cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
            self.onglets.add(cadre, text="  " + t(nom) + "  ")
            construire(cadre)

    def _employes(self) -> list[pt.Employe]:
        return sorted(pt.Registre(self.racine).actifs(), key=lambda e: e.nom.casefold())

    # ------------------------------------------------------------------ jours fériés
    def _feries(self, cadre) -> None:
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Année"), background=CARTE).pack(side="left", padx=(0, 4))
        self.annee = tk.StringVar(value=str(date.today().year))
        choix = ttk.Combobox(g, textvariable=self.annee, values=[str(date.today().year + i) for i in (-1, 0, 1)],
                             state="readonly", width=6)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher_feries())
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Pâques : jour férié"), background=CARTE).pack(side="left", padx=(0, 4))
        self.paques = tk.StringVar(value=t("Vendredi saint") if co.Registre(self.racine).paques == "vendredi"
                                   else t("Lundi de Pâques"))
        choix = ttk.Combobox(g, textvariable=self.paques, values=[t("Vendredi saint"), t("Lundi de Pâques")],
                             state="readonly", width=16)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self._choix_paques())
        self.tableau_feries = tableau_simple(cadre, hauteur=16)
        barre.ajouter(bouton_exporter(barre, self.tableau_feries, lambda: t("Jours fériés")))
        tk.Label(cadre, text=t("Indemnité = 1/20 des heures normales pointées pendant les 4 semaines complètes avant la "
                               "semaine du jour férié (heures supplémentaires exclues) ; elle s'ajoute aux heures "
                               "validées de la période de paie."), background=CARTE, foreground=TEXTE_DOUX,
                 anchor="w", justify="left", wraplength=1050).pack(fill="x", pady=(6, 0))
        self.afficher_feries()

    def _choix_paques(self) -> None:
        registre = co.Registre(self.racine)
        registre.paques = "vendredi" if self.paques.get() == t("Vendredi saint") else "lundi"
        registre.enregistrer()
        self.afficher_feries()

    def afficher_feries(self) -> None:
        from .page_rapports import remplir

        annee = int(self.annee.get())
        registre_conges, registre = co.Registre(self.racine), pt.Registre(self.racine)
        employes = self._employes()
        lignes = []
        for jour, nom in co.jours_feries(annee, registre_conges.paques):
            passe = jour <= date.today()
            indemnites = [f"{e.nom} : {_h(co.indemnite_heures(registre, e, jour))}" for e in employes] if passe else []
            lignes.append([jour.isoformat(), t(nom), t("Passé") if passe else t("À venir"), " ; ".join(indemnites)])
        remplir(self.tableau_feries, ["Date", "Jour férié", "État", "Indemnité par employé"], lignes,
                {"Jour férié": 240, "Indemnité par employé": 560}, decroissant=False)

    # ------------------------------------------------------------------ congés
    def _conges(self, cadre) -> None:
        from .page_rapports import tableau_simple

        forme = Rangee(cadre)
        forme.pack(fill="x")
        self.employes = {e.nom: e for e in self._employes()}
        g = forme.ajouter(forme.groupe(), 10)
        tk.Label(g, text=t("Employé") + " *", background=CARTE).pack(side="left", padx=(0, 4))
        self.employe = tk.StringVar()
        ttk.Combobox(g, textvariable=self.employe, values=list(self.employes), state="readonly",
                     width=24).pack(side="left")
        g = forme.ajouter(forme.groupe(), 10)
        tk.Label(g, text=t("Du"), background=CARTE).pack(side="left")
        self.du = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(g, text=t("au"), background=CARTE).pack(side="left")
        self.au = tk.StringVar(value=date.today().isoformat())
        ChampDate(g, self.au, fond=CARTE).pack(side="left", padx=4)
        g = forme.ajouter(forme.groupe(), 10)
        tk.Label(g, text=t("Type") + " *", background=CARTE).pack(side="left", padx=(0, 4))
        self.type = tk.StringVar(value=t(co.VACANCES))
        ttk.Combobox(g, textvariable=self.type, values=[t(x) for x in co.TYPES], state="readonly",
                     width=26).pack(side="left")
        g = forme.ajouter(forme.groupe(), 10)
        tk.Label(g, text=t("Heures payées par jour"), background=CARTE).pack(side="left", padx=(0, 4))
        self.heures = tk.StringVar(value="8")
        ttk.Entry(g, textvariable=self.heures, width=6).pack(side="left")
        self.planifies = tk.BooleanVar(value=True)
        forme.ajouter(ttk.Checkbutton(forme, text=t("Seulement les jours planifiés"), variable=self.planifies), 10)
        forme.ajouter(Bouton(forme, "➕  " + t("Ajouter le congé"), self.ajouter, fond=CARTE, petit=True), 6)
        forme.ajouter(Bouton(forme, "🗑  " + t("Supprimer"), self.supprimer, "danger", fond=CARTE, petit=True))
        self.etat_conges = tk.Label(cadre, text=t("Congé payé : l'indemnité (heures par jour) est payée avec la paie de "
                                                  "la période. Maladie ou famille : 2 jours payés par année après 3 "
                                                  "mois de service, 10 jours au total."), background=CARTE,
                                    foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=1050)
        self.etat_conges.pack(fill="x", pady=(6, 0))
        self.tableau_conges = tableau_simple(cadre, hauteur=14)
        self.afficher_conges()

    def afficher_conges(self) -> None:
        from .page_rapports import remplir

        noms = {e.id: e.nom for e in pt.Registre(self.racine).employes}
        self.liste_conges = sorted(co.Registre(self.racine).conges, key=lambda c: c.jour, reverse=True)
        remplir(self.tableau_conges, ["Date", "Employé", "Type", "Heures payées", "Saisi par", "Remarque"],
                [[c.jour, noms.get(c.employe, c.employe), t(c.type), _h(Decimal(c.heures)), c.auteur, c.remarque]
                 for c in self.liste_conges], {"Employé": 200, "Type": 220}, decroissant=False)

    def ajouter(self) -> None:
        from .planning import Planning

        e = self.employes.get(self.employe.get())
        type_ = next((x for x in co.TYPES if t(x) == self.type.get()), "")
        try:
            debut, fin = date.fromisoformat(self.du.get().strip()), date.fromisoformat(self.au.get().strip())
            heures = Decimal(self.heures.get().replace(",", ".").strip() or 0)
        except (ValueError, InvalidOperation):
            self.etat_conges.configure(text="✘ " + t("Dates AAAA-MM-JJ et heures en chiffres."), foreground=ROUGE)
            return
        if not e:
            self.etat_conges.configure(text="✘ " + t("Choisissez l'employé."), foreground=ROUGE)
            return
        planning = Planning(self.racine)
        travailles = (lambda j: planning.quart(f"{j:%Y-%m}", e.id, j) is not None) if self.planifies.get() else None
        try:
            ajoutes = co.Registre(self.racine).ajouter(e.id, debut, fin, type_, heures, self.auteur,
                                                       jours_travailles=travailles)
        except ValueError as exc:
            self.etat_conges.configure(text="✘ " + t(str(exc)), foreground=ROUGE)
            return
        s = co.solde(co.Registre(self.racine), e, debut)
        texte = t("✔ {n} jour(s) de congé ajouté(s).", n=len(ajoutes))
        if not ajoutes:
            texte = "⚠ " + t("Aucun jour ajouté : aucun quart planifié dans la période (décochez « Seulement les "
                             "jours planifiés »).")
        if s.remarques:
            texte += " ⚠ " + " ; ".join(t(r) for r in s.remarques)
        self.etat_conges.configure(text=texte, foreground=ROUGE if s.remarques or not ajoutes else VERT_FONCE)
        self.afficher_conges()
        self.afficher_soldes()

    def supprimer(self) -> None:
        choix = self.tableau_conges.selection()
        if not choix:
            return
        c = self.liste_conges[int(choix[0])]
        if messagebox.askyesno(self.title(), t("Supprimer le congé du {j} ?", j=c.jour), parent=self):
            co.Registre(self.racine).supprimer(c.id)
            self.afficher_conges()
            self.afficher_soldes()

    # ------------------------------------------------------------------ soldes
    def _soldes(self, cadre) -> None:
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "📅  " + t("Date d'embauche…"), self.embauche, "secondaire", fond=CARTE,
                             petit=True), 8)
        self.tableau_soldes = tableau_simple(cadre, hauteur=16)
        barre.ajouter(bouton_exporter(barre, self.tableau_soldes, lambda: t("Soldes de congés")))
        self.afficher_soldes()

    def afficher_soldes(self) -> None:
        from .page_rapports import remplir

        registre = co.Registre(self.racine)
        self.liste_soldes = self._employes()
        lignes = []
        for e in self.liste_soldes:
            s = co.solde(registre, e, date.today())
            lignes.append([e.nom, registre.embauches.get(e.id, ""), s.service, f"{s.vacances_semaines}",
                           s.vacances_taux, f"{s.vacances_prises}", f"{s.maladie_payes_dus - s.maladie_payes_pris}",
                           f"{s.maladie_pris}/{co.JOURS_MALADIE_TOTAL}", " ; ".join(t(r) for r in s.remarques)])
        remplir(self.tableau_soldes, ["Employé", "Embauché le", "Service", "Semaines de vacances",
                                      "Indemnité de vacances", "Jours de vacances pris", "Jours de maladie payés restants",
                                      "Absences maladie ou famille", "À vérifier"], lignes,
                {"Employé": 200, "À vérifier": 260}, decroissant=False)

    def embauche(self) -> None:
        choix = self.tableau_soldes.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un employé dans la liste."), parent=self)
            return
        e = self.liste_soldes[int(choix[0])]
        registre = co.Registre(self.racine)
        valeur = simpledialog.askstring(self.title(), t("Date d'embauche de {n} (AAAA-MM-JJ) :", n=e.nom),
                                        initialvalue=registre.embauches.get(e.id, ""), parent=self)
        if valeur is None:
            return
        try:
            date.fromisoformat(valeur.strip())
        except ValueError:
            messagebox.showerror(self.title(), t("Date au format AAAA-MM-JJ."), parent=self)
            return
        registre.embauches[e.id] = valeur.strip()
        registre.enregistrer()
        self.afficher_soldes()

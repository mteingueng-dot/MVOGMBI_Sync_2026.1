"""Planning mensuel (demande du propriétaire du 2026-10-29) : le gérant prépare l'horaire du mois de tous les
employés (« Paie > Planning mensuel ») et le publie ; chaque employé voit le sien (« Paie > Mon horaire », ou le
poste de pointage après son NIP). Données dans planning.py."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from . import paie_temps as pt
from . import planning as pl
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee
from .export_tableau import bouton_exporter
from .langues import t


def _mois_suivant(mois: str, sens: int) -> str:
    annee, m = (int(x) for x in mois.split("-"))
    m += sens
    annee, m = annee + (m - 1) // 12, (m - 1) % 12 + 1
    return f"{annee}-{m:02d}"


class FenetrePlanning(tk.Toplevel):
    def __init__(self, parent, racine: Path):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.mois = _mois_suivant(f"{date.today():%Y-%m}", 1) if date.today().day > 20 else f"{date.today():%Y-%m}"
        self.title(t("Planning mensuel"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1300x620")
        barre = Rangee(self)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "◀", lambda: self.changer(-1), "secondaire", fond=CARTE, petit=True), 4)
        self.libelle = barre.ajouter(tk.Label(barre, text="", background=CARTE, font=("Segoe UI Semibold", 11)), 4)
        barre.ajouter(Bouton(barre, "▶", lambda: self.changer(1), "secondaire", fond=CARTE, petit=True), 14)
        for texte, commande, genre in (("🕑  " + t("Horaire des employés choisis…"), self.horaire, "principal"),
                                       ("📋  " + t("Reprendre le mois précédent"), self.copier, "secondaire"),
                                       ("📣  " + t("Publier le mois"), self.publier, "principal")):
            barre.ajouter(Bouton(barre, texte, commande, genre, fond=CARTE, petit=True))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1250)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=16)
        self.tableau.configure(selectmode="extended")
        self.tableau.bind("<Double-1>", lambda _e: self.horaire())
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.libelle.cget("text")))
        self.afficher()

    def changer(self, sens: int) -> None:
        self.mois = _mois_suivant(self.mois, sens)
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.planning = pl.Planning(self.racine)
        self.employes = pt.Registre(self.racine).actifs()
        jours = pl.jours_du_mois(self.mois)
        publie = self.planning.publies.get(self.mois)
        self.libelle.configure(text=t("Planning de {m}", m=self.mois) + (
            "  ✔ " + t("publié le {d}", d=publie[:10]) if publie else "  ● " + t("non publié")))
        entetes = ["Employé"] + [f"{t(pl.JOURS[j.weekday()])} {j:%d}" for j in jours] + ["Heures"]
        lignes = []
        for e in self.employes:
            quarts = [self.planning.quart(self.mois, e.id, j) for j in jours]
            lignes.append([e.nom] + [q.texte().replace(" min)", ")") if q else "" for q in quarts]
                          + [f"{self.planning.heures(self.mois, e.id):.2f}".replace(".", ",")])
        largeurs = {x: 78 for x in entetes[1:-1]}
        largeurs.update({"Employé": 170, "Heures": 70})
        remplir(self.tableau, entetes, lignes, largeurs, decroissant=False)
        self.etat.configure(text=t("Choisissez un ou plusieurs employés (Ctrl+clic), puis « Horaire des employés "
                                   "choisis… » : jours de la semaine, période, heures de début et de fin, pause non "
                                   "payée, ou repos. « Publier le mois » : chaque employé voit son horaire (« Paie > "
                                   "Mon horaire » et poste de pointage)."), foreground=TEXTE_DOUX)

    def _choisis(self) -> list[pt.Employe]:
        return [self.employes[int(i)] for i in self.tableau.selection()]

    def horaire(self) -> None:
        employes = self._choisis()
        if not employes:
            messagebox.showinfo(self.title(), t("Choisissez au moins un employé dans la liste."), parent=self)
            return
        DialogueHoraire(self, self.planning, employes, self.mois, self.afficher)

    def copier(self) -> None:
        precedent = _mois_suivant(self.mois, -1)
        if not messagebox.askyesno(self.title(), t("Reprendre pour {m} l'horaire de chaque jour de la semaine de {p} "
                                                   "(tous les employés) ? Les quarts déjà saisis ce mois-ci sont "
                                                   "remplacés.", m=self.mois, p=precedent), parent=self):
            return
        n = self.planning.copier_mois(precedent, self.mois, [e.id for e in self.employes])
        self.afficher()
        self.etat.configure(text=t("{n} quart(s) repris de {p}.", n=n, p=precedent), foreground=VERT_FONCE)

    def publier(self) -> None:
        if not messagebox.askyesno(self.title(), t("Publier le planning de {m} ? Chaque employé verra son horaire.",
                                                   m=self.mois), parent=self):
            return
        self.planning.publier(self.mois)
        self.afficher()


class DialogueHoraire(tk.Toplevel):
    def __init__(self, parent, planning: pl.Planning, employes: list[pt.Employe], mois: str, apres):
        super().__init__(parent)
        self.planning, self.employes, self.apres = planning, employes, apres
        jours = pl.jours_du_mois(mois)
        self.title(t("Horaire"))
        self.configure(background=CARTE, padx=16, pady=12)
        self.transient(parent)
        tk.Label(self, text=", ".join(e.nom for e in employes), background=CARTE,
                 font=("Segoe UI Semibold", 10), wraplength=520, justify="left").pack(anchor="w")
        periode = tk.Frame(self, background=CARTE)
        periode.pack(anchor="w", pady=6)
        self.du, self.au = tk.StringVar(value=jours[0].isoformat()), tk.StringVar(value=jours[-1].isoformat())
        tk.Label(periode, text=t("Du"), background=CARTE).pack(side="left")
        ChampDate(periode, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(periode, text=t("au"), background=CARTE).pack(side="left")
        ChampDate(periode, self.au, fond=CARTE).pack(side="left", padx=4)
        cases = tk.Frame(self, background=CARTE)
        cases.pack(anchor="w", pady=4)
        self.jours = [tk.BooleanVar(value=i < 5) for i in range(7)]
        for i, v in enumerate(self.jours):
            ttk.Checkbutton(cases, text=t(pl.JOURS[i]), variable=v).pack(side="left", padx=3)
        heures = tk.Frame(self, background=CARTE)
        heures.pack(anchor="w", pady=6)
        self.debut, self.fin, self.pause = tk.StringVar(value="08:00"), tk.StringVar(value="16:00"), tk.StringVar(
            value="30")
        for libelle, variable, largeur in ((t("Début"), self.debut, 7), (t("Fin"), self.fin, 7),
                                           (t("Pause (min)"), self.pause, 5)):
            tk.Label(heures, text=libelle, background=CARTE).pack(side="left", padx=(8, 4))
            ttk.Entry(heures, textvariable=variable, width=largeur).pack(side="left")
        self.erreur = tk.Label(self, text="", background=CARTE, foreground=ROUGE)
        self.erreur.pack(anchor="w")
        bas = tk.Frame(self, background=CARTE)
        bas.pack(anchor="e", pady=(8, 0))
        Bouton(bas, t("Repos ces jours-là"), lambda: self.appliquer(repos=True), "secondaire", fond=CARTE,
               petit=True).pack(side="left", padx=6)
        Bouton(bas, t("Appliquer l'horaire"), self.appliquer, fond=CARTE, petit=True).pack(side="left")
        self.grab_set()

    def appliquer(self, repos: bool = False) -> None:
        try:
            du, au = date.fromisoformat(self.du.get()), date.fromisoformat(self.au.get())
            if au < du:
                raise pl.ErreurPlanning("« Du » doit précéder « au ».")
            choisis = {i for i, v in enumerate(self.jours) if v.get()}
            jours = [du + timedelta(days=i) for i in range((au - du).days + 1)
                     if (du + timedelta(days=i)).weekday() in choisis]
            if not jours:
                raise pl.ErreurPlanning("Aucun jour choisi.")
            quart = None if repos else pl.Quart(self.debut.get(), self.fin.get(), int(self.pause.get() or 0))
            for e in self.employes:
                self.planning.definir(e.id, jours, quart)
        except (pl.ErreurPlanning, ValueError) as exc:
            self.erreur.configure(text=t(str(exc)))
            return
        self.apres()
        self.destroy()


def lignes_horaire(planning: pl.Planning, employe: str, depuis: date, jours: int = 35) -> list[list]:
    lignes = []
    for jour, quart in planning.horaire_employe(employe, depuis, jours):
        lignes.append([jour.isoformat(), t(pl.JOURS[jour.weekday()]), quart.debut if quart else t("Repos"),
                       quart.fin if quart else "", quart.pause if quart else "",
                       f"{quart.heures:.2f}".replace(".", ",") if quart else ""])
    return lignes


class FenetreMonHoraire(tk.Toplevel):
    """Horaire publié de l'employé relié au compte connecté (5 semaines à partir d'aujourd'hui)."""

    def __init__(self, parent, racine: Path, compte: str):
        from .page_rapports import remplir, tableau_simple

        super().__init__(parent)
        self.title(t("Mon horaire"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("620x560")
        employe = next((e for e in pt.Registre(racine).employes if e.compte and e.compte.casefold() == compte.casefold()),
                       None)
        texte = (t("Horaire publié de {n}, 5 semaines à partir d'aujourd'hui.", n=employe.nom) if employe else
                 t("Votre compte n'est relié à aucun employé : demandez au gérant de le relier dans « Paie > Employés "
                   "et NIP »."))
        tk.Label(self, text=texte, background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                 wraplength=580).pack(fill="x")
        tableau = tableau_simple(self, hauteur=18)
        if employe:
            remplir(tableau, ["Date", "Jour", "Début", "Fin", "Pause (min)", "Heures"],
                    lignes_horaire(pl.Planning(racine), employe.id, date.today()),
                    {"Date": 100, "Jour": 60}, decroissant=False)

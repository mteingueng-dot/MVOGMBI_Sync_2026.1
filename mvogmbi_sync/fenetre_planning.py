"""Planning mensuel (demande du propriétaire du 2026-10-29) : le gérant prépare l'horaire du mois de tous les
employés (« Paie > Planning mensuel ») et le publie ; chaque employé voit le sien (« Paie > Mon horaire », ou le
poste de pointage après son NIP). Données dans planning.py."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox, ttk

from . import paie_temps as pt
from . import planning as pl
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee, \
    employes_visibles
from .export_tableau import bouton_exporter
from .langues import t


def _mois_suivant(mois: str, sens: int) -> str:
    annee, m = (int(x) for x in mois.split("-"))
    m += sens
    annee, m = annee + (m - 1) // 12, (m - 1) % 12 + 1
    return f"{annee}-{m:02d}"


class FenetrePlanning(FenetreOutil):
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
        # une cédule par dépôt (demande du propriétaire du 2026-11-05) : employés du dépôt, « Tout sélectionner »
        from .design import filtre_depots

        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Dépôt"), background=CARTE).pack(side="left")
        self.choix_depot, self.depot = filtre_depots(groupe, self.racine, self.afficher)
        self.choix_depot.pack(side="left", padx=4)
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
        from .design import depots_choisis

        self.employes = pl.employes_du_depot(employes_visibles(self, pt.Registre(self.racine).actifs()),
                                             depots_choisis(self.depot), self.planning, self.mois)
        filtre = depots_choisis(self.depot)
        jours = pl.jours_du_mois(self.mois)
        publie = self.planning.publies.get(self.mois)
        self.libelle.configure(text=t("Planning de {m}", m=self.mois) + (
            "  ✔ " + t("publié le {d}", d=publie[:10]) if publie else "  ● " + t("non publié")))
        from .depots import garde

        entetes = ["Employé", "Dépôt"] + [f"{t(pl.JOURS[j.weekday()])} {j:%d}" for j in jours] + ["Heures"]
        lignes = []
        for e in self.employes:
            quarts = [self.planning.quart(self.mois, e.id, j) for j in jours]
            cases = []
            for q in quarts:  # quart dans un autre dépôt : son nom ; hors du filtre : grisé (entre crochets)
                if not q:
                    cases.append("")
                    continue
                texte = q.texte().replace(" min)", ")")
                ailleurs = pl.depot_du_quart(q, e) != pl.depot_du_quart(None, e)
                texte += f" @{pl.depot_du_quart(q, e)}" if ailleurs else ""
                cases.append(texte if garde(pl.depot_du_quart(q, e), filtre) else f"[{texte}]")
            lignes.append([e.nom, pl.depot_du_quart(None, e)] + cases
                          + [f"{self.planning.heures(self.mois, e.id):.2f}".replace(".", ",")])
        largeurs = {x: 78 for x in entetes[1:-1]}
        largeurs.update({"Employé": 170, "Dépôt": 120, "Heures": 70})
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
        DialogueHoraire(self, self.planning, employes, self.mois, self.afficher, self.racine)

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


DEPOT_PRINCIPAL = "(dépôt principal de l'employé)"


def _noms_depots(racine) -> list[str]:
    import tomllib

    from .depots import noms

    if racine is None:
        return []
    try:
        return noms(tomllib.loads((Path(racine) / "config.toml").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


class DialogueHoraire(tk.Toplevel):
    CREATION = True  # fenêtre de création : reste une fenêtre à part (avec « Fermer »)

    def __init__(self, parent, planning: pl.Planning, employes: list[pt.Employe], mois: str, apres, racine=None):
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
        # dépôt du quart : vide = dépôt principal de chaque employé (un employé peut travailler ailleurs ce jour-là)
        lieu = tk.Frame(self, background=CARTE)
        lieu.pack(anchor="w", pady=4)
        tk.Label(lieu, text=t("Dépôt"), background=CARTE).pack(side="left", padx=(8, 4))
        self.depot = tk.StringVar(value=t(DEPOT_PRINCIPAL))
        ttk.Combobox(lieu, textvariable=self.depot, state="readonly", width=28,
                     values=[t(DEPOT_PRINCIPAL)] + _noms_depots(racine)).pack(side="left")
        self.erreur = tk.Label(self, text="", background=CARTE, foreground=ROUGE)
        self.erreur.pack(anchor="w")
        bas = tk.Frame(self, background=CARTE)
        bas.pack(anchor="e", pady=(8, 0))
        Bouton(bas, "✖  " + t("Fermer"), self.destroy, "secondaire", fond=CARTE, petit=True).pack(side="left")
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
            depot = "" if self.depot.get() == t(DEPOT_PRINCIPAL) else self.depot.get()
            for e in self.employes:
                quart = None if repos else pl.Quart(self.debut.get(), self.fin.get(), int(self.pause.get() or 0),
                                                    "" if pl.depot_du_quart(None, e) == depot else depot)
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


ENTETES_HORAIRE = ["Jour", "Horaire", "Pause", "Heures"]
MOIS_COURTS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def semaines_horaire(lignes: list[list]) -> tuple[list[list], list[Decimal]]:
    """Lignes de `lignes_horaire` regroupées par semaine (dimanche à samedi) pour l'affichage : [jour, horaire, pause,
    heures, sorte] où sorte = « semaine » (titre de la semaine et son total), « quart » ou « repos » ; et le total de
    chaque semaine."""
    sortie, totaux, courante, titre = [], [], None, None
    for iso, jour_semaine, debut, fin, pause, heures in lignes:
        d = date.fromisoformat(iso)
        dimanche = d - timedelta(days=(d.weekday() + 1) % 7)
        if dimanche != courante:
            courante = dimanche
            titre = [t("Semaine du {j} {m}", j=dimanche.day, m=t(MOIS_COURTS[dimanche.month - 1])), "", "", "", "semaine"]
            sortie.append(titre)
            totaux.append(Decimal(0))
        libelle = f"{jour_semaine} {d.day} {t(MOIS_COURTS[d.month - 1])}"
        if fin:
            h = Decimal(heures.replace(",", "."))
            totaux[-1] += h
            sortie.append([libelle, f"{debut} – {fin}", f"{pause} min" if pause else "—", heures, "quart"])
        else:
            sortie.append([libelle, debut, "", "", "repos"])
        titre[3] = f"{totaux[-1]:.2f}".replace(".", ",")
    return sortie, totaux


class FenetreMonHoraire(FenetreOutil):
    """Horaire publié de l'employé relié au compte connecté (5 semaines à partir d'aujourd'hui)."""

    def __init__(self, parent, racine: Path, compte: str):
        from .page_rapports import remplir, tableau_simple

        super().__init__(parent)
        self.title(t("Mon horaire"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("760x620")
        employe = next((e for e in pt.Registre(racine).employes if e.compte and e.compte.casefold() == compte.casefold()),
                       None)
        texte = (t("Horaire publié de {n}, 5 semaines à partir d'aujourd'hui.", n=employe.nom) if employe else
                 t("Votre compte n'est relié à aucun employé : demandez au gérant de le relier dans « Paie > Employés "
                   "et NIP »."))
        tk.Label(self, text=texte, background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                 wraplength=720).pack(fill="x")
        if not employe:
            return
        lignes, semaines = semaines_horaire(lignes_horaire(pl.Planning(racine), employe.id, date.today()))
        travailles = [l for l in lignes if l[-1] == "quart"]
        # cartes : prochain quart, heures de la semaine, jours de travail
        cartes = tk.Frame(self, background=CARTE)
        cartes.pack(fill="x", pady=(8, 2))
        prochain = f"{travailles[0][0]}  {travailles[0][1]}" if travailles else t("Aucun quart publié")
        total = sum(semaines, Decimal(0))
        for colonne, (titre, valeur) in enumerate(((t("Prochain quart"), prochain),
                                                   (t("Heures sur 5 semaines"), f"{total:.2f} h".replace(".", ",")),
                                                   (t("Jours de travail"), str(len(travailles))))):
            carte = tk.Frame(cartes, background="#f4f9f5", highlightthickness=1, highlightbackground="#e1ece4")
            carte.grid(row=0, column=colonne, sticky="nsew", padx=3)
            cartes.columnconfigure(colonne, weight=1, uniform="h")
            tk.Label(carte, text=titre, background="#f4f9f5", foreground=TEXTE_DOUX, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x", padx=8, pady=(5, 0))
            tk.Label(carte, text=valeur, background="#f4f9f5", foreground=VERT_FONCE, font=("Segoe UI Semibold", 12),
                     anchor="w").pack(fill="x", padx=8, pady=(0, 5))
        tableau = tableau_simple(self, hauteur=16)
        remplir(tableau, ENTETES_HORAIRE, [l[:-1] for l in lignes], {}, lambda i: (lignes[i][-1],), decroissant=False)
        tableau.tag_configure("repos", foreground="#9aa79e")
        tableau.tag_configure("semaine", background="#e3f1e7", font=("Segoe UI Semibold", 9))
        tableau.tag_configure("quart", font=("Segoe UI Semibold", 9))
        for colonne, largeur in zip(tableau["columns"], (210, 190, 110, 90)):  # tout le tableau occupe la largeur
            tableau.column(colonne, width=largeur, stretch=True, anchor="center" if largeur < 200 else "w")

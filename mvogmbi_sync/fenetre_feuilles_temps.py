"""Feuilles de temps du gérant (rubrique Paie, demande du propriétaire du 2026-10-29) : période de paie de 14 jours,
heures par jour, normales et supplémentaires, anomalies ; corrections des pointages (motif obligatoire, auteur
noté) ; approbation ; employés et NIP. Calculs dans paie_temps.py."""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import paie_temps as pt
from .design import CARTE, TEXTE_DOUX, VERT_FONCE, Bouton, Rangee
from .export_tableau import bouton_exporter
from .fenetre_pointage import reference
from .langues import t

JOURS_COURTS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
COULEURS = {"anomalie": "#fde2e4", "approuvee": "#e3f1e7", "corrigee": "#fff4d6"}


def _h(v) -> str:
    return "" if not v else f"{v:.2f}".replace(".", ",")


class FenetreFeuilles(tk.Toplevel):
    def __init__(self, parent, racine: Path, auteur: str):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.auteur = Path(racine), auteur
        self.reference = reference(racine)
        self.debut = pt.debut_periode(date.today(), self.reference)
        self.title(t("Feuilles de temps"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1250x640")
        barre = Rangee(self)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "◀", lambda: self.changer(-1), "secondaire", fond=CARTE, petit=True), 4)
        self.libelle = barre.ajouter(tk.Label(barre, text="", background=CARTE, font=("Segoe UI Semibold", 11)), 4)
        barre.ajouter(Bouton(barre, "▶", lambda: self.changer(1), "secondaire", fond=CARTE, petit=True), 14)
        barre.ajouter(Bouton(barre, "✔  " + t("Approuver les feuilles sans anomalie"), self.approuver, fond=CARTE,
                             petit=True))
        barre.ajouter(Bouton(barre, "✎  " + t("Pointages de l'employé…"), self.detail, "secondaire", fond=CARTE,
                             petit=True))
        barre.ajouter(Bouton(barre, "👥  " + t("Employés et NIP…"), lambda: FenetreEmployes(self, self.racine,
                                                                                         self.afficher),
                             "secondaire", fond=CARTE, petit=True))
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=1200)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=16)
        for cle, couleur in COULEURS.items():
            self.tableau.tag_configure(cle, background=couleur)
        self.tableau.bind("<Double-1>", lambda _e: self.detail())
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.libelle.cget("text")))
        self.afficher()

    def changer(self, sens: int) -> None:
        self.debut += timedelta(days=sens * pt.JOURS_PERIODE)
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.registre = pt.Registre(self.racine)
        self.feuilles = pt.feuilles(self.registre, self.debut)
        fin = self.debut + timedelta(days=pt.JOURS_PERIODE - 1)
        self.libelle.configure(text=t("Période de paie du {d} au {f}", d=f"{self.debut:%Y-%m-%d}", f=f"{fin:%Y-%m-%d}"))
        jours = [self.debut + timedelta(days=i) for i in range(pt.JOURS_PERIODE)]
        entetes = (["Employé"] + [f"{t(JOURS_COURTS[j.weekday()])} {j:%d}" for j in jours]
                   + ["Semaine 1", "Semaine 2", "Normales", "Supplémentaires", "État", "Anomalies"])
        lignes = [[f.employe.nom] + [_h(h) for h in f.jours] + [_h(f.semaines[0]), _h(f.semaines[1]),
                                                               _h(f.normales), _h(f.supplementaires), t(f.etat),
                                                               " ; ".join(f.anomalies)] for f in self.feuilles]

        def couleur(i):
            f = self.feuilles[i]
            return ("anomalie",) if f.anomalies else ("approuvee",) if f.etat != pt.A_APPROUVER else (
                ("corrigee",) if f.corrigee else ())

        largeurs = {e: 52 for e in entetes[1:15]}
        largeurs.update({"Employé": 170, "Semaine 1": 75, "Semaine 2": 75, "Normales": 75, "Supplémentaires": 100,
                         "État": 110, "Anomalies": 260})
        remplir(self.tableau, entetes, lignes, largeurs, couleur, decroissant=False)
        total = sum((f.total for f in self.feuilles), pt.Decimal(0))
        self.etat.configure(text=t("{n} employé(s), {h} h dont {s} h supplémentaires — à approuver : {a}, approuvées : "
                                   "{o}, avec anomalies : {x}. Rose : anomalie à corriger ; jaune : pointage corrigé "
                                   "par le gérant ; vert : approuvée. Heures supplémentaires au-delà de 40 h par "
                                   "semaine ; pauses pointées non payées.", n=len(self.feuilles), h=_h(total) or "0",
                                   s=_h(sum((f.supplementaires for f in self.feuilles), pt.Decimal(0))) or "0",
                                   a=sum(1 for f in self.feuilles if f.etat == pt.A_APPROUVER and not f.anomalies),
                                   o=sum(1 for f in self.feuilles if f.etat != pt.A_APPROUVER),
                                   x=sum(1 for f in self.feuilles if f.anomalies)))

    def _feuille(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un employé dans la liste."), parent=self)
            return None
        return self.feuilles[int(choix[0])]

    def approuver(self) -> None:
        pretes = [f for f in self.feuilles if f.etat == pt.A_APPROUVER and not f.anomalies and f.total > 0]
        if not pretes:
            messagebox.showinfo(self.title(), t("Aucune feuille à approuver (sans anomalie et avec des heures)."),
                                parent=self)
            return
        if not messagebox.askyesno(self.title(), t("Approuver {n} feuille(s) de temps ?", n=len(pretes)), parent=self):
            return
        for f in pretes:
            pt.approuver(self.registre, f, self.auteur)
        self.afficher()

    def detail(self) -> None:
        f = self._feuille()
        if f:
            FenetreDetail(self, self.registre, f.employe, self.debut, self.auteur, self.afficher)


class FenetreDetail(tk.Toplevel):
    """Pointages d'un employé pendant la période ; corrections avec motif."""

    def __init__(self, parent, registre: pt.Registre, employe: pt.Employe, debut: date, auteur: str, apres):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.registre, self.employe, self.debut, self.auteur, self.apres = registre, employe, debut, auteur, apres
        self.title(t("Pointages de {n}", n=employe.nom))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("900x520")
        barre = Rangee(self)
        barre.pack(fill="x")
        for texte, commande in (("➕  " + t("Ajouter un pointage"), self.ajouter),
                                ("🕑  " + t("Changer l'heure"), self.changer_heure),
                                ("✖  " + t("Annuler le pointage"), self.annuler)):
            barre.ajouter(Bouton(barre, texte, commande, "secondaire", fond=CARTE, petit=True))
        tk.Label(self, text=t("Chaque correction garde le pointage d'origine, l'auteur et le motif."),
                 background=CARTE, foreground=TEXTE_DOUX, anchor="w").pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=14)
        self.tableau.tag_configure("annule", foreground="#9a9a9a")
        self.tableau.tag_configure("correction", background="#fff4d6")
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: self.title()))
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        fin = (self.debut + timedelta(days=pt.JOURS_PERIODE)).isoformat()
        valides = {p.id for p in self.registre.valides(self.employe.id)}
        self.lignes = sorted((p for p in self.registre.pointages if p.employe == self.employe.id and not p.annule
                              and self.debut.isoformat() <= p.moment[:10] < fin), key=lambda p: p.moment)
        remplir(self.tableau, ["Date", "Heure", "Pointage", "Source", "Auteur", "Motif", "En vigueur"],
                [[p.moment[:10], p.moment[11:16], t(p.type), t(p.source), p.auteur, p.motif,
                  t("Oui") if p.id in valides else t("Annulé")] for p in self.lignes],
                {"Date": 95, "Heure": 60, "Pointage": 120, "Source": 90, "Auteur": 120, "Motif": 260,
                 "En vigueur": 80},
                lambda i: ("annule",) if self.lignes[i].id not in valides else (
                    ("correction",) if self.lignes[i].source == "Correction" else ()), decroissant=False)

    def _choisi(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un pointage."), parent=self)
            return None
        return self.lignes[int(choix[0])]

    def _motif(self) -> str | None:
        motif = simpledialog.askstring(self.title(), t("Motif de la correction (obligatoire) :"), parent=self)
        if motif is not None and not motif.strip():
            messagebox.showerror(self.title(), t("Le motif de la correction est obligatoire."), parent=self)
            return None
        return motif

    def _moment(self, defaut: str) -> datetime | None:
        texte = simpledialog.askstring(self.title(), t("Date et heure (AAAA-MM-JJ HH:MM) :"), initialvalue=defaut,
                                       parent=self)
        if texte is None:
            return None
        try:
            return datetime.strptime(texte.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror(self.title(), t("Format attendu : AAAA-MM-JJ HH:MM (ex. 2026-10-20 08:30)."),
                                 parent=self)
            return None

    def _fin(self) -> None:
        self.afficher()
        self.apres()

    def ajouter(self) -> None:
        choix = TypeChoisi(self)
        if not choix.valeur:
            return
        moment = self._moment(f"{self.debut:%Y-%m-%d} 08:00")
        motif = self._motif() if moment else None
        if moment and motif:
            self.registre.corriger(self.employe.id, choix.valeur, moment, self.auteur, motif)
            self._fin()

    def changer_heure(self) -> None:
        p = self._choisi()
        if not p:
            return
        moment = self._moment(p.moment[:16].replace("T", " "))
        motif = self._motif() if moment else None
        if moment and motif:
            self.registre.corriger(self.employe.id, p.type, moment, self.auteur, motif, remplace=p.id)
            self._fin()

    def annuler(self) -> None:
        p = self._choisi()
        if not p:
            return
        motif = self._motif()
        if motif:
            self.registre.annuler(p.id, self.auteur, motif)
            self._fin()


class TypeChoisi(tk.Toplevel):
    """Petite boîte : type du pointage à ajouter."""

    def __init__(self, parent):
        super().__init__(parent)
        self.valeur = ""
        self.title(t("Ajouter un pointage"))
        self.configure(background=CARTE, padx=16, pady=12)
        self.transient(parent)
        variable = tk.StringVar(value=t(pt.ARRIVEE))
        ttk.Combobox(self, textvariable=variable, values=[t(x) for x in pt.TYPES], state="readonly",
                     width=20).pack(pady=6)

        def ok():
            self.valeur = next(x for x in pt.TYPES if t(x) == variable.get())
            self.destroy()

        Bouton(self, t("Continuer"), ok, fond=CARTE, petit=True).pack(pady=6)
        self.grab_set()
        self.wait_window()


class FenetreEmployes(tk.Toplevel):
    """Employés du pointage : importés de Clover ou ajoutés, NIP (empreinte seulement), actif."""

    def __init__(self, parent, racine: Path, apres):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.apres = Path(racine), apres
        self.title(t("Employés et NIP"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("760x480")
        barre = Rangee(self)
        barre.pack(fill="x")
        for texte, commande in (("⬇  " + t("Importer les employés de Clover"), self.importer),
                                ("➕  " + t("Ajouter un employé"), self.ajouter),
                                ("🔑  " + t("Définir le NIP"), self.nip),
                                ("🔗  " + t("Relier à un compte…"), self.relier),
                                ("⏻  " + t("Activer / désactiver"), self.basculer)):
            barre.ajouter(Bouton(barre, texte, commande, "secondaire", fond=CARTE, petit=True))
        self.etat = tk.Label(self, text=t("Le NIP (4 à 6 chiffres) n'est jamais gardé : seule son empreinte l'est. "
                                          "Un employé sans NIP n'apparaît pas au poste de pointage."),
                             background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=720)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=14)
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.registre = pt.Registre(self.racine)
        self.liste = sorted(self.registre.employes, key=lambda e: (not e.actif, e.nom.casefold()))
        remplir(self.tableau, ["Employé", "NIP", "Actif", "Employé Clover", "Compte de l'application"],
                [[e.nom, t("Défini") if e.nip else t("À définir"), t("Oui") if e.actif else t("Non"),
                  t("Oui") if e.clover else "", e.compte] for e in self.liste],
                {"Employé": 240, "NIP": 90, "Actif": 60, "Employé Clover": 100}, decroissant=False)

    def _choisi(self):
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un employé dans la liste."), parent=self)
            return None
        return self.liste[int(choix[0])]

    def _fin(self) -> None:
        self.registre.enregistrer()
        self.afficher()
        self.apres()

    def importer(self) -> None:
        try:
            from .__main__ import charger_config
            from .api_clover import ClientClover

            client = ClientClover(charger_config(self.racine / "config.toml"))
            n = self.registre.importer_clover(list(client._pages("employees", {})))
        except BaseException as exc:  # SystemExit compris (jeton absent)
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        self._fin()
        self.etat.configure(text=t("{n} employé(s) ajouté(s) depuis Clover. Définissez leur NIP.", n=n),
                            foreground=VERT_FONCE)

    def ajouter(self) -> None:
        nom = simpledialog.askstring(self.title(), t("Nom de l'employé :"), parent=self)
        if not nom:
            return
        try:
            self.registre.ajouter(nom)
        except pt.ErreurPointage as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
            return
        self._fin()

    def nip(self) -> None:
        e = self._choisi()
        if not e:
            return
        premier = simpledialog.askstring(self.title(), t("Nouveau NIP de {n} (4 à 6 chiffres) :", n=e.nom), show="•",
                                         parent=self)
        if premier is None:
            return
        second = simpledialog.askstring(self.title(), t("Confirmez le NIP :"), show="•", parent=self)
        if second != premier:
            messagebox.showerror(self.title(), t("Les deux NIP ne sont pas identiques."), parent=self)
            return
        try:
            self.registre.definir_nip(e.id, premier)
        except pt.ErreurPointage as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
            return
        self._fin()
        self.etat.configure(text=t("NIP de {n} enregistré.", n=e.nom), foreground=VERT_FONCE)

    def relier(self) -> None:
        """Compte de l'application de l'employé : il voit son horaire dans « Paie > Mon horaire »."""
        from .utilisateurs import Registre as Comptes

        e = self._choisi()
        if not e:
            return
        comptes = [u.nom for u in Comptes(self.racine).utilisateurs]
        boite = tk.Toplevel(self)
        boite.title(t("Relier à un compte…"))
        boite.configure(background=CARTE, padx=16, pady=12)
        boite.transient(self)
        tk.Label(boite, text=t("Compte de l'application de {n} :", n=e.nom), background=CARTE).pack(anchor="w")
        choix = tk.StringVar(value=e.compte or (comptes[0] if comptes else ""))
        ttk.Combobox(boite, textvariable=choix, values=[""] + comptes, state="readonly", width=30).pack(pady=6)

        def ok():
            e.compte = choix.get()
            boite.destroy()
            self._fin()

        Bouton(boite, t("Enregistrer"), ok, fond=CARTE, petit=True).pack(anchor="e")
        boite.grab_set()

    def basculer(self) -> None:
        e = self._choisi()
        if e:
            e.actif = not e.actif
            self._fin()


def ouvrir(parent, racine: Path, auteur: str) -> FenetreFeuilles:
    return FenetreFeuilles(parent, racine, auteur)


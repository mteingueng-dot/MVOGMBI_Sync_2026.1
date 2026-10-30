"""Feuilles de temps du gérant (rubrique Paie, demande du propriétaire du 2026-10-29) : période de paie de 14 jours,
heures par jour, normales et supplémentaires, anomalies ; corrections des pointages (motif obligatoire, auteur
noté) ; approbation ; employés et NIP. Calculs dans paie_temps.py."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import paie_temps as pt
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, Rangee, dans_application
from .export_tableau import bouton_exporter
from .fenetre_pointage import reference
from .langues import t

JOURS_COURTS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
COULEURS = {"anomalie": "#fde2e4", "approuvee": "#e3f1e7", "corrigee": "#fff4d6"}


def _h(v) -> str:
    return "" if not v else f"{v:.2f}".replace(".", ",")


class FenetreFeuilles(FenetreOutil):
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
        barre.ajouter(Bouton(barre, "👥  " + t("Employés et NIP…"), lambda: dans_application(
            self, FenetreEmployes(self.nametowidget("."), self.racine, self.afficher)),
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
            dans_application(self, FenetreDetail(self.nametowidget("."), self.registre, f.employe, self.debut,
                                                 self.auteur, self.afficher))


class FenetreDetail(FenetreOutil):
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
    CREATION = True  # fenêtre de création : reste une fenêtre à part (avec « Fermer »)


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


class FenetreEmployes(FenetreOutil):
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
                                ("➕  " + t("Ajouter"), self.ajouter), ("✎  " + t("Modifier"), self.renommer),
                                ("🗑  " + t("Supprimer"), self.supprimer),
                                ("🔑  " + t("Définir le NIP"), self.nip),
                                ("🔗  " + t("Relier à un compte…"), self.relier),
                                ("🔗  " + t("Lier aux employés Sage…"), self.lier_sage),
                                ("✉  " + t("Courriel…"), self.courriel),
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
        remplir(self.tableau, ["Employé", "NIP", "Actif", "Employé Clover", "Employé Sage", "Courriel",
                               "Compte de l'application"],
                [[e.nom, t("Défini") if e.nip else t("À définir"), t("Oui") if e.actif else t("Non"),
                  t("Oui") if e.clover else "", e.numero_sage, e.courriel, e.compte] for e in self.liste],
                {"Employé": 200, "NIP": 80, "Actif": 55, "Employé Clover": 95, "Employé Sage": 180, "Courriel": 200},
                decroissant=False)

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
        DialogueEmploye(self, self.racine, self._apres_liens)

    def renommer(self) -> None:
        e = self._choisi()
        if not e:
            return
        nom = simpledialog.askstring(self.title(), t("Nom de l'employé :"), initialvalue=e.nom, parent=self)
        if not nom:
            return
        try:
            self.registre.renommer(e.id, nom)
        except pt.ErreurPointage as exc:
            messagebox.showerror(self.title(), t(str(exc)), parent=self)
            return
        self._fin()

    def supprimer(self) -> None:
        e = self._choisi()
        if not e or not messagebox.askyesno(self.title(), t("Supprimer {n} ?", n=e.nom), parent=self):
            return
        try:
            self.registre.supprimer(e.id)
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

    def courriel(self) -> None:
        """Adresse où l'employé reçoit son bulletin de paie (à inscrire aussi dans sa fiche Sage si elle change)."""
        from .courriel import adresses_invalides

        e = self._choisi()
        if not e:
            return
        adresse = simpledialog.askstring(self.title(), t("Courriel de {n} (bulletins de paie) :", n=e.nom),
                                         initialvalue=e.courriel, parent=self)
        if adresse is None:
            return
        adresse = adresse.strip()
        if adresse and adresses_invalides(adresse):
            messagebox.showerror(self.title(), t("Adresse de courriel invalide."), parent=self)
            return
        e.courriel = adresse
        self._fin()

    def lier_sage(self) -> None:
        LiensSage(self, self.racine, self._apres_liens)

    def _apres_liens(self) -> None:
        self.afficher()
        self.apres()

    def basculer(self) -> None:
        e = self._choisi()
        if e:
            e.actif = not e.actif
            self._fin()


ROLES_CLOVER = {"Employé": "EMPLOYEE", "Gérant": "MANAGER", "Administrateur": "ADMIN"}


class DialogueEmploye(tk.Toplevel):
    """Nouvel employé (demande du propriétaire du 2026-10-29) : créé dans l'application (poste de pointage, NIP), dans
    Clover (rôle, surnom, courriel facultatif) et dans Sage Paie (robot_paie : fiche remplie par l'application, Sage
    fermé), relié aux trois. Le NAS n'est jamais gardé par l'application : il est transmis à Sage puis oublié."""

    CREATION = True
    CHAMPS = (("nom", "Nom *"), ("surnom", "Surnom (caisse Clover)"), ("role", "Rôle dans Clover"),
              ("courriel", "Courriel (bulletins de paie)"), ("nip", "NIP du poste de pointage (facultatif)"))
    CHAMPS_SAGE = (("rue", "Adresse"), ("ville", "Ville"), ("code_postal", "Code postal"), ("telephone", "Téléphone"),
                   ("nas", "NAS *"), ("naissance", "Date de naissance * (AAAA-MM-JJ)"),
                   ("embauche", "Date d'embauche * (AAAA-MM-JJ)"), ("taux", "Taux horaire * ($)"),
                   ("taux_supp", "Taux des heures supplémentaires ($)"))

    def __init__(self, parent, racine: Path, apres):
        super().__init__(parent)
        self.racine, self.apres = Path(racine), apres
        self.title(t("Nouvel employé"))
        self.configure(background=CARTE, padx=16, pady=12)
        self.transient(parent.winfo_toplevel())
        self.v = {cle: tk.StringVar() for cle, _ in self.CHAMPS + self.CHAMPS_SAGE}
        self.v["role"].set(t("Employé"))
        self.v["ville"].set("Sherbrooke")
        self.v["embauche"].set(date.today().isoformat())
        self.v["taux"].trace_add("write", lambda *_: self._taux_supp())
        colonnes = tk.Frame(self, background=CARTE)
        colonnes.pack(fill="x")
        gauche = ttk.LabelFrame(colonnes, text=" " + t("Application et Clover") + " ", padding=8)
        gauche.pack(side="left", fill="both", padx=(0, 10))
        droite = ttk.LabelFrame(colonnes, text=" " + t("Sage Paie") + " ", padding=8)
        droite.pack(side="left", fill="both")
        for cadre, champs in ((gauche, self.CHAMPS), (droite, self.CHAMPS_SAGE)):
            for rang, (cle, libelle) in enumerate(champs):
                tk.Label(cadre, text=t(libelle), anchor="w").grid(row=rang, column=0, sticky="w", padx=(0, 8), pady=3)
                if cle == "role":
                    ttk.Combobox(cadre, textvariable=self.v[cle], values=[t(r) for r in ROLES_CLOVER],
                                 state="readonly", width=22).grid(row=rang, column=1, sticky="w", pady=3)
                else:
                    ttk.Entry(cadre, textvariable=self.v[cle], width=28 if cadre is gauche else 22,
                              show="•" if cle in ("nip", "nas") else "").grid(row=rang, column=1, sticky="w", pady=3)
        self.clover = tk.BooleanVar(value=True)
        ttk.Checkbutton(gauche, text=t("Créer dans Clover"), variable=self.clover).grid(
            row=len(self.CHAMPS), column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.sage = tk.BooleanVar(value=True)
        ttk.Checkbutton(droite, text=t("Créer dans Sage Paie (Sage fermé)"), variable=self.sage).grid(
            row=len(self.CHAMPS_SAGE), column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.etat = tk.Label(self, text=t("Le courriel reçoit le bulletin de paie (et l'invitation de Clover) ; il est "
                                          "aussi inscrit dans la fiche Sage. Le NAS n'est jamais gardé par "
                                          "l'application. Paie aux 2 semaines (26 périodes), impôt du Québec."),
                             background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=760)
        self.etat.pack(fill="x", pady=(8, 0))
        bas = tk.Frame(self, background=CARTE)
        bas.pack(anchor="e", pady=(10, 0))
        Bouton(bas, "✖  " + t("Fermer"), self.destroy, "secondaire", fond=CARTE).pack(side="right")
        self.bouton = Bouton(bas, "✔  " + t("Créer l'employé"), self.creer, fond=CARTE)
        self.bouton.pack(side="right", padx=8)
        self.grab_set()

    def _taux_supp(self) -> None:
        try:
            taux = Decimal(self.v["taux"].get().replace(",", ".").strip())
            self.v["taux_supp"].set(f"{taux * Decimal('1.5'):.2f}".replace(".", ","))
        except Exception:
            pass

    def _erreur(self, texte: str) -> None:
        self.etat.configure(text="✘ " + texte, foreground=ROUGE)

    def creer(self) -> None:
        from .design import action_permise

        if self.sage.get() and not action_permise(self, "Créer un employé dans Sage"):
            return
        nom = " ".join(self.v["nom"].get().split())
        nip = self.v["nip"].get().strip()
        if not nom:
            return self._erreur(t("Le nom est obligatoire."))
        if nip and not (nip.isdigit() and 4 <= len(nip) <= 6):
            return self._erreur(t("Le NIP doit compter 4 à 6 chiffres."))
        courriel = self.v["courriel"].get().strip()
        from .courriel import adresses_invalides

        if courriel and adresses_invalides(courriel):
            return self._erreur(t("Adresse de courriel invalide."))
        if self.sage.get() and not courriel:
            return self._erreur(t("Le courriel est obligatoire pour la paie : chaque employé reçoit son bulletin "
                                  "de paie par courriel."))
        registre = pt.Registre(self.racine)
        if any(e.nom.casefold() == nom.casefold() for e in registre.employes):
            return self._erreur(t("« {n} » existe déjà.", n=nom))
        fiche_sage = None
        if self.sage.get():
            from .robot_paie import EmployeSage

            nas = "".join(c for c in self.v["nas"].get() if c.isdigit())
            if len(nas) != 9:
                return self._erreur(t("Le NAS doit compter 9 chiffres."))
            for cle in ("naissance", "embauche"):
                try:
                    date.fromisoformat(self.v[cle].get().strip())
                except ValueError:
                    return self._erreur(t("Date au format AAAA-MM-JJ."))
            try:
                if Decimal(self.v["taux"].get().replace(",", ".").strip()) <= 0:
                    raise ValueError
            except Exception:
                return self._erreur(t("Taux horaire invalide."))
            fiche_sage = EmployeSage(nom, self.v["rue"].get().strip(), self.v["ville"].get().strip(), "QC",
                                     self.v["code_postal"].get().strip(), self.v["telephone"].get().strip(),
                                     self.v["courriel"].get().strip(), nas, self.v["naissance"].get().strip(),
                                     self.v["embauche"].get().strip(), self.v["taux"].get().strip(),
                                     self.v["taux_supp"].get().strip())
        id_clover, notes = "", []
        if self.clover.get():
            try:
                from .__main__ import charger_config
                from .api_clover import ClientClover

                role = next((v for k, v in ROLES_CLOVER.items() if t(k) == self.v["role"].get()), "EMPLOYEE")
                id_clover = ClientClover(charger_config(self.racine / "config.toml")).creer_employe(
                    nom, self.v["surnom"].get().strip(), role, self.v["courriel"].get().strip()).get("id", "")
                notes.append(t("Clover : créé"))
            except BaseException as exc:  # SystemExit compris (jeton absent)
                if not messagebox.askyesno(self.title(), t("Clover n'a pas créé l'employé :\n{e}\n\nContinuer sans "
                                                           "Clover ?", e=str(exc)), parent=self):
                    return
                notes.append(t("Clover : NON créé"))
        try:
            e = registre.ajouter(nom, id_clover)
            e.courriel = courriel
            try:  # date d'embauche : soldes de vacances et de congés (conges.py)
                from .conges import Registre as Conges

                embauche = self.v["embauche"].get().strip()
                date.fromisoformat(embauche)
                conges = Conges(self.racine)
                conges.embauches[e.id] = embauche
                conges.enregistrer()
            except ValueError:
                pass
            if nip:
                registre.definir_nip(e.id, nip)
            registre.enregistrer()
        except pt.ErreurPointage as exc:
            return self._erreur(t(str(exc)))
        notes.append(t("Application : créé"))
        if fiche_sage is None:
            return self._fin(nom, notes)
        self.bouton.configure(state="disabled")
        self.bouton._commande = None  # un seul lancement
        self.etat.configure(text=t("Création dans Sage Paie… (l'application ouvre Sage elle-même, environ 2 minutes)"),
                            foreground=TEXTE_DOUX)

        def travail():
            import tomllib

            from .robot_paie import dans_sage

            try:
                config = tomllib.loads((self.racine / "config.toml").read_text(encoding="utf-8"))
                bilan = dans_sage(self.racine, config, [fiche_sage], [])
                r = (bilan.get("employes") or [{}])[0]
                message = "" if r.get("fait") else " ; ".join(r.get("messages") or [t("non créé")])
            except Exception as exc:
                message = str(exc)
            self.after(0, lambda: self._fin_sage(e.id, nom, notes, message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_sage(self, ident: str, nom: str, notes: list[str], erreur: str) -> None:
        if not erreur:
            registre = pt.Registre(self.racine)
            registre.employe(ident).numero_sage = nom  # relié : relevés et paies
            registre.enregistrer()
            notes.append(t("Sage Paie : créé et relié"))
        else:
            notes.append(t("Sage Paie : NON créé ({e})", e=erreur))
        if self.winfo_exists():
            self._fin(nom, notes)

    def _fin(self, nom: str, notes: list[str]) -> None:
        messagebox.showinfo(self.title(), nom + "\n\n" + "\n".join(notes), parent=self.master)
        self.destroy()
        self.apres()


class LiensSage(tk.Toplevel):
    """Lien employé de l'application (importé de Clover) -> employé de Sage Paie (demande du propriétaire du
    2026-10-29) : sert aux relevés de paie et à la saisie des heures validées dans Sage. Employés Sage lus dans Sage
    (paie.employes_sage) ; le nom peut aussi être tapé si Sage ne se lit pas."""

    CREATION = True  # choix puis validation : fenêtre à part

    def __init__(self, parent, racine: Path, apres):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.apres = Path(racine), apres
        self.registre = pt.Registre(self.racine)
        self.noms_sage: list[str] = []
        self.propositions: dict[str, str] = {}
        self.title(t("Lier aux employés Sage"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent.winfo_toplevel())
        self.geometry("880x520")
        self.etat = tk.Label(self, text=t("Lecture des employés dans Sage…"), background=CARTE, foreground=TEXTE_DOUX,
                             anchor="w", justify="left", wraplength=840)
        self.etat.pack(fill="x")
        self.tableau = tableau_simple(self, hauteur=12)
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self._choisir())
        ligne = Rangee(self)
        ligne.pack(fill="x", pady=(8, 0))
        groupe = ligne.ajouter(ligne.groupe(), 8)
        tk.Label(groupe, text=t("Employé Sage"), background=CARTE).pack(side="left", padx=(0, 4))
        self.choix = tk.StringVar()
        self.liste_sage = ttk.Combobox(groupe, textvariable=self.choix, width=34)
        self.liste_sage.pack(side="left")
        ligne.ajouter(Bouton(ligne, "🔗  " + t("Relier"), self.relier, fond=CARTE, petit=True), 6)
        ligne.ajouter(Bouton(ligne, "✖  " + t("Retirer le lien"), self.retirer, "secondaire", fond=CARTE,
                             petit=True), 6)
        ligne.ajouter(Bouton(ligne, "✔  " + t("Accepter les propositions"), self.accepter, "secondaire", fond=CARTE,
                             petit=True))
        bas = tk.Frame(self, background=CARTE)
        bas.pack(fill="x", pady=(10, 0))
        Bouton(bas, "✖  " + t("Fermer"), self.destroy, "secondaire", fond=CARTE).pack(side="right")
        Bouton(bas, "✔  " + t("Enregistrer"), self.enregistrer, fond=CARTE).pack(side="right", padx=8)
        self.afficher()
        threading.Thread(target=self._lire, daemon=True).start()
        self.grab_set()

    def _lire(self) -> None:
        import tomllib

        from .__main__ import lire_sage
        from .paie import employes_sage

        try:
            chemin = self.racine / "config.toml"
            config = tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
            noms = lire_sage(config, employes_sage)
            self.after(0, lambda: self._lus(noms, ""))
        except BaseException as exc:  # SystemExit compris
            message = str(exc) or type(exc).__name__
            self.after(0, lambda: self._lus([], message))

    def _lus(self, noms: list[str], erreur: str) -> None:
        from .paie import proposer_lien

        if not self.winfo_exists():
            return
        self.noms_sage = noms
        self.liste_sage.configure(values=noms)
        self.propositions = {e.id: proposer_lien(e, noms) for e in self.registre.employes if not e.numero_sage}
        self.afficher()
        n = sum(1 for v in self.propositions.values() if v)
        if erreur:
            self.etat.configure(text="✘ " + t("Sage illisible : {e} ; vous pouvez taper le nom de l'employé tel que "
                                              "Sage l'écrit.", e=erreur), foreground=ROUGE)
        else:
            self.etat.configure(text=t("{s} employé(s) dans Sage, {n} proposition(s) par le nom : vérifiez puis "
                                       "« Accepter les propositions ».", s=len(noms), n=n), foreground=TEXTE_DOUX)

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.liste = sorted(self.registre.employes, key=lambda e: (not e.actif, e.nom.casefold()))
        remplir(self.tableau, ["Employé", "Employé Clover", "Employé Sage", "Proposition"],
                [[e.nom, t("Oui") if e.clover else "", e.numero_sage, self.propositions.get(e.id, "")]
                 for e in self.liste],
                {"Employé": 230, "Employé Clover": 100, "Employé Sage": 230, "Proposition": 230}, decroissant=False)

    def _employe(self):
        choix = self.tableau.selection()
        return self.liste[int(choix[0])] if choix else None

    def _choisir(self) -> None:
        e = self._employe()
        if e:
            self.choix.set(e.numero_sage or self.propositions.get(e.id, ""))

    def relier(self) -> None:
        e = self._employe()
        nom = " ".join(self.choix.get().split())
        if not e or not nom:
            self.etat.configure(text=t("Choisissez un employé puis son employé Sage."), foreground=ROUGE)
            return
        deja = next((x for x in self.registre.employes if x.id != e.id and x.numero_sage == nom), None)
        if deja:
            self.etat.configure(text=t("« {s} » est déjà relié à {n}.", s=nom, n=deja.nom), foreground=ROUGE)
            return
        e.numero_sage = nom
        self.propositions.pop(e.id, None)
        self.afficher()
        self.etat.configure(text=t("{n} relié à « {s} » : « Enregistrer » pour garder.", n=e.nom, s=nom),
                            foreground=VERT_FONCE)

    def retirer(self) -> None:
        e = self._employe()
        if e:
            e.numero_sage = ""
            self.afficher()

    def accepter(self) -> None:
        pris = {e.numero_sage for e in self.registre.employes if e.numero_sage}
        n = 0
        for e in self.registre.employes:
            nom = self.propositions.get(e.id, "")
            if nom and not e.numero_sage and nom not in pris:
                e.numero_sage = nom
                pris.add(nom)
                n += 1
        self.propositions = {}
        self.afficher()
        self.etat.configure(text=t("{n} lien(s) accepté(s) : « Enregistrer » pour garder.", n=n),
                            foreground=VERT_FONCE)

    def enregistrer(self) -> None:
        self.registre.enregistrer()
        self.destroy()
        self.apres()


def ouvrir(parent, racine: Path, auteur: str) -> FenetreFeuilles:
    return FenetreFeuilles(parent, racine, auteur)


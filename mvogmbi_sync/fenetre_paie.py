"""Page « Paie > Traitement de la paie » (demande du propriétaire du 2026-10-29) : heures planifiées et réalisées
(récapitulatif par employé et par semaine, ou détail par jour), heures validées à saisir dans la paie de Sage, paies
de Sage et relevé de paie imprimé par l'application. Les heures viennent de l'application (pointages), jamais de
Sage ; calculs dans paie.py."""

from __future__ import annotations

import os
import tempfile
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import paie as pa
from . import paie_temps as pt
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, ChampDate, Rangee, login_limite
from .export_tableau import autorise, bouton_exporter, pdf_depuis_html
from .langues import t

ONGLETS = ["Heures planifiées et réalisées", "Heures validées", "Paies dans Sage", "Fin d'année (T4 / RL-1)"]
VUES = ["Récapitulatif par semaine", "Détail par jour"]
PERIODES_AFFICHEES = 13  # période en cours et les 12 précédentes


def _config(racine: Path) -> dict:
    import tomllib

    chemin = Path(racine) / "config.toml"
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def _ecart(v) -> str:
    return ("+" if v > 0 else "") + pa.heures(v) if v else "0 h"


class FenetrePaie(FenetreOutil):
    def __init__(self, parent, racine: Path, onglet: str = ONGLETS[0], ouvrir_feuilles=None):
        from .fenetre_pointage import reference

        super().__init__(parent)
        self.racine, self.ouvrir_feuilles = Path(racine), ouvrir_feuilles
        self.reference = reference(self.racine)
        self.title(t("Traitement de la paie"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("1150x680")
        self.limite = login_limite(self)  # employé connecté : ses heures, ses paies, ses T4 / RL-1 seulement
        self.moi = self.nametowidget(".").employe_connecte() if self.limite else None
        courante = pt.debut_periode(date.today(), self.reference)
        self.periodes = {self._libelle(courante - timedelta(days=pt.JOURS_PERIODE * i)):
                         courante - timedelta(days=pt.JOURS_PERIODE * i) for i in range(PERIODES_AFFICHEES)}
        self.periode = tk.StringVar(value=next(iter(self.periodes)))
        self.paies: list[pa.PaieSage] = []      # paies affichées
        self.paies_annee: list[pa.PaieSage] = []  # pour le total de l'année du relevé
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True)
        self.cadres = {}
        self.boutons_sage = []
        self.tableau_validees = None
        for nom, construire in zip(ONGLETS, (self._heures, self._validees, self._paies, self._fin_annee)):
            if self.limite and nom == "Heures validées":
                continue
            cadre = ttk.Frame(self.onglets, padding=(0, 8, 0, 0))
            self.onglets.add(cadre, text="  " + t(nom) + "  ")
            self.cadres[nom] = cadre
            construire(cadre)
        self.onglets.select(self.cadres.get(onglet, self.cadres[ONGLETS[0]]))
        self.actualiser_heures()

    @staticmethod
    def _libelle(debut: date) -> str:
        return f"{debut:%Y-%m-%d} au {debut + timedelta(days=pt.JOURS_PERIODE - 1):%Y-%m-%d}"

    def _zone(self, cadre, titre: str):
        from .page_rapports import tableau_simple

        barre = Rangee(cadre)
        barre.pack(fill="x")
        etat = tk.Label(cadre, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                        wraplength=1100)
        etat.pack(fill="x", pady=(6, 0))
        libelle = tk.Label(cadre, text=t(titre), background=CARTE, font=("Segoe UI Semibold", 10), anchor="w")
        libelle.pack(fill="x")
        return barre, etat, libelle, tableau_simple(cadre, hauteur=16)

    def _choix_periode(self, barre) -> None:
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Période de paie"), background=CARTE).pack(side="left")
        choix = ttk.Combobox(groupe, textvariable=self.periode, values=list(self.periodes), state="readonly",
                             width=26)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.actualiser_heures())

    def _feuilles(self) -> list[pt.Feuille]:
        registre = pt.Registre(self.racine)
        feuilles = pt.feuilles(registre, self.periodes[self.periode.get()])
        if self.limite:
            return [f for f in feuilles if self.moi is not None and f.employe.id == self.moi.id]
        return feuilles

    # ------------------------------------------------------------------ heures planifiées et réalisées
    def _heures(self, cadre) -> None:
        barre, self.etat_heures, self.titre_heures, self.tableau_heures = self._zone(
            cadre, "Heures planifiées et réalisées")
        self._choix_periode(barre)
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Afficher"), background=CARTE).pack(side="left")
        self.vue = tk.StringVar(value=t(VUES[0]))
        choix = ttk.Combobox(groupe, textvariable=self.vue, values=[t(v) for v in VUES], state="readonly", width=24)
        choix.pack(side="left", padx=4)
        choix.bind("<<ComboboxSelected>>", lambda _e: self.actualiser_heures())
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.actualiser_heures, fond=CARTE, petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_heures, lambda: self.titre_heures.cget("text")))

    def actualiser_heures(self) -> None:
        from .page_rapports import remplir
        from .planning import Planning

        try:
            feuilles = self._feuilles()
            planning = Planning(self.racine)
        except Exception as exc:
            self.etat_heures.configure(text="✘ " + str(exc), foreground=ROUGE)
            return
        periode = self.periode.get()
        if self.vue.get() == t(VUES[1]):
            lignes = pa.jours(feuilles, planning)
            remplir(self.tableau_heures, pa.ENTETES_JOURS,
                    [[l[0], l[1], l[2], pa.heures(l[3]), pa.heures(l[4]), _ecart(l[5])] for l in lignes],
                    {"Employé": 220}, decroissant=False)
            titre = t("Heures planifiées et réalisées par jour, période du {p}", p=periode)
        else:
            lignes = pa.semaines(feuilles, planning)
            remplir(self.tableau_heures, pa.ENTETES_SEMAINES,
                    [[l.debut.isoformat(), l.fin.isoformat(), l.employe, pa.heures(l.planifiees),
                      pa.heures(l.realisees), _ecart(l.ecart), t(l.etat)] for l in lignes],
                    {"Employé": 220}, decroissant=False)
            titre = t("Récapitulatif des heures par employé et par semaine, période du {p}", p=periode)
        self.titre_heures.configure(text=titre)
        anomalies = sum(len(f.anomalies) for f in feuilles)
        self.etat_heures.configure(
            text=t("Heures réalisées = pointages de l'application ; heures planifiées = planning mensuel.")
            + (" " + t("⚠ {n} anomalie(s) de pointage à corriger dans « Feuilles de temps ».", n=anomalies)
               if anomalies else ""), foreground=ROUGE if anomalies else TEXTE_DOUX)
        self.actualiser_validees(feuilles)

    # ------------------------------------------------------------------ heures validées
    def _validees(self, cadre) -> None:
        barre, self.etat_validees, self.titre_validees, self.tableau_validees = self._zone(
            cadre, "Heures validées à saisir dans la paie de Sage")
        self._choix_periode(barre)
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.actualiser_heures, fond=CARTE, petit=True), 10)
        if self.ouvrir_feuilles:
            barre.ajouter(Bouton(barre, "✔  " + t("Approuver les feuilles de temps…"), self.ouvrir_feuilles,
                                 "secondaire", fond=CARTE, petit=True), 10)
        bouton = Bouton(barre, "💵  " + t("Traiter la paie dans Sage…"), self.traiter_sage, fond=CARTE, petit=True)
        self.boutons_sage.append(bouton)
        barre.ajouter(bouton, 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_validees, lambda: self.titre_validees.cget("text")))
        self.tableau_validees.tag_configure("attente", foreground="#7d8b81")

    def actualiser_validees(self, feuilles: list[pt.Feuille]) -> None:
        from .page_rapports import remplir

        if self.tableau_validees is None:
            return
        try:
            self.extras = pa.extras_periode(self.racine, feuilles)
        except Exception:
            self.extras = {}
        lignes = pa.validees(feuilles, self.extras)
        remplir(self.tableau_validees, pa.ENTETES_VALIDEES,
                [l[:3] + [pa.heures(x) for x in l[3:8]] + [t(l[8]), l[9]] for l in lignes],
                {"Employé": 200, "Approuvée par": 200},
                lambda i: () if lignes[i][8] != pt.A_APPROUVER else ("attente",), decroissant=False)
        approuvees = [l for l in lignes if l[8] != pt.A_APPROUVER]
        total = sum((l[7] for l in approuvees), pa.ZERO)
        self.titre_validees.configure(text=t("Heures validées à saisir dans la paie de Sage, période du {p}",
                                             p=self.periode.get()))
        self.etat_validees.configure(
            text=t("{n} feuille(s) approuvée(s), {h} à saisir dans la paie de Sage ; les feuilles en gris attendent "
                   "l'approbation.", n=len(approuvees), h=pa.heures(total)),
            foreground=VERT_FONCE if approuvees else TEXTE_DOUX)

    def traiter_sage(self) -> None:
        """Chèques de paie dans Sage pour les feuilles approuvées des employés reliés à Sage (robot_paie) ; la feuille
        passe ensuite à « Envoyée à Sage ». Jamais deux fois la même paie (employé + période)."""
        from .design import action_permise

        if not action_permise(self, "Traiter la paie dans Sage"):
            return
        from tkinter import simpledialog

        from .robot_paie import PaieATraiter

        feuilles = self._feuilles()
        approuvees = [f for f in feuilles if f.etat == pt.APPROUVEE and f.total > 0]
        a_payer = [f for f in approuvees if f.employe.numero_sage]
        sans_lien = [f.employe.nom for f in approuvees if not f.employe.numero_sage]
        if not a_payer:
            messagebox.showinfo(self.title(), t("Aucune feuille approuvée d'un employé relié à Sage pour cette période.")
                                + ("\n\n" + t("Sans lien avec Sage : {n}", n=", ".join(sans_lien)) if sans_lien else ""),
                                parent=self)
            return
        debut = self.periodes[self.periode.get()]
        fin = debut + timedelta(days=pt.JOURS_PERIODE - 1)
        from .calendrier_paie import Calendrier

        prevue = Calendrier(self.racine).paie_de_periode(debut)  # date du calendrier de paie, modifiable
        if paie_dans_le_futur(fin, fin, date.today()):
            messagebox.showwarning(self.title(), t(paie_dans_le_futur(fin, fin, date.today())), parent=self)
            return
        jour = simpledialog.askstring(self.title(), t("Date des chèques de paie (AAAA-MM-JJ) :"),
                                      initialvalue=min(prevue.jour if prevue else date.today(), date.today()).isoformat(),
                                      parent=self)
        if not jour:
            return
        try:
            date_cheques = date.fromisoformat(jour.strip())
        except ValueError:
            messagebox.showerror(self.title(), t("Date au format AAAA-MM-JJ."), parent=self)
            return
        probleme = paie_dans_le_futur(fin, date_cheques, date.today())
        if probleme:
            messagebox.showwarning(self.title(), t(probleme), parent=self)
            return
        extras = getattr(self, "extras", {}) or {}

        def normales(f):  # heures normales + jours fériés + congés payés (payés au taux régulier dans Sage)
            feries, conges = extras.get(f.employe.id, (pa.ZERO, pa.ZERO))
            return f.normales + feries + conges

        detail = "\n".join(f"• {f.employe.numero_sage} : {pa.heures(normales(f))}"
                           + (f" + {pa.heures(f.supplementaires)} supp." if f.supplementaires else "") for f in a_payer)
        if not messagebox.askyesno(self.title(), t("Traiter dans Sage les chèques de paie du {d} au {f}, datés du {j} :",
                                                   d=debut.isoformat(), f=fin.isoformat(), j=jour.strip()) + "\n\n"
                                   + detail + ("\n\n" + t("Sans lien avec Sage (ignorés) : {n}", n=", ".join(sans_lien))
                                               if sans_lien else "") + "\n\n"
                                   + t("Sage doit être fermé : l'application l'ouvre elle-même."), parent=self):
            return
        from .robot_paie import numero_desjardins

        paies = [PaieATraiter(f.employe.numero_sage, debut.isoformat(), fin.isoformat(), jour.strip(),
                              str(normales(f)), str(f.supplementaires), f.employe.id,
                              numero_desjardins(jour.strip())) for f in a_payer]
        for bouton in self.boutons_sage:
            bouton._commande = None  # un seul lancement
        for etat in (self.etat_validees, self.etat_paies):
            etat.configure(text=t("Traitement de la paie dans Sage… (l'application ouvre Sage elle-même)"),
                           foreground=TEXTE_DOUX)

        def travail():
            from .robot_paie import dans_sage

            try:
                bilan = dans_sage(self.racine, _config(self.racine), [], paies)
                self.after(0, lambda: self._fin_sage(debut, paies, bilan, ""))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self._fin_sage(debut, paies, {}, message))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_sage(self, debut: date, paies, bilan: dict, erreur: str) -> None:
        for bouton in self.boutons_sage:
            bouton._commande = self.traiter_sage
        resultats = bilan.get("paies", [])
        registre = pt.Registre(self.racine)
        lignes = []
        traitees = [p for p in paies if p.__dict__ not in bilan.get("deja", [])]
        for rang, p in enumerate(traitees):
            r = resultats[rang] if rang < len(resultats) else {"messages": [t("non traité")]}
            if r.get("fait"):
                approbation = registre.feuilles.get(debut.isoformat(), {}).get(p.employe)
                if approbation:
                    approbation.update({"etat": pt.ENVOYEE, "paie": p.date_cheque, "net": r.get("net", "")})
                lignes.append(f"✔ {p.nom_sage} : brut {r.get('brut')} $, net {r.get('net')} $")
            else:
                lignes.append(f"✘ {p.nom_sage} : " + " ; ".join(r.get("messages") or [t("non traité")]))
        for d in bilan.get("deja", []):
            lignes.append(f"• {d['nom_sage']} : " + t("déjà traitée pour cette période"))
        registre.enregistrer()
        if erreur:
            lignes.insert(0, "✘ " + erreur)
        if self.winfo_exists():
            self.actualiser_heures()
            messagebox.showinfo(self.title(), "\n".join(lignes) or t("Rien n'a été traité."), parent=self)
            faits = [p for p, r in zip(traitees, resultats) if r.get("fait")]
            if faits:  # demande du propriétaire du 2026-10-29 : liste des paies traitées pour imprimer les bulletins
                self.du.set(faits[0].date_cheque)
                self.au.set(faits[0].date_cheque)
                self.onglets.select(self.cadres["Paies dans Sage"])
                self._choisir_apres_lecture = {p.nom_sage for p in faits}
                self._envoyer_apres_lecture = True
                self.lire_paies()

    # ------------------------------------------------------------------ paies de Sage et relevé
    def _paies(self, cadre) -> None:
        barre, self.etat_paies, self.titre_paies, self.tableau_paies = self._zone(cadre, "Paies dans Sage")
        groupe = barre.ajouter(barre.groupe(), 10)
        tk.Label(groupe, text=t("Du"), background=CARTE).pack(side="left")
        self.du = tk.StringVar(value=(date.today() - timedelta(days=60)).isoformat())
        ChampDate(groupe, self.du, fond=CARTE).pack(side="left", padx=4)
        tk.Label(groupe, text=t("au"), background=CARTE).pack(side="left")
        self.au = tk.StringVar(value=date.today().isoformat())
        ChampDate(groupe, self.au, fond=CARTE).pack(side="left", padx=4)
        barre.ajouter(Bouton(barre, "🔍  " + t("Lire les paies"), self.lire_paies, fond=CARTE, petit=True), 10)
        if not self.limite:  # paies de la période choisie, d'après les heures approuvées (2026-10-30)
            self._choix_periode(barre)
            bouton = Bouton(barre, "💵  " + t("Créer les paies de la période dans Sage…"), self.traiter_sage, "accent",
                            fond=CARTE, petit=True)
            self.boutons_sage.append(bouton)
            barre.ajouter(bouton, 10)
        barre.ajouter(Bouton(barre, "🖨  " + t("Imprimer les bulletins choisis"), self.imprimer_releve, "secondaire",
                             fond=CARTE, petit=True), 10)
        barre.ajouter(Bouton(barre, "🖨  " + t("Imprimer tous les bulletins"), self.imprimer_tout, "secondaire",
                             fond=CARTE, petit=True), 10)
        self.bouton_envoi = Bouton(barre, "✉  " + t("Envoyer les bulletins par courriel…"), self.envoyer_bulletins,
                                   "secondaire", fond=CARTE, petit=True)
        if not self.limite:
            barre.ajouter(self.bouton_envoi, 10)
        barre.ajouter(Bouton(barre, "📕  " + t("Bulletins en PDF…"), self.releve_pdf, "secondaire", fond=CARTE,
                             petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_paies, lambda: self.titre_paies.cget("text")))
        self.tableau_paies.configure(selectmode="extended")  # plusieurs bulletins : Ctrl ou Maj + clic
        self.tableau_paies.bind("<Double-1>", lambda _e: self.imprimer_releve())
        self.etat_paies.configure(text=t("Choisissez les dates puis « Lire les paies » ; double-clic : bulletin de paie ; "
                                         "plusieurs paies : Ctrl ou Maj + clic."))

    def _fin_annee(self, cadre) -> None:
        barre, self.etat_fa, self.titre_fa, self.tableau_fa = self._zone(cadre, "Concordance de fin d'année")
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Année"), background=CARTE).pack(side="left", padx=(0, 4))
        self.annee_fa = tk.StringVar(value=str(date.today().year))
        ttk.Combobox(g, textvariable=self.annee_fa, values=[str(date.today().year - i) for i in range(3)],
                     state="readonly", width=6).pack(side="left")
        barre.ajouter(Bouton(barre, "🔍  " + t("Calculer"), self.calculer_fin_annee, fond=CARTE, petit=True), 10)
        barre.ajouter(Bouton(barre, "🖨  " + t("Imprimer T4 / RL-1 choisis"), self.imprimer_feuillets, "secondaire",
                             fond=CARTE, petit=True), 10)
        barre.ajouter(Bouton(barre, "🖨  " + t("Imprimer tous les T4 / RL-1"), self.imprimer_tous_feuillets, "secondaire",
                             fond=CARTE, petit=True), 10)
        barre.ajouter(Bouton(barre, "📕  " + t("T4 / RL-1 en PDF…"), self.feuillets_pdf, "secondaire", fond=CARTE,
                             petit=True), 10)
        self.bouton_feuillets = Bouton(barre, "✉  " + t("Envoyer les T4 / RL-1 par courriel…"), self.envoyer_feuillets,
                                       "secondaire", fond=CARTE, petit=True)
        if not self.limite:
            barre.ajouter(self.bouton_feuillets, 10)
            barre.ajouter(Bouton(barre, "🔢  " + t("N° d'employeur…"), self.numero_employeur, "secondaire", fond=CARTE,
                                 petit=True), 10)
        barre.ajouter(bouton_exporter(barre, self.tableau_fa, lambda: self.titre_fa.cget("text")))
        self.tableau_fa.configure(selectmode="extended")  # plusieurs employés : Ctrl ou Maj + clic
        self.tableau_fa.bind("<Double-1>", lambda _e: self.imprimer_feuillets())
        self.feuillets = []
        self.etat_fa.configure(text=t("Cumuls des paies de Sage de l'année par employé. « Calculer », puis choisissez un ou "
                                      "plusieurs employés (Ctrl ou Maj + clic) : T4 et Relevé 1 imprimés ou envoyés à "
                                      "chacun. Les feuillets officiels restent ceux de Sage, à transmettre avant la fin "
                                      "février."))

    def calculer_fin_annee(self) -> None:
        from . import feuillets as fe
        from .__main__ import lire_sage
        from .fin_emploi import ENTETES_CONCORDANCE, concordance
        from .page_rapports import remplir

        annee = int(self.annee_fa.get())
        config = _config(self.racine)

        def executer():
            try:
                paies = self._miennes(lire_sage(config, lambda b: pa.paies_sage(b, date(annee, 1, 1),
                                                                                date(annee, 12, 31))))
                registre = pt.Registre(self.racine)
                lignes = concordance(paies, registre, annee)
                self.feuillets = fe.calculer(paies, annee, registre.employes)
                self.after(0, lambda: fin(lignes))
            except BaseException as exc:
                texte = str(exc) or type(exc).__name__
                self.after(0, lambda: self.etat_fa.configure(text="✘ " + texte, foreground=ROUGE))

        def fin(lignes):
            remplir(self.tableau_fa, ENTETES_CONCORDANCE, lignes, {"Employé": 200, "Contrôle": 220},
                    lambda i: () if lignes[i][-1] == "✔" else ("probleme",), decroissant=False)
            self.tableau_fa.tag_configure("probleme", foreground=ROUGE)
            self.titre_fa.configure(text=t("Concordance de fin d'année {a}", a=annee))
            problemes = sum(1 for l in lignes if l[-1] != "✔")
            self.etat_fa.configure(text=t("{n} employé(s), {p} à vérifier.", n=len(lignes), p=problemes),
                                   foreground=ROUGE if problemes else VERT_FONCE)

        self.etat_fa.configure(text=t("Lecture des paies dans Sage…"), foreground=TEXTE_DOUX)
        threading.Thread(target=executer, daemon=True).start()

    def _miennes(self, paies: list[pa.PaieSage]) -> list[pa.PaieSage]:
        """Login limité : seulement les paies de l'employé relié à son compte."""
        if not self.limite:
            return paies
        employes = pt.Registre(self.racine).employes
        return [p for p in paies if self.moi is not None and (e := pa.employe_de(p, employes)) and e.id == self.moi.id]

    # ------------------------------------------------------------------ T4 et Relevé 1
    def _feuillets_choisis(self) -> list:
        if not self.feuillets:
            messagebox.showinfo(self.title(), t("Cliquez d'abord sur « Calculer »."), parent=self)
            return []
        choix = sorted(self.tableau_fa.selection(), key=self.tableau_fa.index)
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez un ou plusieurs employés dans la liste."), parent=self)
            return []
        return [self.feuillets[self.tableau_fa.index(i)] for i in choix]

    def _employeur(self):
        from .entreprise import lire

        return lire(self.racine)

    def imprimer_feuillets(self, feuillets=None) -> None:
        from . import feuillets as fe

        if not autorise(self):
            return
        feuillets = feuillets or self._feuillets_choisis()
        if not feuillets:
            return
        dossier = Path(tempfile.gettempdir()) / "MVOGMBI_Sync_impression"
        dossier.mkdir(exist_ok=True)
        chemin = dossier / f"t4_rl1_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        # formulaires officiels de l'ARC et de Revenu Québec remplis (demande du propriétaire du 2026-11-01)
        chemin.write_bytes(fe.pdf_officiels(feuillets, self._employeur(), fe.numero_employeur(self.racine),
                                            racine=self.racine, config_toml=_config(self.racine)))
        os.startfile(chemin)

    def imprimer_tous_feuillets(self) -> None:
        if not self.feuillets:
            messagebox.showinfo(self.title(), t("Cliquez d'abord sur « Calculer »."), parent=self)
            return
        self.imprimer_feuillets(self.feuillets)

    def feuillets_pdf(self) -> None:
        from . import feuillets as fe

        if not autorise(self):
            return
        feuillets = self._feuillets_choisis()
        if not feuillets:
            return
        nom = feuillets[0].employe if len(feuillets) == 1 else t("{n} employés", n=len(feuillets))
        chemin = filedialog.asksaveasfilename(parent=self, defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                              initialfile=f"T4 RL-1 {feuillets[0].annee} {nom}.pdf")
        if not chemin:
            return
        try:
            Path(chemin).write_bytes(fe.pdf_officiels(feuillets, self._employeur(), fe.numero_employeur(self.racine),
                                                      racine=self.racine, config_toml=_config(self.racine)))
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        os.startfile(chemin)

    def numero_employeur(self) -> None:
        from tkinter import simpledialog

        from . import feuillets as fe

        numero = simpledialog.askstring(self.title(), t("N° de compte de l'employeur (case 54 du T4) :"),
                                        initialvalue=fe.numero_employeur(self.racine), parent=self)
        if numero is not None:
            fe.definir_numero_employeur(self.racine, numero)

    def envoyer_feuillets(self) -> None:
        """Chaque employé reçoit SON T4 et SON RL-1 (PDF) à son adresse, sans copie ; journal des envois."""
        from . import feuillets as fe
        from .design import action_permise

        if not action_permise(self, "Envoyer les bulletins par courriel") or not autorise(self):
            return
        choisis = self._feuillets_choisis()
        if not choisis:
            return
        envois = [f for f in choisis if f.courriel]
        sans_adresse = [f.employe for f in choisis if not f.courriel]
        if not envois:
            messagebox.showinfo(self.title(), t("Aucun employé choisi n'a de courriel : ajoutez-le dans « Employés et NIP » "
                                                "(« Courriel… »).") + "\n\n" + ", ".join(sans_adresse), parent=self)
            return
        deja = fe.envoyes(self.racine)
        texte = "\n".join(f"• {f.employe} → {f.courriel}" for f in envois)
        if sans_adresse:
            texte += "\n\n" + t("Sans courriel (non envoyés) : {n}", n=", ".join(sans_adresse))
        renvois = [f.employe for f in envois if f.cle in deja]
        if renvois:
            texte += "\n\n" + t("⚠ Déjà envoyés une fois : {n}", n=", ".join(renvois))
        if not messagebox.askyesno(self.title(), t("Envoyer à chaque employé son T4 et son Relevé 1 (PDF) ?") + "\n\n"
                                   + texte, parent=self):
            return
        config, employeur, numero = _config(self.racine), self._employeur(), fe.numero_employeur(self.racine)
        self.bouton_feuillets._commande = None  # un seul envoi à la fois
        self.etat_fa.configure(text=t("Envoi des T4 et Relevés 1…"), foreground=TEXTE_DOUX)

        def travail():
            resultats = []
            for f in envois:
                try:
                    contenu = fe.pdf_officiels([f], employeur, numero, racine=self.racine, config_toml=config)
                    fe.envoyer(config, f, contenu)
                    fe.noter_envoi(self.racine, f)
                    resultats.append(f"✔ {f.employe} → {f.courriel}")
                except Exception as exc:
                    resultats.append(f"✘ {f.employe} : {exc}")
            self.after(0, lambda: fin(resultats))

        def fin(resultats):
            self.bouton_feuillets._commande = self.envoyer_feuillets
            echecs = sum(1 for r in resultats if r.startswith("✘"))
            self.etat_fa.configure(text=t("{n} envoi(s), {e} échec(s).", n=len(resultats) - echecs, e=echecs),
                                   foreground=ROUGE if echecs else VERT_FONCE)
            messagebox.showinfo(self.title(), "\n".join(resultats), parent=self)

        threading.Thread(target=travail, daemon=True).start()

    def lire_paies(self) -> None:
        from .__main__ import lire_sage
        from .page_rapports import remplir

        try:
            du, au = date.fromisoformat(self.du.get().strip()), date.fromisoformat(self.au.get().strip())
        except ValueError:
            self.etat_paies.configure(text="✘ " + t("Date au format AAAA-MM-JJ."), foreground=ROUGE)
            return
        config = _config(self.racine)
        self.etat_paies.configure(text=t("Lecture des paies dans Sage…"), foreground=TEXTE_DOUX)

        def travail():
            debut_annee = date(du.year, 1, 1)  # le relevé montre le total de l'année
            return self._miennes(lire_sage(config, lambda b: pa.paies_sage(b, debut_annee, au)))

        def fin(paies):
            self.paies_annee = paies
            self.paies = [p for p in paies if p.jour >= du]
            remplir(self.tableau_paies, pa.ENTETES_PAIES, pa.lignes_paies(self.paies), {"Employé": 240})
            voulus = getattr(self, "_choisir_apres_lecture", set())
            if voulus:  # paies que l'application vient de traiter : déjà choisies pour l'impression
                self.tableau_paies.selection_set([str(i) for i, p in enumerate(self.paies) if p.employe in voulus])
                self._choisir_apres_lecture = set()
                if getattr(self, "_envoyer_apres_lecture", False) and self.tableau_paies.selection():
                    self._envoyer_apres_lecture = False
                    self.after(300, self.envoyer_bulletins)  # chaque employé reçoit son bulletin (confirmation)
            self.titre_paies.configure(text=t("Paies dans Sage du {d} au {a}", d=du.isoformat(), a=au.isoformat()))
            ecarts = sum(1 for p in self.paies if abs(p.ecart) > pa.CENT)
            self.etat_paies.configure(
                text=t("{n} paie(s) ; double-clic : bulletin de paie ; plusieurs : Ctrl ou Maj + clic.", n=len(self.paies))
                + (" " + t("⚠ {n} écriture(s) de paie non entièrement expliquée(s) (colonne Contrôle).", n=ecarts)
                   if ecarts else ""), foreground=ROUGE if ecarts else VERT_FONCE)

        def executer():
            try:
                resultat = travail()
                self.after(0, lambda: fin(resultat))
            except BaseException as exc:
                texte = str(exc) or type(exc).__name__
                self.after(0, lambda: self.etat_paies.configure(text="✘ " + texte, foreground=ROUGE))

        threading.Thread(target=executer, daemon=True).start()

    def _fiche(self, registre: pt.Registre, ref: date, paie: pa.PaieSage, employe) -> str:
        """Fiche de paie d'une paie : heures de la feuille de temps de la période, montants de Sage."""
        from .calendrier_paie import Calendrier

        feuille = pa.feuille_de_la_paie(registre, employe, paie.jour, ref) if employe else None
        prevue = next((p for p in Calendrier(self.racine).paies(paie.jour.year) if p.jour == paie.jour), None)
        if employe and prevue:  # calendrier de paie : la période payée ce jour-là
            feuille = pt.feuille(registre, employe, prevue.debut)
            feuille = feuille if feuille.total else None
        extras = (pa.ZERO, pa.ZERO)
        if feuille is not None:
            extras = pa.extras_periode(self.racine, [feuille]).get(employe.id, extras)
        periode = f"{prevue.debut:%Y-%m-%d} à {prevue.fin:%Y-%m-%d}" if prevue else ""
        return pa.fiche_de_paie(paie, pa.cumul_annee(self.paies_annee, paie), feuille, extras, periode)

    def _releves(self) -> list[str]:
        """Fiches de paie des paies choisies (plusieurs : Ctrl ou Maj + clic), dans l'ordre de la liste."""
        from .fenetre_pointage import reference

        choix = sorted(self.tableau_paies.selection(), key=self.tableau_paies.index)
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une ou plusieurs paies dans la liste."), parent=self)
            return []
        registre, ref = pt.Registre(self.racine), reference(self.racine)
        releves = []
        for iid in choix:
            paie = self.paies[int(iid)]
            releves.append(self._fiche(registre, ref, paie, pa.employe_de(paie, registre.employes)))
        return releves

    def _page(self, pages: list[str], imprimer: bool) -> str:
        """Une page HTML, une fiche par feuille (saut de page entre deux)."""
        tete = pages[0].split("<body>", 1)[0]
        corps = [p.split("<body>", 1)[1].rsplit("</body>", 1)[0] for p in pages]
        saut = "<div style='page-break-after: always'></div>"
        script = "<script>window.addEventListener('load', () => window.print());</script>" if imprimer else ""
        return tete + "<body>" + saut.join(corps) + script + "</body></html>"

    def imprimer_releve(self) -> None:
        if not autorise(self):
            return
        releves = self._releves()
        if not releves:
            return
        dossier = Path(tempfile.gettempdir()) / "MVOGMBI_Sync_impression"
        dossier.mkdir(exist_ok=True)
        chemin = dossier / f"bulletins_paie_{datetime.now():%Y%m%d_%H%M%S}.html"
        chemin.write_text(self._page(releves, True), encoding="utf-8")
        os.startfile(chemin)

    def envoyer_bulletins(self) -> None:
        """Chaque employé reçoit SON bulletin (PDF) à son adresse, sans copie (demande du propriétaire du 2026-10-29) ;
        un bulletin déjà envoyé n'est renvoyé qu'après confirmation ; journal donnees/journal_bulletins_envoyes.csv."""
        from .design import action_permise

        if not action_permise(self, "Envoyer les bulletins par courriel"):
            return
        if not autorise(self):
            return
        choix = sorted(self.tableau_paies.selection(), key=self.tableau_paies.index)
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une ou plusieurs paies dans la liste."), parent=self)
            return
        registre = pt.Registre(self.racine)
        paies = [self.paies[int(i)] for i in choix]
        envois, sans_adresse = [], []
        for paie in paies:
            employe = pa.employe_de(paie, registre.employes)
            if employe and employe.courriel:
                envois.append((paie, employe))
            else:
                sans_adresse.append(paie.employe)
        deja = pa.bulletins_envoyes(self.racine)
        renvois = [p.employe for p, _e in envois if pa.cle_bulletin(p) in deja]
        if not envois:
            messagebox.showinfo(self.title(), t("Aucun employé choisi n'a de courriel : ajoutez-le dans « Employés et NIP » "
                                                "(« Courriel… »).") + "\n\n" + ", ".join(sans_adresse), parent=self)
            return
        texte = "\n".join(f"• {p.employe} → {e.courriel}" for p, e in envois)
        if sans_adresse:
            texte += "\n\n" + t("Sans courriel (non envoyés) : {n}", n=", ".join(sans_adresse))
        if renvois:
            texte += "\n\n" + t("⚠ Déjà envoyés une fois : {n}", n=", ".join(renvois))
        if not messagebox.askyesno(self.title(), t("Envoyer à chaque employé son bulletin de paie (PDF) ?") + "\n\n"
                                   + texte, parent=self):
            return
        config = _config(self.racine)
        ref = __import__("mvogmbi_sync.fenetre_pointage", fromlist=["reference"]).reference(self.racine)
        bulletins = [(paie, employe, self._fiche(registre, ref, paie, employe)) for paie, employe in envois]
        self.bouton_envoi._commande = None  # un seul envoi à la fois
        self.etat_paies.configure(text=t("Envoi des bulletins de paie…"), foreground=TEXTE_DOUX)

        def travail():
            resultats = []
            for paie, employe, fiche in bulletins:
                try:
                    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
                        chemin = Path(dossier) / "bulletin.pdf"
                        pdf_depuis_html(fiche, chemin)
                        contenu = chemin.read_bytes()
                    pa.envoyer_bulletin(config, employe.courriel, employe.nom, paie, contenu)
                    pa.noter_envoi(self.racine, paie, employe.courriel)
                    resultats.append(f"✔ {paie.employe} → {employe.courriel}")
                except Exception as exc:
                    resultats.append(f"✘ {paie.employe} : {exc}")
            self.after(0, lambda: self._fin_envoi(resultats))

        threading.Thread(target=travail, daemon=True).start()

    def _fin_envoi(self, resultats: list[str]) -> None:
        self.bouton_envoi._commande = self.envoyer_bulletins
        if not self.winfo_exists():
            return
        echecs = sum(1 for r in resultats if r.startswith("✘"))
        self.etat_paies.configure(text=t("{n} bulletin(s) envoyé(s), {e} échec(s).", n=len(resultats) - echecs,
                                         e=echecs), foreground=ROUGE if echecs else VERT_FONCE)
        messagebox.showinfo(self.title(), "\n".join(resultats), parent=self)

    def imprimer_tout(self) -> None:
        self.tableau_paies.selection_set(self.tableau_paies.get_children())
        self.imprimer_releve()

    def releve_pdf(self) -> None:
        if not autorise(self):
            return
        releves = self._releves()
        if not releves:
            return
        nom = self.paies[int(self.tableau_paies.selection()[0])].employe if len(releves) == 1 else t(
            "{n} employés", n=len(releves))
        chemin = filedialog.asksaveasfilename(parent=self, defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                              initialfile=f"{t('Bulletins de paie')} {nom} {date.today().isoformat()}.pdf")
        if not chemin:
            return
        try:
            pdf_depuis_html(self._page(releves, False), Path(chemin))
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        os.startfile(chemin)


def paie_dans_le_futur(fin_periode: date, date_cheques: date, aujourdhui: date) -> str:
    """Raison de refuser une paie (règle du propriétaire du 2026-11-01 : on ne traite pas une paie dans le futur),
    sinon « ». La période doit être terminée et les chèques datés d'aujourd'hui au plus tard."""
    if fin_periode >= aujourdhui:
        return "La période de paie n'est pas terminée : une paie ne se traite pas dans le futur."
    if date_cheques > aujourdhui:
        return "Les chèques de paie ne peuvent pas être datés dans le futur."
    return ""


class FenetreCalendrier(FenetreOutil):
    """Calendrier de paie : la date de la première paie de l'année, le reste se calcule (calendrier_paie.py)."""

    def __init__(self, parent, racine: Path):
        from .calendrier_paie import Calendrier
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.title(t("Calendrier de paie"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.transient(parent)
        self.geometry("820x640")
        self.calendrier = Calendrier(self.racine)
        barre = Rangee(self)
        barre.pack(fill="x")
        annee = date.today().year
        g = barre.ajouter(barre.groupe(), 10)
        tk.Label(g, text=t("Année"), background=CARTE).pack(side="left", padx=(0, 4))
        self.annee = tk.StringVar(value=str(annee))
        choix = ttk.Combobox(g, textvariable=self.annee, values=[str(annee + i) for i in range(-1, 5)], state="readonly",
                             width=6)
        choix.pack(side="left")
        choix.bind("<<ComboboxSelected>>", lambda _e: self.afficher())
        # première paie et délai : « Administration > Sage 50 », carte « Paie » (demande du propriétaire du 2026-11-01)
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left",
                             wraplength=780)
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=20)
        barre.ajouter(bouton_exporter(barre, self.tableau, lambda: t("Calendrier de paie {a}", a=self.annee.get())))
        self.tableau.tag_configure("passee", foreground="#9aa79e")
        self.tableau.tag_configure("prochaine", background="#e3f1e7")
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        annee = int(self.annee.get())
        premiere = self.calendrier.premiere(annee)
        paies = self.calendrier.paies(annee)
        aujourdhui = date.today()
        prochaine = self.calendrier.prochaine(aujourdhui)
        lignes = [[p.numero, p.jour.isoformat(), p.debut.isoformat(), p.fin.isoformat(),
                   t("Payée") if p.jour < aujourdhui else t("À venir")] for p in paies]

        def couleur(i):
            p = paies[i]
            return ("prochaine",) if prochaine and p.jour == prochaine.jour else ("passee",) if p.jour < aujourdhui else ()

        remplir(self.tableau, ["N°", "Date de paie", "Période du", "au", "État"],
                [[str(x) for x in l] for l in lignes], {"N°": 60}, couleur, decroissant=False)
        if not premiere:
            texte = t("Renseignez la date de la première paie de l'année dans « Administration > Sage 50 », carte "
                      "« Paie » : les paies suivantes (tous les 14 jours) et leurs périodes se calculent.")
        else:
            texte = t("{n} paies en {a}.", n=len(paies), a=annee)
            if not self.calendrier.saisie(annee):
                texte += " " + t("Suite de l'année précédente : modifiable dans « Administration > Sage 50 ».")
        self.etat.configure(text=texte, foreground=TEXTE_DOUX)

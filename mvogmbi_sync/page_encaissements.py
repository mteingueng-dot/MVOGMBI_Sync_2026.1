"""Page « Encaissements » : dépôts Clover à encaisser sur les factures journalières, et leur état dans Sage."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .design import CARTE, TEXTE_DOUX, Bouton
from .encaissements import A_SAISIR, A_VENIR, APPLIQUE, ECART, SANS_FACTURE
from .langues import courante, jours_semaine, t

COULEURS = {APPLIQUE: "#e3f4e8", A_SAISIR: "#fff4d6", ECART: "#fde2e4", SANS_FACTURE: "#eef1ef", A_VENIR: "#ffffff"}


def argent(montant: Decimal | None) -> str:
    if montant is None:
        return ""
    texte = f"{montant:,.2f}"
    return f"${texte}" if courante() == "en" else texte.replace(",", " ").replace(".", ",") + " $"


class PageEncaissements(ttk.Frame):
    def __init__(self, parent, racine: Path, titre: str, chemin_config: Path):
        super().__init__(parent, padding=10)
        self.racine, self.titre, self.chemin_config = racine, titre, chemin_config
        self.depots = []

        barre = ttk.Frame(self)
        barre.pack(fill="x")
        hier = date.today() - timedelta(days=1)
        ttk.Label(barre, text=t("Ventes du")).pack(side="left")
        self.debut = tk.StringVar(value=(hier - timedelta(days=30)).isoformat())
        ttk.Entry(barre, textvariable=self.debut, width=12).pack(side="left", padx=4)
        ttk.Label(barre, text=t("au")).pack(side="left")
        self.fin = tk.StringVar(value=hier.isoformat())
        ttk.Entry(barre, textvariable=self.fin, width=12).pack(side="left", padx=4)
        Bouton(barre, "⟳  " + t("Calculer les dépôts"), self.calculer).pack(side="left", padx=8)
        Bouton(barre, "📗  Excel", self.exporter, "secondaire").pack(side="right")
        Bouton(barre, "🤖  " + t("Encaisser dans Sage"), self.encaisser, "accent").pack(side="right", padx=8)
        self.resume = ttk.Label(self, text=t("Cliquez sur « Calculer les dépôts » : lots de cartes Clover et état dans Sage."),
                                foreground=TEXTE_DOUX, padding=(0, 8))
        self.resume.pack(fill="x")

        cadre = ttk.Frame(self)
        cadre.pack(fill="both", expand=True)
        colonnes = (("montant", t("Montant"), 120), ("du", t("Montant dû (Sage)"), 140), ("etat", t("État"), 230))
        self.tableau = ttk.Treeview(cadre, columns=[c[0] for c in colonnes], show="tree headings", height=12,
                                    selectmode="browse")
        self.tableau.heading("#0", text=t("Date du dépôt / facture"))
        self.tableau.column("#0", width=260)
        for cle, titre_col, largeur in colonnes:
            self.tableau.heading(cle, text=titre_col)
            self.tableau.column(cle, width=largeur, anchor="e" if cle != "etat" else "w")
        for etat, couleur in COULEURS.items():
            self.tableau.tag_configure(etat, background=couleur)
        self.tableau.tag_configure("depot", font=("Segoe UI Semibold", 10))
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defilement.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        defilement.pack(side="right", fill="y")
        self.tableau.bind("<<TreeviewSelect>>", lambda _e: self.afficher_saisie())

        bas = tk.Frame(self, background=CARTE, highlightthickness=1, highlightbackground="#e2e8e4")
        bas.pack(fill="x", pady=(10, 0))
        entete = tk.Frame(bas, background=CARTE)
        entete.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(entete, text=t("Saisie dans Sage (Encaissements)"), font=("Segoe UI Semibold", 11),
                 background=CARTE).pack(side="left")
        Bouton(entete, "📋  " + t("Copier"), self.copier, "secondaire", fond=CARTE, petit=True).pack(side="right")
        self.saisie = tk.Text(bas, height=8, wrap="word", font=("Cascadia Mono", 9), relief="flat", background=CARTE,
                              borderwidth=0, padx=14, pady=8)
        self.saisie.pack(fill="x")
        self.saisie.insert("end", t("Sélectionnez un dépôt dans le tableau."))
        self.saisie.configure(state="disabled")

    # ---------------------------------------------------------------- calcul
    def _config(self) -> dict:
        import tomllib
        return tomllib.loads(self.chemin_config.read_text(encoding="utf-8")) if self.chemin_config.exists() else {}

    def compte_depot(self) -> str:
        return str(self._config().get("encaissements", {}).get("compte_depot", "1055"))

    def calculer(self) -> None:
        try:
            debut, fin = date.fromisoformat(self.debut.get().strip()), date.fromisoformat(self.fin.get().strip())
            assert debut <= fin
        except (ValueError, AssertionError):
            messagebox.showerror(self.titre, t("Vérifiez les dates (AAAA-MM-JJ)."))
            return
        self.resume.configure(text=t("Calcul en cours : lots de cartes Clover, puis lecture de Sage…"))

        def travail():
            try:
                from .__main__ import charger_config, lire_sage
                from .api_clover import ClientClover
                from .encaissements import (etat_factures_sage, evaluer, factures_fin_de_semaine, lots_par_jour,
                                            noms_factures_sage, numero_compte_sage, regrouper)
                from .facture import CLIENT

                config = self._config()
                depots = regrouper(lots_par_jour(ClientClover(charger_config(self.chemin_config)), debut, fin))
                compte = numero_compte_sage(self.compte_depot())

                def lecture(base):
                    factures_fin_de_semaine(depots, noms_factures_sage(base, CLIENT))
                    return etat_factures_sage(base, CLIENT, compte, [l.facture for d in depots for l in d.lignes])

                etat = lire_sage(config, lecture, config.get("sage_import", {}).get("fichier_entreprise")) \
                    if depots else {}
                evaluer(depots, etat, date.today())
                self.after(0, lambda: self.afficher(depots))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self.resume.configure(text="✘ " + message))

        threading.Thread(target=travail, daemon=True).start()

    def afficher(self, depots) -> None:
        self.depots = depots
        self.tableau.delete(*self.tableau.get_children())
        jours = jours_semaine()
        for i, d in enumerate(depots):
            parent = self.tableau.insert("", "end", iid=f"d{i}", text=f"{d.date.isoformat()} ({jours[d.date.weekday()]})",
                                         values=(argent(d.montant), "", t(d.etat)), tags=(d.etat, "depot"),
                                         open=d.etat != APPLIQUE)
            for j, l in enumerate(d.lignes):
                self.tableau.insert(parent, "end", iid=f"d{i}l{j}", text=f"   {l.facture}",
                                    values=(argent(l.montant), argent(l.montant_du), t(l.etat)), tags=(l.etat,))
        a_saisir = [d for d in depots if d.etat in (A_SAISIR, ECART)]
        self.resume.configure(text=t("{n} dépôt(s), {total} au total — {a} à saisir dans Sage, {ok} déjà appliqué(s).",
                                     n=len(depots), total=argent(sum((d.montant for d in depots), Decimal(0))),
                                     a=len(a_saisir), ok=sum(1 for d in depots if d.etat == APPLIQUE)))
        if a_saisir:
            index = depots.index(a_saisir[0])
            self.tableau.selection_set(f"d{index}")
            self.tableau.see(f"d{index}")

    def encaisser(self) -> None:
        """Le robot saisit dans Sage chaque dépôt « À saisir » (Sage ouvert, fenêtre Encaissements affichée)."""
        a_saisir = [d for d in self.depots if d.etat == A_SAISIR]
        if not a_saisir:
            messagebox.showinfo(self.titre, t("Aucun dépôt « À saisir dans Sage » : calculez d'abord les dépôts."))
            return
        import ctypes
        if not ctypes.windll.user32.FindWindowW("#32770", "Encaissements"):
            messagebox.showwarning(self.titre, t("Ouvrez Sage sur le fichier d'entreprise, puis la fenêtre "
                                                 "Clients & Ventes > Encaissements, et recommencez."))
            return
        total = argent(sum((d.montant for d in a_saisir), Decimal(0)))
        if not messagebox.askyesno(self.titre, t("Encaisser {n} dépôt(s) ({total}) dans Sage ? N'utilisez pas Sage "
                                                 "pendant la saisie.", n=len(a_saisir), total=total)):
            return
        self.resume.configure(text=t("Saisie des encaissements dans Sage en cours…"))

        def travail():
            from .facture import CLIENT
            from .robot_encaissements import appliquer

            notes = []
            try:
                config = self._config()
                mode = str(config.get("encaissements", {}).get("mode", "Comptant"))
                resultats = appliquer(config, a_saisir, CLIENT, self.compte_depot(), mode, journal=notes.append)
                bilan = t("{ok} dépôt(s) encaissé(s) sur {n}.", ok=sum(r.traite for r in resultats), n=len(a_saisir))
            except Exception as exc:
                bilan = f"✘ {exc}"
            message = bilan + ("\n\n" + "\n".join(notes) if notes else "")
            self.after(0, lambda: (messagebox.showinfo(self.titre, message), self.calculer()))

        threading.Thread(target=travail, daemon=True).start()

    def depot_choisi(self):
        choix = self.tableau.selection()
        if not choix:
            return None
        return self.depots[int(choix[0][1:].split("l")[0])]

    def texte_saisie(self, d) -> str:
        from .facture import CLIENT

        lignes = [t("Encaissements > Payé par : Comptant ; Reçu de : {client}", client=CLIENT),
                  t("Dépôt : {compte} (compte Desjardins)", compte=self.compte_depot()),
                  t("Date : {date}", date=d.date.isoformat()), "",
                  t("Montant reçu, facture par facture :")]
        for l in d.lignes:
            lignes.append(f"   {l.facture:<20} {argent(l.montant):>14}   ({t(l.etat)})")
        lignes += ["", t("Total du dépôt : {total}", total=argent(d.montant)),
                   t("Puis « Traiter ». L'état passera à « Appliqué » au prochain calcul.")]
        return "\n".join(lignes)

    def afficher_saisie(self) -> None:
        d = self.depot_choisi()
        if not d:
            return
        self.saisie.configure(state="normal")
        self.saisie.delete("1.0", "end")
        self.saisie.insert("end", self.texte_saisie(d))
        self.saisie.configure(state="disabled")

    def copier(self) -> None:
        d = self.depot_choisi()
        if d:
            self.clipboard_clear()
            self.clipboard_append(self.texte_saisie(d))

    def exporter(self) -> None:
        if not self.depots:
            messagebox.showinfo(self.titre, t("Calculez d'abord les dépôts."))
            return
        chemin = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="encaissements.xlsx",
                                              filetypes=[("Excel", "*.xlsx")])
        if not chemin:
            return
        from .encaissements import ecrire_excel

        try:
            ecrire_excel(self.depots, Path(chemin), self.compte_depot())
        except PermissionError:
            messagebox.showerror(self.titre, t("Fichier ouvert dans Excel : fermez-le puis recommencez."))
            return
        import os
        os.startfile(chemin)

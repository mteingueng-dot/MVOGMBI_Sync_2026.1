"""Fenêtre « Inventaire Clover et Sage » : export en un fichier, puis saisie de l'inventaire compté dans les deux."""

from __future__ import annotations

import os
import threading
import tkinter as tk
import tomllib
from pathlib import Path
from tkinter import filedialog, messagebox

from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton
from .langues import t


class FenetreInventaire(FenetreOutil):
    def __init__(self, parent, racine: Path):
        super().__init__(parent)
        self.racine = Path(racine)
        self.en_cours = False
        self.title(t("Inventaire Clover et Sage"))
        self.configure(background=CARTE, padx=18, pady=14)
        self.transient(parent)
        self.resizable(False, False)
        texte = t("1. Exportez l'inventaire : un fichier Excel avec, pour chaque article, code et description Clover et "
                  "Sage, quantité Clover, quantité Sage et l'écart.\n2. Comptez, puis inscrivez les quantités dans la "
                  "colonne jaune « Quantité comptée » (laissez vide les articles non comptés).\n3. « Saisir "
                  "l'inventaire compté » : le stock Clover et le stock Sage deviennent la quantité comptée ; un "
                  "rapport donne le coût de l'ajustement.")
        tk.Label(self, text=texte, background=CARTE, justify="left", wraplength=560, anchor="w").pack(fill="x")
        boutons = tk.Frame(self, background=CARTE)
        boutons.pack(fill="x", pady=12)
        Bouton(boutons, "⬇  " + t("Exporter l'inventaire"), self.exporter, fond=CARTE).pack(side="left")
        Bouton(boutons, "📦  " + t("Saisir l'inventaire compté…"), self.saisir, "accent", fond=CARTE).pack(
            side="left", padx=8)
        Bouton(boutons, "📂  " + t("Dossier"), self.ouvrir_dossier, "secondaire", fond=CARTE).pack(side="left")
        self.etat = tk.Label(self, text="", background=CARTE, foreground=TEXTE_DOUX, justify="left", wraplength=560,
                             anchor="w")
        self.etat.pack(fill="x")

    @property
    def dossier(self) -> Path:
        return self.racine / "sortie" / "inventaire"

    def _config(self) -> dict:
        return tomllib.loads((self.racine / "config.toml").read_text(encoding="utf-8"))

    def _lancer(self, message: str, travail) -> None:
        if self.en_cours:
            return
        self.en_cours = True
        self.etat.configure(text=message, foreground=TEXTE_DOUX)

        def fil():
            try:
                resultat, erreur = travail(), ""
            except Exception as exc:
                resultat, erreur = None, str(exc)
            self.after(0, lambda: self._fin(resultat, erreur))

        threading.Thread(target=fil, daemon=True).start()

    def _fin(self, resultat, erreur: str) -> None:
        self.en_cours = False
        if not self.winfo_exists():
            return
        if erreur:
            self.etat.configure(text="✘ " + erreur, foreground=ROUGE)
            return
        texte, fichier = resultat
        self.etat.configure(text="✔ " + texte, foreground=VERT_FONCE)
        os.startfile(fichier)

    def exporter(self) -> None:
        from .export_tableau import autorise

        if not autorise(self):
            return
        from .inventaire import ecrire, lire, nom_fichier

        def travail():
            lignes = lire(self.racine, self._config())
            chemin = ecrire(lignes, self.dossier / nom_fichier("Inventaire"))
            ecarts = sum(1 for l in lignes if l.ecart)
            return t("{n} article(s), {e} écart(s) entre Clover et Sage : {f}", n=len(lignes), e=ecarts,
                     f=chemin.name), chemin

        self._lancer(t("Lecture des stocks Clover et Sage…"), travail)

    def saisir(self) -> None:
        from .inventaire import lire_fichier, saisir

        chemin = filedialog.askopenfilename(parent=self, title=t("Inventaire compté"), initialdir=self.dossier,
                                            filetypes=[("Excel", "*.xlsx")])
        if not chemin:
            return
        try:
            comptees = [l for l in lire_fichier(Path(chemin)) if l.comptee is not None]
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        if not comptees:
            messagebox.showinfo(self.title(), t("Aucune quantité dans la colonne « Quantité comptée »."), parent=self)
            return
        if not messagebox.askyesno(self.title(), t(
                "{n} article(s) compté(s).\n\nLe stock Clover et le stock Sage de ces articles deviendront la quantité "
                "comptée (ajustement d'inventaire dans Sage). L'application ouvre Sage elle-même s'il est fermé ; "
                "s'il est ouvert, ne touchez pas au clavier ni à la souris pendant la saisie.\n\nContinuer ?",
                n=len(comptees)), parent=self):
            return

        def travail():
            saisie, rapport = saisir(self.racine, self._config(), Path(chemin))
            return t("Clover : {c} stock(s), Sage : {s} ajustement(s). Rapport : {f}", c=len(saisie.clover),
                     s=len(saisie.sage), f=rapport.name), rapport

        self._lancer(t("Saisie de l'inventaire (Clover puis Sage)…"), travail)

    def ouvrir_dossier(self) -> None:
        self.dossier.mkdir(parents=True, exist_ok=True)
        os.startfile(self.dossier)

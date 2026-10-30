"""Fenêtre « Administration > Sauvegarde » (demande du propriétaire du 2026-10-29) : dossier des sauvegardes,
sauvegarde à la demande, liste des sauvegardes, restauration. Calculs dans sauvegarde.py."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import sauvegarde as sv
from .design import FenetreOutil, CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, Rangee
from .langues import t


def _taille(octets: int) -> str:
    return f"{octets / 1048576:.1f} Mo".replace(".", ",")


class FenetreSauvegarde(FenetreOutil):
    def __init__(self, parent, racine: Path):
        from .interface import lire_config
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine = Path(racine)
        self.config_toml = lire_config(self.racine / "config.toml")
        self.title(t("Sauvegarde des données"))
        self.configure(background=CARTE, padx=14, pady=10)
        self.geometry("980x600")
        tk.Label(self, text=t("Chaque nuit, le traitement automatique copie les données de l'application (correspondance, "
                              "pointages, feuilles de temps, registres, journaux) et la configuration dans une archive "
                              "vérifiée. Gardées : 14 jours, 8 semaines, 12 mois."),
                 background=CARTE, foreground=TEXTE_DOUX, anchor="w", justify="left", wraplength=940).pack(fill="x")
        ligne = Rangee(self)
        ligne.pack(fill="x", pady=(10, 0))
        groupe = ligne.ajouter(ligne.groupe(), 8)
        tk.Label(groupe, text=t("Dossier des sauvegardes"), background=CARTE).pack(side="left", padx=(0, 6))
        self.dossier = tk.StringVar(value=str(sv.dossier(self.racine, self.config_toml)))
        ttk.Entry(groupe, textvariable=self.dossier, width=62).pack(side="left")
        ligne.ajouter(Bouton(ligne, "📁  " + t("Choisir…"), self.choisir, "secondaire", fond=CARTE, petit=True), 6)
        ligne.ajouter(Bouton(ligne, "✔  " + t("Enregistrer le dossier"), self.enregistrer_dossier, "secondaire",
                             fond=CARTE, petit=True))
        barre = Rangee(self)
        barre.pack(fill="x", pady=(10, 0))
        self.bouton = Bouton(barre, "💾  " + t("Sauvegarder maintenant"), self.sauvegarder, fond=CARTE, petit=True)
        barre.ajouter(self.bouton, 8)
        barre.ajouter(Bouton(barre, "↩  " + t("Restaurer la sauvegarde choisie…"), self.restaurer, "danger",
                             fond=CARTE, petit=True), 8)
        barre.ajouter(Bouton(barre, "📂  " + t("Ouvrir le dossier"), self.ouvrir_dossier, "secondaire", fond=CARTE,
                             petit=True))
        self.etat = tk.Label(self, text="", background=CARTE, anchor="w", justify="left", wraplength=940)
        self.etat.pack(fill="x", pady=(8, 0))
        self.tableau = tableau_simple(self, hauteur=14)
        self.afficher()

    def afficher(self) -> None:
        from .page_rapports import remplir

        self.liste = sv.archives(Path(self.dossier.get()))
        remplir(self.tableau, ["Date", "Sauvegarde", "Taille"],
                [[datetime.fromtimestamp(a.stat().st_mtime).strftime("%Y-%m-%d %H:%M"), a.name, _taille(a.stat().st_size)]
                 for a in self.liste], {"Sauvegarde": 420}, decroissant=False)
        retard, e = sv.en_retard(self.racine), sv.derniere(self.racine)
        if retard:
            texte, couleur = "⚠ " + t(retard), ROUGE
        else:
            texte = t("✔ Dernière sauvegarde : {q} — {n} fichiers, {tl}.", q=e.quand[:16].replace("T", " "),
                      n=e.fichiers, tl=_taille(e.taille))
            couleur = VERT_FONCE
        if e.message:
            texte += "\n" + t(e.message)
            couleur = ROUGE if not e.ok or "même disque" in e.message else couleur
        if sv.meme_disque(self.racine, Path(self.dossier.get())) and "même disque" not in texte:
            texte += "\n⚠ " + t("Dossier sur le même disque que les données : choisissez un autre disque ou OneDrive.")
        self.etat.configure(text=texte, foreground=couleur)

    def choisir(self) -> None:
        choix = filedialog.askdirectory(parent=self, initialdir=self.dossier.get(),
                                        title=t("Dossier des sauvegardes"))
        if choix:
            self.dossier.set(str(Path(choix)))
            self.afficher()

    def enregistrer_dossier(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Changer le dossier des sauvegardes"):
            return
        from .interface import ecrire_config, lire_config

        chemin = self.racine / "config.toml"
        config = lire_config(chemin)
        config.setdefault("sauvegarde", {})["dossier"] = self.dossier.get().strip()
        ecrire_config(chemin, config)
        self.config_toml = config
        self.afficher()

    def sauvegarder(self) -> None:
        self.bouton._commande = None
        self.etat.configure(text=t("Sauvegarde en cours…"), foreground=TEXTE_DOUX)
        cible = Path(self.dossier.get())

        def travail():
            e = sv.sauvegarder(self.racine, self.config_toml, cible)
            self.after(0, lambda: self._fin(e))

        threading.Thread(target=travail, daemon=True).start()

    def _fin(self, e) -> None:
        self.bouton._commande = self.sauvegarder
        if self.winfo_exists():
            self.afficher()
            if not e.ok:
                messagebox.showerror(self.title(), t("Sauvegarde non faite : {m}", m=e.message), parent=self)

    def restaurer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Restaurer une sauvegarde"):
            return
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une sauvegarde dans la liste."), parent=self)
            return
        archive = self.liste[int(choix[0])]
        if not messagebox.askyesno(self.title(), t("Remettre les données telles qu'elles étaient dans « {a} » ?\n\n"
                                                   "L'état actuel est d'abord sauvegardé (dossier "
                                                   "« avant_restauration »). Fermez puis rouvrez l'application "
                                                   "ensuite.", a=archive.name), icon="warning", parent=self):
            return
        try:
            avant, n = sv.restaurer(self.racine, self.config_toml, archive)
        except Exception as exc:
            messagebox.showerror(self.title(), str(exc), parent=self)
            return
        messagebox.showinfo(self.title(), t("{n} fichiers restaurés. État d'avant gardé dans {a}. Fermez puis rouvrez "
                                            "l'application.", n=n, a=Path(avant.fichier).name), parent=self)

    def ouvrir_dossier(self) -> None:
        cible = Path(self.dossier.get())
        cible.mkdir(parents=True, exist_ok=True)
        os.startfile(cible)

"""Fenêtre de connexion au lancement (nom + mot de passe) ; au tout premier lancement, création du compte
administrateur. Aussi : changement de son propre mot de passe."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .design import (BORDURE, CARTE, FOND, ICONE, LOGO, ROUGE, TEXTE, TEXTE_DOUX, VERT, VERT_FONCE, Bouton,
                     styler)
from .langues import t
from .utilisateurs import ADMIN, ErreurUtilisateur, Registre, Utilisateur


def _champ(parent, ligne: int, libelle: str, variable: tk.StringVar, secret: bool = False) -> ttk.Entry:
    tk.Label(parent, text=libelle, font=("Segoe UI", 10), foreground=TEXTE, background=CARTE).grid(
        row=ligne, column=0, sticky="w", pady=(8, 2))
    champ = ttk.Entry(parent, textvariable=variable, show="•" if secret else "", width=32, font=("Segoe UI", 11))
    champ.grid(row=ligne + 1, column=0, sticky="we")
    return champ


class Connexion(tk.Tk):
    def __init__(self, racine: Path, titre: str):
        super().__init__()
        self.registre = Registre(racine)
        self.utilisateur: Utilisateur | None = None
        self.creation = not self.registre.existe()
        self.title(titre)
        self.configure(background=FOND)
        self.resizable(False, False)
        try:
            import sv_ttk
            sv_ttk.set_theme("light")
        except Exception:
            pass
        styler(ttk.Style(self))
        if ICONE.exists():
            self.iconbitmap(default=str(ICONE))

        carte = tk.Frame(self, background=CARTE, highlightthickness=1, highlightbackground=BORDURE, padx=34, pady=26)
        carte.pack(padx=30, pady=30)
        carte.columnconfigure(0, weight=1)
        self._logo = None
        try:
            from PIL import Image, ImageTk

            image = Image.open(LOGO)
            image.thumbnail((110, 110))
            self._logo = ImageTk.PhotoImage(image)
            tk.Label(carte, image=self._logo, background=CARTE).grid(row=0, column=0, pady=(0, 10))
        except Exception:
            pass
        tk.Label(carte, text=t("Créer le compte administrateur") if self.creation else t("Connexion"),
                 font=("Segoe UI Semibold", 15), foreground=VERT_FONCE, background=CARTE).grid(row=1, column=0)
        tk.Label(carte, text=t("Premier lancement : ce compte aura accès à toutes les pages et gérera les "
                               "utilisateurs.") if self.creation else t("Marché MVOG-MBI Sherbrooke"),
                 font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE, wraplength=300,
                 justify="center").grid(row=2, column=0, pady=(2, 6))

        self.nom, self.mdp, self.mdp2 = tk.StringVar(), tk.StringVar(), tk.StringVar()
        premier = _champ(carte, 3, t("Nom d'utilisateur"), self.nom)
        _champ(carte, 5, t("Mot de passe"), self.mdp, secret=True)
        if self.creation:
            _champ(carte, 7, t("Confirmer le mot de passe"), self.mdp2, secret=True)
        self.message = tk.Label(carte, text="", font=("Segoe UI", 9), foreground=ROUGE, background=CARTE,
                                wraplength=300, justify="left")
        self.message.grid(row=9, column=0, sticky="w", pady=(8, 0))
        Bouton(carte, t("Créer le compte et ouvrir") if self.creation else t("Se connecter"), self.valider,
               fond=CARTE, largeur=300).grid(row=10, column=0, pady=(10, 0))
        self.bind("<Return>", lambda _e: self.valider())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
        y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        premier.focus_set()

    def valider(self) -> None:
        nom, mdp = self.nom.get().strip(), self.mdp.get()
        if not nom or not mdp:
            self.message.configure(text=t("Entrez votre nom et votre mot de passe."))
            return
        if self.creation:
            if mdp != self.mdp2.get():
                self.message.configure(text=t("Les deux mots de passe sont différents."))
                return
            try:
                self.registre.ajouter(nom, ADMIN, mdp)
            except ErreurUtilisateur as exc:
                self.message.configure(text=t(str(exc)))
                return
            self.registre.enregistrer()
        self.utilisateur = self.registre.verifier(nom, mdp)
        if self.utilisateur is None:
            self.mdp.set("")
            self.message.configure(text=t("Nom ou mot de passe incorrect, ou compte désactivé."))
            return
        self.destroy()


def connecter(racine: Path, titre: str) -> Utilisateur | None:
    """Ouvre la fenêtre de connexion ; None si elle est fermée sans connexion."""
    fenetre = Connexion(racine, titre)
    fenetre.mainloop()
    return fenetre.utilisateur


def changer_mon_mot_de_passe(parent, racine: Path, utilisateur: Utilisateur, titre: str) -> None:
    """Petite fenêtre : mot de passe actuel, nouveau, confirmation."""
    fenetre = tk.Toplevel(parent)
    fenetre.title(titre)
    fenetre.configure(background=CARTE)
    fenetre.resizable(False, False)
    fenetre.transient(parent)
    cadre = tk.Frame(fenetre, background=CARTE, padx=26, pady=20)
    cadre.pack()
    tk.Label(cadre, text=t("Changer mon mot de passe"), font=("Segoe UI Semibold", 13), foreground=VERT_FONCE,
             background=CARTE).grid(row=0, column=0, sticky="w")
    actuel, nouveau, confirme = tk.StringVar(), tk.StringVar(), tk.StringVar()
    premier = _champ(cadre, 1, t("Mot de passe actuel"), actuel, secret=True)
    _champ(cadre, 3, t("Nouveau mot de passe"), nouveau, secret=True)
    _champ(cadre, 5, t("Confirmer le mot de passe"), confirme, secret=True)
    message = tk.Label(cadre, text="", font=("Segoe UI", 9), foreground=ROUGE, background=CARTE, wraplength=280,
                       justify="left")
    message.grid(row=7, column=0, sticky="w", pady=(8, 0))

    def valider() -> None:
        registre = Registre(racine)
        if registre.verifier(utilisateur.nom, actuel.get()) is None:
            message.configure(text=t("Le mot de passe actuel est incorrect."))
            return
        if nouveau.get() != confirme.get():
            message.configure(text=t("Les deux mots de passe sont différents."))
            return
        try:
            registre.changer_mot_de_passe(utilisateur.nom, nouveau.get())
        except ErreurUtilisateur as exc:
            message.configure(text=t(str(exc)))
            return
        registre.enregistrer()
        message.configure(text=t("Mot de passe changé."), foreground=VERT)
        fenetre.after(900, fenetre.destroy)

    Bouton(cadre, t("Enregistrer"), valider, fond=CARTE, largeur=280).grid(row=8, column=0, pady=(10, 0))
    fenetre.bind("<Return>", lambda _e: valider())
    fenetre.bind("<Escape>", lambda _e: fenetre.destroy())
    premier.focus_set()
    fenetre.grab_set()


class Verrou(tk.Toplevel):
    """Application verrouillée après une période d'inactivité (règle du propriétaire du 2026-10-27) : la fenêtre
    principale est cachée ; le mot de passe de la personne connectée la rouvre, ou l'on change d'utilisateur."""

    def __init__(self, application, racine: Path, utilisateur: Utilisateur, titre: str, deverrouiller, changer):
        super().__init__(application)
        self.racine, self.utilisateur = racine, utilisateur
        self.deverrouiller, self.changer = deverrouiller, changer
        self.title(titre)
        self.configure(background=FOND)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # reste verrouillée tant que le mot de passe manque
        carte = tk.Frame(self, background=CARTE, highlightthickness=1, highlightbackground=BORDURE, padx=34, pady=24)
        carte.pack(padx=30, pady=30)
        self._logo = None
        try:
            from PIL import Image, ImageTk

            image = Image.open(LOGO)
            image.thumbnail((90, 90))
            self._logo = ImageTk.PhotoImage(image)
            tk.Label(carte, image=self._logo, background=CARTE).grid(row=0, column=0, pady=(0, 8))
        except Exception:
            pass
        tk.Label(carte, text="🔒  " + t("Application verrouillée"), font=("Segoe UI Semibold", 15),
                 foreground=VERT_FONCE, background=CARTE).grid(row=1, column=0)
        tk.Label(carte, text=t("Verrouillée après {n} minute(s) sans activité. Session de {nom}.",
                               n=application.minutes_verrou, nom=utilisateur.nom),
                 font=("Segoe UI", 9), foreground=TEXTE_DOUX, background=CARTE, wraplength=300,
                 justify="center").grid(row=2, column=0, pady=(2, 6))
        self.mdp = tk.StringVar()
        champ = _champ(carte, 3, t("Mot de passe"), self.mdp, secret=True)
        self.message = tk.Label(carte, text="", font=("Segoe UI", 9), foreground=ROUGE, background=CARTE)
        self.message.grid(row=5, column=0, sticky="w", pady=(8, 0))
        Bouton(carte, "🔓  " + t("Déverrouiller"), self.valider, fond=CARTE, largeur=300).grid(row=6, column=0,
                                                                                            pady=(10, 4))
        Bouton(carte, t("Changer d'utilisateur"), self.changer, "secondaire", fond=CARTE, largeur=300).grid(
            row=7, column=0)
        self.bind("<Return>", lambda _e: self.valider())
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
        y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.attributes("-topmost", True)
        champ.focus_force()

    def valider(self) -> None:
        if Registre(self.racine).verifier(self.utilisateur.nom, self.mdp.get()) is None:
            self.mdp.set("")
            self.message.configure(text=t("Mot de passe incorrect."))
            return
        self.deverrouiller()

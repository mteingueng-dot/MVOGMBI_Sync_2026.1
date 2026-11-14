"""Carte « ☁ Sauvegarde dans le cloud » de la fenêtre Administration > Sauvegarde des données (demande du propriétaire
du 2026-11-13). Calculs et services dans sauvegarde_cloud.py ; réglages dans [sauvegarde_cloud] de config.toml (seules
leurs lignes changent), secrets dans le coffre-fort de Windows (jamais réaffichés)."""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import coffre
from . import sauvegarde as sv
from . import sauvegarde_cloud as sc
from .design import CARTE, ROUGE, TEXTE_DOUX, VERT_FONCE, Bouton, Rangee
from .langues import t

AUCUN = "Aucun (sauvegarde sur ce poste seulement)"
CHAMPS_S3 = (("s3_adresse", "Adresse du service"), ("s3_region", "Région"), ("s3_compartiment", "Compartiment"),
             ("s3_prefixe", "Dossier (préfixe)"), ("s3_cle_acces", "Clé d'accès"))
CLES_ID = {"onedrive": "onedrive_client_id", "google_drive": "google_client_id", "dropbox": "dropbox_client_id"}


def _taille(octets: int) -> str:
    return f"{octets / 1048576:.1f} Mo".replace(".", ",")


class CarteCloud(tk.LabelFrame):
    def __init__(self, parent, racine: Path, config_toml: dict, relire_config):
        super().__init__(parent, text=" ☁ " + t("Sauvegarde dans le cloud") + " ", background=CARTE, padx=10, pady=6)
        self.racine, self.config_toml, self.relire_config = Path(racine), config_toml, relire_config
        r = sc.reglages(config_toml)
        noms = [AUCUN] + list(sc.SERVICES.values())
        tk.Label(self, text=t("Chaque sauvegarde est CHIFFRÉE sur ce poste (mot de passe de chiffrement) puis déposée sur "
                              "votre compte de stockage. Sans ce mot de passe, une sauvegarde du cloud ne se restaure "
                              "pas : notez-le en lieu sûr."), background=CARTE, foreground=TEXTE_DOUX, anchor="w",
                 justify="left", wraplength=920).pack(fill="x")
        ligne = Rangee(self)
        ligne.pack(fill="x", pady=(6, 0))
        groupe = ligne.ajouter(ligne.groupe(), 10)
        tk.Label(groupe, text=t("Service"), background=CARTE).pack(side="left", padx=(0, 6))
        self.service = tk.StringVar(value=sc.SERVICES.get(r["service"], AUCUN))
        liste = ttk.Combobox(groupe, textvariable=self.service, values=noms, state="readonly", width=40)
        liste.pack(side="left")
        liste.bind("<<ComboboxSelected>>", lambda _e: self.montrer_champs())
        self.actif = tk.BooleanVar(value=r["actif"])
        ligne.ajouter(tk.Checkbutton(ligne, text=t("Envoyer chaque nuit après la sauvegarde"), variable=self.actif,
                                     background=CARTE, activebackground=CARTE), 10)
        # champs des services avec connexion (OneDrive, Google Drive, Dropbox)
        self.cadre_oauth = tk.Frame(self, background=CARTE)
        self.client_id = tk.StringVar()
        tk.Label(self.cadre_oauth, text=t("Identifiant de l'application"), background=CARTE).grid(row=0, column=0,
                                                                                                  sticky="w")
        ttk.Entry(self.cadre_oauth, textvariable=self.client_id, width=52).grid(row=0, column=1, sticky="w", padx=6)
        self.libelle_secret = tk.Label(self.cadre_oauth, text=t("Secret de l'application (Google)"), background=CARTE)
        self.secret_google = tk.StringVar()
        self.champ_secret = ttk.Entry(self.cadre_oauth, textvariable=self.secret_google, show="•", width=52)
        # champs du stockage S3
        self.cadre_s3 = tk.Frame(self, background=CARTE)
        self.s3 = {cle: tk.StringVar(value=r[cle]) for cle, _ in CHAMPS_S3}
        for rang, (cle, libelle) in enumerate(CHAMPS_S3):
            tk.Label(self.cadre_s3, text=t(libelle), background=CARTE).grid(row=rang // 2, column=(rang % 2) * 2,
                                                                          sticky="w", pady=1)
            ttk.Entry(self.cadre_s3, textvariable=self.s3[cle], width=34).grid(row=rang // 2, column=(rang % 2) * 2 + 1,
                                                                             sticky="w", padx=6, pady=1)
        tk.Label(self.cadre_s3, text=t("Clé secrète"), background=CARTE).grid(row=2, column=2, sticky="w")
        self.s3_secret = tk.StringVar()
        ttk.Entry(self.cadre_s3, textvariable=self.s3_secret, show="•", width=34).grid(row=2, column=3, sticky="w",
                                                                                      padx=6)
        barre = Rangee(self)
        self.barre = barre
        barre.ajouter(Bouton(barre, "💾  " + t("Enregistrer"), self.enregistrer, "secondaire", fond=CARTE, petit=True), 6)
        self.bouton_connecter = Bouton(barre, "🔗  " + t("Se connecter au compte…"), self.connecter, fond=CARTE,
                                       petit=True)
        barre.ajouter(self.bouton_connecter, 6)
        barre.ajouter(Bouton(barre, "🔑  " + t("Mot de passe de chiffrement…"), self.mot_de_passe, "secondaire",
                             fond=CARTE, petit=True), 6)
        barre.ajouter(Bouton(barre, "☁  " + t("Envoyer la dernière sauvegarde"), self.envoyer_derniere, "secondaire",
                             fond=CARTE, petit=True), 6)
        barre.ajouter(Bouton(barre, "📋  " + t("Sauvegardes dans le cloud…"), self.liste_nuage, "secondaire",
                             fond=CARTE, petit=True))
        self.etat = tk.Label(self, text="", background=CARTE, anchor="w", justify="left", wraplength=920)
        self.montrer_champs()

    # ------------------------------------------------------------------ affichage
    def code(self) -> str:
        return next((c for c, n in sc.SERVICES.items() if n == self.service.get()), "")

    def montrer_champs(self) -> None:
        code = self.code()
        for cadre in (self.cadre_oauth, self.cadre_s3, self.barre, self.etat):
            cadre.pack_forget()
        if code in CLES_ID:
            self.client_id.set(sc.reglages(self.config_toml)[CLES_ID[code]])
            google = code == "google_drive"
            for w in (self.libelle_secret, self.champ_secret):
                w.grid_forget()
            if google:
                self.libelle_secret.grid(row=1, column=0, sticky="w", pady=(2, 0))
                self.champ_secret.grid(row=1, column=1, sticky="w", padx=6, pady=(2, 0))
            self.cadre_oauth.pack(fill="x", pady=(6, 0))
        elif code == "s3":
            self.cadre_s3.pack(fill="x", pady=(6, 0))
        self.barre.pack(fill="x", pady=(8, 0))
        self.etat.pack(fill="x", pady=(6, 0))
        self.afficher_etat()

    def afficher_etat(self, message: str = "", couleur: str | None = None) -> None:
        r, e = sc.reglages(self.config_toml), sc.derniere(self.racine)
        lignes = []
        if r["service"]:
            lignes.append(t("Compte : {c}", c=r["compte"] or t("pas encore connecté")) if r["service"] != "s3"
                          else t("Compartiment : {c}", c=r["s3_compartiment"] or "—"))
        lignes.append("✔ " + t("Mot de passe de chiffrement défini.") if sc.mot_defini()
                      else "⚠ " + t("Mot de passe de chiffrement à définir."))
        if e.quand:
            lignes.append((("✔ " if e.ok else "✖ ") + t("Dernier envoi : {q} — {f} {m}", q=e.quand[:16].replace("T", " "),
                                                        f=e.fichier, m=e.message)).strip())
        if message:
            lignes.append(message)
        bon = sc.mot_defini() and (e.ok or not e.quand)
        self.etat.configure(text="\n".join(lignes), foreground=couleur or (VERT_FONCE if bon else ROUGE))

    # ------------------------------------------------------------------ actions
    def enregistrer(self, silencieux: bool = False) -> bool:
        from .design import action_permise
        from .ecriture_config import ecrire_valeurs

        if not action_permise(self, "Changer le dossier des sauvegardes"):
            return False
        code = self.code()
        valeurs = {"service": code, "actif": bool(self.actif.get())}
        if code in CLES_ID:
            valeurs[CLES_ID[code]] = self.client_id.get().strip()
            if code == "google_drive" and self.secret_google.get().strip():
                coffre.ecrire(sc.GOOGLE_SECRET, self.secret_google.get().strip())
                self.secret_google.set("")
        if code == "s3":
            valeurs.update({cle: v.get().strip() for cle, v in self.s3.items()})
            if self.s3_secret.get().strip():
                coffre.ecrire(sc.S3_SECRET, self.s3_secret.get().strip())
                self.s3_secret.set("")
        ecrire_valeurs(self.racine / "config.toml", sc.SECTION, valeurs)
        self.config_toml = self.relire_config()
        if not silencieux:
            self.afficher_etat("✔ " + t("Réglages enregistrés."))
        return True

    def connecter(self) -> None:
        code = self.code()
        if not code:
            messagebox.showinfo(self.winfo_toplevel().title(), t("Choisissez d'abord le service."), parent=self)
            return
        if not self.enregistrer(silencieux=True):
            return
        self.afficher_etat(t("Vérification du compte…") if code == "s3" else
                           t("La page de connexion s'ouvre dans le navigateur : connectez-vous puis acceptez."),
                           TEXTE_DOUX)

        def travail():
            try:
                nom = (sc.destination("s3", self.config_toml).compte() if code == "s3"
                       else sc.connecter(self.racine, self.config_toml, code))
                if code == "s3":
                    from .ecriture_config import ecrire_valeurs

                    ecrire_valeurs(self.racine / "config.toml", sc.SECTION, {"compte": nom})
                texte, couleur = "✔ " + t("Compte connecté : {n}", n=nom), VERT_FONCE
            except Exception as exc:  # noqa: BLE001
                texte, couleur = "✖ " + str(exc), ROUGE
            self.after(0, lambda: self._apres(texte, couleur))

        threading.Thread(target=travail, daemon=True).start()

    def _apres(self, texte: str, couleur: str) -> None:
        if self.winfo_exists():
            self.config_toml = self.relire_config()
            self.afficher_etat(texte, couleur)

    def mot_de_passe(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Changer le dossier des sauvegardes"):
            return
        titre = self.winfo_toplevel().title()
        if sc.mot_defini() and not messagebox.askyesno(titre, t(
                "Un mot de passe de chiffrement est déjà défini. Le remplacer ? Les sauvegardes déjà envoyées gardent "
                "l'ANCIEN mot de passe : gardez-le aussi."), parent=self):
            return
        mot = simpledialog.askstring(titre, t("Mot de passe de chiffrement des sauvegardes (12 caractères et 3 sortes "
                                              "au moins) :"), show="•", parent=self)
        if not mot:
            return
        if simpledialog.askstring(titre, t("Retapez le mot de passe :"), show="•", parent=self) != mot:
            messagebox.showerror(titre, t("Les deux mots de passe sont différents : rien n'est changé."), parent=self)
            return
        try:
            sc.definir_mot(mot)
        except sc.ErreurCloud as exc:
            messagebox.showerror(titre, str(exc), parent=self)
            return
        self.afficher_etat("✔ " + t("Mot de passe enregistré dans le coffre-fort de Windows. Notez-le en lieu sûr."))

    def envoyer_derniere(self) -> None:
        e = sv.derniere(self.racine)
        if not (e.ok and e.fichier and Path(e.fichier).exists()):
            messagebox.showinfo(self.winfo_toplevel().title(), t("Faites d'abord une sauvegarde (« Sauvegarder "
                                                                 "maintenant »)."), parent=self)
            return
        self.envoyer(Path(e.fichier))

    def envoyer(self, archive: Path) -> None:
        if not self.code():
            return
        self.afficher_etat(t("Envoi chiffré en cours…"), TEXTE_DOUX)
        sc.envoyer_en_fond(self.racine, self.relire_config(),
                           archive, fin=lambda etat: self.after(0, lambda: self._apres("", None)))

    def liste_nuage(self) -> None:
        FenetreNuage(self, self.racine, self.relire_config())


class FenetreNuage(tk.Toplevel):
    """Sauvegardes déposées sur le compte de stockage ; « Restaurer la sauvegarde choisie » la télécharge, la
    déchiffre, puis la remet en place (l'état actuel est d'abord sauvegardé)."""

    def __init__(self, parent, racine: Path, config_toml: dict):
        from .page_rapports import tableau_simple

        super().__init__(parent)
        self.racine, self.config_toml = Path(racine), config_toml
        self.title(t("Sauvegardes dans le cloud"))
        self.configure(background=CARTE, padx=12, pady=10)
        self.geometry("760x460")
        self.transient(parent.winfo_toplevel())
        barre = Rangee(self)
        barre.pack(fill="x")
        barre.ajouter(Bouton(barre, "🔄  " + t("Actualiser"), self.lire, "secondaire", fond=CARTE, petit=True), 6)
        barre.ajouter(Bouton(barre, "↩  " + t("Restaurer la sauvegarde choisie…"), self.restaurer, "danger",
                             fond=CARTE, petit=True))
        self.etat = tk.Label(self, text=t("Lecture du compte…"), background=CARTE, foreground=TEXTE_DOUX, anchor="w")
        self.etat.pack(fill="x", pady=(6, 0))
        self.tableau = tableau_simple(self, hauteur=14)
        self.fichiers: list[sc.FichierNuage] = []
        self.lire()

    def lire(self) -> None:
        def travail():
            try:
                fichiers, erreur = sc.sauvegardes_nuage(self.config_toml), ""
            except Exception as exc:  # noqa: BLE001
                fichiers, erreur = [], str(exc)
            self.after(0, lambda: self._afficher(fichiers, erreur))

        threading.Thread(target=travail, daemon=True).start()

    def _afficher(self, fichiers, erreur: str) -> None:
        from .page_rapports import remplir

        if not self.winfo_exists():
            return
        self.fichiers = fichiers
        remplir(self.tableau, ["Sauvegarde", "Taille", "Déposée le"],
                [[f.nom, _taille(f.taille), f.quand[:16].replace("T", " ")] for f in fichiers], {"Sauvegarde": 420},
                decroissant=False)
        self.etat.configure(text=("✖ " + erreur) if erreur else t("{n} sauvegarde(s) sur le compte.", n=len(fichiers)),
                            foreground=ROUGE if erreur else TEXTE_DOUX)

    def restaurer(self) -> None:
        from .design import action_permise

        if not action_permise(self, "Restaurer une sauvegarde"):
            return
        choix = self.tableau.selection()
        if not choix:
            messagebox.showinfo(self.title(), t("Choisissez une sauvegarde dans la liste."), parent=self)
            return
        fichier = self.fichiers[int(choix[0])]
        if not messagebox.askyesno(self.title(), t(
                "Télécharger « {a} », la déchiffrer et remettre les données telles qu'elles étaient ?\n\nL'état actuel "
                "est d'abord sauvegardé (dossier « avant_restauration »). Fermez puis rouvrez l'application ensuite.",
                a=fichier.nom), icon="warning", parent=self):
            return
        self.etat.configure(text=t("Téléchargement et déchiffrement…"), foreground=TEXTE_DOUX)

        def travail():
            try:
                archive = sc.telecharger_pour_restaurer(self.racine, self.config_toml, fichier)
                avant, n = sv.restaurer(self.racine, self.config_toml, archive)
                texte = t("{n} fichiers restaurés. État d'avant gardé dans {a}. Fermez puis rouvrez l'application.",
                          n=n, a=Path(avant.fichier).name)
                fin = lambda: messagebox.showinfo(self.title(), texte, parent=self)  # noqa: E731
            except Exception as exc:  # noqa: BLE001
                # message gardé : Python efface « exc » à la sortie du bloc, avant que la fenêtre l'affiche
                fin = lambda erreur=str(exc): messagebox.showerror(self.title(), erreur, parent=self)  # noqa: E731
            self.after(0, lambda: (self.etat.configure(text=""), fin()))

        threading.Thread(target=travail, daemon=True).start()

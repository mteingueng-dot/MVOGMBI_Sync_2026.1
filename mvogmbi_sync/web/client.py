"""Programme client (MVOGMBI_Sync_Client.exe, demande du propriétaire du 2026-11-03) : petit programme à part pour
les postes (magasin, bureau, ordinateurs personnels). Il garde l'adresse du serveur, vérifie que c'est bien le
serveur MVOGMBI_Sync (en-tête Server) et ouvre l'application web dans sa propre fenêtre (Microsoft Edge en mode
application, profil à part : ni onglets ni barre d'adresse ; sinon le navigateur par défaut).

Rien n'est gardé sur le poste que l'adresse du serveur (%APPDATA%\\MVOGMBI_Sync_Client\\client.json) ; la connexion
(nom et mot de passe) se fait dans la fenêtre, sur le serveur. Les téléphones ouvrent la même adresse dans leur
navigateur.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

PORT_DEFAUT = 8765
DELAI = 5  # s
# noms que l'on tape dans le client (demande du propriétaire du 2026-11-03 : « marchemvogmbi.com » au lieu de
# l'adresse et du port) -> serveur ; le domaine reste celui du site web du marché (DNS chez WHC) : il n'est pas
# changé, c'est le client qui fait le lien
NOMS = {"marchemvogmbi.com": "http://100.69.84.52:8765"}  # SERVDC01 par Tailscale
ADRESSE_DEFAUT = "marchemvogmbi.com"


def _nom(saisie: str) -> str:
    nom = saisie.strip().lower().rstrip("/")
    for prefixe in ("http://", "https://", "www."):
        nom = nom.removeprefix(prefixe)
    return nom


def adresse_serveur(saisie: str) -> str:
    """Nom connu (« marchemvogmbi.com ») -> son serveur ; sinon adresse normalisée (IP, nom, port)."""
    return NOMS.get(_nom(saisie)) or normaliser(saisie)


def dossier() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "MVOGMBI_Sync_Client"


def lire_reglages() -> dict:
    try:
        return json.loads((dossier() / "client.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ecrire_reglages(reglages: dict) -> None:
    dossier().mkdir(parents=True, exist_ok=True)
    (dossier() / "client.json").write_text(json.dumps(reglages, ensure_ascii=False, indent=1), encoding="utf-8")


def normaliser(adresse: str) -> str:
    """« 100.69.84.52 » -> « http://100.69.84.52:8765 » ; ValueError si l'adresse n'en est pas une."""
    adresse = adresse.strip().rstrip("/")
    if not adresse:
        raise ValueError("Entrez l'adresse du serveur.")
    if "://" not in adresse:
        adresse = "http://" + adresse
    parties = urlsplit(adresse)
    if parties.scheme not in ("http", "https") or not parties.hostname or (parties.path not in ("", "/")):
        raise ValueError("Adresse invalide (exemple : 100.69.84.52 ou http://100.69.84.52:8765).")
    try:
        port = parties.port
    except ValueError:
        raise ValueError("Port invalide.") from None
    if port is None and parties.scheme == "http":
        return f"http://{parties.hostname}:{PORT_DEFAUT}"
    return f"{parties.scheme}://{parties.netloc}"


def verifier(adresse: str, delai: float = DELAI) -> str:
    """« » si le serveur MVOGMBI_Sync répond à cette adresse, sinon la raison."""
    try:
        with urllib.request.urlopen(adresse + "/connexion", timeout=delai) as r:
            if not r.headers.get("Server", "").startswith("MVOGMBI_Sync"):  # ex. le site web du marché
                return "Un autre programme répond à cette adresse : ce n'est pas le serveur MVOGMBI_Sync."
            return ""
    except urllib.error.HTTPError as erreur:
        return f"Le serveur a répondu {erreur.code}."
    except (urllib.error.URLError, OSError):
        return ("Le serveur ne répond pas. Vérifiez que Tailscale est connecté sur ce poste et que le serveur est "
                "allumé.")


def trouver_edge() -> Path | None:
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            chemin = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if chemin.exists():
                return chemin
    return None


def ouvrir(adresse: str) -> None:
    """Fenêtre de l'application : Edge en mode application (profil à part, gardé d'une fois à l'autre)."""
    edge = trouver_edge()
    if edge is None:
        webbrowser.open(adresse + "/")
        return
    profil = dossier() / "fenetre"
    subprocess.Popen([str(edge), f"--app={adresse}/", f"--user-data-dir={profil}", "--no-first-run",
                      "--no-default-browser-check", "--window-size=1280,860"],
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)


def fichier_rdp(adresse: str) -> Path:
    """Connexion Bureau à distance à l'application complète (application Windows sur le serveur) : même machine
    que le serveur web ; compte Windows du serveur demandé à la connexion (rien n'est gardé ici)."""
    hote = urlsplit(adresse).hostname or ""
    chemin = dossier() / "Application_complete.rdp"
    dossier().mkdir(parents=True, exist_ok=True)
    lignes = [f"full address:s:{hote}", "screen mode id:i:2", "use multimon:i:0", "prompt for credentials:i:1",
              "authentication level:i:2", "redirectclipboard:i:1", "redirectprinters:i:1", "redirectdrives:i:0",
              "autoreconnection enabled:i:1"]
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")  # fins de ligne Windows (mode texte)
    return chemin


def ouvrir_bureau_distance(adresse: str) -> None:
    subprocess.Popen(["mstsc.exe", str(fichier_rdp(adresse))], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                     close_fds=True)


def principal() -> None:
    """Fenêtre du client : serveur (nom gardé), « Application web » (Entrée) ou « Application complète (Bureau à
    distance) » pour les profils qui ont besoin de toute l'application Windows."""
    saisie = lire_reglages().get("adresse", "")
    fenetre_reglage(saisie or ADRESSE_DEFAUT, "")


def fenetre_reglage(adresse: str, message: str) -> None:
    import tkinter as tk
    from tkinter import ttk

    racine = tk.Tk()
    racine.title("MVOGMBI_Sync — Client")
    racine.resizable(False, False)
    cadre = ttk.Frame(racine, padding=18)
    cadre.pack(fill="both", expand=True)
    ttk.Label(cadre, text="MVOGMBI_Sync", font=("Segoe UI", 16, "bold"), foreground="#13772d").pack(anchor="w")
    ttk.Label(cadre, text="Serveur (ex. marchemvogmbi.com)").pack(anchor="w", pady=(12, 2))
    valeur = tk.StringVar(value=adresse)
    champ = ttk.Entry(cadre, textvariable=valeur, width=46)
    champ.pack(fill="x")
    etat = ttk.Label(cadre, text=message, foreground="#c8102e", wraplength=360, justify="left")
    etat.pack(anchor="w", pady=(8, 0))

    def connecter(bureau: bool = False):
        try:
            choisie = adresse_serveur(valeur.get())
        except ValueError as erreur:
            etat.configure(text=str(erreur), foreground="#c8102e")
            return
        etat.configure(text="Connexion au serveur…", foreground="#6b7a70")
        racine.update_idletasks()
        raison = verifier(choisie)
        if raison:
            etat.configure(text=raison, foreground="#c8102e")
            return
        ecrire_reglages({"adresse": valeur.get().strip()})  # le nom tapé : le lien suit la version du client
        if bureau:
            ouvrir_bureau_distance(choisie)
        else:
            ouvrir(choisie)
        racine.destroy()

    boutons = ttk.Frame(cadre)
    boutons.pack(fill="x", pady=(14, 0))
    ttk.Button(boutons, text="Application web", command=connecter).pack(side="right")
    ttk.Button(boutons, text="Application complète (Bureau à distance)",
               command=lambda: connecter(True)).pack(side="right", padx=(0, 8))
    ttk.Label(cadre, text="Application complète : compte Windows du serveur, 2 personnes à la fois.",
              foreground="#6b7a70").pack(anchor="w", pady=(10, 0))
    champ.bind("<Return>", lambda _e: connecter())
    champ.focus_set()
    racine.mainloop()

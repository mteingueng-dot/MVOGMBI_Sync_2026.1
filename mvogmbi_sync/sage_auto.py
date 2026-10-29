"""Pilotage sans intervention de l'outil d'import de Sage 50 (Sage_SA_import.exe).

Comportement observé (Sage 50 2026.2, fichier d'entreprise fermé) :
- l'outil ouvre la base MySQL du fichier dès son lancement, puis affiche « Sage 50 - Password »
  (utilisateur imposé, ex. sysadmin) ; la base est lisible pendant que cette fenêtre attend ;
- après la saisie du mot de passe, il importe puis affiche « Sage 50 - Import Summary » ;
  la base reste lisible tant que ce résumé est affiché, et se ferme quand l'outil se termine ;
- une erreur s'affiche dans une fenêtre « Sage 50 Import » ; un article inconnu ouvre
  « Sage 50 Import - Select Item or Account ».
Si Sage est déjà ouvert sur le fichier, la fenêtre de mot de passe n'apparaît pas.

Ce module répond à ces fenêtres par messages Windows (aucune frappe clavier simulée) :
mot de passe saisi dans le champ, résumé lu puis fermé, toute autre fenêtre lue, notée en erreur et annulée.

Fonctionnement transparent : l'outil est lancé caché et un fil de surveillance masque aussitôt (quelques
millisecondes) toute fenêtre qu'il affiche ; les fenêtres masquées continuent de recevoir les réponses.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

WM_GETTEXT, WM_GETTEXTLENGTH, WM_SETTEXT, WM_COMMAND = 0x000D, 0x000E, 0x000C, 0x0111
IDOK, IDCANCEL = 1, 2
SW_HIDE = 0

TITRE_MOT_DE_PASSE = "Sage 50 - Password"
TITRE_RESUME = "Sage 50 - Import Summary"


def _texte(hwnd) -> str:
    n = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    tampon = ctypes.create_unicode_buffer(n + 1)
    user32.SendMessageW(hwnd, WM_GETTEXT, n + 1, tampon)
    return tampon.value


def _classe(hwnd) -> str:
    tampon = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, tampon, 256)
    return tampon.value


def fenetres_du_processus(pid: int, visibles_seulement: bool = False) -> list[int]:
    """Fenêtres principales (avec un titre) du processus, y compris celles déjà masquées."""
    trouvees = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(hwnd, _):
        proprietaire = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proprietaire))
        if proprietaire.value == pid and user32.GetWindowTextLengthW(hwnd) > 0:
            if not visibles_seulement or user32.IsWindowVisible(hwnd):
                trouvees.append(hwnd)
        return True

    user32.EnumWindows(rappel, 0)
    return trouvees


def surveiller_et_masquer(processus: subprocess.Popen, arret: threading.Event) -> None:
    """Masque en continu toute fenêtre visible de l'outil de Sage : rien n'apparaît à l'écran."""
    while not arret.is_set() and processus.poll() is None:
        for hwnd in fenetres_du_processus(processus.pid, visibles_seulement=True):
            user32.ShowWindow(hwnd, SW_HIDE)
        time.sleep(0.01)


def lancer_cache(commande: list[str]) -> subprocess.Popen:
    """Lance un programme sans afficher sa fenêtre principale."""
    infos = subprocess.STARTUPINFO()
    infos.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    infos.wShowWindow = SW_HIDE
    return subprocess.Popen(commande, startupinfo=infos)


def enfants(hwnd) -> list[tuple[int, str, str]]:
    """(hwnd, classe, texte) des contrôles d'une fenêtre."""
    trouves = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(h, _):
        trouves.append((h, _classe(h), _texte(h)))
        return True

    user32.EnumChildWindows(hwnd, rappel, 0)
    return trouves


def cliquer(hwnd_dialogue, libelles: tuple[str, ...], identifiant_defaut: int) -> None:
    """Actionne le bouton dont le libellé correspond (« OK », « &Select »…), sinon la commande par défaut.

    La commande est envoyée directement à la fenêtre (WM_COMMAND) : BM_CLICK reste sans effet
    sur une fenêtre masquée ou inactive.
    """
    for libelle in libelles:
        for h, classe, texte in enfants(hwnd_dialogue):
            if classe == "Button" and texte.replace("&", "").strip().lower() == libelle:
                user32.PostMessageW(hwnd_dialogue, WM_COMMAND, user32.GetDlgCtrlID(h) & 0xFFFF, h)
                return
    user32.PostMessageW(hwnd_dialogue, WM_COMMAND, identifiant_defaut, 0)


def processus_import() -> list[int]:
    """PID des outils d'import de Sage en cours."""
    sortie = subprocess.run(["tasklist", "/fo", "csv", "/nh", "/fi", "IMAGENAME eq Sage_SA_import.exe"],
                            capture_output=True, text=True, encoding="cp850",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    pids = []
    for ligne in sortie.splitlines():
        champs = [c.strip('"') for c in ligne.split('","')]
        if len(champs) > 1 and champs[1].isdigit():
            pids.append(int(champs[1]))
    return pids


def fermer_restes(attente: float = 10) -> list[str]:
    """Ferme les outils d'import restés ouverts (fenêtre de mot de passe ou résumé en attente).

    Deux outils sur le même fichier se gêneraient. Seules ces deux fenêtres, sans import en cours,
    sont fermées ; un outil occupé à importer est laissé tranquille.
    """
    notes = []
    for pid in processus_import():
        for hwnd in fenetres_du_processus(pid):
            titre = _texte(hwnd)
            if titre == TITRE_MOT_DE_PASSE:
                user32.ShowWindow(hwnd, SW_HIDE)
                cliquer(hwnd, ("cancel", "annuler"), IDCANCEL)
                notes.append(f"Outil d'import resté ouvert (PID {pid}, connexion) : annulé.")
            elif titre == TITRE_RESUME:
                user32.ShowWindow(hwnd, SW_HIDE)
                cliquer(hwnd, ("ok",), IDOK)
                notes.append(f"Outil d'import resté ouvert (PID {pid}, résumé) : fermé.")
    if notes:
        fin = time.time() + attente
        while time.time() < fin and processus_import():
            # après « Cancel », l'outil peut encore afficher un résumé
            for pid in processus_import():
                for hwnd in fenetres_du_processus(pid):
                    if _texte(hwnd) in (TITRE_RESUME, TITRE_MOT_DE_PASSE):
                        user32.ShowWindow(hwnd, SW_HIDE)
                        cliquer(hwnd, ("ok", "cancel"), IDOK)
            time.sleep(0.5)
    return notes


@dataclass
class ResultatSage:
    termine: bool = False
    code_retour: int | None = None
    resume: str = ""
    erreurs: list[str] = field(default_factory=list)
    connexion_annulee: bool = False


def executer(exe: Path, fichier_imp: Path, fichier_sai: Path, mot_de_passe: str | None,
             pendant_connexion: Callable[[], bool] | None = None,
             pendant_resume: Callable[[str], None] | None = None,
             delai: int = 1800, discret: bool = True) -> ResultatSage:
    """Lance l'outil d'import et répond à ses fenêtres jusqu'à sa fermeture.

    pendant_connexion : appelée quand la fenêtre de mot de passe s'affiche (la base est alors lisible) ;
        si elle renvoie False, la connexion est annulée (aucun import).
    pendant_resume : appelée avec le texte du résumé, avant de le fermer (la base est encore lisible).
    """
    from .__main__ import fermer_bases

    resultat = ResultatSage()
    fermer_bases()  # l'import exige qu'aucune autre connexion ne tienne l'entreprise
    fermer_restes()
    commande = [str(exe), str(fichier_imp), str(fichier_sai)]
    processus = lancer_cache(commande) if discret else subprocess.Popen(commande)
    arret = threading.Event()
    if discret:
        threading.Thread(target=surveiller_et_masquer, args=(processus, arret), daemon=True).start()
    deja_vues: set[int] = set()
    debut = time.time()
    try:
        while time.time() - debut < delai:
            if processus.poll() is not None:
                resultat.termine, resultat.code_retour = True, processus.returncode
                return resultat
            for hwnd in fenetres_du_processus(processus.pid):
                titre = _texte(hwnd)
                if hwnd in deja_vues:
                    continue
                if titre == TITRE_MOT_DE_PASSE:
                    deja_vues.add(hwnd)
                    continuer = pendant_connexion() if pendant_connexion else True
                    if not continuer or not mot_de_passe:
                        if continuer and not mot_de_passe:
                            resultat.erreurs.append("Sage demande un mot de passe, mais aucun n'est enregistré.")
                        resultat.connexion_annulee = True
                        cliquer(hwnd, ("cancel", "annuler"), IDCANCEL)
                        continue
                    champs = [h for h, classe, _ in enfants(hwnd) if classe == "Edit"]
                    if not champs:
                        resultat.erreurs.append("Champ du mot de passe introuvable dans la fenêtre de Sage.")
                        cliquer(hwnd, ("cancel", "annuler"), IDCANCEL)
                        continue
                    user32.SendMessageW(champs[-1], WM_SETTEXT, 0, ctypes.c_wchar_p(mot_de_passe))
                    cliquer(hwnd, ("ok",), IDOK)
                elif titre == TITRE_RESUME:
                    deja_vues.add(hwnd)
                    resultat.resume = "\n".join(t for _, classe, t in enfants(hwnd) if classe == "Edit" and t)
                    if pendant_resume:
                        pendant_resume(resultat.resume)
                    cliquer(hwnd, ("ok",), IDOK)
                elif titre.startswith("Sage 50"):
                    # Erreur, question ou article inconnu : on note le message et on annule.
                    deja_vues.add(hwnd)
                    message = " ".join(t.strip() for _, classe, t in enfants(hwnd) if classe in ("Static", "Edit") and t.strip())
                    resultat.erreurs.append(f"{titre} : {message}" if message else titre)
                    if "password" in message.lower() or "mot de passe" in message.lower():
                        resultat.erreurs.append("Mot de passe Sage refusé : vérifiez-le dans la configuration.")
                    # « Import Error … Do you wish to continue? » (Oui / Non) : on ne continue jamais
                    cliquer(hwnd, ("cancel", "annuler", "non", "no", "ok"), IDCANCEL)
            time.sleep(0.1)
        resultat.erreurs.append(f"L'outil d'import ne s'est pas terminé après {delai} s : arrêté.")
        processus.kill()
        return resultat
    finally:
        arret.set()
        if processus.poll() is None:
            processus.kill()


def lire_pendant_connexion(exe: Path, fichier_sai: Path, lecture: Callable[[], object], delai: int = 300):
    """Ouvre la base d'un fichier Sage fermé (via l'outil d'import), exécute `lecture`, puis annule la connexion.

    Aucun import n'a lieu : le fichier .IMP utilisé ne contient aucune transaction.
    """
    retour: dict = {}

    def lire() -> bool:
        derniere_erreur = None
        for _ in range(30):  # la base s'ouvre une à deux secondes après la fenêtre de mot de passe
            try:
                retour["valeur"] = lecture()
                return False
            except PermissionError as exc:  # identifiants refusés : inutile d'insister
                derniere_erreur = exc
                break
            except Exception as exc:  # base pas encore prête
                derniere_erreur = exc
                time.sleep(1)
        retour["erreur"] = derniere_erreur
        return False

    with tempfile.TemporaryDirectory() as dossier:
        vide = Path(dossier) / "lecture.IMP"
        vide.write_text('<Version>\r\n"12001","1"\r\n</Version>\r\n', encoding="cp1252", newline="")
        resultat = executer(exe, vide, fichier_sai, mot_de_passe=None, pendant_connexion=lire, delai=delai)
    if "erreur" in retour:
        if isinstance(retour["erreur"], PermissionError):
            raise retour["erreur"]
        raise RuntimeError(f"Lecture de la base Sage impossible : {retour['erreur']}")
    if "valeur" not in retour:
        raise RuntimeError("Sage n'a pas ouvert la base du fichier (fenêtre de connexion absente). "
                           + " ".join(resultat.erreurs))
    return retour["valeur"]

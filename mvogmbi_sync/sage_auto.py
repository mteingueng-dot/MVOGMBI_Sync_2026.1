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
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

WM_GETTEXT, WM_GETTEXTLENGTH, WM_SETTEXT, WM_COMMAND, BM_CLICK = 0x000D, 0x000E, 0x000C, 0x0111, 0x00F5
IDOK, IDCANCEL = 1, 2

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


def fenetres_du_processus(pid: int) -> list[int]:
    trouvees = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(hwnd, _):
        proprietaire = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proprietaire))
        if proprietaire.value == pid and user32.IsWindowVisible(hwnd):
            trouvees.append(hwnd)
        return True

    user32.EnumWindows(rappel, 0)
    return trouvees


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
    """Clique sur le bouton dont le libellé correspond (« OK », « &Select »…), sinon envoie la commande par défaut."""
    for h, classe, texte in enfants(hwnd_dialogue):
        if classe == "Button" and texte.replace("&", "").strip().lower() in libelles:
            user32.SendMessageW(h, BM_CLICK, 0, 0)
            return
    user32.PostMessageW(hwnd_dialogue, WM_COMMAND, identifiant_defaut, 0)


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
             delai: int = 1800) -> ResultatSage:
    """Lance l'outil d'import et répond à ses fenêtres jusqu'à sa fermeture.

    pendant_connexion : appelée quand la fenêtre de mot de passe s'affiche (la base est alors lisible) ;
        si elle renvoie False, la connexion est annulée (aucun import).
    pendant_resume : appelée avec le texte du résumé, avant de le fermer (la base est encore lisible).
    """
    resultat = ResultatSage()
    processus = subprocess.Popen([str(exe), str(fichier_imp), str(fichier_sai)])
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
                    cliquer(hwnd, ("cancel", "annuler", "ok"), IDCANCEL)
            time.sleep(0.5)
        resultat.erreurs.append(f"L'outil d'import ne s'est pas terminé après {delai} s : arrêté.")
        processus.kill()
        return resultat
    finally:
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
        raise RuntimeError(f"Lecture de la base Sage impossible : {retour['erreur']}")
    if "valeur" not in retour:
        raise RuntimeError("Sage n'a pas ouvert la base du fichier (fenêtre de connexion absente). "
                           + " ".join(resultat.erreurs))
    return retour["valeur"]

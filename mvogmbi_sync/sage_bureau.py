"""Sage 50 piloté sur un bureau Windows caché : aucune fenêtre à l'écran, et fonctionne session verrouillée.

Pourquoi un bureau caché (mis au point le 2026-10-26, session verrouillée) :
- l'accueil de Sage (WinForms) n'accepte un clic que si l'élément est réellement sous le point cliqué
  (WindowFromPoint) ; session verrouillée, l'écran de verrouillage recouvre tout sur le bureau normal ;
- sur un bureau créé pour le robot, Sage est seul : rien ne le recouvre, verrouillage ou non ;
- le clic sur l'icône « Encaissements » n'est pris en compte que si la fenêtre de Sage est active pour son fil et
  si le bouton gauche est « enfoncé » : le robot s'attache au fil de Sage (AttachThreadInput), active la fenêtre et
  marque VK_LBUTTON dans l'état clavier partagé pendant le clic ;
- juste après l'ouverture, Sage répond « Chargement de Sage 50. Veuillez patienter » : on ferme et on recommence.

Parcours : accueil « Sélectionner une entreprise existante » -> « Sage 50 - Ouvrir un fichier » (champ 1148) ->
« Sage 50 - Mot de passe » (utilisateur 21, mot de passe 20, mono-utilisateur 24) -> page « Clients & ventes »
-> icône « Encaissements ». Toute autre fenêtre inattendue arrête le robot (notée, puis Sage est refermé).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import time
from pathlib import Path

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
kernel32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None

BUREAU = "MVOGMBI_Robot"
BM_CLICK, WM_SETTEXT, WM_COMMAND, WM_CLOSE = 0x00F5, 0x000C, 0x0111, 0x0010
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
TITRE_OUVRIR = "Sage 50 - Ouvrir un fichier"
TITRE_CONNEXION = "Sage 50 - Mot de passe"
CHARGEMENT = "Veuillez patienter"


class ErreurSage(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------- bureau caché
class _STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR), ("lpTitle", wt.LPWSTR),
                ("dwX", wt.DWORD), ("dwY", wt.DWORD), ("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD),
                ("dwXCountChars", wt.DWORD), ("dwYCountChars", wt.DWORD), ("dwFillAttribute", wt.DWORD),
                ("dwFlags", wt.DWORD), ("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wt.HANDLE), ("hStdOutput", wt.HANDLE),
                ("hStdError", wt.HANDLE)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE), ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]


def executer_sur_bureau_cache(commande: list[str], dossier: Path | None = None, delai: int = 1800) -> int:
    """Exécute `commande` sur le bureau caché du robot et renvoie son code de sortie (-1 si délai dépassé)."""
    user32.CreateDesktopW.restype = wt.HANDLE
    kernel32.CreateProcessW.argtypes = [wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wt.BOOL, wt.DWORD,
                                        ctypes.c_void_p, wt.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p]
    kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
    kernel32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
    kernel32.CloseHandle.argtypes = [wt.HANDLE]
    bureau = user32.CreateDesktopW(BUREAU, None, None, 0, 0x10000000, None)  # GENERIC_ALL
    if not bureau:
        raise ErreurSage(f"Ouverture de Sage impossible (erreur Windows {kernel32.GetLastError()}).")
    infos = _STARTUPINFO()
    infos.cb = ctypes.sizeof(infos)
    infos.lpDesktop = f"WinSta0\\{BUREAU}"
    processus = _PROCESS_INFORMATION()
    ligne = ctypes.create_unicode_buffer(subprocess.list2cmdline(commande))
    if not kernel32.CreateProcessW(None, ligne, None, None, False, 0x08000000, None,  # CREATE_NO_WINDOW
                                   str(dossier) if dossier else None, ctypes.byref(infos), ctypes.byref(processus)):
        raise ErreurSage(f"Ouverture de Sage impossible (erreur Windows {kernel32.GetLastError()}).")
    try:
        if kernel32.WaitForSingleObject(processus.hProcess, delai * 1000) != 0:
            kernel32.TerminateProcess(processus.hProcess, 1)
            return -1
        code = wt.DWORD()
        kernel32.GetExitCodeProcess(processus.hProcess, ctypes.byref(code))
        return code.value
    finally:
        kernel32.CloseHandle(processus.hProcess)
        kernel32.CloseHandle(processus.hThread)


# --------------------------------------------------------------------------------------------- fenêtres
def _texte(h) -> str:
    n = user32.GetWindowTextLengthW(h)
    tampon = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, tampon, n + 1)
    return tampon.value


def _descendants(h) -> list[int]:
    liste = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(e, _):
        liste.append(e)
        return True

    user32.EnumChildWindows(h, rappel, 0)
    return liste


def _attendre(condition, delai: float, pas: float = 0.5):
    fin = time.time() + delai
    while time.time() < fin:
        resultat = condition()
        if resultat:
            return resultat
        time.sleep(pas)
    return None


def sage_ouvert() -> bool:
    """Sage 50 tourne-t-il ? Un processus arrêté de force peut rester listé (« zombie », 32 Ko) : il ne compte pas."""
    import csv

    sortie = subprocess.run(["tasklist", "/fo", "csv", "/nh", "/fi", "IMAGENAME eq Sage50Accounting.exe"],
                            capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    for ligne in csv.reader(sortie.splitlines()):
        if len(ligne) < 5 or not ligne[0].lower().startswith("sage50accounting"):
            continue
        poignee = kernel32.OpenProcess(0x1000, False, int(ligne[1]))  # PROCESS_QUERY_LIMITED_INFORMATION
        if poignee:
            code = wt.DWORD()
            vivant = kernel32.GetExitCodeProcess(poignee, ctypes.byref(code)) and code.value == 259  # STILL_ACTIVE
            kernel32.CloseHandle(poignee)
            if vivant:
                return True
        elif int("".join(c for c in ligne[4] if c.isdigit()) or 0) > 1024:  # mémoire (Ko) d'un vrai Sage
            return True
    return False


def executable_sage(executable_import: Path | None) -> Path | None:
    """Sage50Accounting.exe, à côté de l'outil d'import."""
    if executable_import:
        candidat = Path(executable_import).with_name("Sage50Accounting.exe")
        if candidat.is_file():
            return candidat
    return None


class SessionSage:
    """Sage 50 ouvert par le robot sur un fichier d'entreprise, en mono-utilisateur (à utiliser sur le bureau caché)."""

    def __init__(self, exe: Path, journal=print):
        self.exe, self.journal = Path(exe), journal
        self.processus: subprocess.Popen | None = None
        self.principale = None

    # ------------------------------------------------------------ fenêtres du processus
    def fenetres(self) -> list[int]:
        trouvees = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def rappel(h, _):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if self.processus and pid.value == self.processus.pid and user32.IsWindowVisible(h) and _texte(h):
                trouvees.append(h)
            return True

        user32.EnumWindows(rappel, 0)
        return trouvees

    def _bouton(self, fenetre, debut_libelle: str):
        return next((e for e in _descendants(fenetre) if _texte(e).startswith(debut_libelle)), None)

    def fermer_message_chargement(self) -> bool:
        for h in self.fenetres():
            if h != self.principale and any(CHARGEMENT in _texte(e) for e in _descendants(h)):
                ok = self._bouton(h, "&OK")
                if ok:
                    user32.SendMessageW(ok, BM_CLICK, 0, 0)
                    return True
        return False

    # ------------------------------------------------------------ ouverture
    def ouvrir(self, fichier_sai: Path, utilisateur: str, mot_de_passe: str, delai: int = 180) -> None:
        self.processus = subprocess.Popen([str(self.exe)])
        self.journal("Sage lancé.")
        accueil = _attendre(lambda: next((h for h in self.fenetres()
                                          if self._bouton(h, "Sélectionner une &entreprise")), None), delai)
        if not accueil:
            raise ErreurSage(f"Écran d'accueil de Sage absent ({[ _texte(h) for h in self.fenetres()]}).")
        user32.SendMessageW(self._bouton(accueil, "Sélectionner une &entreprise"), BM_CLICK, 0, 0)
        user32.SendMessageW(self._bouton(accueil, "&OK"), BM_CLICK, 0, 0)

        ouvrir = _attendre(lambda: user32.FindWindowW("#32770", TITRE_OUVRIR), 60)
        if not ouvrir:
            raise ErreurSage("Fenêtre « Ouvrir un fichier » de Sage absente.")
        _attendre(lambda: user32.IsWindowVisible(ouvrir) and self._largeur(ouvrir) > 0, 30)
        time.sleep(1.5)  # la fenêtre termine son initialisation (sinon elle efface le nom saisi)
        # « Nom du fichier » : le champ Edit (n° 1148) dans la liste déroulante qui porte le même numéro
        champ = next((e for e in _descendants(ouvrir) if user32.GetDlgCtrlID(e) == 1148 and self._classe(e) == "Edit"),
                     None)
        if not champ:
            raise ErreurSage("Champ « Nom du fichier » introuvable dans la fenêtre « Ouvrir un fichier ».")
        for _ in range(3):
            user32.SendMessageW(champ, WM_SETTEXT, 0, ctypes.c_wchar_p(str(fichier_sai)))
            time.sleep(0.5)
            if self._contenu(champ) == str(fichier_sai):
                break
        else:
            raise ErreurSage("Le nom du fichier d'entreprise n'a pas pu être saisi dans « Ouvrir un fichier ».")
        user32.SendMessageW(user32.GetDlgItem(ouvrir, 1), BM_CLICK, 0, 0)  # « Ouvrir »

        connexion = _attendre(lambda: user32.FindWindowW("#32770", TITRE_CONNEXION), 90)
        if not connexion:
            raise ErreurSage(f"Fenêtre de connexion de Sage absente ({[_texte(h) for h in self.fenetres()]}).")
        user32.SendMessageW(user32.GetDlgItem(connexion, 21), WM_SETTEXT, 0, ctypes.c_wchar_p(utilisateur))
        user32.SendMessageW(user32.GetDlgItem(connexion, 20), WM_SETTEXT, 0, ctypes.c_wchar_p(mot_de_passe))
        user32.SendMessageW(user32.GetDlgItem(connexion, 24), BM_CLICK, 0, 0)  # mono-utilisateur
        user32.PostMessageW(connexion, WM_COMMAND, 1, user32.GetDlgItem(connexion, 1))

        nom = Path(fichier_sai).name.upper()
        self.principale = _attendre(lambda: next((h for h in self.fenetres() if _texte(h).upper() == nom), None), delai)
        if not self.principale:
            autres = [_texte(h) for h in self.fenetres()]
            raise ErreurSage(f"Sage n'a pas ouvert {Path(fichier_sai).name} (fenêtres : {autres}) — "
                             "mot de passe de sysadmin refusé ou fichier utilisé par quelqu'un d'autre ?")
        self.journal(f"Sage ouvert sur {Path(fichier_sai).name}.")

    @staticmethod
    def _contenu(h) -> str:
        """Texte d'un contrôle d'un autre processus (WM_GETTEXT ; GetWindowText ne lit que les titres)."""
        tampon = ctypes.create_unicode_buffer(1024)
        user32.SendMessageW(h, 0x000D, 1024, tampon)
        return tampon.value

    @staticmethod
    def _largeur(h) -> int:
        rect = wt.RECT()
        user32.GetWindowRect(h, ctypes.byref(rect))
        return rect.right - rect.left

    @staticmethod
    def _classe(h) -> str:
        tampon = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, tampon, 64)
        return tampon.value

    # ------------------------------------------------------------ fenêtre Encaissements
    def _icone(self, libelle: str):
        etiquette = next((e for e in _descendants(self.principale)
                          if _texte(e) == libelle and user32.IsWindowVisible(e)), None)
        if not etiquette:
            raise ErreurSage(f"Tâche « {libelle} » introuvable sur l'accueil de Sage (page « Clients & ventes » ?).")
        panneau = user32.GetParent(user32.GetParent(etiquette))
        return next(e for e in _descendants(panneau)
                    if user32.GetParent(e) == panneau and e != user32.GetParent(etiquette))

    def _cliquer(self, cible) -> None:
        """Clic accepté par WinForms hors écran : fenêtre active et bouton gauche marqué enfoncé (état partagé)."""
        fil = user32.GetWindowThreadProcessId(self.principale, None)
        moi = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(moi, fil, True)
        try:
            user32.SetActiveWindow(self.principale)
            etat = (ctypes.c_ubyte * 256)()
            user32.GetKeyboardState(etat)
            etat[1] = 0x80  # VK_LBUTTON
            user32.SetKeyboardState(etat)
            position = (20 << 16) | 20
            user32.PostMessageW(cible, WM_MOUSEMOVE, 1, position)
            user32.PostMessageW(cible, WM_LBUTTONDOWN, 1, position)
            time.sleep(0.3)
            etat[1] = 0
            user32.SetKeyboardState(etat)
            user32.PostMessageW(cible, WM_LBUTTONUP, 0, position)
            time.sleep(0.5)
        finally:
            user32.AttachThreadInput(moi, fil, False)

    def ouvrir_encaissements(self, essais: int = 6) -> int:
        icone = _attendre(lambda: self._icone("Encaissements"), 60)
        for _ in range(essais):
            time.sleep(5)  # Sage termine son chargement après l'affichage de l'accueil
            self._cliquer(icone)
            fenetre = _attendre(lambda: user32.FindWindowW("#32770", "Encaissements"), 10)
            if fenetre:
                self.journal("Fenêtre Encaissements ouverte.")
                return fenetre
            self.fermer_message_chargement()
        raise ErreurSage("La fenêtre Encaissements de Sage ne s'ouvre pas.")

    def _visible(self, libelle: str):
        return next((e for e in _descendants(self.principale) if _texte(e) == libelle and user32.IsWindowVisible(e)), None)

    def ouvrir_paiements(self, essais: int = 6) -> int:
        """Page « Fournisseurs & Achats » (menu de gauche), puis tâche « Paiements »."""
        lien = _attendre(lambda: self._visible("Fournisseurs & Achats"), 60)
        if not lien:
            raise ErreurSage("Menu « Fournisseurs & Achats » introuvable dans Sage.")
        for _ in range(essais):
            time.sleep(5)  # Sage termine son chargement après l'affichage de l'accueil
            self.fermer_message_chargement()
            if not self._visible("Paiements"):
                for cible in (lien, user32.GetParent(lien)):  # le libellé, sinon son cadre
                    self._cliquer(cible)
                    if _attendre(lambda: self._visible("Paiements"), 4):
                        break
                continue
            self._cliquer(self._icone("Paiements"))
            fenetre = _attendre(lambda: user32.FindWindowW("#32770", "Paiements"), 10)
            if fenetre:
                self.journal("Fenêtre Paiements ouverte.")
                return fenetre
        raise ErreurSage("La fenêtre Paiements de Sage ne s'ouvre pas.")

    # ------------------------------------------------------------ fermeture
    def _confirmer_abandon(self) -> None:
        """Fenêtre fermée avec une saisie non traitée : Sage demande s'il faut la supprimer -> Oui (rien n'est saisi)."""
        for h in self.fenetres():
            if h != self.principale and any("supprimer" in _texte(e) for e in _descendants(h)):
                oui = self._bouton(h, "&Oui") or self._bouton(h, "Oui")
                if oui:
                    user32.PostMessageW(h, WM_COMMAND, user32.GetDlgCtrlID(oui), oui)

    def fermer(self, delai: int = 60) -> None:
        if not self.processus or self.processus.poll() is not None:
            return
        for titre in ("Encaissements", "Paiements"):
            fenetre = user32.FindWindowW("#32770", titre)
            if fenetre:
                user32.PostMessageW(fenetre, WM_CLOSE, 0, 0)
                time.sleep(2)
                self._confirmer_abandon()
                time.sleep(1)
        if self.principale:
            user32.PostMessageW(self.principale, WM_CLOSE, 0, 0)
        if _attendre(lambda: self.processus.poll() is not None, delai):
            self.journal("Sage refermé.")
            return
        restantes = [_texte(h) for h in self.fenetres()]
        self.processus.kill()
        self.journal(f"Sage ne se refermait pas (fenêtres : {restantes}) : arrêté.")

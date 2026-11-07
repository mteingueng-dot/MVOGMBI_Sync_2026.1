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
import json
import os
import subprocess
import time
from pathlib import Path

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
kernel32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None

BUREAU = "MVOGMBI_Robot"
ENTREPRISE_OCCUPEE = ("Sage refuse d'ouvrir {nom} : « d'autres utilisateurs travaillent avec cette entreprise ». Elle "
                      "est encore ouverte ailleurs (un Sage arrêté de force, ou ouvert sur un autre poste). Fermez Sage "
                      "partout ; au besoin redémarrez l'ordinateur, puis relancez.")
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


def executer_sur_bureau_cache(commande: list[str], dossier: Path | None = None, delai: int = 1800,
                              fermer: bool = True) -> int:
    """Exécute `commande` sur le bureau caché du robot et renvoie son code de sortie (-1 si délai dépassé)."""
    from .__main__ import fermer_bases

    if fermer:
        fermer_bases()  # sinon Sage, lancé par la commande, voit « d'autres utilisateurs »
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


# Sage ouverts par l'application pour lire la base (`__main__._sage_garde`) : ils ne comptent pas comme un Sage de
# la personne ; ils sont refermés par `fermer_bases` avant toute saisie
PIDS_GARDES: set[int] = set()


# --------------------------------------------------------------------------------------------- Sage gardé ouvert
# Règle du propriétaire du 2026-11-06 : Sage s'ouvre (multi-utilisateur, bureau caché) au démarrage de l'application
# et se referme à sa fermeture ; les saisies de la journée l'utilisent tel quel (1,5 à 2,5 min gagnées chacune) ;
# l'import (mono-utilisateur) et la nuit le referment d'abord, comme avant. Chacun travaille dans sa propre session
# (Bureau à distance) : une 2e copie de Sage dans la session de l'application n'est jamais nécessaire.
def _marque_sage_garde() -> Path:
    from .__main__ import RACINE

    return Path(RACINE) / "donnees" / "sage_garde.json"


def _marque_mono() -> Path:
    from .__main__ import RACINE

    return Path(RACINE) / "donnees" / "sage_mono.verrou"


def _vivant(pid: int) -> bool:
    poignee = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not poignee:
        return False
    code = wt.DWORD()
    vivant = kernel32.GetExitCodeProcess(poignee, ctypes.byref(code)) and code.value == 259  # STILL_ACTIVE
    kernel32.CloseHandle(poignee)
    return bool(vivant)


def _session_windows(pid: int | None = None) -> int:
    session = wt.DWORD()
    kernel32.ProcessIdToSessionId(pid or kernel32.GetCurrentProcessId(), ctypes.byref(session))
    return session.value


def _lire_marque() -> dict | None:
    try:
        marque = json.loads(_marque_sage_garde().read_text(encoding="utf-8"))
        return marque if isinstance(marque, dict) else None
    except (OSError, ValueError):
        return None


def garde_en_ouverture() -> dict | None:
    """Sage de la journée en train de s'ouvrir (marque « ouverture » = programme qui l'ouvre, encore vivant).
    Constat du 2026-11-06 sur SERVDCSAGE : pendant ces 2 à 3 minutes, ce Sage était pris pour celui d'une personne
    (« Fermez Sage sur le serveur ») et l'outil d'import relancé par les lectures prenait l'entreprise (« Un autre
    utilisateur utilise actuellement cette entreprise sur cet ordinateur »)."""
    marque = _lire_marque()
    if not marque or marque.get("pid") or not marque.get("ouverture"):
        return None
    try:
        return marque if _vivant(int(marque["ouverture"])) else None
    except (TypeError, ValueError):
        return None


def noter_ouverture_garde(fichier, dossier) -> None:
    try:
        _marque_sage_garde().write_text(json.dumps({"ouverture": os.getpid(), "fichier": str(fichier),
                                                    "dossier": str(dossier), "session": _session_windows(),
                                                    "depuis": time.time()}), encoding="utf-8")
    except OSError:
        pass


def oublier_ouverture_garde() -> None:
    """Retire la marque d'ouverture écrite par ce programme (ouverture ratée)."""
    marque = _lire_marque()
    if marque and not marque.get("pid") and int(marque.get("ouverture") or 0) == os.getpid():
        try:
            _marque_sage_garde().unlink()
        except OSError:
            pass


def attendre_fin_ouverture(delai: float = 900, journal=None) -> None:
    """Attend que le Sage de la journée ait fini de s'ouvrir (prêt ou abandonné) — sauf si c'est ce programme qui
    l'ouvre (il s'attendrait lui-même)."""
    marque = garde_en_ouverture()
    if not marque or int(marque.get("ouverture") or 0) == os.getpid():
        return
    if journal:
        journal("Sage est en train de s'ouvrir pour la journée : attente de la fin de l'ouverture…")
    fin = time.time() + delai
    while time.time() < fin:  # la marque passe du programme qui demande Sage à celui qui l'ouvre : on suit
        marque = garde_en_ouverture()
        if not marque or int(marque.get("ouverture") or 0) == os.getpid():
            return
        time.sleep(2)


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def _processus() -> dict[int, tuple[int, str]]:
    """Processus de la machine : {pid: (pid du parent, nom de l'exécutable en minuscules)}."""
    if kernel32 is None:
        return {}
    creer = kernel32.CreateToolhelp32Snapshot
    creer.restype = wt.HANDLE
    instantane = creer(2, 0)  # TH32CS_SNAPPROCESS
    if not instantane or instantane == ctypes.c_void_p(-1).value:
        return {}
    trouves = {}
    try:
        entree = _PROCESSENTRY32W()
        entree.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(instantane, ctypes.byref(entree))
        while ok:
            trouves[int(entree.th32ProcessID)] = (int(entree.th32ParentProcessID), entree.szExeFile.lower())
            ok = kernel32.Process32NextW(instantane, ctypes.byref(entree))
    finally:
        kernel32.CloseHandle(instantane)
    return trouves


def _sages_lances_par(parent: int) -> set[int]:
    """Sage50Accounting.exe dont le parent est `parent` (le programme qui ouvre le Sage de la journée)."""
    return {p for p, (pere, nom) in _processus().items() if pere == parent and nom == "sage50accounting.exe"}


def sages_du_bureau_cache() -> dict[int, int]:
    """Sage50Accounting.exe qui ont une fenêtre sur le bureau caché de l'application : {pid : pid du parent}. Un Sage
    de ce bureau est toujours celui de l'application (une personne travaille sur son bureau à elle)."""
    if user32 is None:
        return {}
    ouvrir = user32.OpenDesktopW
    ouvrir.restype = wt.HANDLE
    ouvrir.argtypes = [wt.LPCWSTR, wt.DWORD, wt.BOOL, wt.DWORD]
    bureau = ouvrir(BUREAU, 0, False, 0x0041)  # DESKTOP_READOBJECTS | DESKTOP_ENUMERATE
    if not bureau:
        return {}
    pids: set[int] = set()

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(h, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        pids.add(int(pid.value))
        return True

    try:
        user32.EnumDesktopWindows(wt.HANDLE(bureau), rappel, 0)
    finally:
        user32.CloseDesktop(wt.HANDLE(bureau))
    tous = _processus()
    return {p: tous[p][0] for p in pids if p in tous and tous[p][1] == "sage50accounting.exe"}


def sages_orphelins() -> set[int]:
    """Sage du bureau caché dont le programme qui l'a lancé n'existe plus (constat du 2026-11-06 sur SERVDCSAGE :
    l'installation de la 1.0.8 a coupé le programme qui gardait Sage pendant sa fermeture ; Sage est resté seul sur
    le bureau caché, a tenu l'entreprise partagée et a été pris pour le Sage d'une personne)."""
    sages = sages_du_bureau_cache()
    if not sages:
        return set()
    tous = _processus()
    return {p for p, pere in sages.items() if pere not in tous}


def attendre_orphelins(delai: float = 240, journal=None) -> None:
    """Un Sage orphelin tient l'entreprise : on attend que l'application l'ait refermé (fil de la journée)."""
    if not sages_orphelins():
        return
    if journal:
        journal("Un Sage resté ouvert sans l'application se referme : attente…")
    fin = time.time() + delai
    while time.time() < fin and sages_orphelins():
        time.sleep(2)
    if sages_orphelins():
        raise ErreurSage("Un Sage resté ouvert sans l'application ne se referme pas : Sage attend sans doute une "
                         "réponse à une question (voir donnees/journal_sage_garde.log). Rien n'a été saisi.")


def sage_garde(fichier=None, meme_session: bool = True) -> dict | None:
    """Sage gardé ouvert par l'application (marque donnees/sage_garde.json), vivant ; `fichier` : seulement s'il est
    ouvert sur ce fichier ; `meme_session` : seulement dans la session Windows de ce programme."""
    try:
        marque = json.loads(_marque_sage_garde().read_text(encoding="utf-8"))
        pid = int(marque["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not _vivant(pid):
        return None
    if fichier and Path(str(marque.get("fichier", ""))).name.upper() != Path(str(fichier)).name.upper():
        return None
    if meme_session and int(marque.get("session", -1)) != _session_windows():
        return None
    return marque


def pids_gardes() -> set[int]:
    """Sage ouverts par l'application (ce programme, ou la marque du Sage gardé) : jamais « le Sage de la personne »."""
    garde = sage_garde(meme_session=False)
    pids = PIDS_GARDES | ({int(garde["pid"])} if garde else set())
    ouverture = garde_en_ouverture()
    if ouverture:  # Sage de la journée en train de s'ouvrir : déjà celui de l'application
        pids = pids | _sages_lances_par(int(ouverture["ouverture"]))
    return pids | set(sages_du_bureau_cache())  # tout Sage du bureau caché est celui de l'application


def noter_sage_garde(pid: int, fichier, dossier) -> None:
    try:
        _marque_sage_garde().write_text(json.dumps({"pid": int(pid), "fichier": str(fichier), "dossier": str(dossier),
                                                    "session": _session_windows(), "depuis": time.time()}),
                                        encoding="utf-8")
    except OSError:
        pass


def oublier_sage_garde(pid: int) -> None:
    try:
        marque = json.loads(_marque_sage_garde().read_text(encoding="utf-8"))
        if int(marque.get("pid", 0)) == int(pid):
            _marque_sage_garde().unlink()
    except (OSError, ValueError, TypeError):
        pass


def liberer_sage_garde(delai: float = 180) -> bool:
    """Referme le Sage gardé ouvert (import, mono-utilisateur, nuit) ; renvoie vrai s'il était ouvert."""
    attendre_fin_ouverture()  # en train de s'ouvrir : on le laisse finir, puis on le referme
    garde = sage_garde(meme_session=False)
    if not garde:
        return False
    try:
        (Path(garde["dossier"]) / "arret").write_text("1", encoding="utf-8")
    except (OSError, KeyError):
        pass
    fin = time.time() + delai
    while time.time() < fin and _vivant(int(garde["pid"])):
        time.sleep(1)
    time.sleep(2)  # l'entreprise finit d'être relâchée
    return True


def _marque_emprunt() -> Path:
    from .__main__ import RACINE

    return Path(RACINE) / "donnees" / "sage_emprunt.json"


def emprunt_en_cours() -> bool:
    """Une saisie utilise en ce moment le Sage gardé ouvert : il n'est refermé qu'après elle."""
    try:
        return _vivant(int(json.loads(_marque_emprunt().read_text(encoding="utf-8"))["pid"]))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def mono_en_cours() -> bool:
    """Un travail mono-utilisateur (import, compte ou article rendu inactif) tient Sage : le Sage gardé attend."""
    try:
        return _vivant(int(_marque_mono().read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        return False


INACTIVITE = "fermée suite à une période d'inactivité"


def inactivite_signalee(session) -> bool:
    """Sage a fermé l'entreprise après une période d'inactivité et demande s'il faut la rouvrir."""
    try:
        return any(INACTIVITE in m.lower() for m in session._messages())
    except Exception:  # noqa: BLE001
        return False


class _Emprunt:
    """Processus du Sage gardé ouvert, utilisé tel quel : jamais arrêté par la session qui l'emprunte."""

    def __init__(self, pid: int):
        self.pid = int(pid)

    def poll(self):
        return None if _vivant(self.pid) else 0

    def kill(self) -> None:  # jamais : il appartient à l'application
        pass


def _marque_lancement() -> Path:
    from .__main__ import RACINE

    return Path(RACINE) / "donnees" / "sage_lancement.json"


def sage_tourne() -> bool:
    """Un Sage, quel qu'il soit (personne, application, en train de se lancer), tourne sur la machine : l'outil
    d'import ne doit alors jamais ouvrir la base (il prendrait l'entreprise : « Un autre utilisateur utilise
    actuellement cette entreprise sur cet ordinateur », constat du 2026-11-06 sur SERVDCSAGE, 1.0.12)."""
    try:
        marque = json.loads(_marque_lancement().read_text(encoding="utf-8"))
        if _vivant(int(marque["pid"])) and time.time() - float(marque["depuis"]) < 300:
            return True
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return any(nom == "sage50accounting.exe" and _vivant(p) for p, (_pere, nom) in _processus().items())


def sage_ouvert() -> bool:
    """Sage 50 tourne-t-il ? Un processus arrêté de force peut rester listé (« zombie », 32 Ko) : il ne compte pas."""
    import csv

    sortie = subprocess.run(["tasklist", "/fo", "csv", "/nh", "/fi", "IMAGENAME eq Sage50Accounting.exe"],
                            capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    for ligne in csv.reader(sortie.splitlines()):
        if len(ligne) < 5 or not ligne[0].lower().startswith("sage50accounting"):
            continue
        if ligne[1].isdigit() and int(ligne[1]) in pids_gardes():
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


def sage_ouvert_dans_cette_session() -> bool:
    """Sage tourne-t-il dans la session Windows de l'application ? Une 2e copie de Sage dans la même session n'ouvre
    pas d'entreprise : elle n'affiche qu'une fenêtre « Sage 50 » (constat du 2026-11-05 sur SERVDCSAGE : « Écran
    d'accueil de Sage absent (['Sage 50']) » après 3 minutes d'attente)."""
    session = wt.DWORD()
    if not kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(session)):
        return sage_ouvert()
    sortie = subprocess.run(["tasklist", "/fo", "csv", "/nh", "/fi", "IMAGENAME eq Sage50Accounting.exe", "/fi",
                             f"SESSION eq {session.value}"], capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    import csv

    for ligne in csv.reader(sortie.splitlines()):
        if len(ligne) >= 5 and ligne[0].lower().startswith("sage50accounting") and ligne[1].isdigit()                 and int(ligne[1]) not in pids_gardes() and int("".join(c for c in ligne[4] if c.isdigit()) or 0) > 1024:
            return True
    return False


def executable_sage(executable_import: Path | None) -> Path | None:
    """Sage50Accounting.exe, à côté de l'outil d'import."""
    if executable_import:
        candidat = Path(executable_import).with_name("Sage50Accounting.exe")
        if candidat.is_file():
            return candidat
    return None


def _attente(texte: str) -> bool:
    """Écran de démarrage ou de chargement de Sage (pas un message d'erreur)."""
    t = texte.lower()
    return any(m in t for m in ("veuillez patienter", "lancement de sage", "chargement", "please wait", "loading"))


def _est_mise_a_jour(titre: str) -> bool:
    import unicodedata

    texte = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode().lower()
    return "mise a jour" in " ".join(texte.split()) or "update" in texte


class SessionSage:
    """Sage 50 ouvert par le robot sur un fichier d'entreprise, en multi-utilisateur (à utiliser sur le bureau caché)."""

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
    def _messages(self) -> list[str]:
        """Texte des fenêtres de message de Sage ouvertes (avertissements, erreurs)."""
        textes = []
        for h in self.fenetres():
            texte = " ".join((self._contenu(e) or _texte(e)).strip() for e in _descendants(h)
                             if ("static" in self._classe(e).lower() or self._classe(e) == "SimplyStat")
                             and user32.IsWindowVisible(e) and (self._contenu(e) or _texte(e)).strip())
            if texte:
                textes.append(texte)
        return textes

    def ouvrir(self, fichier_sai: Path, utilisateur: str, mot_de_passe: str, delai: int = 180,
               mono: bool = False) -> None:
        """Règle du propriétaire du 2026-10-29 : les saisies (et les lectures) se font en MULTI-utilisateur, la
        personne peut ouvrir Sage en même temps ; seul l'import par l'outil d'import exige le mono-utilisateur
        (`mono=True`). Case « mono-utilisateur » de la connexion et question « entreprise partagée »."""
        from .__main__ import fermer_bases

        self.emprunte = False
        attendre_fin_ouverture(journal=self.journal)  # Sage de la journée en train de s'ouvrir : on l'attend
        attendre_orphelins(journal=self.journal)  # Sage resté seul sur le bureau caché : refermé d'abord
        if not mono and self.emprunter(fichier_sai):
            return
        liberer_sage_garde()  # mono-utilisateur, ou Sage gardé hors de ce bureau : une seule copie par session
        try:  # annoncé avant de relâcher la base : la surveillance du serveur web ne relance pas l'outil d'import
            _marque_lancement().write_text(json.dumps({"pid": os.getpid(), "depuis": time.time()}), encoding="utf-8")
            if mono:  # annoncé AVANT : les autres programmes ferment leurs connexions (Sage les refuserait)
                _marque_mono().write_text(str(os.getpid()), encoding="utf-8")
        except OSError:
            pass
        if mono:
            time.sleep(3)  # le serveur web ferme ses connexions (contrôle chaque seconde)
        fermer_bases()  # aucune connexion de l'application ouverte quand Sage ouvre l'entreprise
        from .__main__ import _attendre_fin_outil_import

        _attendre_fin_outil_import()
        if mono:
            try:
                _marque_mono().write_text(str(os.getpid()), encoding="utf-8")
            except OSError:
                pass
        if sage_ouvert_dans_cette_session():
            raise ErreurSage("Sage 50 est déjà ouvert sur ce poste, sur un autre fichier que celui réglé dans "
                             "« Administration > Sage 50 » : ouvrez ce fichier dans Sage, ou fermez Sage, puis "
                             "recommencez.")
        self.processus = subprocess.Popen([str(self.exe)])
        self.journal("Sage lancé.")
        debut = time.time()

        def accueil_ou_message():
            trouve = next((h for h in self.fenetres() if self._bouton(h, "Sélectionner une &entreprise")), None)
            if trouve or time.time() - debut < 60:
                return trouve
            # Sage affiche un message au lieu de l'accueil : inutile d'attendre 3 min ; l'écran de démarrage
            # (« Lancement de Sage 50. Veuillez patienter... », constat du 2026-11-05 sur SERVDCSAGE) n'en est pas un
            messages = [m for m in self._messages() if not _attente(m)]
            return ("message", messages) if messages else None

        accueil = _attendre(accueil_ou_message, delai)
        if isinstance(accueil, tuple):
            raise ErreurSage("Sage n'a pas ouvert son écran d'accueil : « " + " / ".join(accueil[1])[:400] + " ».")
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

        def connexion_ou_partage():
            self._repondre_entreprise_partagee(mono)
            return user32.FindWindowW("#32770", TITRE_CONNEXION)

        connexion = _attendre(connexion_ou_partage, max(90, delai), pas=1)
        if not connexion:
            messages = self._messages()
            if any("autres utilisateurs" in m.lower() or "other users" in m.lower() for m in messages):
                raise ErreurSage(ENTREPRISE_OCCUPEE.format(nom=Path(fichier_sai).name))
            raise ErreurSage(f"Fenêtre de connexion de Sage absente ({[_texte(h) for h in self.fenetres()]}"
                             + (f" ; message : {' | '.join(messages)}" if messages else "") + ").")
        user32.SendMessageW(user32.GetDlgItem(connexion, 21), WM_SETTEXT, 0, ctypes.c_wchar_p(utilisateur))
        user32.SendMessageW(user32.GetDlgItem(connexion, 20), WM_SETTEXT, 0, ctypes.c_wchar_p(mot_de_passe))
        case = user32.GetDlgItem(connexion, 24)  # mono-utilisateur
        if case and bool(user32.SendMessageW(case, 0x00F0, 0, 0)) != mono:  # BM_GETCHECK
            user32.SendMessageW(case, BM_CLICK, 0, 0)
        user32.PostMessageW(connexion, WM_COMMAND, 1, user32.GetDlgItem(connexion, 1))

        nom = Path(fichier_sai).name.upper()
        self.principale = _attendre(lambda: next((h for h in self.fenetres() if _texte(h).upper() == nom), None), delai)
        if not self.principale:
            autres = [_texte(h) for h in self.fenetres()]
            messages = self._messages()  # texte des avertissements de Sage : la vraie raison
            if any("autres utilisateurs" in m.lower() or "other users" in m.lower() for m in messages):
                raise ErreurSage(ENTREPRISE_OCCUPEE.format(nom=Path(fichier_sai).name))
            raise ErreurSage(f"Sage n'a pas ouvert {Path(fichier_sai).name} (fenêtres : {autres}"
                             + (f" ; message : {' | '.join(m for m in messages if m)}" if any(messages) else "")
                             + ") — mot de passe de sysadmin refusé ou fichier utilisé par quelqu'un d'autre ?")
        self.journal(f"Sage ouvert sur {Path(fichier_sai).name}.")
        self.fermer_mise_a_jour(attente=15)

    def emprunter(self, fichier_sai) -> bool:
        """Sage gardé ouvert par l'application sur ce fichier et sur ce bureau : utilisé tel quel (rien à ouvrir)."""
        garde = sage_garde(fichier_sai)
        if not garde:
            return False
        self.processus = _Emprunt(int(garde["pid"]))
        nom = Path(fichier_sai).name.upper()
        self.principale = next((h for h in self.fenetres() if _texte(h).upper() == nom), None)
        if not self.principale:  # sur un autre bureau : invisible d'ici
            self.processus = None
            return False
        self.emprunte = True
        self._avant = set(self.fenetres())
        try:
            _marque_emprunt().write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        except OSError:
            pass
        self.fermer_mise_a_jour()
        self.journal(f"Sage déjà ouvert sur {Path(fichier_sai).name} : utilisé tel quel.")
        return True

    def _rendre(self) -> None:
        """Fin d'un travail dans le Sage gardé : ses fenêtres de travail refermées, Sage laissé ouvert."""
        for titre in ("Encaissements", "Paiements", "Journal général"):
            fenetre = user32.FindWindowW("#32770", titre)
            if fenetre:
                user32.PostMessageW(fenetre, WM_CLOSE, 0, 0)
                time.sleep(2)
                self._confirmer_abandon()
                time.sleep(1)
        for h in [h for h in self.fenetres() if h != self.principale and h not in self._avant]:
            user32.PostMessageW(h, WM_CLOSE, 0, 0)
            time.sleep(1)
            self._confirmer_abandon()
        self.journal("Sage laissé ouvert pour les saisies suivantes.")
        try:
            if int(json.loads(_marque_emprunt().read_text(encoding="utf-8")).get("pid", 0)) == os.getpid():
                _marque_emprunt().unlink()
        except (OSError, ValueError, TypeError):
            pass

    def _repondre_entreprise_partagee(self, mono: bool) -> bool:
        """Entreprise partagée (le vrai fichier, constat du 2026-10-29) : Sage demande « Comment voulez-vous ouvrir
        cette entreprise partagée? » (WinForms : Mono-utilisateur / Multi-utilisateur / Lecture seule, OK).
        Règle du propriétaire : mono-utilisateur pour l'import, multi-utilisateur pour les saisies et la lecture."""
        for h in self.fenetres():
            elements = _descendants(h)
            if not any("entreprise partag" in _texte(e).lower() or "shared company" in _texte(e).lower()
                       for e in elements):
                continue
            mot = "mono" if mono else "multi"
            choix = next((e for e in elements if mot in _texte(e).replace("&", "").lower()), None)
            ok = next((e for e in elements if _texte(e).replace("&", "") == "OK"), None)
            if not choix or not ok:
                raise ErreurSage("Sage demande comment ouvrir l'entreprise partagée, mais ses boutons sont introuvables.")
            for _ in range(3):
                user32.SendMessageW(choix, BM_CLICK, 0, 0)
                time.sleep(0.3)
                if user32.SendMessageW(choix, 0x00F0, 0, 0):  # BM_GETCHECK
                    break
                self._cliquer(choix, h)
            self.journal(f"Entreprise partagée : mode {'mono' if mono else 'multi'}-utilisateur choisi.")
            user32.SendMessageW(ok, BM_CLICK, 0, 0)
            time.sleep(1)
            if user32.IsWindow(h) and user32.IsWindowVisible(h):
                self._cliquer(ok, h)
            return True
        return False

    def fermer_mise_a_jour(self, attente: float = 0) -> bool:
        """Fenêtre « Sage 50 - Mise à jour » (proposition de mise à jour au démarrage, constat du 2026-10-29) :
        elle bloque les autres fenêtres de Sage. Elle est fermée (la mise à jour reste proposée à la personne la
        prochaine fois qu'elle ouvre Sage)."""
        fin = time.time() + attente
        while True:
            fenetre = next((h for h in self.fenetres() if _est_mise_a_jour(_texte(h))), None)
            if fenetre:
                boutons = [e for e in _descendants(fenetre) if self._classe(e).lower().endswith("button")
                           or "button" in self._classe(e).lower()]
                textes = [_texte(e) for e in boutons if _texte(e)]
                plus_tard = next((e for e in boutons if any(m in _texte(e).replace("&", "").lower() for m in (
                    "plus tard", "rappeler", "later", "remind", "annuler", "cancel", "fermer", "close", "non"))), None)
                if plus_tard:
                    user32.SendMessageW(plus_tard, BM_CLICK, 0, 0)
                else:
                    user32.PostMessageW(fenetre, WM_CLOSE, 0, 0)
                self.journal(f"Proposition de mise à jour de Sage fermée (boutons : {textes} ; "
                             f"{'clic sur « ' + _texte(plus_tard) + ' »' if plus_tard else 'fermeture'}).")
                time.sleep(2)
                return not _attendre(lambda: user32.IsWindow(fenetre) and user32.IsWindowVisible(fenetre), 0.5)
            if time.time() >= fin:
                return False
            time.sleep(1)

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

    def _cliquer(self, cible, fenetre=None) -> None:
        """Clic accepté par WinForms hors écran : fenêtre active et bouton gauche marqué enfoncé (état partagé).
        `fenetre` : fenêtre à activer (par défaut la fenêtre principale de Sage)."""
        fenetre = fenetre or self.principale
        fil = user32.GetWindowThreadProcessId(fenetre, None)
        moi = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(moi, fil, True)
        try:
            user32.SetActiveWindow(fenetre)
            etat = (ctypes.c_ubyte * 256)()
            user32.GetKeyboardState(etat)
            etat[1] = 0x80  # VK_LBUTTON
            user32.SetKeyboardState(etat)
            r = wt.RECT()
            user32.GetClientRect(cible, ctypes.byref(r))
            y = min(20, max(1, (r.bottom - r.top) // 2))  # bouton radio bas : clic au milieu de sa hauteur
            position = (y << 16) | min(20, max(1, (r.right - r.left) // 2))
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

    def ouvrir_tache(self, page: str, tache: str, essais: int = 6) -> int:
        """Page du menu de gauche (ex. « Fournisseurs & Achats »), puis la tâche (ex. « Paiements ») ; renvoie la
        fenêtre de la tâche (même titre que la tâche)."""
        lien = _attendre(lambda: self._visible(page), 60)
        if not lien:
            raise ErreurSage(f"Menu « {page} » introuvable dans Sage.")
        for _ in range(essais):
            time.sleep(5)  # Sage termine son chargement après l'affichage de l'accueil
            self.fermer_message_chargement()
            if not self._visible(tache):
                for cible in (lien, user32.GetParent(lien)):  # le libellé, sinon son cadre
                    self._cliquer(cible)
                    if _attendre(lambda: self._visible(tache), 4):
                        break
                continue
            self._cliquer(self._icone(tache))
            fenetre = _attendre(lambda: user32.FindWindowW("#32770", tache), 10)
            if fenetre:
                self.journal(f"Fenêtre {tache} ouverte.")
                return fenetre
        raise ErreurSage(f"La fenêtre {tache} de Sage ne s'ouvre pas.")

    def ouvrir_paiements(self) -> int:
        return self.ouvrir_tache("Fournisseurs & Achats", "Paiements")

    def ouvrir_journal(self) -> int:
        return self.ouvrir_tache("Entreprise", "Journal général")

    # ------------------------------------------------------------ fermeture
    def decrire(self, h) -> tuple[str, list[str], dict[str, int]]:
        """Titre, textes et boutons d'une fenêtre de Sage (contrôles Windows et WinForms, lus par WM_GETTEXT)."""
        textes, boutons = [], {}
        for e in _descendants(h):
            if not user32.IsWindowVisible(e):
                continue
            texte = (self._contenu(e) or _texte(e)).strip()
            if "button" in self._classe(e).lower():
                if texte:
                    boutons[texte.replace("&", "").strip().lower()] = e
            elif texte:
                textes.append(texte)
        return _texte(h), textes, boutons

    def repondre_confirmations(self) -> list[str]:
        """Questions de Sage pendant sa fermeture (constat du 2026-11-06 sur SERVDCSAGE : « Sage 50 - Confirmation »
        restée ouverte, Sage refusait de se fermer) : sauvegarde proposée -> « Non » (l'application fait ses propres
        sauvegardes) ; confirmation de fermeture -> « Oui » ; toute autre question : rien n'est cliqué, le texte est
        rendu pour le journal."""
        notes = []
        for h in self.fenetres():
            if h == self.principale:
                continue
            titre, textes, boutons = self.decrire(h)
            if _est_mise_a_jour(titre) or not (textes or boutons):
                continue
            question = " ".join(textes).lower()
            choix = None
            if "un autre utilisateur utilise actuellement cette entreprise" in question:
                choix = next((k for k in boutons if k in ("ok",)), None)  # ouverture refusée : Sage se ferme seul
            elif INACTIVITE in question or "closed due to inactivity" in question:
                # entreprise fermée par Sage après une période d'inactivité (constat du 2026-11-06 sur SERVDCSAGE) :
                # ne pas la rouvrir, Sage peut alors se fermer
                choix = next((k for k in boutons if k in ("non", "no")), None)
            elif "un autre utilisateur traitait aussi une transaction" in question:
                choix = next((k for k in boutons if k in ("ok",)), None)  # simple avertissement : OK
            elif any(m in question for m in ("sauvegard", "backup", "back up")):
                choix = next((k for k in boutons if k in ("non", "no")), None)
            elif any(m in question for m in ("quitter", "fermer", "exit", "close", "voulez-vous vraiment",
                                              "do you really")):
                choix = next((k for k in boutons if k in ("oui", "yes", "ok")), None)
            note = f"Fenêtre « {titre} » : « {' / '.join(textes)[:300]} » ; boutons {list(boutons)}"
            if choix:
                user32.PostMessageW(boutons[choix], BM_CLICK, 0, 0)
                note += f" ; réponse « {choix} »"
            else:
                note += " ; aucune réponse automatique"
            notes.append(note)
        return notes

    def _confirmer_abandon(self) -> None:
        """Fenêtre fermée avec une saisie non traitée : Sage demande s'il faut la supprimer -> Oui (rien n'est saisi)."""
        for h in self.fenetres():
            if h != self.principale and any("supprimer" in _texte(e) for e in _descendants(h)):
                oui = self._bouton(h, "&Oui") or self._bouton(h, "Oui")
                if oui:
                    user32.PostMessageW(h, WM_COMMAND, user32.GetDlgCtrlID(oui), oui)

    def fermer(self, delai: int = 60) -> None:
        if getattr(self, "emprunte", False):
            if self.processus.poll() is None:
                self._rendre()
            return
        try:
            self._fermer(delai)
        finally:
            try:
                if _marque_mono().read_text(encoding="utf-8").strip() == str(os.getpid()):
                    _marque_mono().unlink()
            except (OSError, ValueError):
                pass

    def _fermer(self, delai: int = 60) -> None:
        if not self.processus or self.processus.poll() is not None:
            return
        from .__main__ import fermer_bases

        fermer_bases()  # Sage se referme proprement seulement si personne d'autre ne tient l'entreprise
        for titre in ("Encaissements", "Paiements", "Journal général"):
            fenetre = user32.FindWindowW("#32770", titre)
            if fenetre:
                user32.PostMessageW(fenetre, WM_CLOSE, 0, 0)
                time.sleep(2)
                self._confirmer_abandon()
                time.sleep(1)
        if self.principale:
            user32.PostMessageW(self.principale, WM_CLOSE, 0, 0)
        fin = time.time() + delai
        vues: set[str] = set()
        while time.time() < fin:  # Sage peut proposer une mise à jour en se fermant (constat du 2026-10-29)
            if _attendre(lambda: self.processus.poll() is not None, 5):
                self.journal("Sage refermé.")
                return
            self.fermer_mise_a_jour()
            for note in self.repondre_confirmations():
                if note not in vues:
                    vues.add(note)
                    self.journal(note)
        restantes = [_texte(h) for h in self.fenetres()]
        if isinstance(self.processus, _Emprunt):  # Sage d'une autre origine : jamais arrêté de force
            self.journal(f"Sage n° {self.processus.pid} ne se referme pas (fenêtres : {restantes} ; "
                         f"messages : {self._messages()}) ; il n'est pas arrêté de force.")
            return
        self.processus.kill()
        self.journal(f"Sage ne se refermait pas (fenêtres : {restantes} ; messages : {self._messages()}) : arrêté.")

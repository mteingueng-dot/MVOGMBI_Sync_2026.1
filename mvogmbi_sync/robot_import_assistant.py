"""Import d'un fichier .IMP par l'« Assistant d'importation des transactions » de Sage (demande du propriétaire du
2026-11-05 : « il faut importer avec l'entreprise partagée, je ne peux et veux pas arrêter le partage »).

Sage_SA_import refuse une entreprise PARTAGÉE (« You cannot use this utility to import transactions into a shared
company… use the Import Transactions Wizard instead ») ; l'assistant de Sage, lui, l'accepte. Relevé du 2026-11-05
sur la copie d'essai (Sage 50 2026.2, en français) :
- l'assistant est grisé en multi-utilisateur : Sage est ouvert en MONO-utilisateur (l'entreprise partagée le
  permet, `SessionSage._repondre_entreprise_partagee`) ;
- fenêtre principale WinForms, menu sans Win32 : clic sur « Fichier » (34, 37 de la fenêtre principale), puis sur
  « Importer/Exporter » (21e ligne du menu, 452 px sous son haut), puis sur « Importer des transactions… » (1re
  ligne du sous-menu, 12 px sous son haut) ; chaque étape est vérifiée (nouvelle fenêtre ouverte) ;
- assistant #32770 « Assistant d'importation des transactions » (pages dans une sous-fenêtre : les contrôles se
  cherchent parmi les descendants VISIBLES) : bouton radio 443 « Importer des factures d'achat, devis d'achat,
  factures de vente… » (442 = journal général), Suivant 12324, page « Sauvegarder » (Suivant), page « Sélectionner
  le fichier » : champ 450 (WM_SETTEXT accepté), Suivant = import ;
- erreur : fenêtre « Importation - Sage 50 » (texte « Erreur d'importation: Ligne 7. Ce numéro de facture existe
  déjà pour ce client. », OK = 2) ; résumé : « Sage 50 - Importation » (Edit 100 : « Le numéro de facture … a été
  ajouté sans problème. », OK = 1).
Les clics se font par PostMessage (une fenêtre modale bloquait SendMessage). Validé : ESSAI ASSIST 1 et 2 importées
dans la copie d'essai (ESSAI CLIENT 1, 1 × ESSAI0001 à 2,00 $).

Le travail se fait sur le bureau caché (commande interne `import-assistant-bureau`) ; pendant que le résumé est
affiché, Sage reste ouvert et la base se lit : l'appelant vérifie les factures (`pendant_resume`) puis écrit le
signal de fermeture.
"""

from __future__ import annotations

import ctypes
import json
import threading
import time
from ctypes import wintypes as wt
from pathlib import Path

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
kernel32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None
BM_CLICK, BM_SETCHECK, WM_SETTEXT, WM_GETTEXT, WM_COMMAND = 0xF5, 0xF1, 0x0C, 0x0D, 0x111
TITRE_ASSISTANT = "Assistant d'importation des transactions"
TITRE_RESUME, TITRE_ERREUR = "Sage 50 - Importation", "Importation - Sage 50"
RADIO_FACTURES, RADIO_JOURNAL, SUIVANT, CHAMP_FICHIER = 443, 442, 12324, 450
FICHIER, IMPORTER_EXPORTER, IMPORTER_TRANSACTIONS = (34, 37), 452, 12   # positions relevées
ATTENTE_SIGNAL = 300  # s : Sage reste ouvert (base lisible) le temps de la vérification par l'appelant


class ErreurAssistant(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------- fenêtres
def _texte(h) -> str:
    tampon = ctypes.create_unicode_buffer(4096)
    user32.SendMessageTimeoutW(h, WM_GETTEXT, 4096, tampon, 0x0002, 2000, None)
    return tampon.value


def _classe(h) -> str:
    tampon = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(h, tampon, 128)
    return tampon.value


def _rect(h) -> tuple[int, int, int, int]:
    r = wt.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _fenetres(pid: int) -> list[int]:
    trouvees = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(h, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            trouvees.append(h)
        return True

    user32.EnumWindows(rappel, 0)
    return trouvees


def _descendants(h) -> list[int]:
    trouves = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(e, _):
        trouves.append(e)
        return True

    user32.EnumChildWindows(h, rappel, 0)
    return trouves


def _controle(h, ident: int):
    return next((e for e in _descendants(h) if user32.GetDlgCtrlID(e) == ident and user32.IsWindowVisible(e)), None)


def _dialogue(pid: int, debut_titre: str):
    return next((h for h in _fenetres(pid) if _classe(h) == "#32770" and _texte(h).startswith(debut_titre)), None)


def _menus(pid: int, principale) -> list[int]:
    """Menus déroulants WinForms ouverts (fenêtres du processus autres que la principale)."""
    return [h for h in _fenetres(pid) if h != principale and _classe(h).startswith("WindowsForms")
            and "Window.20808" in _classe(h)]


def _nouvelle(pid: int, avant: set, exclues=()) -> int | None:
    """Fenêtre du processus apparue depuis `avant` (menu déroulant : sa classe varie d'un poste à l'autre, constat
    du 2026-11-05 sur SERVDCSAGE : menu ouvert mais pas reconnu) ; la plus petite (un menu, pas une fenêtre)."""
    nouvelles = [h for h in _fenetres(pid) if h not in avant and h not in exclues and _classe(h) != "#32770"
                 and not _classe(h).startswith(("UAC", "SysShadow", "Internet", "tooltips"))]
    if not nouvelles:
        return None

    def surface(h):
        g, hh, d, b = _rect(h)
        return (d - g) * (b - hh)

    candidates = [h for h in nouvelles if surface(h) > 2000]
    return min(candidates, key=surface) if candidates else None


def _fenetre_au_point(racine, x: int, y: int):
    h = racine
    while True:
        pt = wt.POINT(x, y)
        user32.ScreenToClient(h, ctypes.byref(pt))
        enfant = user32.ChildWindowFromPointEx(h, pt, 0x0001 | 0x0004)  # sans fenêtres invisibles ni transparentes
        if not enfant or enfant == h:
            return h
        h = enfant


def _clic(fenetre, x: int, y: int) -> None:
    """Clic accepté par WinForms sur le bureau caché (fenêtre active, bouton gauche marqué enfoncé)."""
    cible = _fenetre_au_point(fenetre, x, y)
    pt = wt.POINT(x, y)
    user32.ScreenToClient(cible, ctypes.byref(pt))
    position = (pt.y << 16) | (pt.x & 0xFFFF)
    fil = user32.GetWindowThreadProcessId(fenetre, None)
    moi = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(moi, fil, True)
    try:
        user32.SetActiveWindow(fenetre)
        etat = (ctypes.c_ubyte * 256)()
        user32.GetKeyboardState(etat)
        etat[1] = 0x80  # VK_LBUTTON
        user32.SetKeyboardState(etat)
        user32.PostMessageW(cible, 0x200, 1, position)
        user32.PostMessageW(cible, 0x201, 1, position)
        time.sleep(0.3)
        etat[1] = 0
        user32.SetKeyboardState(etat)
        user32.PostMessageW(cible, 0x202, 0, position)
        time.sleep(0.5)
    finally:
        user32.AttachThreadInput(moi, fil, False)


def photo(h, chemin: Path) -> Path | None:
    """Image d'une fenêtre (PrintWindow : marche sur le bureau caché)."""
    from PIL import Image

    gauche, haut, droite, bas = _rect(h)
    largeur, hauteur = droite - gauche, bas - haut
    if largeur <= 0 or hauteur <= 0:
        return None
    gdi = ctypes.windll.gdi32
    dc = user32.GetWindowDC(h)
    mdc = gdi.CreateCompatibleDC(dc)
    bmp = gdi.CreateCompatibleBitmap(dc, largeur, hauteur)
    gdi.SelectObject(mdc, bmp)
    user32.PrintWindow(h, mdc, 2)

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]

    tampon = ctypes.create_string_buffer(largeur * hauteur * 4)
    infos = BMI(ctypes.sizeof(BMI), largeur, -hauteur, 1, 32, 0, 0, 0, 0, 0, 0)
    gdi.GetDIBits(mdc, bmp, 0, hauteur, tampon, ctypes.byref(infos), 0)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mdc)
    user32.ReleaseDC(h, dc)
    image = Image.frombuffer("RGBA", (largeur, hauteur), tampon, "raw", "BGRA", 0, 1).convert("RGB")
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    image.resize((largeur * 2, hauteur * 2)).save(chemin)  # agrandie : l'OCR lit mieux les petits caractères
    return chemin


def position_du_texte(h, cherche: str, dossier: Path) -> tuple[int, int] | None:
    """Point (écran) du libellé `cherche` dans la fenêtre `h` (menu WinForms sans contrôles) : photo + OCR de Windows.
    Le menu de Sage diffère d'un poste à l'autre (constat du 2026-11-05 : positions de ce poste fausses sur le
    serveur)."""
    import unicodedata

    from .ocr_windows import mots_image

    def simple(texte: str) -> str:
        return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()

    image = photo(h, Path(dossier) / f"menu_{h}.png")
    if image is None:
        return None
    gauche, haut = _rect(h)[:2]
    for mot in mots_image(image):
        if simple(cherche) in simple(mot.get("t", "")):
            return gauche + int(mot["x"]) // 2 + 10, haut + (int(mot["y"]) + int(mot.get("h", 0)) // 2) // 2
    return None


def _attendre(condition, delai: float, pas: float = 0.5):
    fin = time.time() + delai
    while time.time() < fin:
        resultat = condition()
        if resultat:
            return resultat
        time.sleep(pas)
    return None


# --------------------------------------------------------------------------------------------- assistant
def _fermer_menus(pid: int, principale) -> None:
    for m in _menus(pid, principale):
        user32.PostMessageW(m, 0x0100, 0x1B, 0)  # Échap
    time.sleep(0.5)


def ouvrir_assistant(pid: int, principale, journal=print, diagnostic: Path | None = None):
    """Fichier > Importer/Exporter > Importer des transactions… ; renvoie la fenêtre de l'assistant. Les lignes du menu
    sont repérées par leur texte (OCR), sinon aux positions relevées sur la copie d'essai ; en cas d'échec, les photos
    du menu restent dans `diagnostic` (donnees/diagnostic_assistant/)."""
    import tempfile

    dossier = Path(diagnostic) if diagnostic else Path(tempfile.mkdtemp())
    dossier.mkdir(parents=True, exist_ok=True)
    gauche, haut = _rect(principale)[:2]
    for essai in range(5):
        _fermer_menus(pid, principale)
        if essai == 0:
            photo(principale, dossier / "fenetre_principale.png")
        point = None
        try:
            point = position_du_texte(principale, "Fichier", dossier) if essai else None
        except Exception as exc:  # noqa: BLE001 — OCR indisponible : positions relevées
            journal(f"OCR du menu : {exc}")
        avant = set(_fenetres(pid))
        _clic(principale, *(point or (gauche + FICHIER[0], haut + FICHIER[1])))
        menu = _attendre(lambda: next(iter(_menus(pid, principale)), None) or _nouvelle(pid, avant, (principale,)),
                         8)
        if not menu:
            journal(f"Menu Fichier pas ouvert (essai {essai + 1} ; fenêtres : "
                    f"{[(_classe(h), _texte(h)[:30]) for h in _fenetres(pid)]}).")
            time.sleep(3 + 3 * essai)  # Sage encore occupé (entreprise partagée : synchronisation)
            continue
        photo(menu, dossier / f"menu_fichier_{essai + 1}.png")
        g, h = _rect(menu)[:2]
        try:
            point = position_du_texte(menu, "Importer/Exporter", dossier) or position_du_texte(menu, "Importer",
                                                                                              dossier)
        except Exception as exc:  # noqa: BLE001
            journal(f"OCR du menu : {exc}")
            point = None
        avant = set(_fenetres(pid))
        _clic(menu, *(point or (g + 80, h + IMPORTER_EXPORTER)))
        sous = _attendre(lambda: next((m for m in _menus(pid, principale) if m != menu), None)
                         or _nouvelle(pid, avant, (principale, menu)), 8)
        if not sous:
            journal(f"Sous-menu Importer/Exporter pas ouvert (essai {essai + 1}, point {point}).")
            continue
        g, h = _rect(sous)[:2]
        try:
            point = position_du_texte(sous, "transactions", dossier)
        except Exception as exc:  # noqa: BLE001
            journal(f"OCR du sous-menu : {exc}")
            point = None
        _clic(sous, *(point or (g + 64, h + IMPORTER_TRANSACTIONS)))
        assistant = _attendre(lambda: _dialogue(pid, TITRE_ASSISTANT), 15)
        if assistant:
            return assistant
        journal(f"Assistant d'importation pas encore ouvert (essai {essai + 1}, point {point}).")
        photo(sous, dossier / f"sous_menu_{essai + 1}.png") if user32.IsWindow(sous) else None
    raise ErreurAssistant("L'assistant « Importer des transactions » de Sage ne s'ouvre pas (menu Fichier > "
                          f"Importer/Exporter : Sage doit être en mono-utilisateur). Photos du menu : {dossier}")


def importer(pid: int, assistant, fichier_imp: Path, delai: int = 1800) -> tuple[str, list[str], object]:
    """Remplit l'assistant et lance l'import ; renvoie (résumé, erreurs, fenêtre du résumé ou None)."""
    page = _controle(assistant, RADIO_FACTURES)
    if not page:
        raise ErreurAssistant("Assistant d'importation : choix « factures » introuvable.")
    for ident in (RADIO_JOURNAL, RADIO_FACTURES):
        user32.SendMessageW(_controle(assistant, ident), BM_SETCHECK, int(ident == RADIO_FACTURES), 0)
    user32.SendMessageW(assistant, WM_COMMAND, RADIO_FACTURES, page)
    for titre in ("Sauvegarder", "Sélectionner le fichier"):
        user32.PostMessageW(_controle(assistant, SUIVANT), BM_CLICK, 0, 0)
        if not _attendre(lambda: titre in _texte(assistant), 20):
            raise ErreurAssistant(f"Assistant d'importation : page « {titre} » absente ({_texte(assistant)}).")
    champ = _attendre(lambda: _controle(assistant, CHAMP_FICHIER), 10)
    user32.SendMessageW(champ, WM_SETTEXT, 0, ctypes.c_wchar_p(str(fichier_imp)))
    user32.SendMessageW(user32.GetParent(champ), WM_COMMAND, (0x300 << 16) | CHAMP_FICHIER, champ)  # EN_CHANGE
    if _texte(champ) != str(fichier_imp):
        raise ErreurAssistant("Assistant d'importation : le nom du fichier n'a pas été accepté.")
    user32.PostMessageW(_controle(assistant, SUIVANT), BM_CLICK, 0, 0)
    erreurs: list[str] = []
    fin = time.time() + delai
    calme = None
    while time.time() < fin:
        resume = _dialogue(pid, TITRE_RESUME)
        if resume:
            return _texte(_controle(resume, 100) or resume), erreurs, resume
        erreur = _dialogue(pid, TITRE_ERREUR)
        autres = [h for h in _fenetres(pid) if _classe(h) == "#32770" and h not in (assistant, erreur)
                  and not _texte(h).startswith(TITRE_RESUME)]
        if erreur or autres:
            for h in [x for x in [erreur] + autres if x]:
                texte = " ".join(_texte(e).strip() for e in _descendants(h)
                                 if _classe(e) in ("Static", "SimplyStat", "Edit") and _texte(e).strip())
                erreurs.append(f"{_texte(h)} : {texte}" if texte else _texte(h))
                bouton = next((_controle(h, i) for i in (2, 1, 7, 102) if _controle(h, i)), None)  # OK / Non
                if bouton:
                    user32.PostMessageW(bouton, BM_CLICK, 0, 0)
            calme = None
            time.sleep(1)
            continue
        if erreurs and user32.IsWindowVisible(assistant) and "Sélectionner le fichier" in _texte(assistant):
            calme = calme or time.time()  # revenu à la page du fichier après une erreur : l'import est arrêté
            if time.time() - calme > 8:
                return "", erreurs, None
        if not user32.IsWindow(assistant):
            return "", erreurs, None
        time.sleep(0.5)
    erreurs.append(f"L'assistant d'importation ne s'est pas terminé après {delai} s.")
    return "", erreurs, None


def fermer_assistant(pid: int, assistant, resume=None) -> None:
    if resume and user32.IsWindow(resume):
        user32.PostMessageW(_controle(resume, 1) or resume, BM_CLICK, 0, 0)
        time.sleep(2)
    if assistant and user32.IsWindow(assistant) and user32.IsWindowVisible(assistant):
        bouton = _controle(assistant, 2)  # Annuler
        if bouton:
            user32.PostMessageW(bouton, BM_CLICK, 0, 0)
            time.sleep(2)


def travail_bureau(config_toml: dict, fichier_imp: Path, fichier_sai: Path, sortie: Path, signal: Path,
                   journal=print) -> None:
    """Commande interne `import-assistant-bureau` (bureau caché) : Sage ouvert en mono-utilisateur, import par
    l'assistant, résumé écrit dans `sortie`, Sage gardé ouvert jusqu'au `signal` de l'appelant, puis refermé."""
    from . import coffre
    from .__main__ import executable_import
    from .sage_bureau import SessionSage, executable_sage, sage_ouvert_dans_cette_session

    bilan = {"termine": False, "resume": "", "erreurs": []}
    session = None
    try:
        if sage_ouvert_dans_cette_session():
            raise ErreurAssistant("Sage est ouvert : fermez-le, l'application l'ouvre elle-même pour l'import.")
        exe = executable_sage(executable_import())
        if not exe:
            raise ErreurAssistant("Sage50Accounting.exe introuvable.")
        session = SessionSage(exe, journal)
        utilisateur = str(config_toml.get("sage_import", {}).get("utilisateur", "sysadmin"))
        session.ouvrir(Path(fichier_sai), utilisateur, coffre.lire(coffre.SAGE_IMPORT, ""), mono=True)
        from .__main__ import RACINE

        assistant = ouvrir_assistant(session.processus.pid, session.principale, journal,
                                     Path(RACINE) / "donnees" / "diagnostic_assistant")
        resume, erreurs, fenetre_resume = importer(session.processus.pid, assistant, Path(fichier_imp))
        bilan.update(termine=True, resume=resume, erreurs=erreurs)
        sortie.write_text(json.dumps(bilan, ensure_ascii=False), encoding="utf-8")
        _attendre(signal.exists, ATTENTE_SIGNAL)  # l'appelant vérifie les factures, Sage ouvert
        fermer_assistant(session.processus.pid, assistant, fenetre_resume)
    except Exception as exc:  # noqa: BLE001 — noté dans le bilan
        bilan["erreurs"].append(str(exc))
        sortie.write_text(json.dumps(bilan, ensure_ascii=False), encoding="utf-8")
    finally:
        if session is not None and session.processus:
            session.fermer()


def importer_par_assistant(fichier_imp: Path, fichier_sai: Path, pendant_resume=None, delai: int = 1800):
    """Appelée par `sage_auto.executer` : même résultat (`ResultatSage`) que l'outil d'import."""
    import tempfile

    from .__main__ import RACINE, commande_moteur
    from .sage_auto import ResultatSage
    from .sage_bureau import executer_sur_bureau_cache

    resultat = ResultatSage()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        sortie, signal = Path(dossier) / "bilan.json", Path(dossier) / "fermer.signal"
        code = {}
        fil = threading.Thread(target=lambda: code.update(r=executer_sur_bureau_cache(
            commande_moteur() + ["import-assistant-bureau", "--imp", str(fichier_imp), "--sai", str(fichier_sai),
                                 "--resultat", str(sortie), "--signal", str(signal)], RACINE, delai=delai + 600)),
            daemon=True)
        fil.start()
        _attendre(lambda: sortie.exists() or not fil.is_alive(), delai + 600, 1)
        bilan = {}
        try:
            bilan = json.loads(sortie.read_text(encoding="utf-8")) if sortie.exists() else {}
        except ValueError:
            pass
        resultat.resume = bilan.get("resume", "")
        resultat.erreurs = list(bilan.get("erreurs", []))
        if bilan.get("termine") and pendant_resume:
            try:
                pendant_resume(resultat.resume)  # Sage encore ouvert : la base se lit
            except Exception as exc:  # noqa: BLE001
                resultat.erreurs.append(f"Vérification après l'import : {exc}")
        signal.write_text("1", encoding="utf-8")
        fil.join(600)
        resultat.termine = bool(bilan.get("termine"))
        resultat.code_retour = code.get("r")
        if not bilan:
            resultat.erreurs.append("L'assistant d'importation de Sage n'a rien rendu.")
    return resultat

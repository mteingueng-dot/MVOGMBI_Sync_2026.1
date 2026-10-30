"""Création d'un article de stock dans Sage 50 : la fenêtre « Enregistrements des stocks & services » est remplie
comme une personne le ferait (Sage n'importe pas d'article par fichier .IMP).

Relevé sur la copie d'essai (2026-10-28) : Numéro = SimplyChar 23, Description = SimplyChar 24, Type « Stock » =
bouton 30 ; onglet « Associé » : listes Actif 77, Produits 73, CMV 74, Écart 78 (éléments « 1513 Inventaire … ») ;
« Enreg. et Fermer » = 1002. L'article est ensuite cherché dans la base (tinvent.sPartCode) : seule sa présence fait
foi.

Correction des comptes d'un article existant (demande du propriétaire du 2026-10-28) : la liste de la barre d'outils
de la fiche (ComboBox 504, éléments « N°  Description ») choisit l'article affiché ; les comptes sont changés dans
l'onglet « Associé » (affiché par les flèches du clavier dans la barre d'onglets : Sage ignore un changement fait dans
un onglet caché, et une sélection qui ne vient pas du clavier) ; Sage enregistre l'article quitté en passant au
suivant (3 essais : juste après un enregistrement, la 1re demande est parfois ignorée), puis « Enreg. et Fermer »
pour le dernier. Validé sur la copie d'essai le 2026-10-28 : 7 articles sans compte de produits corrigés.
Les comptes sont ensuite relus dans la base (tinvent.lAcNAsset, lAcNRev, lAcNExp, lAcNVar).
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass, field

from .robot_encaissements import (CB_SETCURSEL, CBN_SELCHANGE, EN_CHANGE, EN_KILLFOCUS, WM_COMMAND, WM_SETTEXT,
                                  ErreurRobot, FenetreEncaissements, _classe, user32)

TITRE = "Enregistrements des stocks & services"
ID_NUMERO, ID_DESCRIPTION, ID_STOCK, ID_SERVICE = 23, 24, 30, 31
ID_ACTIF, ID_PRODUITS, ID_CMV, ID_ECART = 77, 73, 74, 78
ID_ENREGISTRER_FERMER = 1002
ID_NAVIGATION = 504  # liste de la barre d'outils : article affiché dans la fiche
BM_CLICK = 0x00F5
LONGUEUR_NUMERO, LONGUEUR_DESCRIPTION = 20, 75  # limites des champs de Sage


@dataclass
class ArticleACreer:
    numero: str
    description: str
    actif: str      # « 1513 »
    produits: str   # « 4013 »
    cmv: str        # « 5013 » ; pour un service : compte de CHARGES (5xxx)
    ecart: str = ""  # vide = même compte que le CMV
    service: bool = False  # article de service (n° « S… ») : comptes Produits (facultatif) et Charges seulement


@dataclass
class ResultatArticle:
    numero: str
    cree: bool = False
    messages: list[str] = field(default_factory=list)


class FenetreArticle(FenetreEncaissements):
    """La fenêtre « Enregistrements des stocks & services » ouverte sur un nouvel article."""

    titre = TITRE

    def __init__(self, hwnd: int | None = None):
        self.h = hwnd or user32.FindWindowW("#32770", self.titre)
        if not self.h:
            raise ErreurRobot(f"La fenêtre « {self.titre} » de Sage n'est pas ouverte.")
        import ctypes.wintypes as wt
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(self.h, ctypes.byref(pid))
        self.pid = pid.value

    def lire(self, ident: int) -> str:
        tampon = ctypes.create_unicode_buffer(256)
        user32.SendMessageW(user32.GetDlgItem(self.h, ident), 0x000D, 256, tampon)
        return tampon.value

    def ecrire(self, ident: int, texte: str) -> None:
        champ = user32.GetDlgItem(self.h, ident)
        user32.SendMessageW(champ, WM_SETTEXT, 0, ctypes.c_wchar_p(texte))
        user32.SendMessageW(self.h, WM_COMMAND, (EN_CHANGE << 16) | ident, champ)
        user32.SendMessageW(self.h, WM_COMMAND, (EN_KILLFOCUS << 16) | ident, champ)
        time.sleep(0.3)

    def compte(self, ident: int, numero: str) -> str:
        return self.choisir(ident, f"{numero} ")

    def remplir(self, a: ArticleACreer) -> None:
        if self.lire(ID_NUMERO).strip():
            raise ErreurRobot(f"La fenêtre affiche déjà l'article « {self.lire(ID_NUMERO)} » : rien n'est modifié.")
        self.ecrire(ID_NUMERO, a.numero)
        self.ecrire(ID_DESCRIPTION, a.description[:LONGUEUR_DESCRIPTION])
        if a.service:
            # relevé du 2026-10-29 : « Service » = bouton 31 ; l'onglet « Associé » n'a plus que Produits (73) et
            # Charges (74, le même champ que le CMV d'un article de stock)
            user32.SendMessageW(user32.GetDlgItem(self.h, ID_SERVICE), BM_CLICK, 0, 0)
            time.sleep(0.8)
            if a.produits:
                self.compte(ID_PRODUITS, a.produits)
            self.compte(ID_CMV, a.cmv)
        else:
            user32.SendMessageW(user32.GetDlgItem(self.h, ID_STOCK), BM_CLICK, 0, 0)
            time.sleep(0.5)
            self.compte(ID_ACTIF, a.actif)
            self.compte(ID_PRODUITS, a.produits)
            self.compte(ID_CMV, a.cmv)
            self.compte(ID_ECART, a.ecart or a.cmv)
        if self.lire(ID_NUMERO) != a.numero:
            raise ErreurRobot(f"Le numéro n'a pas pu être saisi (lu : « {self.lire(ID_NUMERO)} »).")

    def _navigation(self) -> int:
        from .sage_bureau import _descendants

        for e in _descendants(self.h):
            if user32.GetDlgCtrlID(e) == ID_NAVIGATION and _classe(e) == "ComboBox":
                return e
        raise ErreurRobot("La liste des articles de la fiche Sage est introuvable.")

    @staticmethod
    def _elements(cb) -> list[str]:
        n = user32.SendMessageW(cb, 0x0146, 0, 0)  # CB_GETCOUNT
        elements = []
        for i in range(max(n, 0)):
            tampon = ctypes.create_unicode_buffer(user32.SendMessageW(cb, 0x0149, i, 0) + 2)  # CB_GETLBTEXTLEN
            user32.SendMessageW(cb, 0x0148, i, tampon)  # CB_GETLBTEXT
            elements.append(tampon.value)
        return elements

    def aller(self, numero: str, resultat: ResultatArticle | None = None) -> None:
        """Affiche l'article `numero` dans la fiche (Sage enregistre l'article quitté)."""
        if self.lire(ID_NUMERO).strip() == numero:
            return
        cb = self._navigation()
        index = next((i for i, e in enumerate(self._elements(cb)) if e.split("  ")[0].strip() == numero), None)
        if index is None:
            raise ErreurRobot(f"L'article {numero} n'est pas dans la liste de la fiche Sage.")
        deja = set(self.dialogues())
        for _ in range(3):  # juste après l'enregistrement d'un article, Sage ignore parfois la 1re demande
            if self.lire(ID_NUMERO).strip() == numero:
                break
            self._choisir_navigation(cb, index, numero, deja, resultat)
        if self.lire(ID_NUMERO).strip() != numero:
            raise ErreurRobot(f"La fiche Sage n'affiche pas l'article {numero}.")
        time.sleep(0.5)

    def _choisir_navigation(self, cb, index: int, numero: str, deja: set, resultat) -> None:
        user32.SendMessageW(cb, CB_SETCURSEL, index, 0)
        user32.PostMessageW(user32.GetParent(cb), WM_COMMAND, (CBN_SELCHANGE << 16) | ID_NAVIGATION, cb)
        fin = time.time() + 5
        while time.time() < fin and self.lire(ID_NUMERO).strip() != numero:
            for d in [d for d in self.dialogues() if d not in deja]:
                texte = self.message(d)
                if resultat is not None:
                    resultat.messages.append(texte)
                if "enregistr" in texte.lower() or "save" in texte.lower():
                    self.repondre(d, ("oui", "yes", "ok"))  # enregistrer l'article quitté
                elif not (self.repondre(d, ("non", "no", "annuler", "cancel")) or self.repondre(d, ("ok",))):
                    user32.PostMessageW(d, 0x0010, 0, 0)
                deja.add(d)
            time.sleep(0.3)

    def modifie(self) -> bool:
        """Sage a vu un changement : « Enreg. et Fermer » n'est plus grisé."""
        return bool(user32.IsWindowEnabled(user32.GetDlgItem(self.h, ID_ENREGISTRER_FERMER)))

    def compte_saisi(self, ident: int, numero: str, journal=None) -> None:
        """Choisit le compte comme une personne (onglet « Associé » affiché) : la liste prend le focus clavier,
        l'élément est choisi par une flèche du clavier, puis le focus passe à la description ; Sage voit alors un
        changement (« Enreg. et Fermer » actif). Sinon, le n° est tapé dans la liste."""
        cb = user32.GetDlgItem(self.h, ident)
        elements = self._elements(cb)
        index = next((i for i, e in enumerate(elements) if e.startswith(f"{numero} ")), None)
        if index is None:
            raise ErreurRobot(f"Compte {numero} absent de la liste de Sage.")
        from .sage_bureau import kernel32

        fil, moi = user32.GetWindowThreadProcessId(self.h, None), kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(moi, fil, True)  # focus clavier dans la fiche, comme après un clic
        try:
            user32.SetActiveWindow(self.h)
            user32.SetFocus(cb)
            time.sleep(0.2)
            user32.SendMessageW(cb, CB_SETCURSEL, max(index - 1, 0), 0)
            touche = 0x28 if index > 0 else 0x26  # flèche bas (ou haut pour le 1er élément) : changement au clavier
            if index == 0:
                user32.SendMessageW(cb, CB_SETCURSEL, 1, 0)
            user32.SendMessageW(cb, 0x0100, touche, 0)  # WM_KEYDOWN
            user32.SendMessageW(cb, 0x0101, touche, 0xC0000000)  # WM_KEYUP
            time.sleep(0.4)
            user32.SetFocus(user32.GetDlgItem(self.h, ID_DESCRIPTION))  # quitter la liste : Sage valide
            time.sleep(0.4)
        finally:
            user32.AttachThreadInput(moi, fil, False)
        if self.modifie() and self.lire(ident).startswith(f"{numero} "):
            return
        edit = user32.FindWindowExW(cb, None, "Edit", None)  # saisie au clavier dans la liste
        if edit:
            user32.SendMessageW(edit, 0x00B1, 0, -1)  # EM_SETSEL : tout sélectionner
            for caractere in numero:
                user32.PostMessageW(edit, 0x0102, ord(caractere), 0)  # WM_CHAR
                time.sleep(0.05)
            user32.PostMessageW(edit, 0x0100, 0x09, 1)  # Tab : valide
            user32.PostMessageW(edit, 0x0101, 0x09, 0xC0000001)
            time.sleep(1)

    def onglet_comptes(self) -> None:
        """Affiche l'onglet « Associé » (les listes de comptes) : Sage ignore un changement fait dans un onglet caché
        (constat du 2026-10-28). Les flèches du clavier envoyées à la barre d'onglets changent d'onglet comme une
        personne, jusqu'à ce que la liste « Produits » soit visible."""
        from .sage_bureau import _descendants

        onglets = next((e for e in _descendants(self.h) if _classe(e) == "SysTabControl32"), None)
        produits = user32.GetDlgItem(self.h, ID_PRODUITS)
        if not onglets:
            raise ErreurRobot("Barre d'onglets de la fiche introuvable.")
        for touche in [0x24] + [0x27] * 12:  # Début, puis flèche droite
            if user32.IsWindowVisible(produits):
                return
            user32.SendMessageW(onglets, 0x0100, touche, 0)  # WM_KEYDOWN
            user32.SendMessageW(onglets, 0x0101, touche, 0xC0000000)  # WM_KEYUP
            time.sleep(0.4)
        if not user32.IsWindowVisible(produits):
            raise ErreurRobot("L'onglet des comptes (« Associé ») ne s'affiche pas.")

    def modifier(self, a: ArticleACreer, journal=None) -> None:
        """Comptes de l'article affiché (seuls ceux qui diffèrent sont changés), dans l'onglet « Associé »."""
        if self.lire(ID_NUMERO).strip() != a.numero:
            raise ErreurRobot(f"La fiche n'affiche pas l'article {a.numero} : rien n'est modifié.")
        self.onglet_comptes()
        for ident, compte in ((ID_ACTIF, a.actif), (ID_PRODUITS, a.produits), (ID_CMV, a.cmv),
                              (ID_ECART, a.ecart or a.cmv)):
            if compte and not self.lire(ident).startswith(f"{compte} "):
                self.compte_saisi(ident, compte, journal)

    def enregistrer(self, resultat: ResultatArticle) -> None:
        """« Enreg. et Fermer » ; toute question de Sage est notée puis refusée (rien n'est forcé)."""
        deja = set(self.dialogues())  # autres fenêtres de Sage déjà ouvertes : jamais touchées
        user32.PostMessageW(self.h, WM_COMMAND, ID_ENREGISTRER_FERMER, user32.GetDlgItem(self.h, ID_ENREGISTRER_FERMER))
        for _ in range(4):
            fin = time.time() + 3
            nouveaux = []
            while time.time() < fin and not nouveaux and user32.IsWindow(self.h):
                nouveaux = [d for d in self.dialogues() if d not in deja]
                time.sleep(0.2)
            for d in nouveaux:
                texte = self.message(d)
                resultat.messages.append(texte)
                if not (self.repondre(d, ("non", "annuler")) or self.repondre(d, ("ok",))):
                    user32.PostMessageW(d, 0x0010, 0, 0)
                time.sleep(1)
            if not user32.IsWindow(self.h):
                return
        time.sleep(1)


def creer(fenetre: FenetreArticle, a: ArticleACreer, present) -> ResultatArticle:
    """Remplit la fenêtre ouverte, enregistre, puis vérifie dans la base (`present(numero)` -> bool)."""
    r = ResultatArticle(a.numero)
    fenetre.remplir(a)
    fenetre.enregistrer(r)
    for _ in range(10):
        if present(a.numero):
            r.cree = True
            break
        time.sleep(1)
    if not r.cree and not r.messages:
        r.messages.append("article absent de Sage après l'enregistrement")
    return r


# ----------------------------------------------------------------------------- ouverture de la fiche dans Sage
TITRE_LISTE, CLASSE_LISTE = "Stocks & Services", "SimplyLedger"
COMMANDE_CREER = 3001  # liste « Stocks & Services » : nouvelle fiche
COMMANDE_OUVRIR = 3000  # fiche de l'article sélectionné (modification)


def icone_tache(session, libelle: str):
    """Icône d'une tâche de l'accueil : l'image (environ 72 × 48) placée juste au-dessus de son libellé, dans le cadre
    du libellé ou celui d'au-dessus (le même libellé existe aussi dans le menu de gauche, sans icône)."""
    import ctypes.wintypes as wt

    from .sage_bureau import _descendants, _texte

    def rect(h):
        r = wt.RECT()
        user32.GetWindowRect(h, ctypes.byref(r))
        return r

    for e in _descendants(session.principale):
        if _texte(e) != libelle or not user32.IsWindowVisible(e):
            continue
        r_e = rect(e)
        parent = user32.GetParent(e)
        candidats = []
        for cadre in (parent, user32.GetParent(parent)):
            for f in _descendants(cadre):
                if user32.GetParent(f) != cadre or f in (e, parent) or not user32.IsWindowVisible(f):
                    continue
                r = rect(f)
                largeur, hauteur = r.right - r.left, r.bottom - r.top
                if 40 <= largeur <= 100 and 30 <= hauteur <= 70 and r.bottom <= r_e.top + 4                         and r.left < r_e.right and r.right > r_e.left:
                    candidats.append((r_e.top - r.bottom, f))
        if candidats:
            return min(candidats)[1]
    return None


def cliquer_vrai(cible: int) -> None:
    """Vrai clic de souris au centre de `cible` (Sage de la personne, au premier plan : WinForms n'y accepte pas les
    clics simulés), puis la souris revient où elle était."""
    import ctypes.wintypes as wt

    r, avant = wt.RECT(), wt.POINT()
    user32.GetWindowRect(cible, ctypes.byref(r))
    user32.GetCursorPos(ctypes.byref(avant))
    user32.SetCursorPos((r.left + r.right) // 2, (r.top + r.bottom) // 2)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # bouton gauche enfoncé
    time.sleep(0.08)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # relâché
    time.sleep(0.3)
    user32.SetCursorPos(avant.x, avant.y)


def premier_plan(fenetre: int) -> None:
    """Met la fenêtre principale de Sage au premier plan (restaurée si elle est réduite)."""
    from .sage_bureau import kernel32

    if user32.IsIconic(fenetre):
        user32.ShowWindow(fenetre, 9)  # SW_RESTORE
    fil = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    moi = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(moi, fil, True)
    try:
        user32.BringWindowToTop(fenetre)
        user32.SetForegroundWindow(fenetre)
    finally:
        user32.AttachThreadInput(moi, fil, False)
    time.sleep(0.8)


def ouvrir_fiche(session, essais: int = 6, commande: int = COMMANDE_CREER) -> FenetreArticle:
    """Ouvre une fiche d'article vide : liste « Stocks & Services » (page du même nom), puis sa commande « Créer »
    (`COMMANDE_OUVRIR` : fiche d'un article existant, pour en corriger les comptes)."""
    from .sage_bureau import ErreurSage, _attendre

    if not session.processus:  # Sage de la personne : WinForms n'accepte les clics que s'il est au premier plan
        premier_plan(session.principale)
    liste = user32.FindWindowW(CLASSE_LISTE, TITRE_LISTE)
    for _ in range(essais if not liste else 0):
        if session.processus:
            session.fermer_message_chargement()
        icone = icone_tache(session, TITRE_LISTE)
        if not icone:
            lien = session._visible(TITRE_LISTE)
            if lien:
                for cible in (lien, user32.GetParent(lien)):
                    session._cliquer(cible) if session.processus else cliquer_vrai(cible)
                    if _attendre(lambda: icone_tache(session, TITRE_LISTE), 4):
                        break
            time.sleep(3)
            continue
        if session.processus:
            session._cliquer(icone)
        else:
            premier_plan(session.principale)
            cliquer_vrai(icone)
        liste = _attendre(lambda: user32.FindWindowW(CLASSE_LISTE, TITRE_LISTE), 10)
        if liste:
            break
        time.sleep(3)
    if not liste:
        raise ErreurSage("La liste « Stocks & Services » de Sage ne s'ouvre pas.")
    for _ in range(3):
        user32.PostMessageW(liste, WM_COMMAND, commande, 0)
        fiche = _attendre(lambda: user32.FindWindowW("#32770", TITRE), 10)
        if fiche:
            return FenetreArticle(fiche)
    raise ErreurSage("La fiche « Enregistrements des stocks & services » ne s'ouvre pas.")


def fenetre_principale_ouverte(fichier_sai) -> int:
    """Fenêtre principale d'un Sage déjà ouvert sur ce fichier d'entreprise (0 sinon)."""
    from pathlib import Path

    from .sage_bureau import _texte

    nom = Path(fichier_sai).name.upper()
    trouvee = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def rappel(h, _):
        if user32.IsWindowVisible(h) and _texte(h).upper() == nom:
            trouvee.append(h)
        return True

    user32.EnumWindows(rappel, 0)
    return trouvee[0] if trouvee else 0


def ouvrir_session(config_toml: dict, journal=print):
    """Sage déjà ouvert sur le fichier d'entreprise configuré, sinon ouvert par l'application."""
    from . import coffre
    from .__main__ import executable_import
    from .sage_bureau import SessionSage, executable_sage, sage_ouvert

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    principale = fenetre_principale_ouverte(fichier)
    session = None
    if principale:
        session = SessionSage.__new__(SessionSage)
        session.exe, session.journal, session.processus, session.principale = None, journal, None, principale
    elif sage_ouvert():
        raise ErreurRobot("Sage est ouvert sur un autre fichier d'entreprise : fermez-le.")
    else:
        exe = executable_sage(executable_import())
        if not exe:
            raise ErreurRobot("Sage50Accounting.exe introuvable.")
        session = SessionSage(exe, journal)
        utilisateur = str(config_toml.get("sage_import", {}).get("utilisateur", "sysadmin"))
        try:
            session.ouvrir(fichier, utilisateur, coffre.lire(coffre.SAGE_IMPORT, ""))
        except Exception:
            session.fermer()  # jamais de Sage laissé ouvert (bloqué sur un avertissement) après un échec
            raise
    return session


def creer_articles(config_toml: dict, articles: list[ArticleACreer], journal=print) -> list[ResultatArticle]:
    """Crée les articles dans Sage : dans le Sage déjà ouvert sur le fichier d'entreprise configuré, sinon
    l'application ouvre Sage elle-même (appelé alors depuis la commande interne `creer-articles-bureau`)."""
    from .__main__ import lire_sage

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    session = ouvrir_session(config_toml, journal)

    def present(numero: str) -> bool:
        return bool(lire_sage(config_toml, lambda b: b.requete("SELECT sPartCode FROM tinvent WHERE sPartCode = %s",
                                                                (numero,)), fichier))

    resultats = []
    try:
        for a in articles:
            if present(a.numero):
                resultats.append(ResultatArticle(a.numero, False, [f"le n° {a.numero} existe déjà dans Sage"]))
                continue
            try:
                r = creer(ouvrir_fiche(session), a, present)
            except Exception as exc:
                r = ResultatArticle(a.numero, False, [str(exc)])
                fiche = user32.FindWindowW("#32770", TITRE)
                if fiche:  # fiche laissée à moitié remplie : fermée sans enregistrer
                    user32.PostMessageW(fiche, 0x0010, 0, 0)
            journal(f"{a.numero} {a.description} : {'créé' if r.cree else 'NON créé — ' + ' ; '.join(m for m in r.messages if m)}")
            resultats.append(r)
    finally:
        liste = user32.FindWindowW(CLASSE_LISTE, TITRE_LISTE)
        if liste:
            user32.PostMessageW(liste, 0x0010, 0, 0)
        if session.processus:
            session.fermer()
    return resultats


def lire_comptes(config_toml: dict, numeros: list[str]) -> dict[str, tuple[str, str, str, str]]:
    """N° -> (actif, produits, CMV, écart) lus dans la base (« 1513 »)."""
    from .__main__ import lire_sage
    from .creation_articles import compte4

    if not numeros:
        return {}
    marques = ", ".join(["%s"] * len(numeros))
    lignes = lire_sage(config_toml, lambda b: b.requete(
        "SELECT TRIM(sPartCode) n, lAcNAsset, lAcNRev, lAcNExp, lAcNVar FROM tinvent "
        f"WHERE sPartCode IN ({marques})", tuple(numeros)),
        config_toml.get("sage_import", {}).get("fichier_entreprise"))
    return {l["n"]: tuple(compte4(l[c]) for c in ("lAcNAsset", "lAcNRev", "lAcNExp", "lAcNVar")) for l in lignes}


def corriger_comptes(config_toml: dict, articles: list[ArticleACreer], journal=print) -> list[ResultatArticle]:
    """Remet les comptes des articles existants à ceux demandés (table catégorie -> comptes), puis vérifie dans la
    base (`cree` = comptes conformes). Une fiche déjà ouverte par la personne est reprise, revient à son article à la
    fin et reste ouverte ; sinon la fiche et la liste ouvertes pour l'occasion sont refermées."""
    session = ouvrir_session(config_toml, journal)
    resultats = {a.numero: ResultatArticle(a.numero) for a in articles}
    deja_ouverte = user32.FindWindowW("#32770", TITRE)
    try:
        fiche = FenetreArticle(deja_ouverte) if deja_ouverte else ouvrir_fiche(session, commande=COMMANDE_OUVRIR)
        origine = fiche.lire(ID_NUMERO).strip() if deja_ouverte else ""
        for a in articles:
            r = resultats[a.numero]
            try:
                fiche.aller(a.numero, r)
                fiche.modifier(a, journal)
                journal(f"{a.numero} : fiche « {fiche.lire(ID_NUMERO)} », comptes saisis {fiche.lire(ID_ACTIF)[:4]} / "
                        f"{fiche.lire(ID_PRODUITS)[:4]} / {fiche.lire(ID_CMV)[:4]} / {fiche.lire(ID_ECART)[:4]}")
            except Exception as exc:
                r.messages.append(str(exc))
        if articles:  # le dernier article est enregistré en le quittant (ou par « Enreg. et Fermer »)
            dernier = resultats[articles[-1].numero]
            if origine == articles[-1].numero:  # revenir à l'article de la personne : le quitter puis y revenir
                autre = next(e.split("  ")[0].strip() for e in fiche._elements(fiche._navigation())
                             if e.split("  ")[0].strip() not in ("", ".", origine))
                fiche.aller(autre, dernier)
                fiche.aller(origine, dernier)
            elif origine:
                fiche.aller(origine, dernier)
            else:
                fiche.enregistrer(dernier)
    finally:
        if not deja_ouverte:
            for classe, titre in (("#32770", TITRE), (CLASSE_LISTE, TITRE_LISTE)):
                h = user32.FindWindowW(classe, titre)
                if h:
                    user32.PostMessageW(h, 0x0010, 0, 0)
        if session.processus:
            session.fermer()
    time.sleep(1)
    lus = lire_comptes(config_toml, [a.numero for a in articles])
    for a in articles:
        r = resultats[a.numero]
        r.cree = lus.get(a.numero) == (a.actif, a.produits, a.cmv, a.ecart or a.cmv)
        if not r.cree:
            r.messages.append("comptes lus dans Sage : " + " / ".join(lus.get(a.numero, ("?",) * 4)))
        journal(f"{a.numero} : {'corrigé' if r.cree else 'NON corrigé — ' + ' ; '.join(m for m in r.messages if m)}")
    return list(resultats.values())

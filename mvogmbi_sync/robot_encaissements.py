"""Robot de saisie des encaissements dans la fenêtre « Encaissements » de Sage 50 (messages Windows, sans souris ni clavier).

Sage n'importe pas d'encaissement : le robot remplit la fenêtre comme une personne le ferait, puis « Traiter ».
Méthode mise au point sur la copie d'essai (2026-10-26) :
- en-tête : listes standard (client 25, « Payé par » 49 = « Comptant » (choix du propriétaire), « Dépôt » 51) et date (SimplyDate 31, WM_SETTEXT) ;
- grille (CA_ContainerChild32) : une ligne par facture en souffrance du client, triée par date puis par n° interne
  (ordre identique à la base : tcustr/tcustrdt) ; 16 points par ligne, 1re ligne à y=40, « Montant reçu » à x=692 ;
- surtout pas de Tab pour se déplacer : Sage remplit d'office le « Montant reçu » de chaque cellule traversée.
  On fait défiler la grille (WM_VSCROLL), on clique dans la bonne cellule, on tape le montant, puis un seul Tab ;
- contrôle avant « Traiter » : le montant total affiché (étiquette 100) doit égaler le dépôt, sinon on abandonne ;
- après « Traiter » : « date antérieure à la date de session » -> Oui ; toute autre question -> abandon (Non).
Une facture entièrement payée disparaît de la grille : l'ordre est relu dans la base avant chaque dépôt.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from dataclasses import dataclass, field
from decimal import Decimal

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

WM_LBUTTONDOWN, WM_LBUTTONUP, WM_CHAR, WM_KEYDOWN, WM_KEYUP = 0x0201, 0x0202, 0x0102, 0x0100, 0x0101
WM_COMMAND, WM_SETTEXT, WM_VSCROLL, WM_CLOSE = 0x0111, 0x000C, 0x0115, 0x0010
CB_SETCURSEL, CB_GETCURSEL, CB_GETCOUNT, CB_GETLBTEXT, CB_GETLBTEXTLEN = 0x014E, 0x0147, 0x0146, 0x0148, 0x0149
CBN_SELCHANGE, EN_CHANGE, EN_KILLFOCUS = 1, 0x0300, 0x0200
SB_LINEDOWN, SB_TOP, SB_VERT = 1, 6, 1

TITRE = "Encaissements"
ID_CLIENT, ID_MODE, ID_DEPOT, ID_DATE, ID_TOTAL, ID_TRAITER, ID_GRILLE = 25, 49, 51, 31, 100, 106, 5013
LIGNE_Y0, HAUTEUR_LIGNE, X_MONTANT_RECU, LIGNES_VISIBLES = 40, 16, 692, 8
QUESTION_DATE_ANTERIEURE = "antérieure à la date de session"
QUESTION_SUPPRESSION = "transaction en cours sera supprimée"


class ErreurRobot(RuntimeError):
    pass


@dataclass
class ResultatEncaissement:
    date: str
    montant: Decimal
    traite: bool = False
    messages: list[str] = field(default_factory=list)


def _texte(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    tampon = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, tampon, n + 1)
    return tampon.value


def _classe(hwnd) -> str:
    tampon = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, tampon, 256)
    return tampon.value


def _enfants(hwnd, visibles=True) -> list[int]:
    trouves = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def rappel(h, _):
        if not visibles or user32.IsWindowVisible(h):
            trouves.append(h)
        return True

    user32.EnumChildWindows(hwnd, rappel, 0)
    return trouves


def montant_sage(montant: Decimal) -> str:
    """1942.95 -> « 1942,95 » (saisie à la française, sans séparateur de milliers)."""
    return f"{montant:.2f}".replace(".", ",")


def _lire_montant(texte: str) -> Decimal:
    nettoye = texte.replace("\xa0", "").replace(" ", "").replace(" ", "").replace("$", "").replace(",", ".")
    return Decimal(nettoye or "0")


class SCROLLINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("fMask", wt.UINT), ("nMin", ctypes.c_int), ("nMax", ctypes.c_int),
                ("nPage", wt.UINT), ("nPos", ctypes.c_int), ("nTrackPos", ctypes.c_int)]


class FenetreEncaissements:
    """La fenêtre « Encaissements » ouverte dans Sage 50."""

    def __init__(self, hwnd: int | None = None):
        self.h = hwnd or user32.FindWindowW("#32770", TITRE)
        if not self.h:
            raise ErreurRobot("La fenêtre « Encaissements » de Sage n'est pas ouverte.")
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(self.h, ctypes.byref(pid))
        self.pid = pid.value
        conteneur = user32.GetDlgItem(self.h, ID_GRILLE)
        self.conteneur = conteneur
        self.grille = user32.FindWindowExW(conteneur, 0, "CA_ContainerChild32", None)

    # ------------------------------------------------------------ dialogues de Sage
    def dialogues(self) -> list[int]:
        trouves = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def rappel(h, _):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value == self.pid and h != self.h and user32.IsWindowVisible(h) and _classe(h) == "#32770":
                trouves.append(h)
            return True

        user32.EnumWindows(rappel, 0)
        return trouves

    @staticmethod
    def message(dialogue) -> str:
        return " ".join(_texte(c) for c in _enfants(dialogue) if _classe(c) == "Static" and _texte(c))

    @staticmethod
    def repondre(dialogue, libelles: tuple[str, ...]) -> bool:
        for c in _enfants(dialogue):
            if _classe(c) == "Button" and _texte(c).replace("&", "").strip().lower() in libelles:
                user32.PostMessageW(dialogue, WM_COMMAND, user32.GetDlgCtrlID(c), c)
                return True
        return False

    def attendre_dialogues(self, delai=3.0) -> list[int]:
        fin = time.time() + delai
        while time.time() < fin:
            trouves = self.dialogues()
            if trouves:
                return trouves
            time.sleep(0.2)
        return []

    # ------------------------------------------------------------ en-tête
    def _liste(self, ident: int) -> list[str]:
        cb = user32.GetDlgItem(self.h, ident)
        elements = []
        for i in range(user32.SendMessageW(cb, CB_GETCOUNT, 0, 0)):
            n = user32.SendMessageW(cb, CB_GETLBTEXTLEN, i, 0)
            tampon = ctypes.create_unicode_buffer(max(n, 0) + 1)
            user32.SendMessageW(cb, CB_GETLBTEXT, i, tampon)
            elements.append(tampon.value)
        return elements

    def choisir(self, ident: int, prefixe: str) -> str:
        """Choisit l'élément de la liste qui commence par `prefixe` (ex. « 1055 ») ; ne fait rien s'il est déjà choisi."""
        elements = self._liste(ident)
        index = next((i for i, e in enumerate(elements) if e == prefixe), None)
        if index is None:
            index = next((i for i, e in enumerate(elements) if e.startswith(prefixe)), None)
        if index is None:
            raise ErreurRobot(f"« {prefixe} » introuvable dans la liste de Sage ({', '.join(elements)}).")
        cb = user32.GetDlgItem(self.h, ident)
        if user32.SendMessageW(cb, CB_GETCURSEL, 0, 0) != index:
            user32.SendMessageW(cb, CB_SETCURSEL, index, 0)
            user32.PostMessageW(self.h, WM_COMMAND, (CBN_SELCHANGE << 16) | ident, cb)
            time.sleep(1.2)
            # changer de client efface une saisie en cours : Sage demande confirmation
            for d in self.dialogues():
                if QUESTION_SUPPRESSION in self.message(d):
                    self.repondre(d, ("oui", "ok"))
                    time.sleep(1)
        return elements[index]

    def effacer(self, client: str) -> None:
        """Abandonne la saisie en cours : passer à un autre client puis revenir (Sage confirme la suppression)."""
        autres = [e for e in self._liste(ID_CLIENT) if e != client]
        if autres:
            self.choisir(ID_CLIENT, autres[0])
        self.choisir(ID_CLIENT, client)

    def regler_date(self, jour: str) -> None:
        champ = user32.GetDlgItem(self.h, ID_DATE)
        user32.SendMessageW(champ, WM_SETTEXT, 0, ctypes.c_wchar_p(jour))
        user32.SendMessageW(self.h, WM_COMMAND, (EN_CHANGE << 16) | ID_DATE, champ)
        user32.SendMessageW(self.h, WM_COMMAND, (EN_KILLFOCUS << 16) | ID_DATE, champ)

    def total(self) -> Decimal:
        return _lire_montant(_texte(user32.GetDlgItem(self.h, ID_TOTAL)))

    # ------------------------------------------------------------ grille
    def _position(self) -> int:
        si = SCROLLINFO(ctypes.sizeof(SCROLLINFO), 0x17)
        user32.GetScrollInfo(self.grille, SB_VERT, ctypes.byref(si))
        return si.nPos

    def _editeur(self):
        for c in _enfants(self.conteneur):
            if _classe(c) == "CntSimEdit":
                return c
        return None

    def saisir_ligne(self, ligne: int, montant: Decimal) -> None:
        """Tape `montant` dans « Montant reçu » de la ligne `ligne` (0 = première facture de la grille)."""
        user32.SendMessageW(self.grille, WM_VSCROLL, SB_TOP, 0)
        while self._position() < ligne - (LIGNES_VISIBLES // 2):
            avant = self._position()
            user32.SendMessageW(self.grille, WM_VSCROLL, SB_LINEDOWN, 0)
            if self._position() == avant:
                break
        rang = ligne - self._position()
        if not 0 <= rang < LIGNES_VISIBLES:
            raise ErreurRobot(f"Ligne {ligne} hors de la zone visible de la grille.")
        y = LIGNE_Y0 + HAUTEUR_LIGNE * rang
        position = (y << 16) | X_MONTANT_RECU
        user32.PostMessageW(self.grille, WM_LBUTTONDOWN, 1, position)
        user32.PostMessageW(self.grille, WM_LBUTTONUP, 0, position)
        time.sleep(1.0)
        editeur = self._editeur()
        if not editeur:
            raise ErreurRobot("La cellule « Montant reçu » ne s'est pas ouverte.")
        # surtout pas WM_SETTEXT : Sage croirait la cellule non modifiée et y mettrait tout le montant dû
        for caractere in montant_sage(montant):
            user32.PostMessageW(editeur, WM_CHAR, ord(caractere), 0)
            time.sleep(0.03)
        time.sleep(0.6)
        user32.PostMessageW(editeur, WM_KEYDOWN, 0x09, 1)  # un seul Tab : valide la cellule
        user32.PostMessageW(editeur, WM_CHAR, 0x09, 1)
        user32.PostMessageW(editeur, WM_KEYUP, 0x09, 0xC0000001)
        time.sleep(0.8)

    def traiter(self, resultat: ResultatEncaissement) -> bool:
        user32.PostMessageW(self.h, WM_COMMAND, ID_TRAITER, user32.GetDlgItem(self.h, ID_TRAITER))
        for _ in range(5):
            dialogues = self.attendre_dialogues(4)
            if not dialogues:
                return True
            for d in dialogues:
                texte = self.message(d)
                if QUESTION_DATE_ANTERIEURE in texte:
                    self.repondre(d, ("oui",))
                    resultat.messages.append("Date antérieure à la session de Sage : confirmée.")
                elif texte.startswith("iAdvise"):  # conseil de Sage (ex. compte à découvert) : simple information
                    user32.PostMessageW(d, WM_CLOSE, 0, 0)
                    resultat.messages.append(f"Conseil de Sage noté : {texte[8:].strip()}")
                else:
                    resultat.messages.append(f"Sage : {texte}")
                    self.repondre(d, ("non", "annuler", "ok"))
                    return False
            time.sleep(1.5)
        return False


def ordre_grille(base, client: str) -> list[str]:
    """Numéros des factures en souffrance du client, dans l'ordre de la grille Encaissements de Sage."""
    lignes = base.requete(
        "SELECT t.sSource facture FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
        "JOIN tcustrdt d ON d.lCusTrId = t.lId WHERE c.sName = %s "
        "GROUP BY t.lId, t.dtDate, t.sSource HAVING ROUND(SUM(d.dAmount), 2) <> 0 ORDER BY t.dtDate, t.lId", (client,))
    return [l["facture"] for l in lignes]


def encaisser_depot(fenetre: FenetreEncaissements, depot, ordre: list[str], client: str, compte: str,
                    mode: str = "Comptant") -> ResultatEncaissement:
    """Saisit un dépôt (une ligne par facture), vérifie le total, puis « Traiter »."""
    resultat = ResultatEncaissement(depot.date.isoformat(), depot.montant)
    lignes = [l for l in depot.lignes if l.etat in ("À saisir dans Sage",)]
    if not lignes:
        resultat.messages.append("Rien à saisir.")
        return resultat
    for l in lignes:
        if l.facture not in ordre:
            raise ErreurRobot(f"{l.facture} n'est pas dans la liste des factures en souffrance de Sage.")
        if l.montant_du is not None and l.montant > l.montant_du:
            resultat.messages.append(f"{l.facture} : dépôt {l.montant} $ supérieur au solde dû {l.montant_du} $ "
                                     "(déjà encaissée autrement ?) ; rien n'est saisi.")
            return resultat
    attendu = sum((l.montant for l in lignes), Decimal(0))
    for tentative in range(1, 4):
        fenetre.choisir(ID_CLIENT, client)
        fenetre.choisir(ID_MODE, mode)
        fenetre.choisir(ID_DEPOT, f"{compte} ")
        fenetre.regler_date(depot.date.isoformat())
        for l in lignes:
            fenetre.saisir_ligne(ordre.index(l.facture), l.montant)
        lu = fenetre.total()
        if lu == attendu:
            resultat.traite = fenetre.traiter(resultat)
            return resultat
        # jamais de « Traiter » sur un total faux : on efface et on recommence
        resultat.messages.append(f"Essai {tentative} : total affiché {lu} au lieu de {attendu}, saisie effacée.")
        fenetre.effacer(client)
        time.sleep(1.5)
    resultat.messages.append("Saisie abandonnée après 3 essais.")
    return resultat


def appliquer(config_toml: dict, depots, client: str, compte: str, mode: str = "Comptant", journal=print) -> list:
    """Saisit dans Sage (ouvert, fenêtre Encaissements affichée) chaque dépôt « À saisir », puis vérifie dans la base."""
    from datetime import date as _date

    from .__main__ import ouvrir_base_sage
    from .encaissements import APPLIQUE, A_SAISIR, etat_factures_sage, evaluer, numero_compte_sage

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    fenetre = FenetreEncaissements()
    resultats = []
    for depot in depots:
        if depot.etat != A_SAISIR:
            continue
        with ouvrir_base_sage(config_toml, fichier) as base:
            ordre = ordre_grille(base, client)
        resultat = encaisser_depot(fenetre, depot, ordre, client, compte, mode)
        time.sleep(1.5)
        with ouvrir_base_sage(config_toml, fichier) as base:
            etat = etat_factures_sage(base, client, numero_compte_sage(compte), [l.facture for l in depot.lignes])
        evaluer([depot], etat, _date.today())
        if resultat.traite and depot.etat != APPLIQUE:
            resultat.messages.append(f"Après « Traiter », état dans Sage : {depot.etat}.")
            resultat.traite = False
        journal(f"{depot.date} : dépôt {depot.montant} $ -> {'encaissé' if resultat.traite else 'NON encaissé'} "
                + " ".join(resultat.messages))
        resultats.append(resultat)
        if not resultat.traite:
            break  # on s'arrête au premier problème
    return resultats

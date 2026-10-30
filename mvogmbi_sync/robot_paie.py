"""Paie dans Sage (demande du propriétaire du 2026-10-29) : création de l'employé dans Sage Paie et traitement de son
chèque de paie avec les heures validées dans l'application. Sage n'importe ni employé ni paie : l'application ouvre
Sage elle-même (bureau caché, commande interne `paie-bureau`) et remplit ses fenêtres.

Relevé et validé le 2026-10-29 sur la copie d'essai (« ESSAI EMPLOYE 1 », 10 h × 18,00 $ = 180,00 $, retenues 43,20 $,
net 136,80 $, écriture de paie n° de chèque 6 du 2026-11-30) :
- page « Employés & Paie », icône « Employés » -> liste SimplyLedger « Employés » ; WM_COMMAND 3001 = fiche vide
  « Enregistrements des employés » (#32770). Onglet Personnel : Employé 22, Rue 1 39, Rue 2 40, Ville 41, Province 42,
  code de province 31 (liste « QC »), Code postal 43, Téléphone 44, Courriel 36, NAS 46, Né le 47 ; onglet
  Informations professionnelles : Embauché le 53 ; Impôts : table d'impôt 129 (« Québec ») ; Revenu : Périodes de paie
  81 (« 26 »), grille CA_Container32 (case cliquée puis tapée dans son éditeur CntSimEdit) : ligne « Régulières » à
  y=138, colonne « Montant par unité » à x=244 ; « Supplém. 1 » : une ligne plus bas après un défilement ; état
  « 4/4 champs de paie remplis » (233) ; « Enreg. et Fermer » 1002. Les onglets se changent au clavier (flèche droite
  sur la SysTabControl32) et chaque onglet se remplit pendant qu'il est affiché.
- icône « Chèques de paie » -> fenêtre WinForms « Chèques de paie » : l'employé se choisit COMME UNE PERSONNE (clic
  sur la flèche de la liste puis clic sur son nom dans la liste déroulante ComboLBox) : une sélection posée par
  message ou tapée n'est pas prise en compte (grille des gains vide) ; dates : début (y=162), fin (y=186), chèque
  (y=138) et « N° chèque » (y=114), champs EDIT à x=668, TAPÉS (`_saisir` : un texte posé par WM_SETTEXT s'affiche
  mais Sage garde la date de session et le n° suivant) ; n° = « PAYjjmmaaaa » (`numero_desjardins`, comme les paies
  versées par le service Dépôt salaire de Desjardins) ; questions acceptées : date éloignée de la date de session,
  n° déjà utilisé par une autre paie du jour ; grille des gains (28, 251, 450 × 189) : colonne Heures x=142, lignes
  « Régulières » y=51 et « Supplém. 1 » y=68 (17 points par ligne) ; Salaire brut / Retenu / net : étiquettes à
  x=573, y=483 / 502 / 521 ; « Traiter » (688, 516).
- vérification : écriture du module Paie (tjourent nModule 3) dont la remarque est le nom de l'employé, datée du
  chèque. Une paie déjà traitée pour l'employé et la période n'est jamais refaite (registre donnees/paies_sage.json).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .cache_lectures import vide_apres

user32 = ctypes.windll.user32
FICHE = "Enregistrements des employés"
CHEQUES = "Chèques de paie"
PAGE = "Employés & Paie"
PERIODES_PAR_AN = "26"  # paie aux 2 semaines (choix du propriétaire)


class ErreurPaie(RuntimeError):
    pass


@dataclass
class EmployeSage:
    nom: str
    rue: str = ""
    ville: str = ""
    province: str = "QC"
    code_postal: str = ""
    telephone: str = ""
    courriel: str = ""
    nas: str = ""          # jamais gardé par l'application : transmis à Sage puis oublié
    naissance: str = ""    # AAAA-MM-JJ
    embauche: str = ""     # AAAA-MM-JJ
    taux: str = ""         # taux horaire, ex. « 18,00 »
    taux_supp: str = ""    # taux des heures supplémentaires (1,5 × par défaut)


@dataclass
class PaieATraiter:
    nom_sage: str          # employé tel que Sage l'écrit
    debut: str             # période de paie AAAA-MM-JJ
    fin: str
    date_cheque: str
    heures: str            # heures normales, ex. « 75,5 »
    heures_supp: str = "0"
    employe: str = ""      # identifiant de l'employé de l'application
    numero: str = ""       # « N° chèque » de Sage : « PAYjjmmaaaa », comme les paies versées par Desjardins


@dataclass
class Resultat:
    nom: str
    fait: bool = False
    brut: str = ""
    retenues: str = ""
    net: str = ""
    numero: str = ""
    messages: list[str] = field(default_factory=list)


def _nombre(texte: str) -> str:
    return f"{Decimal(str(texte).replace(',', '.').replace(' ', '') or 0):.2f}".replace(".", ",")


# --------------------------------------------------------------------------------------------- outils fenêtres
def _classe(h) -> str:
    b = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(h, b, 128)
    return b.value


def _rect(h, racine=None) -> tuple[int, int, int, int]:
    r, r0 = wt.RECT(), wt.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    if racine:
        user32.GetWindowRect(racine, ctypes.byref(r0))
    return r.left - r0.left, r.top - r0.top, r.right - r.left, r.bottom - r.top


def _texte_wm(h) -> str:
    b = ctypes.create_unicode_buffer(256)
    user32.SendMessageW(h, 0x000D, 256, b)
    return b.value


def _clic(h, x: int, y: int) -> None:
    position = (y << 16) | x
    user32.PostMessageW(h, 0x0201, 1, position)
    user32.PostMessageW(h, 0x0202, 0, position)
    time.sleep(1.0)


def _taper(h, texte: str) -> None:
    for c in texte:
        user32.PostMessageW(h, 0x0102, ord(c), 0)
        time.sleep(0.03)
    time.sleep(0.5)


def _tab(h) -> None:
    user32.PostMessageW(h, 0x0100, 0x09, 1)
    user32.PostMessageW(h, 0x0102, 0x09, 1)
    user32.PostMessageW(h, 0x0101, 0x09, 0xC0000001)
    time.sleep(0.8)


def _elements(liste) -> list[str]:
    elements = []
    for i in range(user32.SendMessageW(liste, 0x0146, 0, 0)):  # CB_GETCOUNT
        b = ctypes.create_unicode_buffer(user32.SendMessageW(liste, 0x0149, i, 0) + 2)
        user32.SendMessageW(liste, 0x0148, i, b)
        elements.append(b.value)
    return elements


class _Fiche:
    """Fiche « Enregistrements des employés » (boîte de dialogue classique)."""

    def __init__(self, h):
        from .sage_bureau import _descendants

        self.h, self._descendants = h, _descendants

    def ecrire(self, ident: int, texte: str) -> None:
        if not texte:
            return
        champ = user32.GetDlgItem(self.h, ident)
        user32.SendMessageW(champ, 0x000C, 0, ctypes.c_wchar_p(texte))
        user32.SendMessageW(self.h, 0x0111, (0x0300 << 16) | ident, champ)  # EN_CHANGE
        user32.SendMessageW(self.h, 0x0111, (0x0200 << 16) | ident, champ)  # EN_KILLFOCUS
        time.sleep(0.3)

    def choisir(self, ident: int, debut: str) -> None:
        liste = next((e for e in self._descendants(self.h) if user32.GetDlgCtrlID(e) == ident
                      and "ComboBox" in _classe(e)), None)
        elements = _elements(liste) if liste else []
        rang = next((i for i, e in enumerate(elements) if e == debut), None)
        if rang is None:
            rang = next((i for i, e in enumerate(elements) if e.startswith(debut)), None)
        if rang is None:
            raise ErreurPaie(f"« {debut} » absent de la liste de Sage ({', '.join(elements[:15])}).")
        user32.SendMessageW(liste, 0x014E, rang, 0)  # CB_SETCURSEL
        user32.SendMessageW(user32.GetParent(liste), 0x0111, (1 << 16) | ident, liste)  # CBN_SELCHANGE
        time.sleep(0.8)

    def onglet_suivant(self, fois: int = 1) -> None:
        onglets = next(e for e in self._descendants(self.h) if _classe(e) == "SysTabControl32")
        for _ in range(fois):
            user32.SendMessageW(onglets, 0x0100, 0x27, 0)
            user32.SendMessageW(onglets, 0x0101, 0x27, 0xC0000000)
            time.sleep(1)

    def grille(self):
        conteneur = next(e for e in self._descendants(self.h) if _classe(e) == "CA_Container32"
                         and user32.IsWindowVisible(e))
        return conteneur, next(e for e in self._descendants(conteneur) if _classe(e) == "CA_ContainerChild32")

    def case(self, x: int, y: int, texte: str) -> None:
        conteneur, grille = self.grille()
        _clic(grille, x, y)
        editeur = next((c for c in self._descendants(conteneur) if _classe(c) == "CntSimEdit"), None)
        if not editeur:
            raise ErreurPaie("La case du taux horaire ne s'ouvre pas dans la fiche de Sage.")
        _taper(editeur, texte)
        _tab(editeur)

    def defiler(self, lignes: int) -> None:
        _conteneur, grille = self.grille()
        for _ in range(lignes):
            user32.SendMessageW(grille, 0x0115, 1, 0)  # WM_VSCROLL, SB_LINEDOWN
            time.sleep(0.3)


def _ouvrir_page(session) -> None:
    from .sage_bureau import ErreurSage

    lien = session._visible(PAGE)
    if not lien:
        raise ErreurSage(f"Page « {PAGE} » introuvable dans Sage.")
    for cible in (lien, user32.GetParent(lien)):
        session._cliquer(cible)
        time.sleep(3)
    session.fermer_message_chargement()


def _dialogues(session, deja) -> list[int]:
    return [h for h in session.fenetres() if user32.IsWindowVisible(h) and h not in deja]


def _refuser(session, d, resultat: Resultat) -> None:
    """Question de Sage : notée puis refusée (Non / Annuler / OK) ; rien n'est forcé."""
    from .sage_bureau import _descendants, _texte

    textes = [_texte(e) for e in _descendants(d) if _texte(e)]
    resultat.messages.append("Sage : " + " ".join(t for t in textes if t.replace("&", "").lower()
                                                   not in ("oui", "non", "ok", "annuler", "aide")))
    for voulu in ("non", "annuler", "ok"):
        bouton = next((e for e in _descendants(d) if _texte(e).replace("&", "").lower() == voulu), None)
        if bouton:
            user32.PostMessageW(bouton, 0x00F5, 0, 0)  # BM_CLICK
            return
    user32.PostMessageW(d, 0x0010, 0, 0)


# --------------------------------------------------------------------------------------------- employé
def creer_employe(session, e: EmployeSage, journal=print) -> Resultat:
    from .sage_bureau import _attendre

    r = Resultat(e.nom)
    _ouvrir_page(session)
    session._cliquer(session._icone("Employés"))
    liste = _attendre(lambda: user32.FindWindowW("SimplyLedger", "Employés"), 10)
    if not liste:
        raise ErreurPaie("La liste « Employés » de Sage ne s'ouvre pas.")
    try:
        user32.PostMessageW(liste, 0x0111, 3001, 0)  # nouvelle fiche
        h = _attendre(lambda: user32.FindWindowW("#32770", FICHE), 10)
        if not h:
            raise ErreurPaie(f"La fiche « {FICHE} » ne s'ouvre pas.")
        time.sleep(2)
        f = _Fiche(h)
        f.ecrire(22, e.nom)
        for ident, valeur in ((39, e.rue), (41, e.ville), (43, e.code_postal.replace(" ", "")),
                              (44, "".join(c for c in e.telephone if c.isdigit())), (36, e.courriel),
                              (46, "".join(c for c in e.nas if c.isdigit())), (47, e.naissance)):
            f.ecrire(ident, valeur)
        f.ecrire(42, "Québec" if e.province == "QC" else e.province)
        f.choisir(31, e.province)
        f.onglet_suivant()  # Informations professionnelles
        f.ecrire(53, e.embauche)
        f.onglet_suivant()  # Impôts
        f.choisir(129, "Québec" if e.province == "QC" else e.province)
        f.onglet_suivant()  # Revenu
        f.choisir(81, PERIODES_PAR_AN)
        if e.taux:
            f.case(244, 138, _nombre(e.taux))
        if e.taux_supp:
            f.defiler(1)
            f.case(244, 138, _nombre(e.taux_supp))
        etat = _texte_wm(user32.GetDlgItem(h, 233))
        journal(f"{e.nom} : {etat}")
        deja = set(session.fenetres())
        user32.PostMessageW(h, 0x0111, 1002, user32.GetDlgItem(h, 1002))  # Enreg. et Fermer
        for _ in range(5):
            time.sleep(2)
            for d in _dialogues(session, deja):
                deja.add(d)
                _refuser(session, d, r)
            if not user32.IsWindow(h) or not user32.IsWindowVisible(h):
                break
        if user32.IsWindow(h) and user32.IsWindowVisible(h):
            user32.PostMessageW(h, 0x0010, 0, 0)
            time.sleep(2)
            session._confirmer_abandon()
            r.messages.append("fiche non enregistrée par Sage")
        else:
            r.fait = True
    finally:
        user32.PostMessageW(liste, 0x0010, 0, 0)
        time.sleep(1)
    return r


# --------------------------------------------------------------------------------------------- chèque de paie
def _a_la_position(h, x, y, largeur=None, hauteur=None, classe=None):
    from .sage_bureau import _descendants

    for e in _descendants(h):
        rx, ry, rl, rh = _rect(e, h)
        if (rx, ry) == (x, y) and (largeur is None or rl == largeur) and (hauteur is None or rh == hauteur) \
                and (classe is None or classe in _classe(e)):
            return e
    return None


def _choisir_employe(h, nom: str) -> None:
    """Comme une personne : clic sur la flèche de la liste, puis clic sur le nom dans la liste déroulante."""
    liste = _a_la_position(h, 18, 157, classe="COMBOBOX")
    if not liste:
        raise ErreurPaie("Liste des employés introuvable dans « Chèques de paie ».")
    noms = [n.strip() for n in _elements(liste)]
    if nom.strip() not in noms:
        raise ErreurPaie(f"« {nom} » n'est pas dans la liste des employés de Sage (employé inactif ou non prêt ?).")
    rang = noms.index(nom.strip())
    _x, _y, largeur, hauteur = _rect(liste)
    _clic(liste, largeur - 9, hauteur // 2)
    time.sleep(1)
    boites = []

    def chercher(hh, _):
        if _classe(hh) == "ComboLBox" and user32.IsWindowVisible(hh):
            boites.append(hh)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(chercher), 0)
    if not boites:
        raise ErreurPaie("La liste déroulante des employés ne s'ouvre pas.")
    user32.SendMessageW(boites[0], 0x0197, rang, 0)  # LB_SETTOPINDEX
    time.sleep(0.4)
    r = wt.RECT()
    user32.SendMessageW(boites[0], 0x0198, rang, ctypes.byref(r))  # LB_GETITEMRECT
    _clic(boites[0], (r.left + r.right) // 2, (r.top + r.bottom) // 2)
    time.sleep(3)
    if user32.SendMessageW(liste, 0x0147, 0, 0) != rang:  # CB_GETCURSEL
        raise ErreurPaie(f"Sage n'a pas pris « {nom} » dans la liste des employés.")


def _montant(h, y: int) -> Decimal:
    e = _a_la_position(h, 573, y, 80)
    texte = _texte_wm(e) if e else ""
    try:
        return Decimal(texte.replace("\xa0", "").replace(" ", "").replace(",", ".") or 0)
    except Exception:
        return Decimal(0)


def paie_dans_sage(config_toml: dict, nom: str, date_cheque: str) -> bool:
    from .__main__ import lire_sage

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    lignes = lire_sage(config_toml, lambda b: b.requete(
        "SELECT COUNT(*) n FROM tjourent WHERE nModule = 3 AND sComment = %s AND dtJourDate = %s",
        (nom, date_cheque)), fichier)
    return bool(lignes and lignes[0]["n"])


def numero_dans_sage(config_toml: dict, nom: str, date_cheque: str) -> str:
    from .__main__ import lire_sage

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    lignes = lire_sage(config_toml, lambda b: b.requete(
        "SELECT TRIM(sSource) s FROM tjourent WHERE nModule = 3 AND sComment = %s AND dtJourDate = %s "
        "ORDER BY lId DESC LIMIT 1", (nom, date_cheque)), fichier)
    return lignes[0]["s"] if lignes else ""


def traiter_cheque(session, config_toml: dict, p: PaieATraiter, journal=print) -> Resultat:
    from .sage_bureau import _texte

    r = Resultat(p.nom_sage)
    if paie_dans_sage(config_toml, p.nom_sage, p.date_cheque):
        r.messages.append(f"une paie de {p.nom_sage} datée du {p.date_cheque} est déjà dans Sage : rien n'est refait")
        return r
    _ouvrir_page(session)
    avant = set(session.fenetres())
    session._cliquer(session._icone(CHEQUES))
    h = None
    for _ in range(20):
        time.sleep(1)
        h = next((x for x in session.fenetres() if x not in avant and CHEQUES in _texte(x)
                  and user32.IsWindowVisible(x)), None)
        if h:
            break
    if not h:
        raise ErreurPaie(f"La fenêtre « {CHEQUES} » de Sage ne s'ouvre pas.")
    try:
        time.sleep(3)
        _choisir_employe(h, p.nom_sage)
        # dates et n° : TAPÉS comme une personne (constat du 2026-10-29 : un texte posé par WM_SETTEXT s'affiche mais
        # Sage garde sa valeur par défaut, date de session et n° suivant)
        for y, valeur in ((162, p.debut), (186, p.fin), (138, p.date_cheque), (114, p.numero)):
            if valeur:
                _saisir(_a_la_position(h, 668, y, 100, classe="EDIT"), valeur)
        time.sleep(1.5)
        grille = _a_la_position(h, 28, 251, 450, 189)
        if not grille:
            raise ErreurPaie("Grille des gains introuvable dans « Chèques de paie ».")
        for y, heures in ((51, p.heures), (68, p.heures_supp)):
            if Decimal(str(heures).replace(",", ".") or 0) <= 0:
                continue
            _clic(grille, 142, y)
            editeur = next((e for e in _descendants_visibles(h) if "EDIT" in _classe(e).upper()
                            and 251 < _rect(e, h)[1] < 440), None)
            if not editeur:
                raise ErreurPaie("La case des heures ne s'ouvre pas (taux absent de la fiche de l'employé ?).")
            _taper(editeur, _nombre(heures))
            _tab(editeur)
        time.sleep(1.5)
        brut, retenues, net = _montant(h, 483), _montant(h, 502), _montant(h, 521)
        r.brut, r.retenues, r.net = str(brut), str(retenues), str(net)
        journal(f"{p.nom_sage} : brut {brut}, retenues {retenues}, net {net}")
        if brut <= 0:
            raise ErreurPaie("Sage calcule un salaire brut nul : taux horaire absent de la fiche de l'employé ?")
        deja = set(session.fenetres())
        traiter = _a_la_position(h, 688, 516, 100)
        user32.PostMessageW(traiter, 0x00F5, 0, 0)  # BM_CLICK
        for _ in range(8):
            time.sleep(2)
            for d in _dialogues(session, deja):
                deja.add(d)
                if p.numero and _numero_deja_utilise(d):
                    _oui(d)  # même « PAYjjmmaaaa » pour tous les employés de la paie : voulu
                    r.messages.append(f"n° {p.numero} déjà utilisé par une autre paie du jour : accepté")
                elif _question_date(d):
                    _oui(d)  # date des chèques choisie et confirmée par la personne (comme les encaissements)
                    r.messages.append("date des chèques éloignée de la date de session de Sage : confirmée")
                else:
                    _refuser(session, d, r)
            if paie_dans_sage(config_toml, p.nom_sage, p.date_cheque):
                r.fait = True
                r.numero = numero_dans_sage(config_toml, p.nom_sage, p.date_cheque)
                if p.numero and r.numero != p.numero:
                    r.messages.append(f"n° enregistré par Sage : {r.numero} (au lieu de {p.numero})")
                break
    finally:
        if user32.IsWindow(h):
            user32.PostMessageW(h, 0x0010, 0, 0)
            time.sleep(2)
            _repondre_oui_suppression(session)
    return r


def _saisir(champ, valeur: str) -> None:
    """Clic dans le champ, tout sélectionner, frappe caractère par caractère, puis Tab (validation de Sage)."""
    if not champ:
        raise ErreurPaie("Champ introuvable dans « Chèques de paie ».")
    _clic(champ, 5, 5)
    user32.SendMessageW(champ, 0x00B1, 0, -1)  # EM_SETSEL : tout
    user32.PostMessageW(champ, 0x0100, 0x2E, 1)  # Suppr.
    user32.PostMessageW(champ, 0x0101, 0x2E, 0xC0000001)
    time.sleep(0.3)
    _taper(champ, valeur)
    _tab(champ)
    time.sleep(0.5)


def _numero_deja_utilise(d) -> bool:
    from .sage_bureau import _descendants, _texte

    texte = " ".join(_texte(e) for e in _descendants(d)).lower()
    return ("déjà" in texte or "already" in texte) and ("numéro" in texte or "n°" in texte or "number" in texte)


def _question_date(d) -> bool:
    """« La date saisie est postérieure (antérieure) à … Êtes-vous sûr que vous voulez continuer? »"""
    from .sage_bureau import _descendants, _texte

    texte = " ".join(_texte(e) for e in _descendants(d)).lower()
    return "date saisie" in texte and ("postérieure" in texte or "antérieure" in texte)


def _oui(d) -> None:
    from .sage_bureau import _descendants, _texte

    bouton = next((e for e in _descendants(d) if _texte(e).replace("&", "").lower() in ("oui", "yes")), None)
    if bouton:
        user32.PostMessageW(bouton, 0x00F5, 0, 0)


def numero_desjardins(date_cheque: str) -> str:
    """« PAYjjmmaaaa » : n° des paies versées par le service Dépôt salaire de Desjardins (relevé « Depot
    Salaire/PAY05012026 », rapproché par rapprochement.REFERENCE_PAIE)."""
    a, m, j = date_cheque.split("-")
    return f"PAY{j}{m}{a}"


def _descendants_visibles(h):
    from .sage_bureau import _descendants

    return [e for e in _descendants(h) if user32.IsWindowVisible(e)]


def _repondre_oui_suppression(session) -> None:
    """Chèque non traité fermé : Sage demande s'il faut supprimer l'écriture -> Oui (rien n'est enregistré)."""
    from .sage_bureau import _descendants, _texte

    for d in session.fenetres():
        if user32.IsWindowVisible(d) and any("supprimer" in _texte(e) for e in _descendants(d)):
            oui = next((e for e in _descendants(d) if _texte(e).replace("&", "").lower() == "oui"), None)
            if oui:
                user32.PostMessageW(oui, 0x00F5, 0, 0)


# --------------------------------------------------------------------------------------------- registre et lancement
class Registre:
    """Paies traitées par l'application (employé + période) : jamais deux fois."""

    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "paies_sage.json"
        self.paies: list[dict] = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else []

    def deja(self, p: PaieATraiter) -> bool:
        return any(x["nom_sage"] == p.nom_sage and x["debut"] == p.debut and x.get("fait") for x in self.paies)

    def noter(self, p: PaieATraiter, r: Resultat) -> None:
        self.paies.append({**asdict(p), "fait": r.fait, "brut": r.brut, "retenues": r.retenues, "net": r.net,
                           "messages": r.messages, "le": datetime.now().isoformat(timespec="seconds")})
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps(self.paies, ensure_ascii=False, indent=1), encoding="utf-8")


def executer(config_toml: dict, employes: list[EmployeSage], paies: list[PaieATraiter], journal=print) -> dict:
    """Dans Sage ouvert par l'application (bureau caché) : crée les employés puis traite les chèques."""
    from .robot_articles import ouvrir_session

    bilan = {"employes": [], "paies": []}
    session = ouvrir_session(config_toml, journal)
    try:
        if not session.processus:
            raise ErreurPaie("Fermez Sage : l'application l'ouvre elle-même pour la paie.")
        time.sleep(6)
        session.fermer_message_chargement()
        for e in employes:
            try:
                bilan["employes"].append(asdict(creer_employe(session, e, journal)))
            except Exception as exc:
                bilan["employes"].append(asdict(Resultat(e.nom, messages=[str(exc)])))
        for p in paies:
            try:
                bilan["paies"].append(asdict(traiter_cheque(session, config_toml, p, journal)))
            except Exception as exc:
                bilan["paies"].append(asdict(Resultat(p.nom_sage, messages=[str(exc)])))
                break  # jamais de chèque suivant après un échec
    finally:
        session.fermer()
    return bilan


@vide_apres  # mémoire des lectures vidée après une écriture
def dans_sage(racine: Path, config_toml: dict, employes: list[EmployeSage] = (),
              paies: list[PaieATraiter] = ()) -> dict:
    """Lance la commande interne `paie-bureau` (Sage doit être fermé) ; note les paies traitées."""
    import tempfile

    from .__main__ import commande_moteur, fermer_bases
    from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

    if sage_ouvert():
        raise ErreurPaie("Fermez Sage : l'application l'ouvre elle-même pour la paie.")
    registre = Registre(racine)
    a_faire = [p for p in paies if not registre.deja(p)]
    fermer_bases()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:  # le NAS n'y reste pas
        demande, resultat = Path(dossier) / "paie.json", Path(dossier) / "bilan.json"
        demande.write_text(json.dumps({"employes": [asdict(e) for e in employes],
                                       "paies": [asdict(p) for p in a_faire]}, ensure_ascii=False), encoding="utf-8")
        executer_sur_bureau_cache(commande_moteur() + ["paie-bureau", "--demande", str(demande),
                                                      "--resultat", str(resultat)], racine)
        bilan = json.loads(resultat.read_text(encoding="utf-8")) if resultat.exists() else {}
    if bilan.get("erreur"):
        raise ErreurPaie(bilan["erreur"])
    for p, r in zip(a_faire, bilan.get("paies", [])):
        registre.noter(p, Resultat(**r))
    bilan["deja"] = [asdict(p) for p in paies if p not in a_faire]
    return bilan

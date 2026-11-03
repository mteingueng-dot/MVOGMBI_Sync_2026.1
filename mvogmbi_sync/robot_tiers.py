"""Création de clients et de fournisseurs dans Sage (demande du propriétaire du 2026-10-29) : Sage n'importe pas ces
fiches ; l'application remplit la fiche « Enregistrements des clients » / « Enregistrements des fournisseurs »,
comme pour les articles (robot_articles).

Relevé du 2026-10-29 sur la copie d'essai (fiche vide ouverte par la commande 3001 de la liste « Clients » ou
« Fournisseurs », classe SimplyLedger, icône de la page « Clients & Ventes » / « Fournisseurs & Achats ») : mêmes
numéros de champ dans les deux fiches : Nom 26, Contact 43, Rue 1 44, Rue 2 45, Ville 46, Province 47, Code postal
48, Pays 55, Téléphone 1 49, Téléphone 2 50, Courriel 52, Site Web 53 (fournisseur : n° d'inscription aux taxes 58) ;
« Enreg. et Fermer » 1002. La case « utilise mes numéros d'articles » (nécessaire aux imports de factures) est dans
un autre onglet : les onglets sont parcourus au clavier jusqu'à elle, puis elle est cochée. Le tiers créé est
vérifié dans la base (tcustomr / tvendor, avec bUseMyItem).
"""

from __future__ import annotations

import ctypes
import json
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .cache_lectures import vide_apres
from .robot_articles import ErreurRobot, FenetreArticle, _classe, icone_tache, ouvrir_session

user32 = ctypes.windll.user32
BM_GETCHECK, BM_CLICK = 0x00F0, 0x00F5
CREER = 3001
GENRES = {  # page de l'accueil, icône (= titre de la liste), titre de la fiche, table de la base
    "clients": ("Clients & Ventes", "Clients", "Enregistrements des clients", "tcustomr"),
    "fournisseurs": ("Fournisseurs & Achats", "Fournisseurs", "Enregistrements des fournisseurs", "tvendor"),
}
CHAMPS = {"nom": 26, "contact": 43, "rue1": 44, "rue2": 45, "ville": 46, "province": 47, "code_postal": 48,
          "pays": 55, "telephone": 49, "telephone2": 50, "courriel": 52, "site": 53, "no_taxe": 58}
LIBELLES = {"nom": "Nom", "contact": "Contact", "rue1": "Rue 1", "rue2": "Rue 2", "ville": "Ville",
            "province": "Province", "code_postal": "Code postal", "pays": "Pays", "telephone": "Téléphone 1",
            "telephone2": "Téléphone 2", "courriel": "Courriel", "site": "Site Web", "no_taxe": "N° d'inscription aux taxes"}


@dataclass
class FicheTiers:
    nom: str
    contact: str = ""
    rue1: str = ""
    rue2: str = ""
    ville: str = ""
    province: str = "QC"
    code_postal: str = ""
    pays: str = "Canada"
    telephone: str = ""
    telephone2: str = ""
    courriel: str = ""
    site: str = ""
    no_taxe: str = ""
    compte: str = ""           # client : compte de produits ; fournisseur : compte de charges (onglet Options)
    mes_numeros: bool = True   # « Ce client / fournisseur utilise mes n° articles » (onglet Importer/Exporter)


@dataclass
class ResultatTiers:
    nom: str
    cree: bool = False
    mes_numeros: bool = False
    messages: list[str] = field(default_factory=list)


def _simple(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower().replace("&", "")


ID_COMPTE_CLIENT, ID_COMPTE_FOURNISSEUR = 80, 105  # onglet « Options » des fiches (relevé du 2026-11-03)


class FenetreTiers(FenetreArticle):
    """Fiche « Enregistrements des clients » ou « … des fournisseurs » ouverte sur un nouveau tiers."""

    def __init__(self, hwnd: int, titre: str):
        self.titre = titre
        super().__init__(hwnd)

    def remplir(self, f: FicheTiers, genre: str) -> None:
        if self.lire(CHAMPS["nom"]).strip():
            raise ErreurRobot(f"La fiche affiche déjà « {self.lire(CHAMPS['nom'])} » : rien n'est modifié.")
        for cle, ident in CHAMPS.items():
            valeur = getattr(f, cle, "")
            if not valeur or (cle == "no_taxe" and genre != "fournisseurs"):
                continue
            self.ecrire(ident, valeur)
        self.verifier_nom(f.nom)

    def verifier_nom(self, nom: str) -> None:
        """Sage peut effacer un champ tapé pendant qu'il finit d'ouvrir la fiche (constat du 2026-10-29 : « Veuillez
        entrer nom » pour un fournisseur) : le nom est relu et retapé au besoin."""
        for _ in range(3):
            if self.lire(CHAMPS["nom"]).strip() == nom.strip():
                return
            self.ecrire(CHAMPS["nom"], nom)
            time.sleep(0.5)
        raise ErreurRobot(f"Le nom « {nom} » ne reste pas dans la fiche de Sage.")

    def compte_options(self, numero: str, genre: str) -> bool:
        """Compte de produits (client, liste 80) ou de charges (fournisseur, liste 105) de l'onglet « Options »
        (relevé du 2026-11-03) : onglet affiché au clavier, puis compte choisi comme une personne (focus clavier, flèche),
        sinon tapé dans la liste ; True si la liste affiche le compte."""
        from .robot_encaissements import CB_SETCURSEL
        from .sage_bureau import _descendants, kernel32

        ident = ID_COMPTE_CLIENT if genre == "clients" else ID_COMPTE_FOURNISSEUR
        onglets = next((e for e in _descendants(self.h) if _classe(e) == "SysTabControl32"), None)
        cb = user32.GetDlgItem(self.h, ident)
        for touche in [0x24] + [0x27] * 6:
            if cb and user32.IsWindowVisible(cb):
                break
            if not onglets:
                return False
            user32.SendMessageW(onglets, 0x0100, touche, 0)
            user32.SendMessageW(onglets, 0x0101, touche, 0xC0000000)
            time.sleep(0.4)
        if not (cb and user32.IsWindowVisible(cb)):
            return False
        elements = self._elements(cb)
        if not elements:  # liste remplie par Sage à son ouverture seulement
            user32.SendMessageW(cb, 0x014F, 1, 0)  # CB_SHOWDROPDOWN
            time.sleep(1)
            elements = self._elements(cb)
            user32.SendMessageW(cb, 0x014F, 0, 0)
        import re

        motif = re.compile(rf"(^|\D){re.escape(numero)}(\D|$)")
        index = next((i for i, e in enumerate(elements) if motif.search(e)), None)
        if index is None and not elements:  # toujours vide : le n° est tapé dans la liste, comme une personne
            return self._taper_compte(cb, numero, motif)
        if index is None:
            raise ErreurRobot(f"Compte {numero} absent de la liste de Sage ({len(elements)} éléments, ex. "
                              f"{' | '.join(elements[:3])}).")
        fil, moi = user32.GetWindowThreadProcessId(self.h, None), kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(moi, fil, True)
        try:
            user32.SetActiveWindow(self.h)
            user32.SetFocus(cb)
            time.sleep(0.2)
            user32.SendMessageW(cb, CB_SETCURSEL, max(index - 1, 0) if index else 1, 0)
            touche = 0x28 if index > 0 else 0x26
            user32.SendMessageW(cb, 0x0100, touche, 0)
            user32.SendMessageW(cb, 0x0101, touche, 0xC0000000)
            time.sleep(0.4)
            user32.SetFocus(user32.GetDlgItem(self.h, 112))  # quitter la liste : Sage valide le choix
            time.sleep(0.4)
        finally:
            user32.AttachThreadInput(moi, fil, False)
        return bool(motif.search(self.lire(ident)))

    def _taper_compte(self, cb, numero: str, motif) -> bool:
        from .sage_bureau import kernel32

        edit = user32.FindWindowExW(cb, None, "Edit", None) or cb
        fil, moi = user32.GetWindowThreadProcessId(self.h, None), kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(moi, fil, True)
        try:
            user32.SetActiveWindow(self.h)
            user32.SetFocus(edit)
            time.sleep(0.2)
            for caractere in numero:
                user32.PostMessageW(edit, 0x0102, ord(caractere), 0)  # WM_CHAR
                time.sleep(0.1)
            time.sleep(0.5)
            user32.SetFocus(user32.GetDlgItem(self.h, 112))  # quitter la liste : Sage valide le n°
            time.sleep(0.8)
        finally:
            user32.AttachThreadInput(moi, fil, False)
        for d in self.dialogues():  # n° inconnu : Sage ouvre sa liste de comptes, fermée sans choix
            user32.PostMessageW(d, 0x0010, 0, 0)
        return bool(motif.search(self.lire(user32.GetDlgCtrlID(cb))))

    def mes_numeros(self) -> bool:
        """Coche « … utilise mes numéros d'articles » (onglet trouvé au clavier) ; True si la case est cochée."""
        from .sage_bureau import _descendants, _texte

        onglets = next((e for e in _descendants(self.h) if _classe(e) == "SysTabControl32"), None)

        def case():
            return next((e for e in _descendants(self.h) if _classe(e) == "Button" and user32.IsWindowVisible(e)
                         and "mes n" in _simple(_texte(e))), None)

        for touche in [0x24] + [0x27] * 12:  # Début, puis flèche droite : onglet par onglet, comme une personne
            trouvee = case()
            if trouvee:
                if not user32.SendMessageW(trouvee, BM_GETCHECK, 0, 0):
                    user32.SendMessageW(trouvee, BM_CLICK, 0, 0)
                    time.sleep(0.4)
                return bool(user32.SendMessageW(trouvee, BM_GETCHECK, 0, 0))
            if not onglets:
                return False
            user32.SendMessageW(onglets, 0x0100, touche, 0)
            user32.SendMessageW(onglets, 0x0101, touche, 0xC0000000)
            time.sleep(0.4)
        return False


def ouvrir_liste(session, genre: str) -> int:
    """Liste « Clients » ou « Fournisseurs » de Sage (icône de sa page d'accueil)."""
    from .robot_articles import cliquer_vrai, premier_plan
    from .sage_bureau import ErreurSage, _attendre

    page, icone_nom, _titre, _table = GENRES[genre]
    liste = user32.FindWindowW("SimplyLedger", icone_nom)
    for _ in range(0 if liste else 6):
        if session.processus:
            session.fermer_message_chargement()
        else:
            premier_plan(session.principale)
        icone = icone_tache(session, icone_nom)
        if not icone:
            lien = session._visible(page)
            if lien:
                for cible in (lien, user32.GetParent(lien)):
                    session._cliquer(cible) if session.processus else cliquer_vrai(cible)
                    if _attendre(lambda: icone_tache(session, icone_nom), 4):
                        break
            time.sleep(2)
            continue
        session._cliquer(icone) if session.processus else cliquer_vrai(icone)
        liste = _attendre(lambda: user32.FindWindowW("SimplyLedger", icone_nom), 10)
        if liste:
            break
        time.sleep(2)
    if not liste:
        raise ErreurSage(f"La liste « {icone_nom} » de Sage ne s'ouvre pas.")
    return liste


def creer_tiers(config_toml: dict, genre: str, fiches: list[FicheTiers], journal=print) -> list[ResultatTiers]:
    """Crée les clients ou fournisseurs dans le Sage ouvert sur le fichier configuré, sinon l'application ouvre Sage
    elle-même (commande interne `tiers-bureau`)."""
    from .__main__ import lire_sage
    from .sage_bureau import _attendre

    _page, _icone, titre, table = GENRES[genre]
    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")

    def lu(nom: str):
        colonne = "lAcDefRev" if genre == "clients" else "lAcDefExp"
        lignes = lire_sage(config_toml, lambda b: b.requete(
            f"SELECT bUseMyItem m, {colonne} c FROM {table} WHERE sName = %s", (nom,)), fichier)
        return lignes[0] if lignes else None

    session = ouvrir_session(config_toml, journal)
    resultats, liste = [], None
    try:
        for f in fiches:
            r = ResultatTiers(f.nom)
            if lu(f.nom):
                r.messages.append(f"« {f.nom} » existe déjà dans Sage")
                resultats.append(r)
                continue
            try:
                liste = liste or ouvrir_liste(session, genre)
                user32.PostMessageW(liste, 0x0111, CREER, 0)
                h = _attendre(lambda: user32.FindWindowW("#32770", titre), 10)
                if not h:
                    raise ErreurRobot(f"La fiche « {titre} » ne s'ouvre pas.")
                time.sleep(2)  # la fiche finit de s'ouvrir (sinon Sage efface ce qui est tapé)
                fenetre = FenetreTiers(h, titre)
                fenetre.remplir(f, genre)
                if f.compte and not fenetre.compte_options(f.compte, genre):
                    r.messages.append(f"compte {f.compte} non choisi dans l'onglet Options : à choisir dans Sage")
                r.mes_numeros = fenetre.mes_numeros() if f.mes_numeros else False
                fenetre.verifier_nom(f.nom)  # changer d'onglet ne doit rien avoir effacé
                fenetre.enregistrer(r)
                for _ in range(10):
                    ligne = lu(f.nom)
                    if ligne:
                        r.cree, r.mes_numeros = True, bool(ligne["m"])
                        if f.compte and int(ligne["c"] or 0) // 10000 != int(f.compte):
                            r.messages.append(f"compte {f.compte} absent de la fiche : à choisir dans Sage")
                        break
                    time.sleep(1)
                if not r.cree and not r.messages:
                    r.messages.append("absent de Sage après l'enregistrement")
            except Exception as exc:
                r.messages.append(str(exc))
                reste = user32.FindWindowW("#32770", titre)
                if reste:  # fiche à moitié remplie : fermée sans enregistrer
                    user32.PostMessageW(reste, 0x0010, 0, 0)
            journal(f"{f.nom} : " + ("créé" + ("" if r.mes_numeros else " (case « mes numéros d'articles » à cocher "
                                                                          "dans Sage)") if r.cree else
                                     "NON créé — " + " ; ".join(m for m in r.messages if m)))
            resultats.append(r)
    finally:
        if liste and user32.IsWindow(liste):
            user32.PostMessageW(liste, 0x0010, 0, 0)
        if session.processus:
            session.fermer()
    return resultats


@vide_apres  # mémoire des lectures vidée après une écriture
def creer_dans_sage(racine: Path, config_toml: dict, genre: str, fiches: list[FicheTiers]) -> list[dict]:
    """Sage ouvert sur le fichier configuré : rempli directement ; Sage fermé : l'application l'ouvre elle-même."""
    import tempfile

    from .__main__ import commande_moteur
    from .robot_articles import fenetre_principale_ouverte
    from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")
    if fenetre_principale_ouverte(fichier):
        return [asdict(r) for r in creer_tiers(config_toml, genre, fiches)]
    if sage_ouvert():
        raise RuntimeError("Sage est ouvert sur un autre fichier d'entreprise : fermez-le, l'application l'ouvrira "
                           "elle-même.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        demandes, bilan = Path(dossier) / "tiers.json", Path(dossier) / "bilan.json"
        demandes.write_text(json.dumps({"genre": genre, "fiches": [asdict(f) for f in fiches]}, ensure_ascii=False),
                            encoding="utf-8")
        executer_sur_bureau_cache(commande_moteur() + ["tiers-bureau", "--demande", str(demandes),
                                                      "--resultat", str(bilan)], racine)
        resultat = json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {}
    if resultat.get("erreur"):
        raise RuntimeError(resultat["erreur"])
    return resultat.get("resultats", [])

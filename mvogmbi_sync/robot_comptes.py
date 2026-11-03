"""Plan comptable dans Sage : créer, modifier, supprimer un compte (demande du propriétaire du 2026-11-01).

Relevé du 2026-11-03 sur la copie d'essai (lecture seule) : page « Entreprise » de l'accueil, icône « Plan comptable »
-> liste SimplyLedger « Comptes » (commandes : 3000 Ouvrir, 3001 Ajouter, 3003 Supprimer) -> fiche « Enregistrements
du plan comptable » : n° de compte SimplyNumLimitless 22, description SimplyChar 26, type de compte (SimplyBoldRadio)
40 en-tête de groupe, 41 compte de sous-groupe, 42 compte de groupe, 43 total de sous-groupe, 44 total de groupe ;
« Compte inactif » 200 ; liste de la barre d'outils 504 (compte affiché) ; « Enreg. et Fermer » 1002 ; menu de la
fiche : 411 Ajouter, 423 Enregistrer, 412 Supprimer. Chaque changement est vérifié dans taccount (lId = n° × 10000).
Sage refuse de supprimer un compte qui a des écritures ou un solde : son message est rapporté.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .cache_lectures import vide_apres
from .robot_articles import ErreurRobot, FenetreArticle, _classe, icone_tache, ouvrir_session
from .robot_encaissements import WM_COMMAND
from .robot_tiers import CREER, user32

TITRE = "Enregistrements du plan comptable"
LISTE = "Comptes"
ID_NUMERO, ID_DESCRIPTION, ID_INACTIF, ID_ENREGISTRER, ID_NAVIGATION = 22, 26, 200, 1002, 504
MENU_SUPPRIMER = 412
VUE_PREMIER, VUE_PRECEDENT, VUE_PROCHAIN, VUE_DERNIER = 500, 501, 502, 503
MENU_CHERCHER = 413
DUREE_MAX_NAVIGATION = 150
OUVRIR = 3000
TYPES = {"H": 40, "L": 41, "R": 42, "S": 43, "T": 44}  # taccount.cFunc -> case du type dans la fiche
BM_CLICK, BM_GETCHECK = 0x00F5, 0x00F0


@dataclass
class DemandeCompte:
    action: str              # « creer », « modifier », « supprimer »
    numero: str
    nom: str = ""
    type: str = "R"
    inactif: bool | None = None


@dataclass
class ResultatCompte:
    numero: str
    action: str
    fait: bool = False
    messages: list[str] = field(default_factory=list)


class FenetreCompte(FenetreArticle):
    titre = TITRE

    def comptes_de_la_liste(self) -> list[str]:
        return self._elements(user32.GetDlgItem(self.h, ID_NAVIGATION))

    def aller(self, numero: str) -> None:
        """Affiche le compte `numero`. La liste « Sélect. » de cette fiche reste vide (relevé du 2026-11-03) : la
        fenêtre « Chercher » (menu 413 : n° tapé dans le champ 40, choix « Numéro » 50, bouton « Chercher » 223) amène
        la fiche sur le compte ; à défaut, la fiche est feuilletée (502 Prochain) depuis le premier compte, en au plus
        DUREE_MAX_NAVIGATION secondes."""
        if self.lire(ID_NUMERO).strip() == numero:
            return
        self._chercher(numero)
        if self.lire(ID_NUMERO).strip() == numero:
            time.sleep(0.5)
            return
        cible, fin = int(numero), time.time() + DUREE_MAX_NAVIGATION
        self._vue(VUE_PREMIER)
        while time.time() < fin:
            actuel = self.lire(ID_NUMERO).strip()
            if actuel == numero:
                time.sleep(0.5)
                return
            if (actuel.isdigit() and int(actuel) > cible) or not self._vue(VUE_PROCHAIN):
                break
        raise ErreurRobot(f"La fiche Sage n'affiche pas le compte {numero}.")

    def _chercher(self, numero: str) -> None:
        from .sage_bureau import _attendre

        avant = set(self.dialogues())
        user32.PostMessageW(self.h, WM_COMMAND, MENU_CHERCHER, 0)
        fenetre = _attendre(lambda: user32.FindWindowW("#32770", "Chercher"), 5)
        if not fenetre:
            return
        try:
            user32.SendMessageW(user32.GetDlgItem(fenetre, 50), BM_CLICK, 0, 0)  # chercher par numéro
            champ = user32.GetDlgItem(fenetre, 40)
            import ctypes

            user32.SendMessageW(champ, 0x000C, 0, ctypes.c_wchar_p(numero))
            time.sleep(0.3)
            user32.SendMessageW(user32.GetDlgItem(fenetre, 223), BM_CLICK, 0, 0)
            fin = time.time() + 6
            while time.time() < fin and self.lire(ID_NUMERO).strip() != numero:
                time.sleep(0.2)
        finally:
            if user32.IsWindow(fenetre) and user32.IsWindowVisible(fenetre):
                user32.PostMessageW(fenetre, 0x0010, 0, 0)
            for d in [d for d in self.dialogues() if d not in avant]:
                if not self.repondre(d, ("ok", "non", "no")):
                    user32.PostMessageW(d, 0x0010, 0, 0)

    def _vue(self, commande: int) -> bool:
        """Commande du menu Vue ; True si le compte affiché a changé."""
        avant = self.lire(ID_NUMERO).strip()
        user32.PostMessageW(self.h, WM_COMMAND, commande, 0)
        fin = time.time() + 4
        while time.time() < fin:
            self._repondre_dialogues(("non", "no"))  # « enregistrer les changements ? » : rien n'a été changé
            if self.lire(ID_NUMERO).strip() != avant:
                return True
            time.sleep(0.1)
        return False

    def _repondre_dialogues(self, reponses, notes: list[str] | None = None) -> None:
        for d in self.dialogues():
            texte = self.message(d)
            if notes is not None and texte:
                notes.append(texte)
            if not self.repondre(d, reponses) and not self.repondre(d, ("ok",)):
                user32.PostMessageW(d, 0x0010, 0, 0)

    def type_compte(self, lettre: str) -> None:
        user32.PostMessageW(user32.GetDlgItem(self.h, TYPES[lettre]), BM_CLICK, 0, 0)
        time.sleep(0.5)

    def inactif(self, valeur: bool, notes: list[str]) -> None:
        """« Compte inactif » : Sage refuse en multi-utilisateur (« Impossible de configurer Compte à inactif … mode
        multi-utilisateur », constat du 2026-11-03) ; son message est noté et la demande échoue."""
        case = user32.GetDlgItem(self.h, ID_INACTIF)
        if bool(user32.SendMessageW(case, BM_GETCHECK, 0, 0)) != valeur:
            user32.PostMessageW(case, BM_CLICK, 0, 0)
            time.sleep(1)
            avant = len(notes)
            self._repondre_dialogues(("ok", "oui", "yes"), notes)
            if any("multi-utilisateur" in n for n in notes[avant:]):
                raise ErreurRobot(" ".join(notes[avant:]))

    def enregistrer_compte(self, notes: list[str]) -> None:
        user32.PostMessageW(self.h, WM_COMMAND, ID_ENREGISTRER, user32.GetDlgItem(self.h, ID_ENREGISTRER))
        fin = time.time() + 15
        while time.time() < fin and user32.IsWindow(self.h) and user32.IsWindowVisible(self.h):
            self._repondre_dialogues(("oui", "yes"), notes)
            time.sleep(0.4)

    def supprimer(self, notes: list[str]) -> None:
        user32.PostMessageW(self.h, WM_COMMAND, MENU_SUPPRIMER, 0)
        fin = time.time() + 10
        while time.time() < fin:
            avant = len(notes)
            self._repondre_dialogues(("oui", "yes"), notes)
            if len(notes) > avant and any(m in notes[-1].lower() for m in ("impossible", "ne peut", "cannot")):
                break
            time.sleep(0.4)


def ouvrir_liste(session) -> int:
    from .sage_bureau import ErreurSage, _attendre

    liste = user32.FindWindowW("SimplyLedger", LISTE)
    for _ in range(0 if liste else 5):
        lien = session._visible("Entreprise")
        if lien:
            for cible in (lien, user32.GetParent(lien)):
                session._cliquer(cible)
                if _attendre(lambda: icone_tache(session, "Plan comptable"), 4):
                    break
        icone = icone_tache(session, "Plan comptable")
        if icone:
            session._cliquer(icone)
            liste = _attendre(lambda: user32.FindWindowW("SimplyLedger", LISTE), 10)
            if liste:
                break
        time.sleep(2)
    if not liste:
        raise ErreurSage("La liste « Comptes » (plan comptable) de Sage ne s'ouvre pas.")
    return liste


def traiter(config_toml: dict, demandes: list[DemandeCompte], journal=print) -> list[ResultatCompte]:
    """Applique les demandes dans Sage (ouvert par l'application, multi-utilisateur) et vérifie chacune."""
    from .__main__ import lire_sage
    from .sage_bureau import _attendre

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")

    def lu(numero: str):
        lignes = lire_sage(config_toml, lambda b: b.requete(
            "SELECT TRIM(sName) n, bInactive i FROM taccount WHERE lId = %s", (int(numero) * 10000,)), fichier)
        return lignes[0] if lignes else None

    # rendre un compte inactif (ou actif) : Sage l'exige en mono-utilisateur ; le reste en multi-utilisateur
    session = ouvrir_session(config_toml, journal, mono=any(d.inactif is not None for d in demandes))
    resultats, liste = [], None
    try:
        for d in demandes:
            r = ResultatCompte(d.numero, d.action)
            notes: list[str] = []
            try:
                if not d.numero.isdigit():
                    raise ErreurRobot("Le n° de compte doit être fait de chiffres.")
                existe = lu(d.numero)
                if d.action == "creer" and existe:
                    raise ErreurRobot(f"Le compte {d.numero} existe déjà ({existe['n']}).")
                if d.action != "creer" and not existe:
                    raise ErreurRobot(f"Le compte {d.numero} n'existe pas dans Sage.")
                liste = liste or ouvrir_liste(session)
                # compte existant : fiche ouverte par « Ouvrir » (3000), sa liste de navigation (504) est alors
                # remplie ; nouveau compte : « Ajouter » (3001, liste vide)
                user32.PostMessageW(liste, WM_COMMAND, CREER if d.action == "creer" else OUVRIR, 0)
                h = _attendre(lambda: user32.FindWindowW("#32770", TITRE), 10)
                if not h:
                    raise ErreurRobot(f"La fiche « {TITRE} » ne s'ouvre pas.")
                time.sleep(2)
                f = FenetreCompte(h)
                if d.action == "creer":
                    f.ecrire(ID_NUMERO, d.numero)
                    f.ecrire(ID_DESCRIPTION, d.nom)
                    f.type_compte(d.type or "R")
                    if d.inactif:
                        f.inactif(True, notes)
                    f.enregistrer_compte(notes)
                elif d.action == "modifier":
                    f.aller(d.numero)
                    if d.nom:
                        f.ecrire(ID_DESCRIPTION, d.nom)
                    if d.inactif is not None:
                        f.inactif(d.inactif, notes)
                    f.enregistrer_compte(notes)
                else:
                    f.aller(d.numero)
                    f.supprimer(notes)
                    if user32.IsWindow(h):
                        user32.PostMessageW(h, 0x0010, 0, 0)
                time.sleep(1)
                apres = None
                for _ in range(8):
                    apres = lu(d.numero)
                    if (d.action == "supprimer" and not apres) or (
                            d.action != "supprimer" and apres and (not d.nom or apres["n"] == d.nom.strip())
                            and (d.inactif is None or bool(apres["i"]) == d.inactif)):
                        r.fait = True
                        break
                    time.sleep(1)
                if not r.fait:
                    r.messages.append("changement absent de Sage après l'enregistrement")
            except Exception as exc:
                r.messages.append(str(exc))
            r.messages += [n for n in notes if n]
            reste = user32.FindWindowW("#32770", TITRE)
            if reste:
                user32.PostMessageW(reste, 0x0010, 0, 0)
                time.sleep(1)
            journal(f"{d.action} {d.numero} : {'fait' if r.fait else 'NON fait — ' + ' ; '.join(r.messages)}")
            resultats.append(r)
    finally:
        if liste and user32.IsWindow(liste):
            user32.PostMessageW(liste, 0x0010, 0, 0)
        if session.processus:
            session.fermer()
    return resultats


@vide_apres
def appliquer(racine: Path, config_toml: dict, demandes: list[DemandeCompte]) -> list[dict]:
    """Sage fermé : l'application l'ouvre elle-même (commande interne `comptes-bureau`) ; Sage ouvert sur le fichier
    configuré : refusé (fermez Sage), la fiche de compte de la personne n'est jamais touchée."""
    import json
    import tempfile

    from .__main__ import commande_moteur
    from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

    if sage_ouvert():
        raise RuntimeError("Fermez Sage : l'application l'ouvre elle-même pour changer le plan comptable.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        fichier, bilan = Path(dossier) / "comptes.json", Path(dossier) / "bilan.json"
        fichier.write_text(json.dumps([asdict(d) for d in demandes], ensure_ascii=False), encoding="utf-8")
        executer_sur_bureau_cache(commande_moteur() + ["comptes-bureau", "--demande", str(fichier),
                                                      "--resultat", str(bilan)], racine, delai=600)
        resultat = json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {}
    if resultat.get("erreur"):
        raise RuntimeError(resultat["erreur"])
    return resultat.get("resultats", [])

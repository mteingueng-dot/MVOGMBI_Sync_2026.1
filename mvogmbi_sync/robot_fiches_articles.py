"""Modifier ou supprimer des articles de Sage depuis l'application (demande du propriétaire du 2026-11-03, liste des
articles : « Modifier » et « Supprimer » ne renvoient plus à Sage).

Fiche « Enregistrements des stocks & services » (relevé du 2026-11-03 sur la copie d'essai) : description 24,
« Article inactif » 153, menu Fichier 412 Supprimer (« Oui » à la confirmation), « Enreg. et Fermer » 1002 ; ouverte
par la liste « Stocks & Services » (3000 Ouvrir) puis amenée sur l'article par sa liste de navigation (504,
`FenetreArticle.aller`). Rendre un article inactif : Sage ouvert en mono-utilisateur, comme pour un compte (Sage le
refuse en multi-utilisateur pour un compte, même règle supposée ici). Chaque changement est vérifié dans tinvent.
Sage refuse de supprimer un article qui a des mouvements : son message est rapporté (le rendre inactif à la place).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .cache_lectures import vide_apres
from .robot_articles import COMMANDE_OUVRIR, ID_DESCRIPTION, ErreurRobot, ouvrir_fiche, ouvrir_session
from .robot_encaissements import WM_COMMAND
from .robot_tiers import user32

ID_INACTIF, MENU_SUPPRIMER, ID_ENREGISTRER = 153, 412, 1002
BM_CLICK, BM_GETCHECK = 0x00F5, 0x00F0


@dataclass
class DemandeArticle:
    action: str                 # « modifier » ou « supprimer »
    numero: str
    description: str = ""
    inactif: bool | None = None


@dataclass
class ResultatFiche:
    numero: str
    action: str
    fait: bool = False
    messages: list[str] = field(default_factory=list)


def _repondre(fiche, reponses, notes: list[str]) -> None:
    for d in fiche.dialogues():
        texte = fiche.message(d)
        if texte:
            notes.append(texte)
        if not fiche.repondre(d, reponses) and not fiche.repondre(d, ("ok",)):
            user32.PostMessageW(d, 0x0010, 0, 0)


def traiter(config_toml: dict, demandes: list[DemandeArticle], journal=print) -> list[ResultatFiche]:
    from .__main__ import lire_sage

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")

    def lu(numero: str):
        lignes = lire_sage(config_toml, lambda b: b.requete(
            "SELECT TRIM(sName) n, bInactive i FROM tinvent WHERE sPartCode = %s", (numero,)), fichier)
        return lignes[0] if lignes else None

    session = ouvrir_session(config_toml, journal, mono=any(d.inactif is not None for d in demandes))
    resultats = []
    try:
        for d in demandes:
            r, notes = ResultatFiche(d.numero, d.action), []
            fiche = None
            try:
                if not lu(d.numero):
                    raise ErreurRobot(f"L'article {d.numero} n'existe pas dans Sage.")
                fiche = ouvrir_fiche(session, commande=COMMANDE_OUVRIR)
                time.sleep(1.5)
                fiche.aller(d.numero)
                if d.action == "supprimer":
                    user32.PostMessageW(fiche.h, WM_COMMAND, MENU_SUPPRIMER, 0)
                    fin = time.time() + 10
                    while time.time() < fin and user32.IsWindow(fiche.h):
                        _repondre(fiche, ("oui", "yes"), notes)
                        if any(m in " ".join(notes).lower() for m in ("impossible", "ne peut", "ne pouvez", "cannot")):
                            break
                        time.sleep(0.4)
                else:
                    if d.description:
                        fiche.ecrire(ID_DESCRIPTION, d.description)
                    if d.inactif is not None:
                        case = user32.GetDlgItem(fiche.h, ID_INACTIF)
                        if bool(user32.SendMessageW(case, BM_GETCHECK, 0, 0)) != d.inactif:
                            user32.PostMessageW(case, BM_CLICK, 0, 0)  # jamais SendMessage : une question bloquerait
                            time.sleep(1)
                            _repondre(fiche, ("ok", "oui", "yes"), notes)
                    user32.PostMessageW(fiche.h, WM_COMMAND, ID_ENREGISTRER, user32.GetDlgItem(fiche.h, ID_ENREGISTRER))
                    fin = time.time() + 15
                    while time.time() < fin and user32.IsWindow(fiche.h) and user32.IsWindowVisible(fiche.h):
                        _repondre(fiche, ("oui", "yes"), notes)
                        time.sleep(0.4)
                for _ in range(8):
                    apres = lu(d.numero)
                    if (d.action == "supprimer" and not apres) or (
                            d.action == "modifier" and apres and (not d.description or apres["n"] == d.description)
                            and (d.inactif is None or bool(apres["i"]) == d.inactif)):
                        r.fait = True
                        break
                    time.sleep(1)
                if not r.fait:
                    r.messages.append("changement absent de Sage")
            except Exception as exc:
                r.messages.append(str(exc))
            finally:
                if fiche is not None and user32.IsWindow(fiche.h):
                    user32.PostMessageW(fiche.h, 0x0010, 0, 0)
                    time.sleep(1)
                    _repondre(fiche, ("non", "no"), [])
            r.messages += notes
            journal(f"{d.action} {d.numero} : {'fait' if r.fait else 'NON fait — ' + ' ; '.join(r.messages)}")
            resultats.append(r)
    finally:
        if session.processus:
            session.fermer()
    return resultats


@vide_apres
def appliquer(racine: Path, config_toml: dict, demandes: list[DemandeArticle]) -> list[dict]:
    """Sage fermé : l'application l'ouvre elle-même (commande interne `fiches-articles-bureau`)."""
    import tempfile

    from .__main__ import commande_moteur
    from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

    if sage_ouvert():
        raise RuntimeError("Fermez Sage : l'application l'ouvre elle-même pour modifier les articles.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        fichier, bilan = Path(dossier) / "articles.json", Path(dossier) / "bilan.json"
        fichier.write_text(json.dumps([asdict(d) for d in demandes], ensure_ascii=False), encoding="utf-8")
        executer_sur_bureau_cache(commande_moteur() + ["fiches-articles-bureau", "--demande", str(fichier),
                                                      "--resultat", str(bilan)], racine, delai=600)
        resultat = json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {}
    if resultat.get("erreur"):
        raise RuntimeError(resultat["erreur"])
    return resultat.get("resultats", [])

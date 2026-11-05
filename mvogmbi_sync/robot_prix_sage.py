"""Prix de vente régulier d'un article écrit dans Sage (prix_sage.py).

Fiche « Enregistrements des stocks & services » (relevé du 2026-11-04 sur la copie d'essai) : ouverte par la liste
« Stocks & Services » (3000 Ouvrir) puis amenée sur l'article (`FenetreArticle.aller`) ; 3e onglet (flèches clavier
sur la SysTabControl32 : Début, Droite, Droite) = grille des prix CA_Container32 3679 (535 × 117) : ligne « Régulier »
y=25, colonne du prix x=150 ; un clic ouvre l'éditeur CntSimEdit, le prix se TAPE avec la virgule décimale
(« 1.23 » tapé donne 123,00 : constat du 2026-11-04) puis Tab ; « Enreg. et Fermer » 1002. Vérifié dans tinvprc
(liste 1).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

from .cache_lectures import vide_apres
from .robot_articles import COMMANDE_OUVRIR, ErreurRobot, ouvrir_fiche, ouvrir_session
from .robot_tiers import _classe, user32

X_PRIX, Y_REGULIER = 150, 25
ID_ENREGISTRER = 1002


@dataclass
class DemandePrix:
    numero: str
    prix: str  # « 12.99 »


@dataclass
class ResultatPrix:
    numero: str
    fait: bool = False
    messages: list[str] = field(default_factory=list)


def _texte_prix(prix: str) -> str:
    return f"{Decimal(prix):.2f}".replace(".", ",")


def traiter(config_toml: dict, demandes: list[DemandePrix], journal=print) -> list[ResultatPrix]:
    from .__main__ import lire_sage
    from .robot_paie import _clic, _tab, _taper
    from .sage_bureau import _descendants

    fichier = config_toml.get("sage_import", {}).get("fichier_entreprise")

    def lu(numero: str):
        lignes = lire_sage(config_toml, lambda b: b.requete(
            "SELECT p.dPrice p FROM tinvprc p JOIN tinvent i ON i.lId = p.lInventId WHERE i.sPartCode = %s "
            "AND p.lPrcListId = 1 AND p.lCurrncyId = 1", (numero,)), fichier)
        return Decimal(str(lignes[0]["p"])).quantize(Decimal("0.01")) if lignes else None

    session = ouvrir_session(config_toml, journal)
    resultats = []
    try:
        for d in demandes:
            r, fiche = ResultatPrix(d.numero), None
            voulu = Decimal(d.prix).quantize(Decimal("0.01"))
            try:
                if lu(d.numero) == voulu:
                    r.fait = True
                    r.messages.append("déjà à ce prix")
                    resultats.append(r)
                    continue
                fiche = ouvrir_fiche(session, commande=COMMANDE_OUVRIR)
                time.sleep(1.5)
                fiche.aller(d.numero)
                time.sleep(1)
                h = fiche.h
                onglets = next(e for e in _descendants(h) if _classe(e) == "SysTabControl32")
                for touche in (0x24, 0x27, 0x27):
                    user32.SendMessageW(onglets, 0x0100, touche, 0)
                    user32.SendMessageW(onglets, 0x0101, touche, 0xC0000000)
                    time.sleep(0.8)
                conteneur = next((e for e in _descendants(h) if _classe(e) == "CA_Container32"
                                  and user32.IsWindowVisible(e)), None)
                if not conteneur:
                    raise ErreurRobot("La grille des prix de la fiche de Sage ne s'affiche pas.")
                grille = next(e for e in _descendants(conteneur) if _classe(e) == "CA_ContainerChild32")
                _clic(grille, X_PRIX, Y_REGULIER)
                editeur = next((c for c in _descendants(conteneur) if _classe(c) == "CntSimEdit"
                                and user32.IsWindowVisible(c)), None)
                if not editeur:
                    raise ErreurRobot("La case du prix régulier ne s'ouvre pas dans la fiche de Sage.")
                user32.PostMessageW(editeur, 0x00B1, 0, -1)  # EM_SETSEL : tout le prix actuel
                time.sleep(0.2)
                _taper(editeur, _texte_prix(d.prix))
                _tab(editeur)
                user32.PostMessageW(h, 0x0111, ID_ENREGISTRER, user32.GetDlgItem(h, ID_ENREGISTRER))
                fin = time.time() + 15
                while time.time() < fin and user32.IsWindow(h) and user32.IsWindowVisible(h):
                    for q in fiche.dialogues():
                        texte = fiche.message(q)
                        if texte:
                            r.messages.append(texte)
                        fiche.repondre(q, ("oui", "yes", "ok"))
                    time.sleep(0.5)
                for _ in range(8):
                    if lu(d.numero) == voulu:
                        r.fait = True
                        break
                    time.sleep(1)
                if not r.fait:
                    r.messages.append(f"prix absent de Sage (lu : {lu(d.numero)})")
            except Exception as exc:  # noqa: BLE001
                r.messages.append(str(exc))
            finally:
                if fiche is not None and user32.IsWindow(fiche.h):
                    user32.PostMessageW(fiche.h, 0x0010, 0, 0)
                    time.sleep(1)
                    for q in fiche.dialogues():
                        fiche.repondre(q, ("non", "no"))
            journal(f"prix {d.numero} -> {d.prix} : {'fait' if r.fait else 'NON fait — ' + ' ; '.join(r.messages)}")
            resultats.append(r)
    finally:
        if session.processus:
            session.fermer()
    return resultats


@vide_apres
def appliquer(racine: Path, config_toml: dict, demandes: list[DemandePrix]) -> list[dict]:
    """Sage fermé : l'application l'ouvre elle-même (commande interne `prix-sage-bureau`)."""
    import tempfile

    from .__main__ import commande_moteur
    from .sage_bureau import executer_sur_bureau_cache, sage_ouvert

    if not demandes:
        return []
    if sage_ouvert():
        raise RuntimeError("Fermez Sage : l'application l'ouvre elle-même pour changer les prix.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        fichier, bilan = Path(dossier) / "prix.json", Path(dossier) / "bilan.json"
        fichier.write_text(json.dumps([asdict(d) for d in demandes], ensure_ascii=False), encoding="utf-8")
        executer_sur_bureau_cache(commande_moteur() + ["prix-sage-bureau", "--demande", str(fichier),
                                                      "--resultat", str(bilan)], racine,
                                  delai=max(600, 40 * len(demandes)))
        resultat = json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {}
    if resultat.get("erreur"):
        raise RuntimeError(resultat["erreur"])
    return resultat.get("resultats", [])

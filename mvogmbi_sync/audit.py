"""Table d'audit de toutes les actions (demande du propriétaire du 2026-11-01).

Chaque action est une ligne de donnees/audit.jsonl : moment, poste, utilisateur, fenêtre, action, détail. On n'y
ajoute que des lignes (rien n'est jamais réécrit) et chaque ligne porte l'empreinte de la précédente (`chaine`) :
une ligne modifiée ou retirée après coup se voit (`verifier`). Sont notés : chaque bouton cliqué dans l'application
(design.Bouton), chaque entrée du menu ouverte, les connexions et refus, les verrouillages. Jamais de mot de passe ni
de NAS : seulement le libellé du bouton et le titre de la fenêtre.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

FICHIER = "audit.jsonl"
_VERROU = threading.Lock()
SESSION = {"racine": None, "utilisateur": ""}  # réglé à la connexion (interface.Application)


@dataclass
class Entree:
    moment: str
    poste: str
    utilisateur: str
    fenetre: str
    action: str
    detail: str = ""
    chaine: str = ""  # empreinte SHA-256 de la ligne précédente + de celle-ci

    def calcul(self, precedente: str) -> str:
        contenu = json.dumps([precedente, self.moment, self.poste, self.utilisateur, self.fenetre, self.action,
                              self.detail], ensure_ascii=False)
        return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


def _chemin(racine) -> Path:
    return Path(racine) / "donnees" / FICHIER


def _derniere_chaine(chemin: Path) -> str:
    if not chemin.exists() or chemin.stat().st_size == 0:
        return ""
    with open(chemin, "rb") as f:
        f.seek(max(0, chemin.stat().st_size - 4096))
        lignes = f.read().decode("utf-8", "replace").strip().splitlines()
    try:
        return json.loads(lignes[-1]).get("chaine", "")
    except (ValueError, IndexError):
        return ""


def noter(racine, action: str, fenetre: str = "", detail: str = "", utilisateur: str | None = None) -> None:
    """Ajoute une ligne (sans jamais lever d'erreur : l'audit ne bloque pas le travail)."""
    racine = racine or SESSION["racine"]
    if racine is None or not action:
        return
    try:
        with _VERROU:
            chemin = _chemin(racine)
            chemin.parent.mkdir(parents=True, exist_ok=True)
            e = Entree(datetime.now().isoformat(timespec="seconds"), socket.gethostname(),
                       SESSION["utilisateur"] if utilisateur is None else utilisateur, fenetre[:120], action[:200],
                       detail[:500])
            e.chaine = e.calcul(_derniere_chaine(chemin))
            with open(chemin, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(e), ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
    except Exception:
        pass


def lire(racine) -> list[Entree]:
    chemin = _chemin(racine)
    if not chemin.exists():
        return []
    entrees = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        try:
            entrees.append(Entree(**json.loads(ligne)))
        except (ValueError, TypeError):
            entrees.append(Entree("", "", "", "", "(ligne illisible)", ligne[:200], "x"))
    return entrees


def verifier(entrees: list[Entree]) -> list[int]:
    """Rangs (0 = première ligne) dont l'empreinte ne suit pas : ligne changée, retirée ou insérée après coup."""
    rompues, precedente = [], ""
    for rang, e in enumerate(entrees):
        if e.chaine != e.calcul(precedente):
            rompues.append(rang)
        precedente = e.chaine
    return rompues

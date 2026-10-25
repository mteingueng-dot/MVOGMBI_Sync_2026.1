"""Tâche planifiée Windows qui lance le traitement automatique chaque jour (ex. à 1 h).

La tâche s'exécute dans la session de l'utilisateur (ordinateur allumé, session ouverte) : l'outil d'import
de Sage affiche des fenêtres auxquelles l'application répond, ce qui exige une session Windows active.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

NOM_TACHE = "MVOGMBI_Sync - import des ventes Clover dans Sage"


def commande_lancement(racine: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve().with_name("MVOGMBI_Sync_console.exe")), "auto"]
    executable = Path(sys.executable)
    sans_console = executable.with_name("pythonw.exe")
    return [str(sans_console if sans_console.exists() else executable), "-m", "mvogmbi_sync", "auto"]


def ecrire_lanceur(racine: Path) -> Path:
    """Fichier .cmd lancé par la tâche : se place dans le dossier de l'application et garde une trace."""
    commande = " ".join(f'"{c}"' if " " in c else c for c in commande_lancement(racine))
    lanceur = racine / "lancer_traitement.cmd"
    lanceur.write_text(
        "@echo off\r\n"
        f'cd /d "{racine}"\r\n'
        f'{commande} >> "donnees\\sortie_traitement.log" 2>&1\r\n',
        encoding="cp1252",
    )
    return lanceur


def installer(racine: Path, heure: str = "01:00") -> str:
    lanceur = ecrire_lanceur(racine)
    resultat = subprocess.run(
        ["schtasks", "/Create", "/F", "/TN", NOM_TACHE, "/SC", "DAILY", "/ST", heure,
         "/TR", f'"{lanceur}"', "/RL", "LIMITED"],
        capture_output=True, text=True, encoding="cp850",
    )
    if resultat.returncode != 0:
        raise RuntimeError(resultat.stderr.strip() or resultat.stdout.strip())
    return f"Tâche « {NOM_TACHE} » installée : chaque jour à {heure}."


def retirer() -> str:
    resultat = subprocess.run(["schtasks", "/Delete", "/F", "/TN", NOM_TACHE],
                              capture_output=True, text=True, encoding="cp850")
    if resultat.returncode != 0:
        raise RuntimeError(resultat.stderr.strip() or resultat.stdout.strip())
    return f"Tâche « {NOM_TACHE} » retirée."


def etat() -> str:
    resultat = subprocess.run(["schtasks", "/Query", "/TN", NOM_TACHE, "/V", "/FO", "LIST"],
                              capture_output=True, text=True, encoding="cp850")
    if resultat.returncode != 0:
        return "Tâche non installée."
    utiles = [l for l in resultat.stdout.splitlines()
              if l.split(":")[0].strip().lower() in ("prochaine exécution", "heure de la dernière exécution",
                                                     "dernier résultat", "statut", "next run time",
                                                     "last run time", "last result", "status")]
    return "\n".join(utiles) or "Tâche installée."

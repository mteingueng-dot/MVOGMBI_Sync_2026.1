"""Plan comptable de Sage (taccount) dans l'application (demande du propriétaire du 2026-11-01) : liste, et contrôle
que chaque compte saisi dans une opération (dépense, RIA, comptes par catégorie, client, fournisseur…) existe dans
le plan et y est actif. Créer, modifier, supprimer : robot_comptes.py."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

CLASSES = {1: "Actif", 2: "Passif", 3: "Capitaux propres", 4: "Produits", 5: "Charges"}


@dataclass
class Compte:
    numero: str
    nom: str
    type: str          # taccount.cFunc : H en-tête, L sous-groupe, R groupe, S / T totaux, X bénéfice net
    inactif: bool
    solde: Decimal

    @property
    def classe(self) -> str:
        return CLASSES.get(int(self.numero[0]) if self.numero[:1].isdigit() else 0, "")


def lire(base) -> list[Compte]:
    lignes = base.requete("SELECT lId, TRIM(sName) n, cFunc t, bInactive i, dYts s FROM taccount ORDER BY lId")
    return [Compte(str(int(l["lId"]) // 10000), l["n"] or "", str(l["t"] or "").strip(), bool(l["i"]),
                   Decimal(str(l["s"] or 0))) for l in lignes]


TYPES = {"H": "En-tête de groupe", "L": "Compte de sous-groupe", "R": "Compte de groupe", "S": "Total de sous-groupe",
         "T": "Total de groupe", "X": "Bénéfice de l'exercice"}
DETAIL = ("L", "R")  # comptes où l'on passe des écritures


def comptes_connus(racine: Path, config_toml: dict, forcer: bool = False) -> dict[str, Compte]:
    """N° -> compte, lu dans Sage (mémoire partagée de cache_lectures, 5 min) ; {} si Sage ne se lit pas."""
    from .cache_lectures import lire as memoire

    def lecture():
        from .__main__ import lire_sage

        return {c.numero: c for c in lire_sage(config_toml, lire, config_toml.get("sage_import", {}).get(
            "fichier_entreprise"), ouvrir=False)}

    try:
        return memoire("plan_comptable", lecture, forcer=forcer)
    except Exception:
        return {}


def problemes(numeros, connus: dict[str, Compte]) -> list[str]:
    """Comptes absents du plan ou inactifs (vide si tout va, ou si le plan n'a pas pu être lu)."""
    if not connus:
        return []
    sortie = []
    for n in [str(x).strip() for x in numeros if str(x).strip()]:
        c = connus.get(n)
        if c is None:
            sortie.append(f"compte {n} absent du plan comptable de Sage")
        elif c.inactif:
            sortie.append(f"compte {n} inactif dans Sage")
        elif c.type and c.type not in DETAIL:
            sortie.append(f"compte {n} ({c.nom}) est un en-tête ou un total : choisissez un compte de détail")
    return sortie


def verifier(racine: Path, config_toml: dict, numeros) -> None:
    """Refuse (ValueError) une opération dont un compte n'existe pas dans le plan comptable (règle du propriétaire
    du 2026-11-01)."""
    erreurs = problemes(numeros, comptes_connus(racine, config_toml))
    if erreurs:
        raise ValueError(" ; ".join(erreurs) + ". Créez-le dans « Comptabilité > Plan comptable ».")

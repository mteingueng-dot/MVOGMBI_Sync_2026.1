"""Comparaison article par article de deux rapports (export Clover vs API Clover)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from .models import LigneVente, RapportVentes

ZERO = Decimal("0")


@dataclass
class Ecart:
    nom: str
    export: LigneVente | None
    api: LigneVente | None

    def valeurs(self, ligne: LigneVente | None) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        if ligne is None:
            return ZERO, ZERO, ZERO, ZERO
        return ligne.quantite_nette, ligne.ventes_brutes, ligne.rabais + ligne.remboursements, ligne.ventes_nettes


def _par_nom(rapport: RapportVentes) -> dict[str, LigneVente]:
    """Regroupe par nom d'article (insensible à la casse et aux espaces) ; la catégorie est ignorée."""
    resultat: dict[str, LigneVente] = {}
    for ligne in rapport.lignes:
        cle = " ".join(ligne.nom.lower().split())
        if cle not in resultat:
            resultat[cle] = LigneVente(categorie=ligne.categorie, nom=ligne.nom)
        resultat[cle].ajouter(ligne)
    return resultat


def comparer(export: RapportVentes, api: RapportVentes) -> list[Ecart]:
    a, b = _par_nom(export), _par_nom(api)
    ecarts = []
    for cle in sorted(a.keys() | b.keys()):
        ecart = Ecart(nom=(a.get(cle) or b[cle]).nom, export=a.get(cle), api=b.get(cle))
        if ecart.valeurs(ecart.export) != ecart.valeurs(ecart.api):
            ecarts.append(ecart)
    return ecarts


def ecrire_comparaison(ecarts: list[Ecart], chemin: Path) -> Path:
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Écarts"
    feuille.append([
        "Article", "Qté export", "Qté API", "Brut export", "Brut API",
        "Rabais+remb. export", "Rabais+remb. API", "Net export", "Net API", "Écart net",
    ])
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    for e in ecarts:
        qe, be, re, ne = e.valeurs(e.export)
        qa, ba, ra, na = e.valeurs(e.api)
        feuille.append([e.nom, qe, qa, be, ba, re, ra, ne, na, na - ne])
    feuille.column_dimensions["A"].width = 48
    chemin.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(chemin)
    return chemin

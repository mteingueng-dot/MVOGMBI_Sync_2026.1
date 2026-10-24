"""Lecture de l'export Excel « Ventes d'articles » du tableau de bord Clover (version française)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl

from .models import LigneVente, RapportVentes, cumuler

COLONNES = {
    "categorie": "Nom de la catégorie",
    "nom": "Nom",
    "vendu": "Vendu(e)",
    "rembourse": "Remboursé(e)",
    "brutes": "Ventes brutes d'articles",
    "rabais": "Rabais",
    "remboursements": "Remboursements",
}


def montant(valeur) -> Decimal:
    """Convertit '1 234,56 $', '-31,04 $', '10544.14' ou un nombre en Decimal."""
    if valeur is None:
        return Decimal("0")
    if isinstance(valeur, (int, float, Decimal)):
        return Decimal(str(valeur))
    texte = str(valeur).replace("\xa0", "").replace(" ", "").replace(" ", "").replace("$", "")
    if texte in ("", "-"):
        return Decimal("0")
    if "," in texte:
        texte = texte.replace(".", "").replace(",", ".")
    try:
        return Decimal(texte)
    except InvalidOperation as exc:
        raise ValueError(f"Montant illisible : {valeur!r}") from exc


def lire_export(chemin: Path, debut: date, fin: date) -> RapportVentes:
    """Lit un export Clover. La période n'est pas dans le fichier : elle est fournie par l'utilisateur."""
    feuille = openpyxl.load_workbook(chemin, data_only=True, read_only=True).worksheets[0]
    lignes_brutes = feuille.iter_rows(values_only=True)
    entete = [str(c).strip() if c is not None else "" for c in next(lignes_brutes)]
    try:
        index = {cle: entete.index(titre) for cle, titre in COLONNES.items()}
    except ValueError as exc:
        raise ValueError(f"Colonne attendue absente de l'export Clover : {exc}") from exc

    lignes: list[LigneVente] = []
    for rangee in lignes_brutes:
        categorie = rangee[index["categorie"]]
        if categorie is None or str(categorie).strip().upper() == "TOTAL":
            continue
        lignes.append(
            LigneVente(
                categorie=str(categorie).strip(),
                nom=str(rangee[index["nom"]] or "").strip(),
                quantite_vendue=montant(rangee[index["vendu"]]),
                quantite_remboursee=montant(rangee[index["rembourse"]]),
                ventes_brutes=montant(rangee[index["brutes"]]),
                rabais=montant(rangee[index["rabais"]]),
                remboursements=montant(rangee[index["remboursements"]]),
            )
        )
    return RapportVentes(debut=debut, fin=fin, source=f"Export Clover : {chemin.name}", lignes=cumuler(lignes))

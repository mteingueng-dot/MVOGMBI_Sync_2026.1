"""Lecture des exports « Ventes d'articles » du tableau de bord Clover (version française).

Deux formats existent :
- Excel (.xlsx) : une ligne par article, catégorie répétée sur chaque ligne ;
- CSV (.csv) : en-tête de rapport (période, totaux), puis une ligne par catégorie
  suivie de ses articles (première colonne vide).
"""

from __future__ import annotations

import csv
import re
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


MOIS = {m: i for i, m in enumerate(
    ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"], start=1)}
RE_DATE_CSV = re.compile(r"(\d{1,2}) (\w+)\.? (\d{4})")


def periode_csv(texte: str) -> tuple[date, date] | None:
    """« ven. 23 oct. 2026, 00 h 00 - ven. 23 oct. 2026, 23 h 59 » -> (2026-10-23, 2026-10-23)."""
    dates = []
    for jour, mois, annee in RE_DATE_CSV.findall(texte):
        if mois.lower().rstrip(".") not in MOIS:
            return None
        dates.append(date(int(annee), MOIS[mois.lower().rstrip(".")], int(jour)))
    return (dates[0], dates[-1]) if len(dates) >= 2 else None


def lire_export_csv(chemin: Path, debut: date | None = None, fin: date | None = None) -> RapportVentes:
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        rangees = list(csv.reader(fichier))

    periode = next((p for r in rangees[:6] if r and (p := periode_csv(r[0]))), None)
    if periode and (debut or fin) and periode != (debut, fin):
        raise ValueError(f"Le fichier couvre {periode[0]} → {periode[1]}, pas {debut} → {fin}.")
    debut, fin = periode or (debut, fin)
    if debut is None or fin is None:
        raise ValueError("Période introuvable dans le fichier : indiquez-la avec --date.")

    try:
        n_entete = next(i for i, r in enumerate(rangees) if r and r[0] == "Catégorie")
    except StopIteration as exc:
        raise ValueError("En-tête « Catégorie » absent de l'export CSV Clover.") from exc
    entete = rangees[n_entete]
    index = {cle: entete.index(titre) for cle, titre in {
        "article": "Catégorie / Article", "brutes": "Ventes brutes", "vendu": "Vendu(e)",
        "rabais": "Rabais", "remboursements": "Remboursements",
    }.items()}

    lignes: list[LigneVente] = []
    categorie = ""
    for rangee in rangees[n_entete + 1:]:
        if not rangee or not any(rangee):
            continue
        if rangee[0]:
            categorie = rangee[0].strip()  # ligne de sous-total de catégorie (ou « Total »)
            continue
        lignes.append(LigneVente(
            categorie=categorie,
            nom=rangee[index["article"]].strip(),
            quantite_vendue=montant(rangee[index["vendu"]]),
            ventes_brutes=montant(rangee[index["brutes"]]),
            rabais=montant(rangee[index["rabais"]]),
            remboursements=montant(rangee[index["remboursements"]]),
        ))
    return RapportVentes(debut=debut, fin=fin, source=f"Export Clover : {chemin.name}", lignes=cumuler(lignes))


def lire_export(chemin: Path, debut: date | None = None, fin: date | None = None) -> RapportVentes:
    """Lit un export Clover (.csv ou .xlsx).

    Le CSV contient sa période ; pour l'Excel, la période doit être fournie.
    """
    if chemin.suffix.lower() == ".csv":
        return lire_export_csv(chemin, debut, fin)
    if debut is None or fin is None:
        raise ValueError("L'export Excel ne contient pas sa période : indiquez-la avec --date.")
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

"""Lecture de la liste des articles exportée de Sage 50 (fichier texte, Windows-1252).

Format observé (« E:\\Article.txt ») : une ligne d'en-tête « 33101,3,Inventory », puis une ligne par article :
numéro, description, type (Inventory / Service), unité, prix, prix, compte d'actif,
compte de revenus, compte CPV, compte d'écart, description 2, unité de vente.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArticleSage:
    numero: str
    description: str
    type: str
    compte_revenus: str


def reparer_texte(texte: str) -> str:
    """Corrige les accents abîmés par une double conversion (« DepulpÃ© » -> « Depulpé »)."""
    if "Ã" not in texte and "Â" not in texte:
        return texte
    try:
        return texte.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texte


def lire_articles_sage(chemin: Path) -> list[ArticleSage]:
    with chemin.open(encoding="cp1252", newline="") as fichier:
        rangees = list(csv.reader(fichier))
    articles = []
    for rangee in rangees[1:]:
        if len(rangee) < 12 or not rangee[0].strip() or rangee[0].strip() == ".":
            continue
        articles.append(ArticleSage(
            numero=rangee[0].strip(),
            description=reparer_texte(rangee[1].strip()),
            type=rangee[2].strip(),
            compte_revenus=rangee[7].strip(),
        ))
    return articles

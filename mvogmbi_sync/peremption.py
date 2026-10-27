"""Dates de péremption des articles (règle du propriétaire du 2026-10-27) : la date est saisie dans le champ SKU de
l'article Clover (le plus souvent « JJ/MM/AAAA »). Les SKU vides ou qui ne sont pas une date (codes-barres…) sont
ignorés. Trois couleurs : plus de 3 mois = fond neutre, de 1 à 3 mois = jaune, un mois ou moins (et périmé) = rouge.
"""

from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

NEUTRE, ORANGE, ROUGE = "Plus de 3 mois", "De 1 à 3 mois", "Un mois ou moins"
PERIME = "Périmé"
FORMATS = [  # jour en premier (usage québécois)
    (re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$"), ("j", "m", "a")),
    (re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2})$"), ("j", "m", "aa")),
    (re.compile(r"^(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})$"), ("a", "m", "j")),
]


def lire_date(texte: str | None) -> date | None:
    """« 25/05/2028 » -> 2028-05-25 ; None si vide ou pas une date valide."""
    texte = (texte or "").strip()
    for motif, ordre in FORMATS:
        trouve = motif.match(texte)
        if not trouve:
            continue
        valeurs = dict(zip(ordre, (int(x) for x in trouve.groups())))
        annee = valeurs.get("a") or 2000 + valeurs["aa"]
        try:
            return date(annee, valeurs["m"], valeurs["j"])
        except ValueError:
            return None
    return None


def ajouter_mois(jour: date, mois: int) -> date:
    m = jour.month - 1 + mois
    annee, m = jour.year + m // 12, m % 12 + 1
    return date(annee, m, min(jour.day, monthrange(annee, m)[1]))


@dataclass
class ArticlePeremption:
    nom: str
    sku: str
    peremption: date
    jours: int
    etat: str
    couleur: str          # « rouge », « orange » ou « neutre »
    categorie: str
    stock: Decimal | None
    prix: Decimal


def etat(peremption: date, aujourdhui: date) -> tuple[str, str]:
    if peremption < aujourdhui:
        return PERIME, "rouge"
    if peremption <= ajouter_mois(aujourdhui, 1):
        return ROUGE, "rouge"
    if peremption <= ajouter_mois(aujourdhui, 3):
        return ORANGE, "orange"
    return NEUTRE, "neutre"


def articles_peremption(articles: list[dict], aujourdhui: date | None = None) -> list[ArticlePeremption]:
    """Articles Clover (avec catégories et stock) dont le SKU est une date, du plus proche au plus lointain."""
    a = aujourdhui or date.today()
    resultat = []
    for x in articles:
        if x.get("deleted"):
            continue
        jour = lire_date(x.get("sku"))
        if not jour:
            continue
        nom_etat, couleur = etat(jour, a)
        stock = (x.get("itemStock") or {}).get("quantity")
        categories = (x.get("categories") or {}).get("elements") or []
        resultat.append(ArticlePeremption(
            (x.get("name") or "").strip(), x["sku"].strip(), jour, (jour - a).days, nom_etat, couleur,
            categories[0].get("name", "") if categories else "",
            None if stock is None else Decimal(str(stock)).normalize(), Decimal(int(x.get("price") or 0)) / 100))
    return sorted(resultat, key=lambda p: (p.peremption, p.nom))

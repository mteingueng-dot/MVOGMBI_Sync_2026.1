"""Étiquettes de prix avec code-barres (demande du propriétaire du 2026-10-29) : feuille d'étiquettes 3 × 10
(format Avery 5160 / 8160 : 66,7 × 25,4 mm) imprimée par le navigateur ; nom, prix (au kg ou à l'unité), code
produit en code-barres Code 128 dessiné en SVG (aucune bibliothèque). Articles choisis à la main, ou ceux dont le prix a
changé depuis une date (journal des prix Clover)."""

from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# Code 128 : motifs des valeurs 0 à 106 (largeurs barre/espace)
MOTIFS = ("212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 "
          "113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 "
          "212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 "
          "113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 "
          "314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 "
          "241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 "
          "214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 "
          "211232 2331112").split()
DEBUT_B, ARRET = 104, 106


def code128(texte: str) -> list[int]:
    """Valeurs Code 128 (jeu B) avec la clé de contrôle et l'arrêt."""
    valeurs = [DEBUT_B] + [ord(c) - 32 for c in texte if 32 <= ord(c) <= 126]
    cle = (valeurs[0] + sum(i * v for i, v in enumerate(valeurs[1:], 1))) % 103
    return valeurs + [cle, ARRET]


def svg_code_barres(texte: str, hauteur: int = 34, module: float = 1.0) -> str:
    x, barres = 10.0, []  # zone calme de 10 modules
    for valeur in code128(texte):
        for i, largeur in enumerate(MOTIFS[valeur]):
            w = int(largeur) * module
            if i % 2 == 0:
                barres.append(f"<rect x='{x:.1f}' y='0' width='{w:.1f}' height='{hauteur}'/>")
            x += w
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {x + 10:.0f} {hauteur}' "
            f"preserveAspectRatio='none' class='cb'>{''.join(barres)}</svg>")


@dataclass
class Etiquette:
    nom: str
    prix: Decimal
    unite: str = ""     # « kg », « lb » pour un prix au poids
    code: str = ""


def depuis_article(a: dict) -> Etiquette:
    unite = (a.get("unitName") or "").strip() if a.get("priceType") == "PER_UNIT" else ""
    return Etiquette((a.get("name") or "").strip(), Decimal(int(a.get("price") or 0)) / 100, unite,
                     str(a.get("code") or a.get("sku") or "").strip())


def prix_changes(racine: Path, depuis: str) -> set[str]:
    """ID Clover des articles dont le prix a changé depuis `depuis` (AAAA-MM-JJ), d'après journal_prix_clover.csv."""
    chemin = Path(racine) / "donnees" / "journal_prix_clover.csv"
    if not chemin.exists():
        return set()
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        return {r.get("ID Clover", "") for r in csv.DictReader(f, delimiter=";") if (r.get("Date") or "")[:10] >= depuis}


def page(etiquettes: list[Etiquette], imprimer: bool = True) -> str:
    e = html.escape
    cases = []
    for x in etiquettes:
        prix = f"{x.prix:,.2f} $".replace(",", " ").replace(".", ",") + (f" / {e(x.unite)}" if x.unite else "")
        cb = svg_code_barres(x.code) if x.code else ""
        cases.append(f"<div class='e'><div class='n'>{e(x.nom)}</div><div class='p'>{prix}</div>"
                     f"{cb}<div class='c'>{e(x.code)}</div></div>")
    script = "<script>window.addEventListener('load', () => window.print());</script>" if imprimer else ""
    return f"""<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Étiquettes de prix</title><style>
@page {{ size: Letter; margin: 12.7mm 4.8mm; }}
body {{ margin: 0; font-family: 'Segoe UI', Arial, sans-serif; }}
.f {{ display: grid; grid-template-columns: repeat(3, 66.7mm); grid-auto-rows: 25.4mm; column-gap: 3.2mm; }}
.e {{ box-sizing: border-box; padding: 1.5mm 2.5mm; overflow: hidden; page-break-inside: avoid; }}
.n {{ font-size: 8.5pt; font-weight: 600; line-height: 1.1; max-height: 2.3em; overflow: hidden; }}
.p {{ font-size: 15pt; font-weight: 700; color: #13772d; }}
.cb {{ width: 100%; height: 6.5mm; }}
.c {{ font-size: 6pt; color: #555; text-align: center; letter-spacing: .5px; }}
</style></head><body><div class='f'>{''.join(cases)}</div>{script}</body></html>"""

"""Contrôle des marges et prix Clover (demande du propriétaire du 2026-10-29, rubrique Articles).

Coût d'un article Clover = CUMP de son article Sage (correspondance Confirmé ou Automatique, couts_sage relu), sinon
coût Clover. Marge = (prix − coût) / prix. Un article sous la marge minimale choisie reçoit un prix proposé = coût /
(1 − marge minimale), arrondi vers le haut (,49 / ,99, ,99 ou au cent). Rien n'est écrit dans Clover sans que la
personne coche la ligne et lance la mise à jour ; chaque prix écrit est noté dans donnees/journal_prix_clover.csv.

Jamais de prix tiré d'une valeur aberrante : coût absent, plus de 5 fois le prix (`SEUIL_CUMP_DOUTEUX`) ou moins de
5 % du prix : non cochable. Prix variable (fixé à la caisse) : non traité. À vérifier, proposé décoché : hausse de
plus de 30 %, n° Sage relié à plusieurs articles Clover (formats différents ?). Effet estimé = (nouveau prix − prix)
× quantité vendue pendant les 90 derniers jours.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from pathlib import Path

from .couts_clover import SEUIL_CUMP_BAS
from .statistiques_clover import SEUIL_CUMP_DOUTEUX

CENT = Decimal("0.01")
MARGES = (15, 20, 25, 30, 35, 40, 45, 50)
ARRONDIS = (",49 / ,99", ",99", "Au cent")
HAUSSE_FORTE = Decimal("0.30")
JOURS_VENTES = 90
SOUS_MARGE = "Sous la marge minimale"
A_VERIFIER = "À vérifier"
ABERRANT = "Coût aberrant"
SANS_COUT = "Coût inconnu"
VARIABLE = "Prix variable"
ENTETE_JOURNAL = ["Date", "ID Clover", "Article Clover", "N° Sage", "Coût", "Prix avant", "Prix après", "Marge après"]


@dataclass
class LignePrix:
    id_clover: str
    nom: str
    categorie: str
    numero_sage: str
    cout: Decimal | None
    source_cout: str
    prix: Decimal | None
    vendu: Decimal = Decimal(0)
    nouveau: Decimal | None = None
    etat: str = SOUS_MARGE
    note: str = ""

    @property
    def marge(self) -> Decimal | None:
        if not self.prix or self.cout is None:
            return None
        return ((self.prix - self.cout) / self.prix * 100).quantize(Decimal("0.1"))

    @property
    def marge_apres(self) -> Decimal | None:
        if not self.nouveau or self.cout is None:
            return None
        return ((self.nouveau - self.cout) / self.nouveau * 100).quantize(Decimal("0.1"))

    @property
    def effet(self) -> Decimal | None:
        if self.nouveau is None or self.prix is None:
            return None
        return ((self.nouveau - self.prix) * self.vendu).quantize(CENT)

    @property
    def permis(self) -> bool:
        return self.etat in (SOUS_MARGE, A_VERIFIER)

    @property
    def cochee_par_defaut(self) -> bool:
        return self.etat == SOUS_MARGE


def arrondir(prix: Decimal, mode: str) -> Decimal:
    """Prix arrondi vers le haut : « ,49 / ,99 » -> 7,12 -> 7,49 ; 7,60 -> 7,99 ; « ,99 » -> 7,99 ; au cent."""
    prix = prix.quantize(CENT, ROUND_CEILING)
    if mode == "Au cent":
        return prix
    entier = prix.to_integral_value(rounding="ROUND_FLOOR")
    fins = [Decimal("0.49"), Decimal("0.99")] if mode == ",49 / ,99" else [Decimal("0.99")]
    for fin in fins:
        if prix <= entier + fin:
            return entier + fin
    return entier + 1 + fins[0]


def _cents(valeur) -> Decimal | None:
    return None if valeur is None else Decimal(int(valeur)) / 100


def analyser(articles: list[dict], liens: dict[str, str], couts: dict, ventes: dict, marge_min: int,
             mode: str) -> tuple[list[LignePrix], int]:
    """Articles Clover sous la marge minimale (ou à examiner) ; renvoie (lignes, nombre d'articles à la bonne marge).
    `couts` : n° Sage -> CoutSage ; `ventes` : ID Clover -> VenteArticle des 90 derniers jours."""
    par_numero = Counter(liens.values())
    taux = Decimal(marge_min) / 100
    lignes, correctes = [], 0
    for a in articles:
        if a.get("deleted"):
            continue
        numero = liens.get(a["id"], "")
        cump = couts[numero].cump if numero in couts else None
        cout, source = (cump.quantize(CENT, ROUND_HALF_UP), "CUMP Sage") if cump and cump > 0 else (
            _cents(a.get("cost")) or None, "Coût Clover")
        categories = [c.get("name", "") for c in (a.get("categories") or {}).get("elements") or []]
        v = ventes.get(a["id"])
        l = LignePrix(a["id"], (a.get("name") or "").strip(), ", ".join(c for c in categories if c), numero, cout,
                      source if cout else "", _cents(a.get("price")), v.quantite if v else Decimal(0))
        if a.get("priceType") == "VARIABLE":
            l.etat = VARIABLE
        elif not cout:
            l.etat = SANS_COUT
        elif l.prix and (cout > SEUIL_CUMP_DOUTEUX * l.prix or cout < SEUIL_CUMP_BAS * l.prix):
            l.etat, l.note = ABERRANT, "coût plus de 5 fois le prix ou sous 5 % du prix"
        elif l.prix and l.marge >= marge_min:
            correctes += 1
            continue
        else:
            l.nouveau = arrondir(cout / (1 - taux), mode)
            if not l.prix:
                l.etat, l.note = A_VERIFIER, "aucun prix dans Clover"
            elif l.nouveau > l.prix * (1 + HAUSSE_FORTE):
                l.etat, l.note = A_VERIFIER, "hausse de plus de 30 %"
            elif numero and par_numero[numero] > 1:
                l.etat, l.note = A_VERIFIER, f"n° Sage relié à {par_numero[numero]} articles Clover (formats ?)"
        if l.etat in (VARIABLE, SANS_COUT) and not l.vendu:
            continue  # rien à décider pour un article qui ne se vend pas
        lignes.append(l)
    ordre = {SOUS_MARGE: 0, A_VERIFIER: 1, ABERRANT: 2, SANS_COUT: 3, VARIABLE: 4}
    lignes.sort(key=lambda l: (ordre[l.etat], -(l.effet or 0), l.nom.casefold()))
    return lignes, correctes


def lire_donnees(racine: Path, config_toml: dict) -> dict:
    """Catalogue Clover, correspondance, CUMP Sage relus et ventes Clover des 90 derniers jours (cache)."""
    from .__main__ import charger_config
    from .api_clover import ClientClover
    from .couts_sage import charger, correspondance
    from .previsions import ventes_par_article
    from .statistiques_clover import lire as lire_clover

    client = ClientClover(charger_config(Path(racine) / "config.toml"))
    hier = date.today() - timedelta(days=1)
    debut = hier - timedelta(days=JOURS_VENTES - 1)
    donnees = lire_clover(client, debut, hier, Path(racine) / "donnees" / "cache_clover")
    return {"articles": client.inventaire(), "liens": correspondance(racine),
            "couts": charger(racine, config_toml, forcer=True), "ventes": ventes_par_article(donnees, debut, hier)}


def appliquer(racine: Path, lignes: list[LignePrix], progression=None) -> list[tuple[LignePrix, str]]:
    """Écrit le prix proposé dans Clover pour les lignes choisies ; renvoie [(ligne, erreur ou "")]."""
    from .__main__ import charger_config
    from .api_clover import ClientClover

    client = ClientClover(charger_config(Path(racine) / "config.toml"))
    journal = Path(racine) / "donnees" / "journal_prix_clover.csv"
    journal.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not journal.exists()
    resultats = []
    with journal.open("a", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.writer(f, delimiter=";")
        if nouveau:
            ecrivain.writerow(ENTETE_JOURNAL)
        for i, l in enumerate(lignes, 1):
            erreur = ""
            if not l.permis or not l.nouveau:
                erreur = l.etat
            else:
                try:
                    client.regler_prix(l.id_clover, l.nouveau)
                    ecrivain.writerow([datetime.now().isoformat(timespec="seconds"), l.id_clover, l.nom, l.numero_sage,
                                       l.cout, "" if l.prix is None else l.prix, l.nouveau, l.marge_apres])
                    f.flush()
                except Exception as exc:
                    erreur = str(exc)
            resultats.append((l, erreur))
            if progression:
                progression(i, len(lignes))
    return resultats

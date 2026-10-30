"""Coûts d'achat des articles dans Sage (CUMP, coût unitaire moyen pondéré) et lien articles Clover -> Sage, pour les
bénéfices et la liste d'articles de la page Rapports (demande du propriétaire du 2026-10-27).

CUMP d'un article = valeur du stock / quantité en stock, d'après les lots de Sage (tinvlot : quantité et valeur
restantes) ; stock vide : dernier coût unitaire d'entrée. Lien Clover -> Sage : lignes « Confirmé » ou
« Automatique » du fichier de correspondance (ID Clover -> n° d'article Sage), comme pour la facturation. Les coûts
lus sont gardés dans donnees/couts_sage.json (relus au plus une fois par jour, ou à la demande).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

FICHIER = "couts_sage.json"


@dataclass
class CoutSage:
    numero: str
    nom: str
    cump: Decimal | None
    quantite: Decimal
    valeur: Decimal


def lire_couts(base) -> dict[str, CoutSage]:
    """N° d'article Sage -> CUMP, quantité et valeur du stock."""
    lignes = base.requete(
        "SELECT TRIM(i.sPartCode) n, TRIM(i.sName) nom, COALESCE(SUM(l.dQty), 0) q, COALESCE(SUM(l.dValue), 0) v "
        "FROM tinvent i LEFT JOIN tinvlot l ON l.lInventId = i.lId GROUP BY i.lId, i.sPartCode, i.sName")
    derniers: dict[str, Decimal] = {}
    for l in base.requete("SELECT TRIM(i.sPartCode) n, l.dUnitCost c FROM tinvlot l JOIN tinvent i ON i.lId = l.lInventId "
                          "WHERE l.dUnitCost > 0 ORDER BY l.dtEntDate, l.lId"):
        derniers[l["n"]] = Decimal(str(l["c"]))  # le plus récent l'emporte
    couts = {}
    for l in lignes:
        quantite = Decimal(str(l["q"])).quantize(Decimal("0.001"))
        valeur = Decimal(str(l["v"])).quantize(Decimal("0.01"))
        cump = (valeur / quantite).quantize(Decimal("0.0001")) if quantite > 0 and valeur > 0 else derniers.get(l["n"])
        couts[l["n"]] = CoutSage(l["n"], l["nom"], cump.quantize(Decimal("0.0001")) if cump else None, quantite,
                                 valeur)
    return couts


def correspondance(racine: Path, pv=None) -> dict[str, str]:
    """ID Clover -> n° d'article Sage (lignes « Confirmé » ou « Automatique » de la correspondance du point de
    vente, n° 1 par défaut)."""
    from .points_vente import fichier_correspondance

    chemin = fichier_correspondance(racine, pv)
    if not chemin.exists():
        return {}
    from .correspondance import lire_feuille

    lignes = iter(lire_feuille(chemin))  # lue une fois tant que le fichier ne change pas
    entete = list(next(lignes))
    i_statut, i_sage, i_id = entete.index("Statut"), entete.index("N° article Sage"), entete.index("ID Clover")
    return {str(l[i_id]): str(l[i_sage]).strip() for l in lignes
            if l[i_id] and l[i_sage] and str(l[i_statut]) in ("Confirmé", "Automatique")}


def charger(racine: Path, config_toml: dict, forcer: bool = False) -> dict[str, CoutSage]:
    """Coûts du jour depuis donnees/couts_sage.json, sinon lus dans Sage (l'application ouvre Sage s'il est fermé)."""
    chemin = Path(racine) / "donnees" / FICHIER
    if not forcer and chemin.exists():
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        if donnees.get("date") == date.today().isoformat():
            return {n: CoutSage(n, c["nom"], Decimal(c["cump"]) if c["cump"] else None, Decimal(c["quantite"]),
                                Decimal(c["valeur"])) for n, c in donnees["couts"].items()}
    from .__main__ import lire_sage

    couts = lire_sage(config_toml, lire_couts, config_toml.get("sage_import", {}).get("fichier_entreprise"))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({"date": date.today().isoformat(), "couts": {
        n: {**{k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(c).items()}} for n, c in couts.items()}},
        ensure_ascii=False), encoding="utf-8")
    return couts


def cout_par_clover(racine: Path, couts: dict[str, CoutSage]) -> dict[str, tuple[str, Decimal | None]]:
    """ID Clover -> (n° Sage, CUMP)."""
    return {i: (n, couts[n].cump if n in couts else None) for i, n in correspondance(racine).items()}

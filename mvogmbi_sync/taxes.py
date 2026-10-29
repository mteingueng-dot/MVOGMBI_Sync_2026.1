"""Taxe d'une ligne de facture (demande du propriétaire du 2026-10-29) : certaines factures n'appliquent qu'une des
deux taxes, d'autres aucune. Code « GQ » = TPS + TVQ, « G » = TPS seulement, « Q » = TVQ seulement, « » = aucune.
Une ligne enregistrée avant ce choix (seulement « taxable ») vaut « GQ » si elle était taxable."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .facture import TAUX_TPS, TAUX_TVQ

CHOIX = {"": "Aucune", "GQ": "TPS + TVQ", "G": "TPS seulement", "Q": "TVQ seulement"}
CENT = Decimal("0.01")


def code(ligne) -> str:
    """Code de taxe d'une ligne (champ `taxe`, sinon `taxable`)."""
    valeur = ligne.get("taxe") if isinstance(ligne, dict) else getattr(ligne, "taxe", None)
    if valeur in ("GQ", "G", "Q"):
        return valeur
    taxable = ligne.get("taxable") if isinstance(ligne, dict) else getattr(ligne, "taxable", False)
    return "GQ" if taxable else ""  # « taxable » est toujours enregistré avec le code (vrai si une taxe)


def libelle(code_taxe: str) -> str:
    return CHOIX.get(code_taxe or "", CHOIX[""])


def code_du_libelle(texte: str, traduire=lambda x: x) -> str:
    return next((c for c, l in CHOIX.items() if traduire(l) == texte or l == texte), "")


def montants(montant: Decimal, code_taxe: str) -> tuple[Decimal, Decimal]:
    """(TPS, TVQ) d'une ligne hors taxes selon son code."""
    tps = (montant * TAUX_TPS).quantize(CENT, ROUND_HALF_UP) if "G" in (code_taxe or "") else Decimal(0)
    tvq = (montant * TAUX_TVQ).quantize(CENT, ROUND_HALF_UP) if "Q" in (code_taxe or "") else Decimal(0)
    return tps, tvq

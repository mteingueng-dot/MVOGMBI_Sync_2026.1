"""Préparation des lignes de la facture de vente Sage à partir d'un rapport de ventes.

Règle fixée par le propriétaire : le montant de chaque ligne est exactement le montant net Clover
(ventes brutes + rabais + remboursements) et le prix unitaire = montant net / quantité nette.
Le total de la facture est donc égal aux ventes nettes Clover de la période.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .models import RapportVentes

ZERO = Decimal("0")
DECIMALES_QUANTITE = Decimal("0.001")  # Clover mesure les poids au millième
DECIMALES_PRIX = Decimal("0.0001")  # 4 décimales : maximum accepté par Sage pour un prix


@dataclass
class LigneFacture:
    categorie: str
    nom: str
    quantite: Decimal
    prix_unitaire: Decimal
    montant: Decimal

    @property
    def ecart_arrondi(self) -> Decimal:
        """Différence entre quantité x prix arrondi et le montant net imposé (quelques fractions de cent)."""
        return (self.quantite * self.prix_unitaire).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) - self.montant


@dataclass
class Facture:
    lignes: list[LigneFacture] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((l.montant for l in self.lignes), ZERO)


def preparer_facture(rapport: RapportVentes) -> Facture:
    facture = Facture()
    for ligne in rapport.lignes:
        quantite = ligne.quantite_nette.quantize(DECIMALES_QUANTITE, rounding=ROUND_HALF_UP)
        montant = ligne.ventes_nettes
        if quantite == 0:
            if montant != 0:
                facture.anomalies.append(
                    f"{ligne.nom} : montant net de {montant} $ sans quantité nette (à traiter à la main)."
                )
            continue  # rien à facturer
        prix = (montant / quantite).quantize(DECIMALES_PRIX, rounding=ROUND_HALF_UP)
        facture.lignes.append(LigneFacture(ligne.categorie, ligne.nom, quantite, prix, montant))
    return facture

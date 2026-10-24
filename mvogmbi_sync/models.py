"""Structures de données communes : une ligne de vente cumulée par article."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")


@dataclass
class LigneVente:
    """Cumul des ventes d'un article sur une période (mêmes notions que le rapport Clover)."""

    categorie: str
    nom: str
    quantite_vendue: Decimal = ZERO
    quantite_remboursee: Decimal = ZERO
    ventes_brutes: Decimal = ZERO
    rabais: Decimal = ZERO  # négatif, comme dans Clover
    remboursements: Decimal = ZERO  # négatif, comme dans Clover
    taxable: bool | None = None  # TPS + TVQ ; None si inconnu (exports Clover sans information de taxe)

    @property
    def quantite_nette(self) -> Decimal:
        return self.quantite_vendue - self.quantite_remboursee

    @property
    def ventes_nettes(self) -> Decimal:
        return self.ventes_brutes + self.rabais + self.remboursements

    @property
    def prix_unitaire_net(self) -> Decimal:
        if self.quantite_nette == 0:
            return ZERO
        return (self.ventes_nettes / self.quantite_nette).quantize(Decimal("0.0001"))

    def ajouter(self, autre: "LigneVente") -> None:
        self.quantite_vendue += autre.quantite_vendue
        self.quantite_remboursee += autre.quantite_remboursee
        self.ventes_brutes += autre.ventes_brutes
        self.rabais += autre.rabais
        self.remboursements += autre.remboursements


@dataclass
class RapportVentes:
    """Ventes cumulées par article pour une période donnée."""

    debut: date
    fin: date  # inclusive
    source: str
    lignes: list[LigneVente] = field(default_factory=list)
    # Articles payés mais marqués « non-recette » dans Clover : exclus des ventes, signalés pour vérification
    hors_recettes: list[LigneVente] = field(default_factory=list)

    @property
    def total_brut(self) -> Decimal:
        return sum((l.ventes_brutes for l in self.lignes), ZERO)

    @property
    def total_rabais(self) -> Decimal:
        return sum((l.rabais for l in self.lignes), ZERO)

    @property
    def total_remboursements(self) -> Decimal:
        return sum((l.remboursements for l in self.lignes), ZERO)

    @property
    def total_net(self) -> Decimal:
        return sum((l.ventes_nettes for l in self.lignes), ZERO)


def cumuler(lignes: list[LigneVente]) -> list[LigneVente]:
    """Regroupe les lignes par (catégorie, nom, taxable) et trie par ventes nettes décroissantes."""
    cumul: dict[tuple[str, str, bool | None], LigneVente] = {}
    for ligne in lignes:
        cle = (ligne.categorie, ligne.nom, ligne.taxable)
        if cle not in cumul:
            cumul[cle] = LigneVente(categorie=ligne.categorie, nom=ligne.nom, taxable=ligne.taxable)
        cumul[cle].ajouter(ligne)
    return sorted(cumul.values(), key=lambda l: (l.categorie, -l.ventes_nettes, l.nom))

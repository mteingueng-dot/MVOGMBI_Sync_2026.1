"""Préparation de la facture de vente Sage à partir d'un rapport de ventes.

Règles fixées par le propriétaire :
- client « Vente Hebdomadaire », mode de paiement « Payer plus tard » (les dépôts bancaires
  sont appliqués ensuite sur la facture) ;
- montant de chaque ligne = montant net Clover hors taxes (ventes brutes + rabais + remboursements),
  prix unitaire = montant net / quantité nette ; le sous-total de la facture = ventes nettes Clover ;
- articles taxés dans Clover (TPS 5 % + TVQ 9,975 %) : code de taxe Sage « GQ », Sage calcule les taxes ;
- numéro : « Vente 2026-10-23 » (jour), « Vente 2026-10-23/25 » (vendredi au dimanche, une seule facture
  encaissée par le dépôt du lundi ; 19 caractères, le n° de facture Sage en accepte 20), « Vente S43-2026 »
  (semaine), « Vente Octobre 2026 » (mois).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import RapportVentes
from .periodes import TypePeriode

ZERO = Decimal("0")
CENT = Decimal("0.01")
DECIMALES_QUANTITE = Decimal("0.001")  # précision Clover ; Sage accepte jusqu'à 4 décimales
DECIMALES_PRIX = Decimal("0.0001")  # 4 décimales, comme sur les factures Sage existantes

CLIENT = "Vente Hebdomadaire"
MODE_PAIEMENT = "Payer plus tard"
CODE_TAXE_TAXABLE = "GQ"  # TPS + TVQ
TAUX_TPS = Decimal("0.05")
TAUX_TVQ = Decimal("0.09975")

MOIS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
        "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def numero_facture(type_periode: TypePeriode, debut: date, fin: date | None = None) -> str:
    if type_periode is TypePeriode.JOUR:
        return f"Vente {debut.isoformat()}"
    if type_periode is TypePeriode.FIN_DE_SEMAINE:
        return numero_fin_de_semaine(debut, fin or debut)
    if type_periode is TypePeriode.SEMAINE:
        annee, semaine, _ = debut.isocalendar()
        return f"Vente S{semaine:02d}-{annee}"
    return f"Vente {MOIS[debut.month - 1]} {debut.year}"


def numero_fin_de_semaine(debut: date, fin: date) -> str:
    """« Vente 2026-10-23/25 » : du vendredi 23 au dimanche 25 (jour de fin seul : il suit toujours le début)."""
    return f"Vente {debut.isoformat()}/{fin.day:02d}"


def jours_facture(numero: str) -> list[date]:
    """Jours de vente couverts par une facture « Vente AAAA-MM-JJ » ou « Vente AAAA-MM-JJ/JJ » ; [] sinon."""
    import re
    from datetime import timedelta

    m = re.fullmatch(r"Vente (\d{4}-\d{2}-\d{2})(?:/(\d{2}))?", numero.strip())
    if not m:
        return []
    debut = date.fromisoformat(m.group(1))
    if not m.group(2):
        return [debut]
    jours = [debut]
    while jours[-1].day != int(m.group(2)) and len(jours) < 7:
        jours.append(jours[-1] + timedelta(days=1))
    return jours


@dataclass
class LigneFacture:
    categorie: str
    nom: str
    quantite: Decimal
    prix_unitaire: Decimal
    montant: Decimal
    code_taxe: str = ""
    id_article: str = ""

    @property
    def ecart_arrondi(self) -> Decimal:
        """Différence entre quantité x prix arrondi et le montant net imposé (quelques fractions de cent)."""
        return (self.quantite * self.prix_unitaire).quantize(CENT, rounding=ROUND_HALF_UP) - self.montant


@dataclass
class Facture:
    numero: str
    date_facture: date
    client: str = CLIENT
    mode_paiement: str = MODE_PAIEMENT
    lignes: list[LigneFacture] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)  # bloquantes pour l'import
    avertissements: list[str] = field(default_factory=list)  # informatives : la facture reste exacte

    @property
    def sous_total(self) -> Decimal:
        return sum((l.montant for l in self.lignes), ZERO)

    @property
    def base_taxable(self) -> Decimal:
        return sum((l.montant for l in self.lignes if l.code_taxe), ZERO)

    @property
    def tps(self) -> Decimal:
        """Estimation ; Sage refait le calcul (arrondi ligne par ligne possible, à un cent près)."""
        return (self.base_taxable * TAUX_TPS).quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def tvq(self) -> Decimal:
        return (self.base_taxable * TAUX_TVQ).quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def total(self) -> Decimal:
        return self.sous_total + self.tps + self.tvq


def preparer_facture(rapport: RapportVentes, type_periode: TypePeriode) -> Facture:
    """La facture est datée du dernier jour de la période."""
    facture = Facture(numero=numero_facture(type_periode, rapport.debut, rapport.fin), date_facture=rapport.fin)
    taxes_inconnues = 0
    for ligne in rapport.lignes:
        quantite = ligne.quantite_nette.quantize(DECIMALES_QUANTITE, rounding=ROUND_HALF_UP)
        montant = ligne.ventes_nettes
        if quantite == 0:
            if montant != 0:
                facture.anomalies.append(
                    f"{ligne.nom} : montant net de {montant} $ sans quantité nette (à traiter à la main)."
                )
            continue  # rien à facturer
        if ligne.taxable is None:
            taxes_inconnues += 1
        prix = (montant / quantite).quantize(DECIMALES_PRIX, rounding=ROUND_HALF_UP)
        facture.lignes.append(LigneFacture(
            ligne.categorie, ligne.nom, quantite, prix, montant,
            CODE_TAXE_TAXABLE if ligne.taxable else "", ligne.id_article,
        ))
    for l in rapport.hors_recettes:
        facture.avertissements.append(
            f"« {l.nom} » ({l.quantite_vendue} x, {l.ventes_brutes} $) a été payé mais est marqué « non-recette » "
            "dans Clover : il n'est pas facturé. Vérifiez la configuration de cet article dans Clover."
        )
    if taxes_inconnues:
        facture.anomalies.append(
            f"{taxes_inconnues} ligne(s) sans information de taxe (source : export Clover) : "
            "utilisez l'API Clover pour obtenir les codes de taxe."
        )
    return facture

"""Mise à jour de Clover après l'import d'une facture fournisseur dans Sage (règle du propriétaire du 2026-10-28) :
pour chaque article reçu, stock Clover = stock actuel + quantité reçue (Qté Sage) et coût Clover = nouveau prix
d'achat (Prix Sage = montant / Qté Sage).

L'article Clover est trouvé par la correspondance (lignes « Confirmé » ou « Automatique » vers le n° Sage). Un n° Sage
relié à plusieurs articles Clover reçoit le coût sur chacun, mais son stock n'est pas touché (à répartir à la main).
Chaque mise à jour est notée dans `donnees/journal_stock_clover.csv` : une facture n'est jamais ajoutée deux fois.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from .cache_lectures import vide_apres

ENTETE = ["Date", "Fournisseur", "Facture", "N° Sage", "ID Clover", "Stock avant", "Quantité ajoutée", "Stock après",
          "Coût"]


@dataclass
class Reception:
    numero_sage: str
    quantite: Decimal  # en unités Sage
    montant: Decimal

    @property
    def cout(self) -> Decimal:
        return (self.montant / self.quantite).quantize(Decimal("0.01"), ROUND_HALF_UP) if self.quantite else Decimal(0)


def receptions(facture) -> list[Reception]:
    """Lignes d'articles de la facture regroupées par n° Sage (quantité et montant additionnés)."""
    cumul: dict[str, Reception] = {}
    for l in facture.lignes:
        if l.nature != "article" or not l.numero_sage:
            continue
        quantite, _ = l.en_sage()
        r = cumul.setdefault(l.numero_sage, Reception(l.numero_sage, Decimal(0), Decimal(0)))
        r.quantite += quantite
        r.montant += l.montant
    return [r for r in cumul.values() if r.quantite > 0]


def articles_clover_par_numero(correspondances) -> dict[str, list[str]]:
    from .correspondance import AUTOMATIQUE, CONFIRME, PREFIXE_SANS_ID

    resultat = defaultdict(list)
    for c in correspondances:
        if c.statut in (CONFIRME, AUTOMATIQUE) and c.numero_sage and c.id_clover \
                and not c.id_clover.startswith(PREFIXE_SANS_ID):
            resultat[c.numero_sage.strip()].append(c.id_clover)
    return resultat


def _q(valeur: Decimal) -> str:
    """12.000 -> « 12 », 2.500 -> « 2.5 »."""
    texte = format(Decimal(valeur).normalize(), "f")
    return texte


class Journal:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "journal_stock_clover.csv"

    def faits(self) -> set[tuple[str, str, str]]:
        if not self.chemin.exists():
            return set()
        with self.chemin.open(encoding="utf-8-sig", newline="") as f:
            return {(r["Fournisseur"], r["Facture"], r["N° Sage"]) for r in csv.DictReader(f, delimiter=";")}

    def noter(self, facture, r: Reception, id_clover: str, avant, apres) -> None:
        nouveau = not self.chemin.exists()
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with self.chemin.open("a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            if nouveau:
                w.writerow(ENTETE)
            w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), facture.fournisseur_sage, facture.numero,
                        r.numero_sage, id_clover, avant, r.quantite, apres, r.cout])


def mettre_a_jour(client, facture, correspondances, journal: Journal) -> list[str]:
    """Ajoute le stock reçu et remplace le coût dans Clover ; renvoie les messages (un par article)."""
    par_numero = articles_clover_par_numero(correspondances)
    faits = journal.faits()
    messages = []
    for r in receptions(facture):
        cle = (facture.fournisseur_sage, facture.numero, r.numero_sage)
        if cle in faits:
            messages.append(f"{r.numero_sage} : déjà ajouté au stock Clover")
            continue
        ids = par_numero.get(r.numero_sage, [])
        if not ids:
            messages.append(f"{r.numero_sage} : aucun article Clover relié (Articles > Correspondance) — stock et coût Clover non modifiés")
            continue
        try:
            for id_clover in ids:
                client.regler_cout(id_clover, r.cout)
            if len(ids) > 1:
                messages.append(f"{r.numero_sage} : coût {r.cout} $ mis sur {len(ids)} articles Clover ; stock NON "
                                f"modifié (plusieurs articles Clover reliés : répartir {_q(r.quantite)} à la main)")
                journal.noter(facture, r, ",".join(ids), "", "")
                continue
            avant = client.stock(ids[0])
            apres = avant + r.quantite
            client.regler_stock(ids[0], apres)
            journal.noter(facture, r, ids[0], avant, apres)
            messages.append(f"{r.numero_sage} : stock Clover {_q(avant)} + {_q(r.quantite)} = {_q(apres)}, "
                            f"coût {r.cout} $")
        except Exception as exc:
            messages.append(f"{r.numero_sage} : Clover non mis à jour ({exc})")
    return messages


@vide_apres  # mémoire des lectures vidée après une écriture
def mettre_a_jour_factures(racine: Path, config_toml_chemin: Path, factures, point_vente=None) -> dict[str, list[str]]:
    """Après l'import : met à jour le Clover du point de vente (n° 1 par défaut) pour chaque facture importée ;
    {fichier : messages}."""
    from .__main__ import charger_config
    from .api_clover import ClientClover
    from .correspondance import lire_correspondances
    from .points_vente import fichier_correspondance

    client = ClientClover(charger_config(Path(config_toml_chemin), point_vente))
    correspondances = lire_correspondances(fichier_correspondance(racine, point_vente))
    journal = Journal(racine)
    return {f.fichier: mettre_a_jour(client, f, correspondances, journal) for f in factures}

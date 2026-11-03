"""RIA (transferts d'argent) dans Sage (demande du propriétaire du 2026-10-30, Comptabilité > RIA).

Le marché est agent RIA. L'argent de RIA passe par le compte de banque 1055 sans être une vente :

- l'argent reçu des clients de RIA est déposé avec les espèces des ventes : le dépôt d'espèces peut dépasser les
  ventes ; le surplus est à RIA, qui le retire ensuite du compte (un autre jour) ;
- le marché verse l'argent aux bénéficiaires (en espèces ou par virement Interac envoyé) ; RIA dépose ensuite le
  montant dans le compte ;
- à la fin du mois, RIA dépose les commissions, seul vrai revenu.

Entrées et sorties s'annulent : le compte RIA (un compte de bilan de Sage, à créer par le propriétaire) revient à
zéro, sauf les opérations en cours. Écritures de journal, toutes par la fenêtre Journal général de Sage :

| Opération | Débit | Crédit |
|---|---|---|
| Dépôt de RIA | banque | compte RIA |
| Surplus d'un dépôt d'espèces | banque | compte RIA |
| Retrait par RIA | compte RIA | banque |
| Paiement Interac RIA | compte RIA | banque |
| Paiement RIA en espèces | compte RIA | compte des espèces |
| Commission RIA | banque | compte de commissions |

Mouvements du relevé : décisions du registre des relevés (état « Compte choisi »), comme à la page Rapprochement.
Surplus et paiements en espèces, sans ligne de relevé à eux : opérations de donnees/ria.json.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

ZERO = Decimal(0)
RIA = re.compile(r"\bRIA\b", re.I)
FRAIS = re.compile(r"fonds manquants", re.I)  # avis de la caisse, pas une opération de RIA
DEPOT, RETRAIT, INTERAC, COMMISSION, SURPLUS, ESPECES, ENVOI = (
    "Dépôt de RIA", "Retrait par RIA", "Paiement Interac RIA", "Commission RIA", "Surplus de dépôt d'espèces",
    "Paiement RIA en espèces", "Envoi RIA reçu en espèces")
A_SAISIR, SAISIE = "À saisir dans Sage", "Saisie dans Sage"
COMPTES = {"ria": "Compte RIA (bilan)", "commissions": "Compte de commissions (4xxx)",
           "especes": "Compte des espèces"}


def est_ria(m) -> bool:
    return bool(RIA.search(m.description)) and not FRAIS.search(m.description)


def genre(m, commissions=()) -> str:
    if m.cle in commissions:
        return COMMISSION
    if m.montant > 0:
        return DEPOT
    return INTERAC if "interac" in m.description.lower() else RETRAIT


@dataclass
class Operation:
    numero: str
    jour: str
    genre: str
    montant: str                # positif
    description: str = ""
    cle: str = ""               # surplus : clé du mouvement de dépôt d'espèces
    etat: str = A_SAISIR
    ecriture: int | None = None
    auteur: str = ""


@dataclass
class Bilan:
    """Totaux d'une période (positifs) ; solde : ce que le marché doit à RIA (négatif : RIA doit au marché)."""
    depots: Decimal = ZERO
    surplus: Decimal = ZERO
    retraits: Decimal = ZERO
    paiements: Decimal = ZERO
    commissions: Decimal = ZERO

    @property
    def solde(self) -> Decimal:
        return self.depots + self.surplus - self.retraits - self.paiements


class Registre:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "ria.json"
        self.comptes: dict[str, str] = {"especes": "1050"}  # « mode » : « etats » si les états RIA sont traités
        self.commissions: list[str] = []   # clés des dépôts du relevé marqués comme commissions
        self.operations: list[Operation] = []
        if self.chemin.exists():
            donnees = json.loads(self.chemin.read_text(encoding="utf-8"))
            self.comptes.update(donnees.get("comptes", {}))
            self.commissions = list(donnees.get("commissions", []))
            self.operations = [Operation(**o) for o in donnees.get("operations", [])]

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"comptes": self.comptes, "commissions": self.commissions,
                                          "operations": [asdict(o) for o in self.operations]},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)

    def comptes_manquants(self) -> list[str]:
        return [libelle for cle, libelle in COMPTES.items() if not str(self.comptes.get(cle, "")).isdigit()]

    def a_saisir(self) -> int:
        return sum(1 for o in self.operations if o.etat == A_SAISIR)

    def ajouter(self, jour: str, genre_: str, montant: Decimal, description: str = "", cle: str = "",
                auteur: str = "") -> Operation:
        date.fromisoformat(jour)
        if montant <= 0:
            raise ValueError("Le montant doit être positif.")
        if cle and genre_ == SURPLUS and cle in self.parts_depots():
            raise ValueError("La part de RIA de ce dépôt est déjà confirmée.")
        rangs = [int(o.numero[3:]) for o in self.operations if o.numero[3:].isdigit()]
        o = Operation(f"RI-{max(rangs, default=0) + 1:04d}", jour, genre_, str(montant), description, cle, auteur=auteur)
        self.operations.append(o)
        return o

    def supprimer(self, numero: str) -> None:
        o = next(x for x in self.operations if x.numero == numero)
        if o.etat == SAISIE:
            raise ValueError(f"{numero} est déjà dans Sage.")
        self.operations.remove(o)

    def parts_depots(self) -> dict[str, Decimal]:
        """Part de RIA de chaque dépôt d'espèces confirmée : retirée du dépôt avant l'encaissement sur les ventes."""
        return {o.cle: Decimal(o.montant) for o in self.operations if o.genre == SURPLUS and o.cle}

    def mouvements_a_saisir(self) -> list:
        """Opérations à saisir, sous la forme des mouvements du journal général (compte de contrepartie : banque,
        ou espèces pour un paiement en espèces)."""
        from .rapprochement import MouvementBanque

        sortie = []
        if not str(self.comptes.get("ria", "")).isdigit():
            return sortie
        for rang, o in enumerate(self.operations):
            if o.etat != A_SAISIR:
                continue
            especes = o.genre == ESPECES
            # contrepartie : banque, ou espèces pour ce qui passe au comptoir (envoi reçu, versement payé)
            comptoir = o.genre in (ESPECES, ENVOI)
            compte = self.comptes["ria"]
            if o.genre == SURPLUS and self.comptes.get("mode") == "etats":
                compte = str(self.comptes.get("especes", ""))  # envois déjà portés au compte RIA par les états
            m = MouvementBanque(o.jour, f"{o.genre} {o.description}".strip(),
                                -Decimal(o.montant) if especes else Decimal(o.montant), releve="ria", rang=rang,
                                compte=compte)
            m.operation, m.source_sage = o.numero, o.numero
            if comptoir:
                m.compte_contre = str(self.comptes.get("especes", ""))
            sortie.append(m)
        return sortie

    def noter_saisie(self, m, fait: bool) -> None:
        if fait:
            o = next(x for x in self.operations if x.numero == m.operation)
            o.etat, o.ecriture = SAISIE, (m.sage or [None])[0]

    def lignes(self, mouvements: list, depots: list, du: date, au: date) -> tuple[list[list], Bilan]:
        """Tableau de la page : mouvements RIA du relevé, surplus à confirmer, opérations ; et les totaux."""
        from .rapprochement import RAPPROCHE, SAISI

        lignes, bilan = [], Bilan()
        for m in mouvements:
            g = genre(m, self.commissions)
            montant = abs(m.montant)
            fait = m.etat in (RAPPROCHE, SAISI)
            lignes.append({"date": m.date, "genre": g, "description": m.description, "montant": m.montant,
                           "etat": "Dans Sage" if fait else m.etat, "sorte": "releve", "mouvement": m})
            if g == COMMISSION:
                bilan.commissions += montant
            elif g == DEPOT:
                bilan.depots += montant
            elif g == RETRAIT:
                bilan.retraits += montant
            else:
                bilan.paiements += montant
        for d in depots:
            if d.ria:
                lignes.append({"date": d.date.isoformat(), "genre": SURPLUS, "description": d.remarque,
                               "montant": d.ria, "etat": "À confirmer", "sorte": "surplus", "depot": d})
                bilan.surplus += d.ria
        for o in self.operations:
            if du.isoformat() <= o.jour <= au.isoformat():
                signe = -1 if o.genre == ESPECES else 1
                lignes.append({"date": o.jour, "genre": o.genre, "description": o.description,
                               "montant": signe * Decimal(o.montant), "etat": o.etat, "sorte": "operation",
                               "operation": o})
                if o.genre == ESPECES:
                    bilan.paiements += Decimal(o.montant)
                elif o.genre == ENVOI:
                    bilan.depots += Decimal(o.montant)
                else:
                    bilan.surplus += Decimal(o.montant)
        lignes.sort(key=lambda x: x["date"], reverse=True)
        return lignes, bilan

"""Budget mensuel et écarts, et coût de la main-d'œuvre (demande du propriétaire du 2026-10-29).

Budget : pour chaque mois, ventes (produits 4xxx), coût des marchandises vendues (50xx) et autres charges
(51xx-59xx) ; réel = comptabilite.etat_resultats (Sage) ; écart et écart en % ; proposition = même mois de l'an
dernier × (1 + croissance). Registre donnees/budget.json.

Main-d'œuvre : par jour, ventes nettes Clover, heures pointées (et planifiées), coût estimé = heures × taux horaire
moyen × (1 + charges sociales) ([paie] taux_moyen, défaut 18 $ ; [paie] charges_sociales, défaut 15 %), part des
ventes ; l'application ne garde aucun taux d'employé.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ZERO = Decimal(0)
CENT = Decimal("0.01")
POSTES = ["Produits (ventes)", "Coût des marchandises vendues", "Autres charges"]
ENTETES_BUDGET = ["Poste", "Réel", "Budget", "Écart", "Écart (%)", "Réel depuis janvier", "Budget depuis janvier"]


class Budget:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "budget.json"
        self.valeurs: dict = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else {}

    def mois(self, annee: int, mois: int) -> dict[str, Decimal]:
        d = self.valeurs.get(f"{annee}-{mois:02d}", {})
        return {p: Decimal(str(d.get(p, 0))) for p in POSTES}

    def definir(self, annee: int, mois: int, valeurs: dict[str, Decimal]) -> None:
        self.valeurs[f"{annee}-{mois:02d}"] = {p: str(Decimal(valeurs.get(p, 0)).quantize(CENT)) for p in POSTES}
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps(self.valeurs, ensure_ascii=False, indent=1), encoding="utf-8")


def reel(lignes_resultats: list[list], colonne: int = 1) -> dict[str, Decimal]:
    """Réel d'une colonne de comptabilite.etat_resultats (1 = le mois, 3 = même mois l'an dernier)."""
    par_nom = {l[0]: Decimal(l[colonne]) for l in lignes_resultats}
    return {p: par_nom.get(p, ZERO) for p in POSTES}


def ecarts(reel_mois: dict, budget_mois: dict, reel_cumul: dict, budget_cumul: dict) -> list[list]:
    lignes = []
    for p in POSTES + ["Résultat"]:
        if p == "Résultat":
            r = reel_mois[POSTES[0]] - reel_mois[POSTES[1]] - reel_mois[POSTES[2]]
            b = budget_mois[POSTES[0]] - budget_mois[POSTES[1]] - budget_mois[POSTES[2]]
            rc = reel_cumul[POSTES[0]] - reel_cumul[POSTES[1]] - reel_cumul[POSTES[2]]
            bc = budget_cumul[POSTES[0]] - budget_cumul[POSTES[1]] - budget_cumul[POSTES[2]]
        else:
            r, b, rc, bc = reel_mois[p], budget_mois[p], reel_cumul[p], budget_cumul[p]
        pourcent = f"{(r - b) / b * 100:+.1f} %".replace(".", ",") if b else "—"
        lignes.append([p, r, b, r - b, pourcent, rc, bc])
    return lignes


def proposer(reel_an_dernier: dict[str, Decimal], croissance: Decimal) -> dict[str, Decimal]:
    return {p: (v * (1 + croissance / 100)).quantize(Decimal("1")) for p, v in reel_an_dernier.items()}


# --------------------------------------------------------------------------------------------- main-d'œuvre
def taux_et_charges(config_toml: dict) -> tuple[Decimal, Decimal]:
    p = config_toml.get("paie", {})
    return Decimal(str(p.get("taux_moyen", "18"))), Decimal(str(p.get("charges_sociales", "15")))


def main_oeuvre(ventes_par_jour: dict[date, Decimal], heures: dict[date, Decimal], planifiees: dict[date, Decimal],
                debut: date, fin: date, taux: Decimal, charges: Decimal) -> list[list]:
    """[date, ventes, heures pointées, heures planifiées, coût estimé, part des ventes]."""
    lignes, jour = [], debut
    while jour <= fin:
        v, h, hp = ventes_par_jour.get(jour, ZERO), heures.get(jour, ZERO), planifiees.get(jour, ZERO)
        if v or h or hp:
            cout = (h * taux * (1 + charges / 100)).quantize(CENT)
            part = f"{cout / v * 100:.1f} %".replace(".", ",") if v else "—"
            lignes.append([jour.isoformat(), v.quantize(CENT), h, hp, cout, part])
        jour += timedelta(days=1)
    return lignes


def heures_par_jour_tous(racine: Path, debut: date, fin: date) -> tuple[dict, dict]:
    """(heures pointées, heures planifiées) de tous les employés, par jour."""
    from . import paie_temps as pt
    from .planning import Planning

    registre, planning = pt.Registre(racine), Planning(racine)
    pointees: dict[date, Decimal] = {}
    for e in registre.employes:
        liste, _ = pt.presences(registre.valides(e.id))
        for p in liste:
            if debut <= p.jour <= fin:
                pointees[p.jour] = pointees.get(p.jour, ZERO) + p.heures
    planifiees: dict[date, Decimal] = {}
    jour = debut
    while jour <= fin:
        total = ZERO
        for e in registre.employes:
            q = planning.quart(f"{jour:%Y-%m}", e.id, jour)
            if q:
                total += q.heures
        if total:
            planifiees[jour] = total
        jour += timedelta(days=1)
    return pointees, planifiees

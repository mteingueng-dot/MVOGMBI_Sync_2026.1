"""Contrôle de la caisse (demande du propriétaire du 2026-10-29, priorité n° 2) : espèces attendues d'après Clover,
comptage du soir saisi au magasin, écart du jour, et sur une période : espèces à déposer contre dépôts d'espèces au
guichet lus dans les relevés Desjardins (« DGA Dépôt au GA », page Rapprochement).

Espèces attendues dans le tiroir à la fermeture = fond de caisse + paiements en espèces réussis (montant + pourboire)
− remboursements de paiements en espèces − argent remis sur carte (cashbackAmount, sorti du tiroir). Une vente est
comptée au jour de son paiement (fuseau de Clover), comme la facturation. Écart = compté − attendu (négatif : il
manque de l'argent). À déposer = compté − fond laissé dans la caisse pour le lendemain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

CENT = Decimal("0.01")
ZERO = Decimal(0)
ESPECES = "com.clover.tender.cash"
COUPURES = ["100", "50", "20", "10", "5", "2", "1", "0.25", "0.10", "0.05"]
FOND_DEFAUT = Decimal("200.00")
SEUIL_ECART = Decimal("5.00")  # au-delà, l'écart est signalé (rouge, résumé du matin)
ENTETES_JOURS = ["Date", "Ventes en espèces", "Remboursements", "Argent remis", "Fond", "Attendu", "Compté", "Écart",
                 "À déposer", "Compté par"]


def _cents(v) -> Decimal:
    return (Decimal(v or 0) / 100).quantize(CENT)


def est_especes(paiement: dict) -> bool:
    tender = paiement.get("tender") or {}
    return tender.get("labelKey") == ESPECES or (tender.get("label") or "").lower().startswith(("esp", "cash"))


@dataclass
class Attendu:
    jour: date
    ventes: Decimal = ZERO          # paiements en espèces (montant + pourboire)
    remboursements: Decimal = ZERO  # remboursements de paiements en espèces
    remis: Decimal = ZERO           # argent remis sur paiement par carte
    paiements: int = 0
    par_employe: dict[str, Decimal] = field(default_factory=dict)
    par_appareil: dict[str, Decimal] = field(default_factory=dict)

    @property
    def net(self) -> Decimal:
        return self.ventes - self.remboursements - self.remis


def attendus(d, fuseau: str | None = None) -> dict[date, Attendu]:
    """Espèces de chaque jour d'après les données Clover (statistiques_clover.lire)."""
    zone = ZoneInfo(fuseau or getattr(d, "fuseau", "America/Toronto"))
    jour_de = lambda ms: datetime.fromtimestamp(ms / 1000, zone).date()  # noqa: E731
    resultat: dict[date, Attendu] = {}
    especes_ids = set()
    for p in d.paiements:
        if p.get("result") != "SUCCESS":
            continue
        a = resultat.setdefault(jour_de(p["createdTime"]), Attendu(jour_de(p["createdTime"])))
        if est_especes(p):
            especes_ids.add(p.get("id"))
            montant = _cents(p.get("amount")) + _cents(p.get("tipAmount"))
            a.ventes += montant
            a.paiements += 1
            employe = d.employes.get((p.get("employee") or {}).get("id"), "?") if d.employes else "?"
            appareil = d.appareils.get((p.get("device") or {}).get("id"), "?") if d.appareils else "?"
            a.par_employe[employe] = a.par_employe.get(employe, ZERO) + montant
            a.par_appareil[appareil] = a.par_appareil.get(appareil, ZERO) + montant
        elif p.get("cashbackAmount"):
            a.remis += _cents(p.get("cashbackAmount"))
    for r in d.remboursements:
        if (r.get("payment") or {}).get("id") in especes_ids:
            j = jour_de(r["createdTime"])
            resultat.setdefault(j, Attendu(j)).remboursements += _cents(r.get("amount"))  # montant remis, taxes comprises
    return resultat


# --------------------------------------------------------------------------------------------- comptages
def total_coupures(coupures: dict[str, int | str]) -> Decimal:
    total = ZERO
    for valeur, nombre in coupures.items():
        try:
            total += Decimal(valeur) * Decimal(str(nombre or 0))
        except Exception:
            raise ValueError(f"Nombre invalide pour {valeur} $ : « {nombre} ».") from None
    return total.quantize(CENT)


@dataclass
class Comptage:
    jour: str
    compte: str               # total compté (fond compris)
    fond: str                 # fond laissé dans la caisse pour le lendemain
    coupures: dict = field(default_factory=dict)
    par: str = ""
    le: str = ""
    remarque: str = ""

    @property
    def a_deposer(self) -> Decimal:
        return Decimal(self.compte) - Decimal(self.fond)


class Registre:
    """Comptages du soir (donnees/caisse.json) ; un recomptage remplace le précédent, gardé dans l'historique."""

    def __init__(self, racine: Path, pv=None):
        donnees = Path(racine) / "donnees"
        self.chemin = (pv.dossier(donnees) if pv else donnees) / "caisse.json"  # un tiroir par point de vente
        donnees = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else {}
        self.comptages: dict[str, dict] = donnees.get("comptages", {})
        self.historique: list[dict] = donnees.get("historique", [])

    def comptage(self, jour: date) -> Comptage | None:
        c = self.comptages.get(jour.isoformat())
        return Comptage(**c) if c else None

    def noter(self, c: Comptage) -> None:
        ancien = self.comptages.get(c.jour)
        if ancien:
            self.historique.append(ancien)
        c.le = c.le or datetime.now().isoformat(timespec="seconds")
        self.comptages[c.jour] = c.__dict__.copy()
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"comptages": self.comptages, "historique": self.historique},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)


def fond_de_caisse(config_toml: dict) -> Decimal:
    try:
        return Decimal(str(config_toml.get("caisse", {}).get("fond", FOND_DEFAUT))).quantize(CENT)
    except Exception:
        return FOND_DEFAUT


def fond_du_matin(registre: Registre, jour: date, config_toml: dict) -> Decimal:
    """Fond au début de la journée : celui laissé au dernier comptage d'avant, sinon le fond habituel."""
    for i in range(1, 8):
        c = registre.comptage(jour - timedelta(days=i))
        if c:
            return Decimal(c.fond)
    return fond_de_caisse(config_toml)


def lignes_jours(attendu: dict[date, Attendu], registre: Registre, debut: date, fin: date,
                 config_toml: dict) -> list[list]:
    lignes = []
    jour = debut
    while jour <= fin:
        a = attendu.get(jour) or Attendu(jour)
        c = registre.comptage(jour)
        fond = fond_du_matin(registre, jour, config_toml)
        prevu = fond + a.net
        if a.ventes or c:
            compte = Decimal(c.compte) if c else None
            lignes.append([jour.isoformat(), a.ventes, a.remboursements, a.remis, fond, prevu,
                           compte if compte is not None else "", (compte - prevu) if compte is not None else "",
                           c.a_deposer if c else "", c.par if c else "Non compté"])
        jour += timedelta(days=1)
    return lignes


# --------------------------------------------------------------------------------------------- dépôts
def depots_especes(racine: Path, debut: date, fin: date) -> list[tuple[str, Decimal, str]]:
    """Dépôts d'espèces au guichet (DGA) des relevés Desjardins chargés, entre deux dates : (date, montant, relevé)."""
    from .rapprochement import DEPOT_ESPECES, RegistreReleves

    depots = []
    for releve in RegistreReleves(racine).lire():
        for m in releve.mouvements:
            if m.montant > 0 and DEPOT_ESPECES.search(m.description) and debut.isoformat() <= m.date <= fin.isoformat():
                depots.append((m.date, m.montant, releve.fichier))
    return sorted(depots)


def bilan_depots(lignes: list[list], depots: list[tuple[str, Decimal, str]]) -> dict:
    a_deposer = sum((l[8] for l in lignes if isinstance(l[8], Decimal)), ZERO)
    depose = sum((d[1] for d in depots), ZERO)
    non_comptes = sum(1 for l in lignes if l[9] == "Non compté")
    return {"a_deposer": a_deposer, "depose": depose, "ecart": depose - a_deposer, "non_comptes": non_comptes}

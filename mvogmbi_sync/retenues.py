"""État des retenues à la source (demande du propriétaire du 2026-10-29) — lecture seule de la comptabilité Sage.

Les paies de Sage (module Paie, tjourent.nModule 3) portent les retenues des employés et les cotisations de
l'employeur dans des comptes de passif (« RRQ à payer », « Québec à payer », « FSSQ à payer », « RQAP à payer »,
« CNESST à payer », impôt fédéral, AE…). L'état les lit sans avoir besoin d'accès au module Paie :
- retenues et cotisations du mois = mouvements des écritures de paie dans chaque compte ;
- versements = autres mouvements du compte (paiements aux organismes) ;
- solde à la fin du mois = ouverture de l'exercice + tous les mouvements jusqu'à la fin du mois ;
- organisme d'après le nom du compte : Revenu Québec (RRQ, impôt du Québec, FSS, RQAP, CNT), Agence du revenu du
  Canada (impôt fédéral, AE), CNESST. Échéance d'un remetteur régulier : le 15 du mois suivant.
- information : salaires bruts et cotisations de l'employeur (comptes de charges touchés par les paies).
Le détail par employé (T4, Relevé 1) demande l'accès en lecture au module Paie de Sage.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from .comptabilite import CORRIGEES, bornes_mois

CENT = Decimal("0.01")
RQ, ARC, CNESST, AUTRE = "Revenu Québec", "Agence du revenu du Canada", "CNESST", "Autre retenue"
VACANCES = "Vacances à payer (non remises)"  # provision des congés payés : jamais remise à un organisme
ENTETES = ["Organisme", "Compte Sage", "Solde au début", "Retenues et cotisations du mois", "Versements du mois",
           "Solde à la fin", "À remettre pour le mois"]


def organisme(nom: str) -> str | None:
    """Organisme d'un compte de retenue d'après son nom ; None pour un compte de total."""
    texte = nom.casefold()
    if texte.startswith("total"):
        return None
    if "vacance" in texte:
        return VACANCES
    if "cnesst" in texte or "csst" in texte:
        return CNESST
    if any(m in texte for m in ("rrq", "québec", "quebec", "fss", "rqap", "cnt", "provincial")):
        return RQ
    if any(m in texte for m in ("fédéral", "federal", "a.e.", "ae ", "ae à", "assurance-emploi", "assurance emploi",
                                "rpc", "receveur", "impôt sur le revenu")) or texte.startswith("ae"):
        return ARC
    return AUTRE


def _d(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def etat(base, annee: int, mois: int) -> tuple[list[list], dict]:
    """Lignes par compte de retenue (passif touché par les paies), totaux par organisme, informations."""
    du, au = bornes_mois(annee, mois)
    comptes = base.requete("SELECT lId, sName, dYtcLY FROM taccount")
    noms = {r["lId"]: r["sName"] or "" for r in comptes}
    ouvertures = {r["lId"]: _d(r["dYtcLY"]) for r in comptes}
    touches = [r["c"] for r in base.requete(
        f"SELECT DISTINCT a.lAcctId c FROM tjentact a JOIN tjourent e ON e.lId = a.lJEntId WHERE e.nModule = 3 "
        f"AND e.nType NOT IN {CORRIGEES}")]
    passifs = [c for c in touches if str(c).startswith("2") and organisme(noms.get(c, ""))]
    charges = [c for c in touches if str(c).startswith("5")]
    if not passifs:
        return [], {"salaires": Decimal(0), "charges": [], "echeance": _echeance(annee, mois)}
    liste = ", ".join(str(int(c)) for c in passifs + charges)
    mouvements = base.requete(
        f"SELECT a.lAcctId c, e.nModule = 3 paie, e.dtJourDate < %s avant, ROUND(SUM(a.dAmount), 2) s "
        f"FROM tjentact a JOIN tjourent e ON e.lId = a.lJEntId WHERE a.lAcctId IN ({liste}) AND e.nType NOT IN "
        f"{CORRIGEES} AND e.dtJourDate <= %s GROUP BY a.lAcctId, e.nModule = 3, e.dtJourDate < %s",
        (du.isoformat(), au.isoformat(), du.isoformat()))
    cumul: dict[int, dict] = defaultdict(lambda: {"avant": Decimal(0), "paie": Decimal(0), "versements": Decimal(0)})
    for m in mouvements:
        s = _d(m["s"])
        if m["avant"]:
            cumul[m["c"]]["avant"] += s
        elif m["paie"]:
            cumul[m["c"]]["paie"] += s
        else:
            cumul[m["c"]]["versements"] += s
    lignes, totaux = [], defaultdict(lambda: [Decimal(0)] * 5)
    for c in sorted(passifs, key=lambda c: (organisme(noms[c]), c)):
        v = cumul[c]
        debut = ouvertures.get(c, Decimal(0)) + v["avant"]
        fin = debut + v["paie"] + v["versements"]
        org = organisme(noms[c])
        ligne = [org, f"{str(c)[:4]} {noms[c]}", debut, v["paie"], -v["versements"], fin, v["paie"]]
        lignes.append(ligne)
        if org == VACANCES:
            continue
        for i in range(5):
            totaux[org][i] += ligne[2 + i]
    for org, t in sorted(totaux.items()):
        lignes.append([org, "Total à remettre", *t])
    salaires = [[f"{str(c)[:4]} {noms.get(c, '')}", cumul[c]["paie"] + cumul[c]["versements"]] for c in charges]
    return lignes, {"salaires": sum((s for _n, s in salaires), Decimal(0)), "charges": salaires,
                    "echeance": _echeance(annee, mois),
                    "a_remettre": {org: t[4] for org, t in totaux.items()}}


def _echeance(annee: int, mois: int) -> date:
    _du, au = bornes_mois(annee, mois)
    return (au + timedelta(days=1)).replace(day=15)

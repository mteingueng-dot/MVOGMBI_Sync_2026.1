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


# --------------------------------------------------------------------------------------------- suivi des remises
REMIS, REMIS_EN_RETARD, A_REMETTRE, EN_RETARD, RIEN = (
    "Remis à temps", "Remis en retard", "À remettre", "EN RETARD", "Rien à remettre")
JOURS_ALERTE = 5  # le résumé du matin prévient 5 jours avant l'échéance
ENTETES_SUIVI = ["Mois", "Organisme", "À remettre", "Versé", "Versé le", "Échéance", "État"]


def versements(base, passifs_par_organisme: dict[str, list[int]], du: date, au: date) -> dict[str, list]:
    """Versements aux organismes (débits des comptes de retenues hors écritures de paie) : {organisme: [(date,
    montant)]}, du plus ancien au plus récent."""
    tous = [c for comptes in passifs_par_organisme.values() for c in comptes]
    if not tous:
        return {}
    lignes = base.requete(
        f"SELECT a.lAcctId c, e.dtJourDate d, ROUND(SUM(a.dAmount), 2) s FROM tjentact a JOIN tjourent e "
        f"ON e.lId = a.lJEntId WHERE a.lAcctId IN ({', '.join(str(int(c)) for c in tous)}) AND e.nModule <> 3 "
        f"AND e.nType NOT IN {CORRIGEES} AND e.dtJourDate BETWEEN %s AND %s GROUP BY a.lAcctId, e.dtJourDate "
        f"ORDER BY e.dtJourDate", (du.isoformat(), au.isoformat()))
    organisme_de = {c: org for org, comptes in passifs_par_organisme.items() for c in comptes}
    resultat: dict[str, list] = defaultdict(list)
    for l in lignes:
        montant = -_d(l["s"])  # un versement diminue le passif (sens normal : crédit positif)
        if montant > 0:
            jour = l["d"].date() if hasattr(l["d"], "date") else l["d"]
            resultat[organisme_de[l["c"]]].append((jour, montant))
    return resultat


def etat_remise(a_remettre: Decimal, verses: list[tuple[date, Decimal]], echeance: date,
                aujourdhui: date) -> tuple[str, Decimal, date | None]:
    """(état, versé, date où le montant dû est couvert)."""
    if a_remettre <= CENT / 2:
        return RIEN, Decimal(0), None
    cumul, couvert = Decimal(0), None
    for jour, montant in verses:
        cumul += montant
        if couvert is None and cumul >= a_remettre - CENT:
            couvert = jour
    if couvert:
        return (REMIS if couvert <= echeance else REMIS_EN_RETARD), cumul, couvert
    return (EN_RETARD if aujourdhui > echeance else A_REMETTRE), cumul, None


def suivi(base, aujourdhui: date, mois: int = 12) -> list[list]:
    """Suivi des remises des `mois` derniers mois terminés (le plus récent d'abord) : versements cherchés du 1er
    du mois suivant jusqu'à 60 jours après l'échéance."""
    comptes = {r["lId"]: r["sName"] or "" for r in base.requete("SELECT lId, sName FROM taccount")}
    touches = [r["c"] for r in base.requete(
        f"SELECT DISTINCT a.lAcctId c FROM tjentact a JOIN tjourent e ON e.lId = a.lJEntId WHERE e.nModule = 3 "
        f"AND e.nType NOT IN {CORRIGEES}")]
    par_org: dict[str, list[int]] = defaultdict(list)
    for c in touches:
        org = organisme(comptes.get(c, ""))
        if str(c).startswith("2") and org and org != VACANCES:
            par_org[org].append(c)
    lignes = []
    annee, m = aujourdhui.year, aujourdhui.month
    for _ in range(mois):
        m -= 1
        if m == 0:
            annee, m = annee - 1, 12
        _lignes, info = etat(base, annee, m)
        echeance = info["echeance"]
        _du, au = bornes_mois(annee, m)
        verses = versements(base, par_org, au + timedelta(days=1), echeance + timedelta(days=60))
        for org, a_remettre in sorted(info.get("a_remettre", {}).items()):
            etat_, verse, le = etat_remise(a_remettre, verses.get(org, []), echeance, aujourdhui)
            lignes.append([f"{annee}-{m:02d}", org, a_remettre, verse, le.isoformat() if le else "",
                           echeance.isoformat(), etat_])
    return lignes


def alertes(lignes_suivi: list[list], aujourdhui: date) -> list[str]:
    """Remises en retard, ou à faire d'ici JOURS_ALERTE jours."""
    resultat = []
    for mois, org, a_remettre, _verse, _le, echeance, etat_ in lignes_suivi:
        jours = (date.fromisoformat(echeance) - aujourdhui).days
        if etat_ == EN_RETARD:
            resultat.append(f"Retenues de {mois} à {org} EN RETARD ({a_remettre} $, échéance {echeance})")
        elif etat_ == A_REMETTRE and jours <= JOURS_ALERTE:
            resultat.append(f"Retenues de {mois} à remettre à {org} d'ici le {echeance} ({a_remettre} $)")
    return resultat

"""Traitement de la paie (demande du propriétaire du 2026-10-29) : calculs de la page « Paie > Traitement de la paie ».

- Heures : lues dans l'application (pointages du poste, feuilles de temps), jamais dans Sage ; heures planifiées =
  planning mensuel (planning.py). Récapitulatif par employé et par semaine (du dimanche au samedi, 2 semaines par
  période de paie).
- Heures validées = feuilles de temps « Approuvée » : ce sont elles qui sont saisies dans la paie de Sage.
- Paies de Sage : écritures du module Paie (tjourent.nModule 3), lisibles sans accès au module Paie : une écriture
  par employé (nom dans la remarque) ; sens normal des comptes (charges et passifs positifs, compte de banque
  négatif pour le net versé). Gains = charges de salaire ; cotisations de l'employeur = charges dont le nom désigne
  un organisme (RRQ, AE, RQAP, FSS, CNESST…) ; retenues de l'employé = passif de l'organisme − cotisation de
  l'employeur ; net = sortie du compte de banque ; vacances = provision (ni gain ni retenue).
- Relevé de paie imprimé par l'application (en-tête de l'entreprise, heures de l'application, montants de Sage,
  cumul de l'année).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from . import paie_temps as pt
from .comptabilite import CORRIGEES
from .retenues import AUTRE, VACANCES, organisme

CENT = Decimal("0.01")
ZERO = Decimal(0)
ENTETES_SEMAINES = ["Semaine du", "au", "Employé", "Heures planifiées", "Heures réalisées", "Écart",
                    "Feuille de temps"]
ENTETES_JOURS = ["Date", "Employé", "Quart planifié", "Heures planifiées", "Heures réalisées", "Écart"]
ENTETES_VALIDEES = ["Employé", "Période du", "au", "Heures normales", "Heures supplémentaires", "Jours fériés",
                    "Congés payés", "Total à payer", "État", "Approuvée par"]
ENTETES_PAIES = ["Date", "Source", "Employé", "Salaire brut", "Retenues", "Salaire net",
                 "Cotisations de l'employeur", "Contrôle"]


def heures(v: Decimal) -> str:
    """« 37,5 h » : les heures ne sont jamais affichées comme des montants."""
    return f"{Decimal(v).quantize(CENT):f}".replace(".", ",").rstrip("0").rstrip(",") + " h"


def argent(v) -> str:
    return "" if v == "" else f"{Decimal(v):,.2f} $".replace(",", " ").replace(".", ",")


def _simple(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c if c.isalnum() else " " for c in texte).split())


# sorte de retenue d'après le nom du compte (passif « RRQ à payer » et charge « RRQ - employeur » : même rubrique)
RUBRIQUES = (("rqap", "RQAP"), ("rrq", "RRQ"), ("rpc", "RPC"), ("fss", "FSS"), ("cnesst", "CNESST"),
             ("csst", "CNESST"), ("cnt", "CNT"), ("assurance emploi", "Assurance-emploi"),
             ("quebec a payer", "Impôt du Québec"))


def rubrique(nom: str) -> str:
    """« RRQ à payer » / « RRQ - employeur » -> « RRQ » ; impôts : « Impôt du Québec » / « Impôt fédéral »."""
    texte = _simple(nom)
    mots = texte.split()
    for cle, libelle in RUBRIQUES:
        if cle in mots or (" " in cle and cle in texte):
            return libelle
    if "ae" in mots or texte.startswith("ae "):
        return "Assurance-emploi"
    if "impot" in mots or "receveur" in mots:
        return "Impôt fédéral" if any(m in mots for m in ("federal", "receveur")) else "Impôt du Québec"
    return " ".join(nom.split())


# --------------------------------------------------------------------------------------------- heures
@dataclass
class LigneSemaine:
    debut: date
    employe: str
    planifiees: Decimal
    realisees: Decimal
    etat: str

    @property
    def fin(self) -> date:
        return self.debut + timedelta(days=6)

    @property
    def ecart(self) -> Decimal:
        return self.realisees - self.planifiees


def _planifiees(planning, employe_id: str, jour: date) -> tuple[Decimal, str]:
    quart = planning.quart(f"{jour:%Y-%m}", employe_id, jour) if planning else None
    return (quart.heures, quart.texte()) if quart else (ZERO, "")


def semaines(feuilles: list[pt.Feuille], planning) -> list[LigneSemaine]:
    """Récapitulatif : une ligne par employé et par semaine de la période (heures réalisées = feuille de temps)."""
    lignes = []
    for f in feuilles:
        for rang in range(2):
            debut = f.debut + timedelta(days=7 * rang)
            prevues = sum((_planifiees(planning, f.employe.id, debut + timedelta(days=j))[0] for j in range(7)), ZERO)
            lignes.append(LigneSemaine(debut, f.employe.nom, prevues, f.semaines[rang], f.etat))
    return sorted(lignes, key=lambda l: (l.debut, l.employe.casefold()))


def jours(feuilles: list[pt.Feuille], planning) -> list[list]:
    """Détail jour par jour : quart planifié et heures réalisées (jours sans l'un ni l'autre omis)."""
    lignes = []
    for f in feuilles:
        for j, realise in enumerate(f.jours):
            jour = f.debut + timedelta(days=j)
            prevues, texte = _planifiees(planning, f.employe.id, jour)
            if prevues or realise:
                lignes.append([jour.isoformat(), f.employe.nom, texte, prevues, realise, realise - prevues])
    return sorted(lignes, key=lambda l: (l[0], l[1].casefold()))


def validees(feuilles: list[pt.Feuille], extras: dict | None = None) -> list[list]:
    """Heures à saisir dans la paie de Sage : feuilles approuvées d'abord, puis celles qui attendent. `extras` :
    {employé : (heures de jours fériés, heures de congés payés)} (conges.heures_a_payer)."""
    lignes = []
    for f in sorted(feuilles, key=lambda f: (f.etat == pt.A_APPROUVER, f.employe.nom.casefold())):
        feries, conges = (extras or {}).get(f.employe.id, (ZERO, ZERO))
        if not (f.total or feries or conges) and f.etat == pt.A_APPROUVER:
            continue
        lignes.append([f.employe.nom, f.debut.isoformat(), (f.debut + timedelta(days=pt.JOURS_PERIODE - 1)).isoformat(),
                       f.normales, f.supplementaires, feries, conges, f.total + feries + conges, f.etat,
                       f.approuvee_par])
    return lignes


def extras_periode(racine, feuilles: list[pt.Feuille]) -> dict:
    """Heures de jours fériés et de congés payés de chaque employé pour la période des feuilles."""
    from .conges import Registre as Conges, heures_a_payer

    if not feuilles:
        return {}
    conges, registre = Conges(racine), pt.Registre(racine)
    debut = feuilles[0].debut
    fin = debut + timedelta(days=pt.JOURS_PERIODE - 1)
    return {f.employe.id: heures_a_payer(conges, registre, f.employe, debut, fin)[:2] for f in feuilles}


# --------------------------------------------------------------------------------------------- paies de Sage
# Tables de paie de Sage (accès Vue au module Paie). Revenus : tcomppy5, retenues : tcomppy6, par n° d'ordre.
RETENUES_SAGE = {1: "Assurance-emploi", 2: "RPC", 3: "Impôt fédéral", 6: "Impôt du Québec", 7: "RRQ", 29: "RQAP"}
VACANCES_ACQUISES, VACANCES_PAYEES = 4, 5
ACCES_REFUSE = 1142


@dataclass
class GainSage:
    libelle: str
    unite: str         # « Heure » ou « Période »
    taux: Decimal
    unites: Decimal
    montant: Decimal
    cumul: Decimal


@dataclass
class DetailPaie:
    """Détail d'une paie lu dans les tables de paie de Sage (`tpydet`, `tpydet1`, `tpydet2`, `tpydluc`) : montants
    exacts de l'employé. Constat du 2026-10-30 : les écritures comptables comptent la provision de vacances dans le
    brut et ne séparent pas toujours la part de l'employeur (2026 : brut 81 505 $ contre 79 445 $, A-E 2 416 $ contre
    1 007 $), d'où cette lecture ; le NAS (temp.sSIN) et le compte bancaire ne sont jamais lus."""
    brut: Decimal = ZERO
    retenues: dict[str, Decimal] = field(default_factory=dict)
    retenues_annee: dict[str, Decimal] = field(default_factory=dict)
    gains: list[GainSage] = field(default_factory=list)
    heures: Decimal = ZERO
    debut: date | None = None
    fin: date | None = None
    vacances_acquises: Decimal = ZERO
    vacances_acquises_annee: Decimal = ZERO
    vacances_payees_annee: Decimal = ZERO
    solde_reporte: Decimal = ZERO
    gains_ae: Decimal = ZERO
    gains_pension: Decimal = ZERO
    gains_rqap: Decimal = ZERO
    adresse: str = ""
    courriel: str = ""

    @property
    def vacances_dues(self) -> Decimal:
        return self.solde_reporte + self.vacances_acquises_annee - self.vacances_payees_annee


@dataclass
class PaieSage:
    ident: int
    jour: date
    source: str
    employe: str
    gains: dict[str, Decimal] = field(default_factory=dict)        # compte de salaire -> montant
    passifs: dict[str, Decimal] = field(default_factory=dict)      # rubrique -> montant au passif
    cotisations: dict[str, Decimal] = field(default_factory=dict)  # rubrique -> part de l'employeur
    autres_retenues: dict[str, Decimal] = field(default_factory=dict)  # compte de passif sans organisme connu
    vacances: Decimal = ZERO
    net: Decimal = ZERO
    detail: DetailPaie | None = None

    @property
    def brut(self) -> Decimal:
        return self.detail.brut if self.detail else sum(self.gains.values(), ZERO)

    @property
    def retenues(self) -> dict[str, Decimal]:
        """Retenues de l'employé par rubrique (passif − part de l'employeur), puis les autres retenues."""
        if self.detail:
            return dict(self.detail.retenues)
        r = {o: max(ZERO, m - self.cotisations.get(o, ZERO)) for o, m in self.passifs.items()}
        r.update(self.autres_retenues)
        return {k: v for k, v in r.items() if v}

    @property
    def total_retenues(self) -> Decimal:
        return sum(self.retenues.values(), ZERO)

    @property
    def total_cotisations(self) -> Decimal:
        return sum(self.cotisations.values(), ZERO)

    @property
    def ecart(self) -> Decimal:
        """Brut − retenues − net : 0 si l'écriture est entièrement expliquée."""
        return self.brut - self.total_retenues - self.net


def classer(paie: PaieSage, numero: int, nom: str, montant: Decimal) -> None:
    """Range une ligne de l'écriture de paie (compte n° 4 chiffres, nom, montant au sens normal du compte)."""
    premier = str(numero)[:1]
    if premier == "1":
        paie.net -= montant  # sortie du compte de banque
    elif premier == "2":
        org = organisme(nom)
        if org == VACANCES:
            return  # provision des vacances : ni gain ni retenue
        if org in (None, AUTRE):
            paie.autres_retenues[nom] = paie.autres_retenues.get(nom, ZERO) + montant
        else:
            cle = rubrique(nom)
            paie.passifs[cle] = paie.passifs.get(cle, ZERO) + montant
    else:
        org = organisme(nom)
        if org == VACANCES:
            paie.vacances += montant
        elif org in (None, AUTRE):
            paie.gains[nom] = paie.gains.get(nom, ZERO) + montant
        else:
            cle = rubrique(nom)
            paie.cotisations[cle] = paie.cotisations.get(cle, ZERO) + montant


def paies_sage(base, du: date, au: date) -> list[PaieSage]:
    """Écritures de paie de Sage entre deux dates (écritures corrigées exclues), une par employé."""
    lignes = base.requete(
        "SELECT e.lId i, e.dtJourDate d, e.sSource s, e.sComment c, a.lAcctId compte, TRIM(k.sName) nom, "
        "ROUND(SUM(a.dAmount), 2) m FROM tjentact a JOIN tjourent e ON e.lId = a.lJEntId "
        "JOIN taccount k ON k.lId = a.lAcctId "
        f"WHERE e.nModule = 3 AND e.nType NOT IN {CORRIGEES} AND e.dtJourDate >= %s AND e.dtJourDate < %s "
        "GROUP BY e.lId, e.dtJourDate, e.sSource, e.sComment, a.lAcctId, k.sName ORDER BY e.dtJourDate, e.lId",
        (du.isoformat(), (au + timedelta(days=1)).isoformat()))
    paies: dict[int, PaieSage] = {}
    for l in lignes:
        p = paies.get(l["i"])
        if p is None:
            jour = l["d"].date() if hasattr(l["d"], "date") else date.fromisoformat(str(l["d"])[:10])
            p = paies[l["i"]] = PaieSage(l["i"], jour, (l["s"] or "").strip(), (l["c"] or "").strip())
        classer(p, int(l["compte"]) // 10000, l["nom"] or "", Decimal(str(l["m"] or 0)).quantize(CENT))
    liste = list(paies.values())
    completer_details(base, liste)
    return liste


def _argent(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _jour(v) -> date | None:
    return v.date() if hasattr(v, "date") else None


def adresses_sage(base) -> dict[int, tuple[str, str]]:
    """Adresse (lignes séparées par « | ») et courriel de chaque employé. Colonnes nommées : jamais le NAS."""
    sortie = {}
    for l in base.requete("SELECT lId, sStreet1, sStreet2, sCity, sProvState, sPostalZip, sEmail FROM temp"):
        ville = " ".join(x.strip() for x in (l["sCity"], l["sProvState"], l["sPostalZip"]) if x and x.strip())
        lignes = [x.strip() for x in (l["sStreet1"], l["sStreet2"], ville) if x and x.strip()]
        sortie[l["lId"]] = (" | ".join(lignes), (l["sEmail"] or "").strip())
    return sortie


def completer_details(base, paies: list[PaieSage]) -> bool:
    """Ajoute à chaque paie son détail lu dans les tables de paie de Sage. Accès au module Paie refusé : False, les
    montants restent ceux des écritures comptables."""
    if not paies:
        return False
    marques = ",".join(["%s"] * len(paies))
    try:
        entetes = base.requete(
            "SELECT a.lId, a.lEmpId, a.lJourId, a.dGross, a.dHrsWorked, a.dtPrdStart, a.dtPrdEnd, a.dEIEarn, a.dPenEarn, "
            f"a.dQpipEarn, c.dVacBalFor FROM tpydet a LEFT JOIN tpydluc c ON c.lDetID = a.lId WHERE a.lJourId IN ({marques})",
            tuple(p.ident for p in paies))
        noms_revenus = {l["lId"]: (l["sName"].strip(), (l["sUnit"] or "").strip()) for l in base.requete(
            "SELECT lId, sName, sUnit FROM tcomppy5 WHERE lCompId = 1")}
        noms_retenues = {l["lId"]: l["sName"].strip() for l in base.requete(
            "SELECT lId, sName FROM tcomppy6 WHERE lCompId = 1")}
        adresses = adresses_sage(base)
    except Exception as exc:
        if exc.args and exc.args[0] == ACCES_REFUSE:
            return False  # accès au module Paie pas (encore) donné pour ce fichier
        raise
    par_ecriture = {e["lJourId"]: e for e in entetes}
    if not par_ecriture:
        return False
    marques = ",".join(["%s"] * len(entetes))
    ids = tuple(e["lId"] for e in entetes)
    revenus: dict[tuple, list] = {}
    for l in base.requete("SELECT lDetId, lEmpId, lIncId, nType, dAmtPrUnit, dUnitsPrPd, dAmtPerPd, dAmtYTD FROM tpydet1 "
                          f"WHERE lDetId IN ({marques}) ORDER BY lIncId", ids):
        revenus.setdefault((l["lDetId"], l["lEmpId"]), []).append(l)
    retenues: dict[tuple, list] = {}
    for l in base.requete(f"SELECT lDetId, lEmpId, lDedId, dDedPerPd, dAmtYTD FROM tpydet2 WHERE lDetId IN ({marques}) "
                          "ORDER BY lDedId", ids):
        retenues.setdefault((l["lDetId"], l["lEmpId"]), []).append(l)
    for p in paies:
        e = par_ecriture.get(p.ident)
        if e is None:
            continue
        cle = (e["lId"], e["lEmpId"])
        adresse, courriel = adresses.get(e["lEmpId"], ("", ""))
        d = DetailPaie(brut=_argent(e["dGross"]), heures=_argent(e["dHrsWorked"]), debut=_jour(e["dtPrdStart"]),
                       fin=_jour(e["dtPrdEnd"]), solde_reporte=_argent(e["dVacBalFor"]), gains_ae=_argent(e["dEIEarn"]),
                       gains_pension=_argent(e["dPenEarn"]), gains_rqap=_argent(e["dQpipEarn"]), adresse=adresse,
                       courriel=courriel)
        for l in revenus.get(cle, []):
            montant, cumul = _argent(l["dAmtPerPd"]), _argent(l["dAmtYTD"])
            if l["lIncId"] == VACANCES_ACQUISES:
                d.vacances_acquises, d.vacances_acquises_annee = montant, cumul
                continue
            if l["lIncId"] == VACANCES_PAYEES:
                d.vacances_payees_annee = cumul
            if l["nType"] != -1 and (montant or cumul):  # -1 : prêts, avantages, avances, hors du brut payé
                nom, unite = noms_revenus.get(l["lIncId"], (f"Revenu {l['lIncId']}", ""))
                d.gains.append(GainSage(nom, unite, _argent(l["dAmtPrUnit"]), _argent(l["dUnitsPrPd"]), montant, cumul))
        for l in retenues.get(cle, []):
            nom = RETENUES_SAGE.get(l["lDedId"]) or noms_retenues.get(l["lDedId"], f"Retenue {l['lDedId']}")
            montant, cumul = _argent(l["dDedPerPd"]), _argent(l["dAmtYTD"])
            if montant:
                d.retenues[nom] = montant
            if cumul:
                d.retenues_annee[nom] = cumul
        p.detail = d
    return True


def lignes_paies(paies: list[PaieSage]) -> list[list]:
    return [[p.jour.isoformat(), p.source, p.employe, p.brut, p.total_retenues, p.net, p.total_cotisations,
             "✔" if abs(p.ecart) <= CENT else f"Écart {p.ecart}"] for p in paies]


def employes_sage(base) -> list[str]:
    """Employés de Sage : fiches du module Paie si l'utilisateur de lecture y a accès, sinon noms lus dans les
    écritures de paie des deux dernières années (remarque de l'écriture = nom de l'employé)."""
    try:
        noms = [r["n"] for r in base.requete("SELECT TRIM(sName) n FROM temp WHERE sName <> ''")]
    except Exception:  # constat du 2026-10-29 : SELECT refusé sur temp (pas d'accès au module Paie)
        noms = [r["n"] for r in base.requete(
            f"SELECT DISTINCT TRIM(sComment) n FROM tjourent WHERE nModule = 3 AND nType NOT IN {CORRIGEES} "
            "AND dtJourDate >= DATE_SUB(CURDATE(), INTERVAL 2 YEAR) AND TRIM(sComment) <> ''")]
    return sorted({n for n in noms if n}, key=str.casefold)


def _correspond(nom: str, texte: str) -> bool:
    mots = _simple(texte).split()
    return bool(nom.strip()) and all(m in mots for m in _simple(nom).split())


def proposer_lien(employe: pt.Employe, noms_sage: list[str]) -> str:
    """Employé Sage proposé : celui dont le nom contient tous les mots du nom de l'employé (ou l'inverse) ; rien
    si aucun ou plusieurs."""
    trouves = [n for n in noms_sage if _correspond(employe.nom, n) or _correspond(n, employe.nom)]
    return trouves[0] if len(trouves) == 1 else ""


def employe_de(paie: PaieSage, employes: list[pt.Employe]) -> pt.Employe | None:
    """Employé de l'application relié à l'employé Sage de la paie ; sinon celui dont tous les mots du nom figurent
    dans la remarque (ou la source) de la paie."""
    relie = [e for e in employes if e.numero_sage and _simple(e.numero_sage) == _simple(paie.employe)]
    if relie:
        return relie[0]
    texte = f"{paie.employe} {paie.source}"
    candidats = [e for e in employes if not e.numero_sage and _correspond(e.nom, texte)]
    return max(candidats, key=lambda e: len(e.nom)) if candidats else None


def feuille_de_la_paie(registre: pt.Registre, employe: pt.Employe, jour: date, reference: date) -> pt.Feuille | None:
    """Feuille de la dernière période terminée au plus tard le jour de la paie (paie versée dans les 14 jours)."""
    debut = pt.debut_periode(jour, reference)
    if debut + timedelta(days=pt.JOURS_PERIODE - 1) > jour:
        debut -= timedelta(days=pt.JOURS_PERIODE)
    f = pt.feuille(registre, employe, debut)
    return f if f.total else None


def cumul_annee(paies: list[PaieSage], paie: PaieSage) -> PaieSage:
    """Somme des paies du même employé de l'année, jusqu'à celle-ci comprise."""
    total = PaieSage(0, paie.jour, "", paie.employe)
    for p in paies:
        if p.employe == paie.employe and p.jour.year == paie.jour.year and (p.jour, p.ident) <= (paie.jour, paie.ident):
            for cible, source in ((total.gains, p.gains), (total.passifs, p.passifs),
                                  (total.cotisations, p.cotisations), (total.autres_retenues, p.autres_retenues)):
                for k, v in source.items():
                    cible[k] = cible.get(k, ZERO) + v
            total.net += p.net
            total.vacances += p.vacances
    if paie.detail:  # cumuls tenus par Sage, reprises de solde comprises
        d = paie.detail
        total.detail = DetailPaie(brut=sum((g.cumul for g in d.gains), ZERO), retenues=dict(d.retenues_annee))
    return total


def releve(paie: PaieSage, cumul: PaieSage, f: pt.Feuille | None,
           heures_annee: Decimal | None = None) -> tuple[list[str], list[list[str]], str]:
    """Relevé de paie : (en-têtes, lignes en texte, sous-titre). Montants de Sage, heures de l'application."""
    lignes: list[list[str]] = []

    def ligne(rubrique: str, h="", ici="", annee="") -> None:
        lignes.append([rubrique, heures(h) if h != "" else "", argent(ici), argent(annee)])

    if f is not None:
        ligne("Heures normales", f.normales)
        ligne("Heures supplémentaires", f.supplementaires)
    if heures_annee is not None:
        ligne("Heures de l'année (pointées)", heures_annee)
    ligne("GAINS")
    for nom in sorted(set(paie.gains) | set(cumul.gains)):
        ligne(f"   {nom}", "", paie.gains.get(nom, ZERO), cumul.gains.get(nom, ZERO))
    ligne("Salaire brut", "", paie.brut, cumul.brut)
    ligne("RETENUES")
    retenues, retenues_annee = paie.retenues, cumul.retenues
    for nom in sorted(set(retenues) | set(retenues_annee)):
        ligne(f"   {nom}", "", retenues.get(nom, ZERO), retenues_annee.get(nom, ZERO))
    ligne("Total des retenues", "", paie.total_retenues, cumul.total_retenues)
    ligne("SALAIRE NET VERSÉ", "", paie.net, cumul.net)
    if paie.vacances or cumul.vacances:
        ligne("Vacances accumulées", "", paie.vacances, cumul.vacances)
    periode = (f" — période du {f.debut:%Y-%m-%d} au {f.debut + timedelta(days=pt.JOURS_PERIODE - 1):%Y-%m-%d}"
               if f is not None else "")
    sous_titre = f"{paie.employe} — paie du {paie.jour:%Y-%m-%d} ({paie.source}){periode}"
    return ["Rubrique", "Heures", "Cette paie", "Total de l'année"], lignes, sous_titre


# --------------------------------------------------------------------------------------------- fiche de paie
# format de la fiche de Sage (demande du propriétaire du 2026-10-30) : gains à gauche, retenues à droite, colonnes
# Période et Cumul ; sans les cotisations de l'employeur ; en-tête de l'entreprise gardé
LIBELLES_RETENUES = (("Assurance-emploi", "A-E"), ("RQAP", "RQAP"), ("RRQ", "RRQ"), ("RPC", "RPC"),
                     ("Impôt fédéral", "Impôt"), ("Impôt du Québec", "Impôt Qc"))
CSS_FICHE = """<style>
.fiche { font-size: 9.5pt; }
.fiche .tete { display: flex; justify-content: space-between; gap: 18px; padding: 8px 2px 4px; font-weight: 600; }
.fiche .periode { padding: 2px 2px 8px; color: #5b6a60; }
.fiche .colonnes { display: flex; gap: 14px; align-items: flex-start; }
.fiche .colonnes > div { flex: 1; }
.fiche .gains { flex: 1.45; }
.fiche table td, .fiche table th { padding: 4px 7px; }
.fiche tr.total td { font-weight: 700; background: #eaf4ed; }
.fiche tr.net td { font-weight: 700; background: #1f7a3a; color: #fff; }
.fiche td.v, .fiche th.v { text-align: right; white-space: nowrap; }
</style>"""


def _nombre(v) -> str:
    return "" if v in ("", None) else f"{Decimal(v):,.2f}".replace(",", " ").replace(".", ",")


def lignes_fiche(paie: PaieSage, cumul: PaieSage, f: pt.Feuille | None, extras=(ZERO, ZERO)) -> dict:
    """Lignes de la fiche : gains [libellé, heures, période, cumul], retenues [libellé, période, cumul], vacances. Le
    taux se déduit du brut et des heures de l'application ; sans feuille de temps : les comptes de salaire de Sage."""
    gains: list[list] = []
    if paie.detail:
        for g in paie.detail.gains:
            horaire = g.unite.casefold().startswith("heure")
            libelle = f"{g.libelle} @ {_nombre(g.taux)}/Hr" if horaire and g.taux else g.libelle
            gains.append([libelle, g.unites if horaire else "", g.montant, g.cumul])
    elif f is not None and f.total and paie.brut:
        regulieres = f.normales + sum(extras, ZERO)
        taux = (paie.brut / (regulieres + f.supplementaires * Decimal("1.5"))).quantize(CENT)
        if f.supplementaires:
            montant_supp = (f.supplementaires * taux * Decimal("1.5")).quantize(CENT)
            gains.append([f"Régulières @ {_nombre(taux)}/Hr", regulieres, paie.brut - montant_supp, ""])
            gains.append([f"Supplém. 1 @ {_nombre(taux * Decimal('1.5'))}/Hr", f.supplementaires, montant_supp, ""])
        else:
            gains.append([f"Régulières @ {_nombre(taux)}/Hr", regulieres, paie.brut, cumul.brut])
    else:
        for nom in sorted(set(paie.gains) | set(cumul.gains)):
            gains.append([nom, "", paie.gains.get(nom, ZERO), cumul.gains.get(nom, ZERO)])
    retenues, retenues_annee = paie.retenues, cumul.retenues
    connues = [c for c, _l in LIBELLES_RETENUES]
    lignes_r = [[l, retenues.get(c, ZERO), retenues_annee.get(c, ZERO)] for c, l in LIBELLES_RETENUES
                if retenues.get(c) or retenues_annee.get(c)]
    lignes_r += [[n, retenues.get(n, ZERO), retenues_annee.get(n, ZERO)]
                 for n in sorted((set(retenues) | set(retenues_annee)) - set(connues))]
    return {"gains": gains, "retenues": lignes_r, "vacances": (paie.vacances, cumul.vacances)}


def fiche_de_paie(paie: PaieSage, cumul: PaieSage, f: pt.Feuille | None, extras=(ZERO, ZERO), periode: str = "") -> str:
    """Page HTML de la fiche de paie (en-tête de l'entreprise, puis format de la fiche de Sage)."""
    import html

    from .export_tableau import page_html

    e = html.escape
    d = lignes_fiche(paie, cumul, f, extras)
    if paie.detail and paie.detail.debut and paie.detail.fin:  # dates inscrites dans Sage
        periode = f"{paie.detail.debut:%Y-%m-%d} à {paie.detail.fin:%Y-%m-%d}"
    if f is not None and not periode:
        periode = f"{f.debut:%Y-%m-%d} à {f.debut + timedelta(days=pt.JOURS_PERIODE - 1):%Y-%m-%d}"

    def rangee(cellules, classe=""):
        return (f"<tr class='{classe}'><td>{e(str(cellules[0]))}</td>"
                + "".join(f"<td class='v'>{e(str(c))}</td>" for c in cellules[1:]) + "</tr>")

    gauche = "".join(rangee([l, "", _nombre(h), _nombre(p), _nombre(c)]) for l, h, p, c in d["gains"])
    gauche += rangee(["Salaire brut", "", "", _nombre(paie.brut), _nombre(cumul.brut)], "total")
    gauche += rangee(["Brut payé", "", "", _nombre(paie.brut), _nombre(cumul.brut)])
    acquises, acquises_annee = d["vacances"]
    if paie.detail:
        v = paie.detail
        if v.vacances_acquises or v.vacances_acquises_annee or v.solde_reporte:
            gauche += rangee(["Vac. cumul.", "", "", _nombre(v.vacances_acquises), _nombre(v.vacances_acquises_annee)])
            gauche += rangee(["Vac. payées", "", "", "", _nombre(v.vacances_payees_annee)])
            gauche += rangee(["Solde rep.", "", "", "", _nombre(v.solde_reporte)])
            gauche += rangee(["Vacances dues", "", "", "", _nombre(v.vacances_dues)], "total")
    elif acquises or acquises_annee:
        gauche += rangee(["Vacances acquises", "", "", _nombre(acquises), _nombre(acquises_annee)])
    droite = "".join(rangee([l, _nombre(p), _nombre(c)]) for l, p, c in d["retenues"])
    droite += rangee(["Retenues", _nombre(paie.total_retenues), _nombre(cumul.total_retenues)], "total")
    droite += rangee(["Salaire net", _nombre(paie.net), _nombre(cumul.net)], "net")
    if paie.detail and paie.detail.heures:
        droite += rangee(["Hres AE assurables", _nombre(paie.detail.heures), ""])
    elif f is not None and f.total:
        droite += rangee(["Hres AE assurables", _nombre(f.total + sum(extras, ZERO)), ""])
    corps = (f"{CSS_FICHE}<div class='fiche'><div class='tete'><span>{e(paie.employe)}</span>"
             f"<span>{paie.jour:%Y-%m-%d}</span><span>{e(paie.source)}</span></div>"
             + (f"<div class='periode'>Période de paie : {e(periode)}</div>" if periode else "")
             + "<div class='colonnes'><div class='gains'><table><thead><tr><th></th><th class='v'>Pièces</th>"
               "<th class='v'>Heures</th><th class='v'>Période</th><th class='v'>Cumul</th></tr></thead><tbody>"
             + gauche + "</tbody></table></div><div><table><thead><tr><th></th><th class='v'>Période</th>"
               "<th class='v'>Cumul</th></tr></thead><tbody>" + droite + "</tbody></table></div></div></div>")
    page = page_html("Fiche de paie", [], [], sous_titre=f"{paie.employe} — {paie.jour:%Y-%m-%d}")
    return page.replace("</body></html>", corps + "</body></html>")


# --------------------------------------------------------------------------------------------- envoi des bulletins
def cle_bulletin(paie: PaieSage) -> str:
    return f"{paie.employe}|{paie.jour.isoformat()}|{paie.source}"


def bulletins_envoyes(racine) -> set[str]:
    import csv
    from pathlib import Path

    chemin = Path(racine) / "donnees" / "journal_bulletins_envoyes.csv"
    if not chemin.exists():
        return set()
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        return {r["Paie"] for r in csv.DictReader(f, delimiter=";")}


def noter_envoi(racine, paie: PaieSage, courriel: str) -> None:
    import csv
    from datetime import datetime
    from pathlib import Path

    chemin = Path(racine) / "donnees" / "journal_bulletins_envoyes.csv"
    nouveau = not chemin.exists()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.writer(f, delimiter=";")
        if nouveau:
            ecrivain.writerow(["Envoyé le", "Paie", "Employé", "Courriel"])
        ecrivain.writerow([datetime.now().isoformat(timespec="seconds"), cle_bulletin(paie), paie.employe, courriel])


def envoyer_bulletin(config_toml: dict, courriel: str, nom: str, paie: PaieSage, pdf: bytes) -> None:
    """Bulletin de paie en PDF, au seul employé concerné."""
    from .courriel import envoyer_a

    jour = paie.jour.isoformat()
    envoyer_a(config_toml, courriel, f"Bulletin de paie du {jour}",
              f"Bonjour {nom},\n\nVous trouverez ci-joint votre bulletin de paie du {jour}.\n\n"
              "Ce message est personnel et confidentiel.\n",
              [(f"Bulletin de paie {jour}.pdf", pdf)])

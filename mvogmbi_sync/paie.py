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
             ("csst", "CNESST"), ("cnt", "CNT"), ("assurance emploi", "Assurance-emploi"))


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

    @property
    def brut(self) -> Decimal:
        return sum(self.gains.values(), ZERO)

    @property
    def retenues(self) -> dict[str, Decimal]:
        """Retenues de l'employé par rubrique (passif − part de l'employeur), puis les autres retenues."""
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
    return list(paies.values())


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
    if paie.cotisations or cumul.cotisations:
        ligne("COTISATIONS DE L'EMPLOYEUR (information)")
        for nom in sorted(set(paie.cotisations) | set(cumul.cotisations)):
            ligne(f"   {nom}", "", paie.cotisations.get(nom, ZERO), cumul.cotisations.get(nom, ZERO))
    if paie.vacances or cumul.vacances:
        ligne("Vacances accumulées", "", paie.vacances, cumul.vacances)
    periode = (f" — période du {f.debut:%Y-%m-%d} au {f.debut + timedelta(days=pt.JOURS_PERIODE - 1):%Y-%m-%d}"
               if f is not None else "")
    sous_titre = f"{paie.employe} — paie du {paie.jour:%Y-%m-%d} ({paie.source}){periode}"
    return ["Rubrique", "Heures", "Cette paie", "Total de l'année"], lignes, sous_titre


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

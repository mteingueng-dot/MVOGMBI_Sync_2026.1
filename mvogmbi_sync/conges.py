"""Jours fériés et congés (demande du propriétaire du 2026-10-29, priorité n° 4) — Loi sur les normes du travail du
Québec (repères généraux ; en cas de doute, la CNESST fait foi) :

- jours fériés : 1er janvier, Vendredi saint ou lundi de Pâques (au choix de l'employeur), lundi qui précède le
  25 mai (Journée nationale des patriotes), 24 juin (Fête nationale ; le 25 si le 24 est un dimanche), 1er juillet
  (le 2 si c'est un dimanche), 1er lundi de septembre (fête du Travail), 2e lundi d'octobre (Action de grâces),
  25 décembre ;
- indemnité d'un jour férié : 1/20 du salaire gagné (sans les heures supplémentaires) pendant les 4 semaines
  complètes de paie qui précèdent la semaine du jour férié ; l'application la compte en HEURES (1/20 des heures
  normales pointées), payées au taux de l'employé dans Sage ;
- congés pour maladie ou obligations familiales : 10 jours par année, dont 2 payés après 3 mois de service continu
  (indemnité calculée comme celle d'un jour férié) ;
- vacances : année de référence du 1er mai au 30 avril ; moins de 3 ans de service : 2 semaines, 4 % ; 3 ans et
  plus : 3 semaines, 6 % (Sage calcule la paie de vacances ; l'application suit les jours dus et pris).

Les heures de jour férié et de congé payé s'ajoutent aux heures normales envoyées à Sage (Traitement de la paie).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from . import paie_temps as pt

ZERO = Decimal(0)
VACANCES, MALADIE_PAYE, MALADIE_NON_PAYE, SANS_SOLDE = (
    "Vacances", "Maladie ou famille (payé)", "Maladie ou famille (non payé)", "Congé sans solde")
TYPES = [VACANCES, MALADIE_PAYE, MALADIE_NON_PAYE, SANS_SOLDE]
PAYES = {VACANCES, MALADIE_PAYE}
JOURS_MALADIE_PAYES = 2
JOURS_MALADIE_TOTAL = 10


# --------------------------------------------------------------------------------------------- jours fériés
def paques(annee: int) -> date:
    """Dimanche de Pâques (calendrier grégorien, algorithme de Meeus/Jones/Butcher)."""
    a, b, c = annee % 19, annee // 100, annee % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = (h + l - 7 * m + 114) % 31 + 1
    return date(annee, mois, jour)


def _lundi(annee: int, mois: int, rang: int) -> date:
    premier = date(annee, mois, 1)
    return premier + timedelta(days=(7 - premier.weekday()) % 7 + 7 * (rang - 1))


def jours_feries(annee: int, paques_choix: str = "vendredi") -> list[tuple[date, str]]:
    p = paques(annee)
    patriotes = date(annee, 5, 24) - timedelta(days=date(annee, 5, 24).weekday())  # lundi qui précède le 25 mai
    nationale = date(annee, 6, 24) + (timedelta(days=1) if date(annee, 6, 24).weekday() == 6 else timedelta(0))
    canada = date(annee, 7, 1) + (timedelta(days=1) if date(annee, 7, 1).weekday() == 6 else timedelta(0))
    return [(date(annee, 1, 1), "Jour de l'An"),
            (p - timedelta(days=2), "Vendredi saint") if paques_choix == "vendredi"
            else (p + timedelta(days=1), "Lundi de Pâques"),
            (patriotes, "Journée nationale des patriotes"),
            (nationale, "Fête nationale du Québec"),
            (canada, "Fête du Canada"),
            (_lundi(annee, 9, 1), "Fête du Travail"),
            (_lundi(annee, 10, 2), "Action de grâces"),
            (date(annee, 12, 25), "Noël")]


def feries_entre(debut: date, fin: date, paques_choix: str = "vendredi") -> list[tuple[date, str]]:
    return [(j, n) for a in range(debut.year, fin.year + 1) for j, n in jours_feries(a, paques_choix)
            if debut <= j <= fin]


def debut_semaine(jour: date) -> date:
    """Semaine de paie du dimanche au samedi (comme les périodes de paie)."""
    return jour - timedelta(days=(jour.weekday() + 1) % 7)


def heures_par_jour(registre: pt.Registre, employe: pt.Employe, debut: date, fin: date) -> dict[date, Decimal]:
    liste, _isoles = pt.presences(registre.valides(employe.id))
    heures: dict[date, Decimal] = {}
    for pr in liste:
        if debut <= pr.jour <= fin:
            heures[pr.jour] = heures.get(pr.jour, ZERO) + pr.heures
    return heures


def indemnite_heures(registre: pt.Registre, employe: pt.Employe, jour: date) -> Decimal:
    """1/20 des heures normales (40 h au plus par semaine) des 4 semaines complètes avant la semaine du jour."""
    fin = debut_semaine(jour) - timedelta(days=1)
    debut = fin - timedelta(days=27)
    heures = heures_par_jour(registre, employe, debut, fin)
    total = ZERO
    for s in range(4):
        semaine = debut + timedelta(days=7 * s)
        total += min(pt.HEURES_SEMAINE, sum((heures.get(semaine + timedelta(days=i), ZERO) for i in range(7)), ZERO))
    return (total / 20).quantize(Decimal("0.01"))


# --------------------------------------------------------------------------------------------- congés
@dataclass
class Conge:
    id: str
    employe: str
    jour: str
    type: str
    heures: str = "0"          # heures payées (congé payé : indemnité ; vacances : heures du jour)
    remarque: str = ""
    auteur: str = ""
    le: str = ""


class Registre:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "conges.json"
        donnees = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else {}
        self.conges = [Conge(**c) for c in donnees.get("conges", [])]
        self.embauches: dict[str, str] = donnees.get("embauches", {})   # employé -> AAAA-MM-JJ
        self.paques: str = donnees.get("paques", "vendredi")

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"conges": [asdict(c) for c in self.conges], "embauches": self.embauches,
                                          "paques": self.paques}, ensure_ascii=False, indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)

    def ajouter(self, employe: str, debut: date, fin: date, type_: str, heures_par_jour: Decimal, auteur: str,
                remarque: str = "", jours_travailles=None) -> list[Conge]:
        """Un congé par jour de `debut` à `fin` (jours sans quart planifié sautés si `jours_travailles` est donné)."""
        if type_ not in TYPES:
            raise ValueError("Choisissez le type de congé.")
        if fin < debut:
            raise ValueError("La date de fin précède la date de début.")
        ajoutes = []
        jour = debut
        while jour <= fin:
            if jours_travailles is None or jours_travailles(jour):
                if any(c.employe == employe and c.jour == jour.isoformat() for c in self.conges):
                    raise ValueError(f"Un congé existe déjà le {jour.isoformat()}.")
                heures = heures_par_jour if type_ in PAYES else ZERO
                ajoutes.append(Conge(f"{employe}-{jour.isoformat()}", employe, jour.isoformat(), type_, str(heures),
                                     remarque, auteur, datetime.now().isoformat(timespec="seconds")))
            jour += timedelta(days=1)
        self.conges += ajoutes
        self.enregistrer()
        return ajoutes

    def supprimer(self, ident: str) -> None:
        self.conges = [c for c in self.conges if c.id != ident]
        self.enregistrer()

    def de(self, employe: str, debut: date, fin: date) -> list[Conge]:
        return [c for c in self.conges if c.employe == employe and debut.isoformat() <= c.jour <= fin.isoformat()]


def annees_service(embauche: str, jour: date) -> Decimal:
    try:
        d = date.fromisoformat(embauche)
    except (TypeError, ValueError):
        return ZERO
    return Decimal((jour - d).days) / Decimal("365.25")


def annee_reference(jour: date) -> tuple[date, date]:
    """Année de référence des vacances : du 1er mai au 30 avril."""
    debut = date(jour.year if jour.month >= 5 else jour.year - 1, 5, 1)
    return debut, date(debut.year + 1, 4, 30)


@dataclass
class Solde:
    employe: str
    service: str
    vacances_semaines: int
    vacances_taux: str
    vacances_prises: int
    maladie_payes_dus: int
    maladie_payes_pris: int
    maladie_pris: int
    remarques: list[str] = field(default_factory=list)


def solde(registre: Registre, employe: pt.Employe, jour: date) -> Solde:
    embauche = registre.embauches.get(employe.id, "")
    service = annees_service(embauche, jour)
    debut_ref, fin_ref = annee_reference(jour)
    vacances = [c for c in registre.de(employe.id, debut_ref, fin_ref) if c.type == VACANCES]
    annee = registre.de(employe.id, date(jour.year, 1, 1), date(jour.year, 12, 31))
    maladie_payes = [c for c in annee if c.type == MALADIE_PAYE]
    maladie = [c for c in annee if c.type in (MALADIE_PAYE, MALADIE_NON_PAYE)]
    remarques = []
    if not embauche:
        remarques.append("Date d'embauche à saisir")
    trois_mois = embauche and date.fromisoformat(embauche) + timedelta(days=91) <= jour
    if len(maladie_payes) > JOURS_MALADIE_PAYES:
        remarques.append("Plus de 2 jours de maladie payés cette année")
    if len(maladie) > JOURS_MALADIE_TOTAL:
        remarques.append("Plus de 10 jours d'absence pour maladie ou famille cette année")
    semaines = 3 if service >= 3 else 2
    return Solde(employe.nom, f"{service:.1f} an(s)".replace(".", ",") if embauche else "?", semaines,
                 "6 %" if semaines == 3 else "4 %", len(vacances), JOURS_MALADIE_PAYES if trois_mois else 0,
                 len(maladie_payes), len(maladie), remarques)


def heures_a_payer(conges: Registre, registre: pt.Registre, employe: pt.Employe, debut: date,
                   fin: date) -> tuple[Decimal, Decimal, list[str]]:
    """Pour une période de paie : (heures de jours fériés, heures de congés payés, détail)."""
    detail, feries = [], ZERO
    for jour, nom in feries_entre(debut, fin, conges.paques):
        h = indemnite_heures(registre, employe, jour)
        feries += h
        detail.append(f"{jour.isoformat()} {nom} : {h} h")
    payes = sum((Decimal(c.heures) for c in conges.de(employe.id, debut, fin) if c.type in PAYES), ZERO)
    return feries, payes, detail

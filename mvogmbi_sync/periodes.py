"""Calcul des périodes jour / fin de semaine / semaine / mois."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


class TypePeriode(str, Enum):
    JOUR = "jour"
    FIN_DE_SEMAINE = "fin-de-semaine"  # vendredi, samedi et dimanche : une seule facture (déposés ensemble le lundi)
    SEMAINE = "semaine"
    MOIS = "mois"


def bornes(type_periode: TypePeriode, jour_reference: date) -> tuple[date, date]:
    """Premier et dernier jour (inclus) de la période qui contient `jour_reference`.

    La semaine va du lundi au dimanche.
    """
    if type_periode is TypePeriode.JOUR:
        return jour_reference, jour_reference
    if type_periode is TypePeriode.FIN_DE_SEMAINE:
        vendredi = jour_reference - timedelta(days=(jour_reference.weekday() - 4) % 7)
        return vendredi, vendredi + timedelta(days=2)
    if type_periode is TypePeriode.SEMAINE:
        debut = jour_reference - timedelta(days=jour_reference.weekday())
        return debut, debut + timedelta(days=6)
    dernier = calendar.monthrange(jour_reference.year, jour_reference.month)[1]
    return jour_reference.replace(day=1), jour_reference.replace(day=dernier)


def est_fin_de_semaine(jour: date) -> bool:
    return jour.weekday() >= 4  # vendredi, samedi, dimanche


def dimanche(jour: date) -> date:
    return jour + timedelta(days=6 - jour.weekday())


def blocs_facturation(debut: date, fin: date) -> list[tuple[date, date, TypePeriode]]:
    """Factures d'une période : une par jour du lundi au jeudi, une pour vendredi-samedi-dimanche."""
    blocs, jour = [], debut
    while jour <= fin:
        if est_fin_de_semaine(jour):
            dernier = min(dimanche(jour), fin)
            blocs.append((jour, dernier, TypePeriode.FIN_DE_SEMAINE))
        else:
            dernier = jour
            blocs.append((jour, jour, TypePeriode.JOUR))
        jour = dernier + timedelta(days=1)
    return blocs


def jours(debut: date, fin: date) -> list[date]:
    return [debut + timedelta(days=i) for i in range((fin - debut).days + 1)]


def en_millisecondes(debut: date, fin: date, fuseau: str) -> tuple[int, int]:
    """Intervalle [début 00:00, lendemain de fin 00:00[ en millisecondes epoch, heure locale."""
    tz = ZoneInfo(fuseau)
    t0 = datetime.combine(debut, time.min, tzinfo=tz)
    t1 = datetime.combine(fin + timedelta(days=1), time.min, tzinfo=tz)
    return int(t0.timestamp() * 1000), int(t1.timestamp() * 1000)

"""Calcul des périodes jour / semaine / mois."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


class TypePeriode(str, Enum):
    JOUR = "jour"
    SEMAINE = "semaine"
    MOIS = "mois"


def bornes(type_periode: TypePeriode, jour_reference: date) -> tuple[date, date]:
    """Premier et dernier jour (inclus) de la période qui contient `jour_reference`.

    La semaine va du lundi au dimanche.
    """
    if type_periode is TypePeriode.JOUR:
        return jour_reference, jour_reference
    if type_periode is TypePeriode.SEMAINE:
        debut = jour_reference - timedelta(days=jour_reference.weekday())
        return debut, debut + timedelta(days=6)
    dernier = calendar.monthrange(jour_reference.year, jour_reference.month)[1]
    return jour_reference.replace(day=1), jour_reference.replace(day=dernier)


def jours(debut: date, fin: date) -> list[date]:
    return [debut + timedelta(days=i) for i in range((fin - debut).days + 1)]


def en_millisecondes(debut: date, fin: date, fuseau: str) -> tuple[int, int]:
    """Intervalle [début 00:00, lendemain de fin 00:00[ en millisecondes epoch, heure locale."""
    tz = ZoneInfo(fuseau)
    t0 = datetime.combine(debut, time.min, tzinfo=tz)
    t1 = datetime.combine(fin + timedelta(days=1), time.min, tzinfo=tz)
    return int(t0.timestamp() * 1000), int(t1.timestamp() * 1000)

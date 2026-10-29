"""Planning mensuel des employés (demande du propriétaire du 2026-10-29) : le gérant prépare l'horaire du mois de
chaque employé, le publie ; chaque employé voit le sien (poste de pointage après son NIP, ou « Paie > Mon horaire »
s'il a un compte de l'application relié à sa fiche d'employé).

Fichier donnees/planning.json : {"mois": {"AAAA-MM": {id employé: {"AAAA-MM-JJ": {"debut", "fin", "pause"}}}},
"publies": {"AAAA-MM": "date de publication"}}. Une modification après publication est visible tout de suite (le
planning publié est le planning en cours) ; la date de publication reste notée.
"""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


class ErreurPlanning(ValueError):
    """Horaire refusé (message à afficher tel quel)."""


@dataclass
class Quart:
    debut: str   # HH:MM
    fin: str     # HH:MM (après minuit : fin < début, compté le lendemain)
    pause: int = 0  # minutes non payées

    @property
    def heures(self) -> Decimal:
        d = datetime.strptime(self.debut, "%H:%M")
        f = datetime.strptime(self.fin, "%H:%M")
        if f <= d:
            f += timedelta(days=1)
        return (Decimal((f - d).total_seconds() - self.pause * 60) / 3600).quantize(Decimal("0.01"))

    def texte(self) -> str:
        return f"{self.debut}-{self.fin}" + (f" ({self.pause} min)" if self.pause else "")


def lire_heure(texte: str) -> str:
    """« 8 », « 8h », « 8:30 », « 08h30 » -> « 08:30 »."""
    t = texte.strip().lower().replace("h", ":").rstrip(":")
    if not t:
        raise ErreurPlanning("Heure manquante.")
    heures, _, minutes = t.partition(":")
    try:
        h, m = int(heures), int(minutes or 0)
    except ValueError:
        raise ErreurPlanning(f"Heure invalide : « {texte} » (ex. 8:30).") from None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ErreurPlanning(f"Heure invalide : « {texte} ».")
    return f"{h:02d}:{m:02d}"


def jours_du_mois(mois: str) -> list[date]:
    annee, m = (int(x) for x in mois.split("-"))
    return [date(annee, m, j) for j in range(1, calendar.monthrange(annee, m)[1] + 1)]


class Planning:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "planning.json"
        donnees = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else {}
        self.mois: dict = donnees.get("mois", {})
        self.publies: dict = donnees.get("publies", {})

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"mois": self.mois, "publies": self.publies}, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        provisoire.replace(self.chemin)

    def quart(self, mois: str, employe: str, jour: date) -> Quart | None:
        q = self.mois.get(mois, {}).get(employe, {}).get(jour.isoformat())
        return Quart(**q) if q else None

    def definir(self, employe: str, jours: list[date], quart: Quart | None) -> None:
        """Horaire de l'employé pour ces jours (None = repos) ; vérifié avant d'écrire."""
        if quart is not None:
            quart = Quart(lire_heure(quart.debut), lire_heure(quart.fin), int(quart.pause or 0))
            if quart.heures <= 0:
                raise ErreurPlanning("La pause est plus longue que le quart.")
        for jour in jours:
            mois = f"{jour:%Y-%m}"
            jours_employe = self.mois.setdefault(mois, {}).setdefault(employe, {})
            if quart is None:
                jours_employe.pop(jour.isoformat(), None)
            else:
                jours_employe[jour.isoformat()] = {"debut": quart.debut, "fin": quart.fin, "pause": quart.pause}
        self.enregistrer()

    def copier_mois(self, depuis: str, vers: str, employes: list[str]) -> int:
        """Reprend l'horaire de chaque jour de la semaine du mois `depuis` (1re occurrence de chaque jour de semaine)
        pour tout le mois `vers` ; renvoie le nombre de quarts créés."""
        n = 0
        for e in employes:
            source = self.mois.get(depuis, {}).get(e, {})
            par_jour_semaine = {}
            for texte, q in sorted(source.items()):
                par_jour_semaine.setdefault(date.fromisoformat(texte).weekday(), q)
            for jour in jours_du_mois(vers):
                q = par_jour_semaine.get(jour.weekday())
                if q:
                    self.mois.setdefault(vers, {}).setdefault(e, {})[jour.isoformat()] = dict(q)
                    n += 1
        self.enregistrer()
        return n

    def publier(self, mois: str) -> None:
        self.publies[mois] = datetime.now().isoformat(timespec="seconds")
        self.enregistrer()

    def heures(self, mois: str, employe: str) -> Decimal:
        return sum((Quart(**q).heures for q in self.mois.get(mois, {}).get(employe, {}).values()), Decimal(0))

    def horaire_employe(self, employe: str, depuis: date, jours: int = 35, publie_seulement: bool = True
                        ) -> list[tuple[date, Quart | None]]:
        """Horaire d'un employé de `depuis` sur `jours` jours (mois publiés seulement si demandé)."""
        resultat = []
        for i in range(jours):
            jour = depuis + timedelta(days=i)
            mois = f"{jour:%Y-%m}"
            if publie_seulement and mois not in self.publies:
                continue
            resultat.append((jour, self.quart(mois, employe, jour)))
        return resultat

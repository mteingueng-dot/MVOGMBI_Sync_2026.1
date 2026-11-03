"""Calendrier de paie (demande du propriétaire du 2026-10-30) : on renseigne la date de la première paie de l'année,
le reste se calcule : une paie tous les 14 jours jusqu'à la fin de l'année, chacune pour une période de 14 jours
terminée `delai` jours avant la paie (15 par défaut, comme les paies du marché : paie du 2026-02-02 pour la période
du 2026-01-05 au 2026-01-18).

Une année sans première paie saisie continue celle d'avant (14 jours après sa dernière paie) : le calendrier des
années à venir est donc toujours connu. Le calendrier donne aussi le premier jour des périodes de paie aux feuilles
de temps (`fenetre_pointage.reference`). Fichier : donnees/calendrier_paie.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

JOURS = 14
DELAI_DEFAUT = 15
ANNEES_MAX = 10  # recherche de la dernière année renseignée


@dataclass
class PaieCalendrier:
    numero: int
    jour: date    # date de la paie
    debut: date   # période de paie
    fin: date


class Calendrier:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "calendrier_paie.json"
        self.premieres: dict[str, str] = {}
        self.delai = DELAI_DEFAUT
        if self.chemin.exists():
            donnees = json.loads(self.chemin.read_text(encoding="utf-8"))
            self.premieres = dict(donnees.get("premieres", {}))
            self.delai = int(donnees.get("delai", DELAI_DEFAUT))

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"premieres": self.premieres, "delai": self.delai}, ensure_ascii=False,
                                         indent=1), encoding="utf-8")
        provisoire.replace(self.chemin)

    def definir(self, annee: int, jour: date, delai: int | None = None) -> None:
        if jour.year != annee:
            raise ValueError(f"La première paie de {annee} doit être datée de {annee}.")
        if delai is not None:
            if not 0 <= delai <= 60:
                raise ValueError("Le délai doit être de 0 à 60 jours.")
            self.delai = delai
        self.premieres[str(annee)] = jour.isoformat()

    def premiere(self, annee: int) -> date | None:
        """Première paie de l'année : saisie, sinon suite de l'année précédente (14 jours après sa dernière paie)."""
        if str(annee) in self.premieres:
            return date.fromisoformat(self.premieres[str(annee)])
        for avant in range(annee - 1, annee - 1 - ANNEES_MAX, -1):
            if str(avant) in self.premieres:
                jour = date.fromisoformat(self.premieres[str(avant)])
                while jour.year < annee:
                    jour += timedelta(days=JOURS)
                return jour
        return None

    def saisie(self, annee: int) -> bool:
        return str(annee) in self.premieres

    def paies(self, annee: int) -> list[PaieCalendrier]:
        jour = self.premiere(annee)
        liste = []
        while jour and jour.year == annee:
            fin = jour - timedelta(days=self.delai)
            liste.append(PaieCalendrier(len(liste) + 1, jour, fin - timedelta(days=JOURS - 1), fin))
            jour += timedelta(days=JOURS)
        return liste

    def reference(self, jour: date) -> date | None:
        """Premier jour d'une période de paie, pour les feuilles de temps ; None sans calendrier."""
        liste = self.paies(jour.year) or self.paies(jour.year + 1)
        return liste[0].debut if liste else None

    def paie_de_periode(self, debut: date) -> PaieCalendrier | None:
        """Paie qui règle la période commençant le `debut`."""
        for annee in (debut.year, debut.year + 1):
            for p in self.paies(annee):
                if p.debut == debut:
                    return p
        return None

    def prochaine(self, jour: date) -> PaieCalendrier | None:
        for annee in (jour.year, jour.year + 1):
            for p in self.paies(annee):
                if p.jour >= jour:
                    return p
        return None

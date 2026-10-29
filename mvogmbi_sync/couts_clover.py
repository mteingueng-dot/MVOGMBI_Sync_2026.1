"""Coûts Clover mis à jour à partir du CUMP des articles dans Sage (demande du propriétaire du 2026-10-28).

Le coût Sage remplace le coût Clover. La personne voit les deux coûts, coche les lignes à mettre à jour puis lance la
mise à jour. Jamais de valeur aberrante : un CUMP absent, nul, plus de 5 fois le prix de vente Clover
(`SEUIL_CUMP_DOUTEUX`, valeur de stock erronée dans Sage) ou moins de 5 % du prix ne peut pas être coché. Un CUMP égal
ou supérieur au prix de vente, ou un n° Sage relié à plusieurs articles Clover (formats différents), est proposé
décoché. Chaque coût écrit est noté dans `donnees/journal_couts_clover.csv`.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from .statistiques_clover import SEUIL_CUMP_DOUTEUX
from .cache_lectures import vide_apres

SEUIL_CUMP_BAS = Decimal("0.05")  # CUMP sous 5 % du prix de vente : aberrant
ECART_FORT = 3  # CUMP plus de 3 fois plus haut ou plus bas que le coût Clover : proposé décoché
CENT = Decimal(100)
A_METTRE_A_JOUR = "À mettre à jour"
A_VERIFIER = "À vérifier"
ABERRANT = "Valeur aberrante"
SANS_CUMP = "Aucun coût dans Sage"
ENTETE_JOURNAL = ["Date", "ID Clover", "Article Clover", "N° Sage", "Coût Clover avant", "Coût Sage (CUMP)"]


@dataclass
class PropositionCout:
    id_clover: str
    nom: str
    numero_sage: str
    prix: Decimal | None        # prix de vente Clover
    cout_clover: Decimal | None
    cump: Decimal | None        # coût moyen Sage (CUMP), arrondi au cent
    etat: str = A_METTRE_A_JOUR
    note: str = ""

    @property
    def permis(self) -> bool:
        """Peut être cochée (jamais une valeur aberrante ni un coût absent)."""
        return self.etat in (A_METTRE_A_JOUR, A_VERIFIER)

    @property
    def cochee_par_defaut(self) -> bool:
        return self.etat == A_METTRE_A_JOUR


def _cents(valeur) -> Decimal | None:
    return None if valeur is None else (Decimal(int(valeur)) / CENT)


def proposer(articles_clover: list[dict], liens: dict[str, str], couts: dict) -> tuple[list[PropositionCout], int]:
    """Articles Clover reliés à Sage dont le coût diffère du CUMP Sage. `liens` : ID Clover -> n° Sage ; `couts` :
    n° Sage -> CoutSage (couts_sage). Renvoie (propositions, nombre d'articles déjà à jour)."""
    par_numero = Counter(liens.values())
    propositions, a_jour = [], 0
    for a in articles_clover:
        numero = liens.get(a.get("id"))
        if not numero:
            continue
        prix, cout_clover = _cents(a.get("price")), _cents(a.get("cost"))
        cump = couts[numero].cump if numero in couts else None
        cump = cump.quantize(Decimal("0.01"), ROUND_HALF_UP) if cump is not None else None
        p = PropositionCout(a["id"], (a.get("name") or "").strip(), numero, prix, cout_clover, cump)
        if cump is None or cump <= 0:
            p.etat = SANS_CUMP
        elif cout_clover is not None and cump == cout_clover:
            a_jour += 1
            continue
        elif prix and cump > SEUIL_CUMP_DOUTEUX * prix:
            p.etat, p.note = ABERRANT, f"coût Sage plus de {SEUIL_CUMP_DOUTEUX} fois le prix de vente"
        elif prix and cump < SEUIL_CUMP_BAS * prix:
            p.etat, p.note = ABERRANT, "coût Sage sous 5 % du prix de vente"
        elif prix and cump >= prix:
            p.etat, p.note = A_VERIFIER, "coût Sage égal ou supérieur au prix de vente"
        elif cout_clover and (cump > ECART_FORT * cout_clover or cump * ECART_FORT < cout_clover):
            p.etat, p.note = A_VERIFIER, f"plus de {ECART_FORT} fois d'écart avec le coût Clover"
        elif par_numero[numero] > 1:
            p.etat, p.note = A_VERIFIER, f"n° Sage relié à {par_numero[numero]} articles Clover (formats ?)"
        propositions.append(p)
    ordre = {A_METTRE_A_JOUR: 0, A_VERIFIER: 1, ABERRANT: 2, SANS_CUMP: 3}
    propositions.sort(key=lambda p: (ordre[p.etat], p.nom.casefold()))
    return propositions, a_jour


def lire(racine: Path, config_toml: dict) -> tuple[list[PropositionCout], int]:
    """Articles Clover (coût, prix) et CUMP Sage relus maintenant (l'application ouvre Sage s'il est fermé)."""
    from .api_clover import ClientClover
    from .__main__ import charger_config
    from .couts_sage import charger, correspondance

    client = ClientClover(charger_config(Path(racine) / "config.toml"))
    couts = charger(racine, config_toml, forcer=True)
    from .cache_lectures import inventaire_clover
    del client
    return proposer(inventaire_clover(racine), correspondance(racine), couts)


@vide_apres  # mémoire des lectures vidée après une écriture
def appliquer(racine: Path, propositions: list[PropositionCout], progression=None) -> list[tuple[PropositionCout, str]]:
    """Écrit le CUMP Sage comme coût Clover des lignes choisies ; renvoie [(ligne, erreur ou "")]."""
    from .api_clover import ClientClover
    from .__main__ import charger_config

    client = ClientClover(charger_config(Path(racine) / "config.toml"))
    journal = Path(racine) / "donnees" / "journal_couts_clover.csv"
    journal.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not journal.exists()
    resultats = []
    with journal.open("a", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.writer(f, delimiter=";")
        if nouveau:
            ecrivain.writerow(ENTETE_JOURNAL)
        for i, p in enumerate(propositions, 1):
            erreur = ""
            if not p.permis:
                erreur = p.etat
            else:
                try:
                    client.regler_cout(p.id_clover, p.cump)
                    ecrivain.writerow([datetime.now().isoformat(timespec="seconds"), p.id_clover, p.nom,
                                       p.numero_sage, "" if p.cout_clover is None else p.cout_clover, p.cump])
                    f.flush()
                except Exception as exc:
                    erreur = str(exc)
            resultats.append((p, erreur))
            if progression:
                progression(i, len(propositions))
    return resultats

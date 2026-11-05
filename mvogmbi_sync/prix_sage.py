"""Prix de vente de Sage mis à jour depuis les prix de vente de Clover (demande du propriétaire du 2026-11-04 :
« ajoute une fonction dans article pour mettre à jour les prix de vente dans Sage à partir des prix de vente de
Clover »).

Articles Clover reliés à un n° Sage (correspondance « Confirmé » ou « Automatique ») ; prix Clover (cents) comparé
au prix de vente régulier de Sage (tinvprc, liste de prix 1 « Régulier »). États :
- « Différent » : coché, le prix Sage prendra le prix Clover ;
- « Identique » : rien à faire ;
- « Plusieurs prix Clover » : plusieurs articles Clover de prix différents sur le même n° Sage (formats) : décoché ;
- « Prix variable » / « Sans prix Clover » : non cochable (prix tapé à la caisse ou absent) ;
- « Absent de Sage » : n° Sage relié introuvable : non cochable.

L'écriture passe par la fiche « Enregistrements des stocks & services » de Sage (`robot_prix_sage`, commande
interne `prix-sage-bureau`), vérifiée dans tinvprc ; journal `donnees/journal_prix_sage.csv`.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

DIFFERENT, IDENTIQUE, PLUSIEURS, VARIABLE, SANS_PRIX, ABSENT = (
    "Différent", "Identique", "Plusieurs prix Clover", "Prix variable", "Sans prix Clover", "Absent de Sage")
LISTE_REGULIERE = 1
JOURNAL = "journal_prix_sage.csv"


@dataclass
class LignePrixSage:
    numero_sage: str
    description_sage: str
    articles_clover: list[str]
    prix_clover: Decimal | None
    prix_sage: Decimal | None
    etat: str
    note: str = ""
    ids_clover: list[str] = field(default_factory=list)

    @property
    def permis(self) -> bool:
        return self.etat in (DIFFERENT, PLUSIEURS, IDENTIQUE) and self.prix_clover is not None

    @property
    def cochee_par_defaut(self) -> bool:
        return self.etat == DIFFERENT

    @property
    def ecart(self) -> Decimal | None:
        if self.prix_clover is None or self.prix_sage is None:
            return None
        return self.prix_clover - self.prix_sage


def prix_sage(base) -> dict[str, tuple[str, Decimal]]:
    """N° Sage -> (description, prix de vente régulier) des articles actifs."""
    lignes = base.requete(
        "SELECT TRIM(i.sPartCode) n, TRIM(i.sName) d, p.dPrice p FROM tinvent i LEFT JOIN tinvprc p "
        "ON p.lInventId = i.lId AND p.lPrcListId = %s AND p.lCurrncyId = 1 WHERE i.bInactive = 0",
        (LISTE_REGULIERE,))
    return {r["n"]: (r["d"] or "", Decimal(str(r["p"] or 0)).quantize(Decimal("0.01"))) for r in lignes}


def analyser(articles: list[dict], liens: dict[str, str], sage: dict) -> list[LignePrixSage]:
    """`articles` : catalogue Clover ; `liens` : ID Clover -> n° Sage ; `sage` : n° -> (description, prix)."""
    par_numero: dict[str, list[dict]] = defaultdict(list)
    for a in articles:
        numero = liens.get(a.get("id", ""))
        if numero:
            par_numero[numero].append(a)
    lignes = []
    for numero, groupe in sorted(par_numero.items()):
        noms = [a.get("name", "") for a in groupe]
        ids = [a.get("id", "") for a in groupe]
        description, prix_s = sage.get(numero, ("", None))
        variables = [a for a in groupe if a.get("priceType") == "VARIABLE"]
        prix = sorted({Decimal(int(a.get("price") or 0)) / 100 for a in groupe if a.get("priceType") != "VARIABLE"
                       and a.get("price")})
        if numero not in sage:
            etat, prix_c, note = ABSENT, (prix[0] if prix else None), "n° Sage relié introuvable (ou inactif)"
        elif variables and not prix:
            etat, prix_c, note = VARIABLE, None, "prix tapé à la caisse"
        elif not prix:
            etat, prix_c, note = SANS_PRIX, None, ""
        elif len(prix) > 1:
            etat, prix_c = PLUSIEURS, prix[-1]
            note = "prix Clover : " + " / ".join(f"{p:.2f}".replace(".", ",") for p in prix) + " (le plus élevé proposé)"
        else:
            prix_c, note = prix[0], ""
            etat = IDENTIQUE if prix_s is not None and prix_s == prix_c else DIFFERENT
        lignes.append(LignePrixSage(numero, description, noms, prix_c, prix_s, etat, note, ids))
    ordre = {DIFFERENT: 0, PLUSIEURS: 1, ABSENT: 2, VARIABLE: 3, SANS_PRIX: 4, IDENTIQUE: 5}
    return sorted(lignes, key=lambda l: (ordre[l.etat], l.numero_sage))


def lire(racine: Path, config_toml: dict, ouvrir: bool = True) -> tuple[list[LignePrixSage], str]:
    """`ouvrir` faux (application web) : Sage n'est jamais ouvert pour une simple lecture."""
    from .__main__ import lire_sage
    from .cache_lectures import inventaire_clover
    from .couts_sage import correspondance

    articles = inventaire_clover(racine)
    liens = correspondance(racine)
    sage = lire_sage(config_toml, prix_sage, ouvrir=ouvrir)
    lignes = analyser(articles, liens, sage)
    differents = sum(1 for l in lignes if l.etat == DIFFERENT)
    identiques = sum(1 for l in lignes if l.etat == IDENTIQUE)
    return lignes, (f"{len(lignes)} article(s) Sage reliés à Clover : {differents} au prix différent (cochés), "
                    f"{identiques} déjà au prix de Clover.")


def noter(racine: Path, ligne: LignePrixSage, resultat: str) -> None:
    chemin = Path(racine) / "donnees" / JOURNAL
    nouveau = not chemin.exists()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if nouveau:
            w.writerow(["Moment", "N° Sage", "Description", "Ancien prix Sage", "Prix Clover", "Résultat"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), ligne.numero_sage, ligne.description_sage,
                    ligne.prix_sage, ligne.prix_clover, resultat])


def appliquer(racine: Path, config_toml: dict, lignes: list[LignePrixSage], progression=None) -> list[tuple]:
    """Prix des lignes écrits dans Sage (l'application ouvre Sage elle-même, Sage fermé) ; renvoie
    [(ligne, erreur ou « »)]."""
    from .robot_prix_sage import DemandePrix, appliquer as dans_sage

    demandes = [DemandePrix(l.numero_sage, str(l.prix_clover)) for l in lignes if l.prix_clover is not None]
    resultats = {r["numero"]: r for r in dans_sage(racine, config_toml, demandes)}
    sortie = []
    for l in lignes:
        r = resultats.get(l.numero_sage, {"fait": False, "messages": ["non traité"]})
        erreur = "" if r.get("fait") else " ; ".join(r.get("messages") or ["non fait"])
        noter(racine, l, erreur or "fait")
        sortie.append((l, erreur))
        if progression:
            progression(f"{l.numero_sage} : {'fait' if not erreur else erreur}")
    from .cache_lectures import vider

    vider()
    return sortie

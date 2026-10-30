"""Journal des opérations (piste de vérification) — demande du propriétaire du 2026-10-29 : réunit en un seul
tableau ce que les journaux et registres de l'application notent déjà (imports, prix, coûts, stock, articles créés,
connexions, bulletins envoyés, paies, pertes, comptages de caisse, documents, sauvegardes, traitement de nuit), avec
la date, la source, la personne quand elle est connue et le détail. Lecture seule."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

DATE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T]?(\d{2}:\d{2}(:\d{2})?)?")
JOURNAUX_CSV = {
    "journal_imports.csv": "Factures de vente importées",
    "journal_prix_clover.csv": "Prix Clover changés",
    "journal_couts_clover.csv": "Coûts Clover changés",
    "journal_stock_clover.csv": "Stock Clover (achats)",
    "journal_articles_crees.csv": "Articles créés",
    "journal_ugs_effacees.csv": "UGS effacées",
    "journal_bulletins_envoyes.csv": "Bulletins de paie envoyés",
}
PERSONNE = ("par", "auteur", "utilisateur", "saisi par", "déclarée par", "compté par")


@dataclass
class Operation:
    quand: str
    source: str
    personne: str
    detail: str


def _quand(texte: str) -> str:
    m = DATE.search(texte or "")
    return f"{m.group(1)} {m.group(2) or ''}".strip() if m else ""


def _csv(chemin: Path, source: str) -> list[Operation]:
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        lecteur = csv.reader(f, delimiter=";")
        entete = next(lecteur, [])
        i_personne = next((i for i, x in enumerate(entete) if x.strip().lower() in PERSONNE), None)
        operations = []
        for ligne in lecteur:
            if not ligne:
                continue
            quand = next((_quand(x) for x in ligne if _quand(x)), "")
            detail = " ; ".join(f"{e} : {v}" for e, v in zip(entete, ligne) if v and _quand(v) != v.strip()
                                and (i_personne is None or e != entete[i_personne]))
            operations.append(Operation(quand, source, ligne[i_personne] if i_personne is not None and
                                        i_personne < len(ligne) else "", detail))
    return operations


def _log(chemin: Path, source: str) -> list[Operation]:
    operations, quand = [], ""
    for ligne in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
        q = _quand(ligne)
        if q:
            quand = q
        texte = ligne.strip(" =")
        if texte and (q or source == "Connexions"):
            operations.append(Operation(quand, source, "", texte[:300]))
    return operations


def _json(chemin: Path) -> object:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def lire(racine: Path) -> list[Operation]:
    donnees = Path(racine) / "donnees"
    ops: list[Operation] = []
    for nom, source in JOURNAUX_CSV.items():
        if (donnees / nom).exists():
            ops += _csv(donnees / nom, source)
    for nom, source in (("journal_connexions.log", "Connexions"), ("journal_automatique.log", "Traitement de nuit")):
        if (donnees / nom).exists():
            ops += [o for o in _log(donnees / nom, source) if source == "Connexions" or "=====" not in o.detail]
    for p in _json(donnees / "pertes.json") or []:
        ops.append(Operation(_quand(p.get("cree", "")), "Pertes", p.get("auteur", ""),
                             f"{p.get('numero')} {p.get('motif')} — {len(p.get('lignes', []))} ligne(s)"))
    caisse = _json(donnees / "caisse.json") or {}
    for jour, c in (caisse.get("comptages") or {}).items():
        ops.append(Operation(_quand(c.get("le", "")), "Comptage de caisse", c.get("par", ""),
                             f"journée {jour} : compté {c.get('compte')} $, fond {c.get('fond')} $"))
    for p in _json(donnees / "paies_sage.json") or []:
        ops.append(Operation(_quand(p.get("le", "")), "Paies traitées dans Sage", "",
                             f"{p.get('nom_sage')} {p.get('debut')}→{p.get('fin')} : "
                             f"{'faite' if p.get('fait') else 'NON faite'}, net {p.get('net')}"))
    docs = _json(donnees / "documents.json")
    for d in (docs.get("documents", []) if isinstance(docs, dict) else docs or []):
        ops.append(Operation(_quand(d.get("cree", "")), "Documents saisis", d.get("auteur", ""),
                             f"{d.get('numero')} {d.get('genre')} — {d.get('etat')}"))
    etat = _json(donnees / "derniere_sauvegarde.json") or {}
    if etat:
        ops.append(Operation(_quand(etat.get("quand", "")), "Sauvegarde", "",
                             f"{'réussie' if etat.get('ok') else 'ÉCHEC'} — {Path(etat.get('fichier', '')).name}"))
    return sorted(ops, key=lambda o: o.quand, reverse=True)


def filtrer(ops: list[Operation], du: str = "", au: str = "", source: str = "", texte: str = "") -> list[Operation]:
    texte = texte.casefold().strip()
    return [o for o in ops if (not du or o.quand[:10] >= du) and (not au or o.quand[:10] <= au)
            and (not source or o.source == source)
            and (not texte or texte in f"{o.personne} {o.detail} {o.source}".casefold())]

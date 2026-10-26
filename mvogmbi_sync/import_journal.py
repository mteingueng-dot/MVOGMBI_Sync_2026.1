"""Écritures de journal général importées dans Sage 50 : mouvements du relevé Desjardins absents de Sage.

Fichier .IMP (même enveloppe <Version> que les factures ; bloc <GenJour> au format du journal général de Sage :
date mm-jj-aaaa, source, commentaire, puis une ligne « compte, montant » par compte, débit positif, crédit négatif) :
    <GenJour>
    "02-27-2026","Relevé 2026-02-27","FIX Frais fixes d'utilisation"
    "1055","-5.95"
    "5450","5.95"
    </GenJour>
Un dépôt à la banque débite le 1055 ; un retrait le crédite. Contrôle après l'import : l'écriture (même source, même
date, même montant au 1055) existe dans tjourent / tjentact. Une écriture déjà présente n'est jamais réimportée.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from .import_achats import _nombre, _texte, sage_ouvert
from .rapprochement import COMPTE_BANQUE, SAISI, MouvementBanque

LONGUEUR_SOURCE, LONGUEUR_COMMENTAIRE = 20, 39


def compte_sage(numero: str) -> int:
    """« 5450 » -> 54500000 (numéro interne de Sage sur 8 chiffres)."""
    return int(str(numero).strip().ljust(8, "0"))


def source(m: MouvementBanque) -> str:
    return f"Relevé {m.date}"[:LONGUEUR_SOURCE]


def bloc_journal(m: MouvementBanque, compte_banque: str = "1055") -> list[str]:
    jour = date.fromisoformat(m.date)
    return ["<GenJour>",
            ",".join([_texte(jour.strftime("%m-%d-%Y")), _texte(source(m)), _texte(m.description[:LONGUEUR_COMMENTAIRE])]),
            f"{_texte(compte_banque)},{_nombre(m.montant, 2)}",
            f"{_texte(m.compte)},{_nombre(-m.montant, 2)}",
            "</GenJour>"]


def ecrire_imp_journal(mouvements: list[MouvementBanque], chemin: Path, version: str = "12001", pays: str = "1",
                       encodage: str = "cp1252") -> Path:
    lignes = ["<Version>", f"{_texte(version)},{_texte(pays)}", "</Version>", ""]
    for m in mouvements:
        lignes += bloc_journal(m)
    lignes.append("")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\r\n".join(lignes), encoding=encodage, errors="replace", newline="")
    return chemin


def ecriture_presente(base, m: MouvementBanque) -> int | None:
    """N° de l'écriture déjà dans Sage pour ce mouvement (même source, date et montant au compte de banque)."""
    lignes = base.requete(
        "SELECT e.lId FROM tjourent e JOIN tjentact a ON a.lJEntId = e.lId WHERE TRIM(e.sSource) = %s AND "
        "e.dtJourDate = %s AND a.lAcctId = %s AND ROUND(a.dAmount, 2) = %s ORDER BY e.lId DESC LIMIT 1",
        (source(m), m.date, COMPTE_BANQUE, str(m.montant)))
    return lignes[0]["lId"] if lignes else None


def comptes_valides(base, mouvements: list[MouvementBanque]) -> dict[str, str]:
    """Problème par compte choisi : inexistant, inactif, ou compte de banque lui-même."""
    problemes = {}
    for numero in {m.compte for m in mouvements}:
        if not numero.isdigit() or compte_sage(numero) == COMPTE_BANQUE:
            problemes[numero] = "compte invalide"
            continue
        lignes = base.requete("SELECT bInactive FROM taccount WHERE lId = %s", (compte_sage(numero),))
        if not lignes:
            problemes[numero] = "compte absent de Sage"
        elif lignes[0]["bInactive"]:
            problemes[numero] = "compte inactif dans Sage"
    return problemes


def importer_journal(racine: Path, config_toml: dict, mouvements: list[MouvementBanque], journal=print) -> dict[str, str]:
    """Contrôle, écrit le .IMP et l'importe (Sage fermé), puis vérifie chaque écriture ; les mouvements présents dans
    Sage passent à « Saisi dans Sage ». Renvoie {clé du mouvement: résultat}."""
    from . import coffre
    from .__main__ import executable_import, lire_sage, ouvrir_base_sage
    from .sage_auto import executer

    c = config_toml.get("sage_import", {})
    fichier_sai = Path(c.get("fichier_entreprise", ""))
    exe = executable_import()
    if not fichier_sai.is_file() or not exe:
        raise RuntimeError("Fichier d'entreprise Sage ou outil d'import introuvable (page Sage 50).")
    if sage_ouvert():
        raise RuntimeError("Sage est ouvert : fermez-le avant l'import.")
    problemes, deja = lire_sage(config_toml, lambda base: (
        comptes_valides(base, mouvements), {m.cle: ecriture_presente(base, m) for m in mouvements}), str(fichier_sai))
    resultats, a_importer = {}, []
    for m in mouvements:
        if deja.get(m.cle):
            m.etat, m.sage = SAISI, [deja[m.cle]]
            resultats[m.cle] = f"déjà dans Sage (écriture n° {deja[m.cle]})"
        elif m.compte in problemes:
            resultats[m.cle] = f"non saisi : compte {m.compte} — {problemes[m.compte]}"
        else:
            a_importer.append(m)
    if a_importer:
        chemin = ecrire_imp_journal(a_importer, Path(racine) / "sortie" / "journal" /
                                    f"Banque_{datetime.now():%Y%m%d_%H%M%S}.IMP",
                                    str(c.get("version", "12001")), str(c.get("pays", "1")))
        journal(f"Import de {len(a_importer)} écriture(s) dans {fichier_sai.name}…")
        presentes: dict[str, int | None] = {}

        def verifier(_resume: str = "") -> None:
            import time
            for _ in range(10):
                try:
                    with ouvrir_base_sage(config_toml, fichier_sai) as base:
                        for m in a_importer:
                            presentes[m.cle] = ecriture_presente(base, m)
                    return
                except Exception:
                    time.sleep(1)

        resultat = executer(exe, chemin, fichier_sai, coffre.lire(coffre.SAGE_IMPORT), pendant_resume=verifier,
                            delai=int(config_toml.get("automatique", {}).get("delai_import", 3600)))
        for m in a_importer:
            if presentes.get(m.cle):
                m.etat, m.sage = SAISI, [presentes[m.cle]]
                resultats[m.cle] = f"saisi (écriture n° {presentes[m.cle]})"
            else:
                resultats[m.cle] = "ÉCHEC : absente de Sage après l'import" + (
                    " — " + " ; ".join(resultat.erreurs) if resultat.erreurs else "")
    for m in mouvements:
        journal(f"{m.date} {m.montant} $ {m.description[:40]} -> compte {m.compte} : {resultats[m.cle]}")
    return resultats


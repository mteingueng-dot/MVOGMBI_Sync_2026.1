"""Ligne de commande.

Exemples :
    python -m mvogmbi_sync rapport --periode jour --date 2026-01-15
    python -m mvogmbi_sync rapport --periode semaine --date 2026-01-15 --par-jour
    python -m mvogmbi_sync rapport --periode mois --date 2026-01-01 --export "Ventes Janvier.xlsx"
    python -m mvogmbi_sync verifier
    python -m mvogmbi_sync comparer --date 2026-10-23 --export "Ventes 23 octobre.xlsx"
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

from .models import RapportVentes
from .periodes import TypePeriode, bornes, jours
from .sortie_excel import ecrire_rapports

RACINE = Path(__file__).resolve().parent.parent


def charger_config(chemin: Path):
    from .api_clover import ConfigClover

    if not chemin.exists():
        sys.exit(f"Fichier de configuration introuvable : {chemin}\n"
                 "Copiez config.example.toml en config.toml et complétez-le.")
    donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
    clover = donnees.get("clover", {})
    if not clover.get("merchant_id") or not clover.get("api_token"):
        sys.exit(f"Complétez merchant_id et api_token dans {chemin} avant de continuer.")
    return ConfigClover(
        merchant_id=clover.get("merchant_id", ""),
        api_token=clover.get("api_token", ""),
        base_url=clover.get("base_url", "https://api.clover.com"),
        fuseau_horaire=donnees.get("general", {}).get("fuseau_horaire", "America/Toronto"),
    )


def afficher(rapport: RapportVentes) -> None:
    print(f"\n{rapport.debut} → {rapport.fin}  ({rapport.source})")
    print(f"  Articles distincts : {len(rapport.lignes)}")
    print(f"  Ventes brutes      : {rapport.total_brut:>12,.2f} $")
    print(f"  Rabais             : {rapport.total_rabais:>12,.2f} $")
    print(f"  Remboursements     : {rapport.total_remboursements:>12,.2f} $")
    print(f"  Ventes nettes      : {rapport.total_net:>12,.2f} $")


def commande_rapport(args: argparse.Namespace) -> None:
    debut, fin = bornes(TypePeriode(args.periode), date.fromisoformat(args.date))

    if args.export:
        if args.par_jour:
            sys.exit("--par-jour n'est pas possible avec un export : le fichier Clover ne contient pas les dates.")
        from .export_clover import lire_export
        rapports = [lire_export(Path(args.export), debut, fin)]
    else:
        from .api_clover import ClientClover
        client = ClientClover(charger_config(Path(args.config)))
        periodes = [(j, j) for j in jours(debut, fin)] if args.par_jour else [(debut, fin)]
        rapports = [client.rapport(d, f) for d, f in periodes]

    for rapport in rapports:
        afficher(rapport)
    sortie = RACINE / "sortie" / f"ventes_{args.periode}_{debut}_{fin}.xlsx"
    print(f"\nRapport Excel : {ecrire_rapports(rapports, sortie)}")


def commande_verifier(args: argparse.Namespace) -> None:
    import requests

    from .api_clover import ClientClover

    client = ClientClover(charger_config(Path(args.config)))
    try:
        infos = client.marchand()
    except requests.HTTPError as exc:
        code = exc.response.status_code
        raison = {401: "jeton refusé (invalide ou expiré)",
                  403: "droits insuffisants sur le jeton",
                  404: "identifiant marchand introuvable"}.get(code, "erreur inattendue")
        sys.exit(f"Échec de la connexion à Clover : {code} — {raison}.")
    print(f"Connexion à Clover réussie : {infos.get('name', '(nom inconnu)')}")
    hier = date.today() - timedelta(days=1)
    nombre = sum(1 for _ in client.commandes(hier, hier))
    print(f"Commandes trouvées pour hier ({hier}) : {nombre}")


def commande_comparer(args: argparse.Namespace) -> None:
    from .api_clover import ClientClover
    from .comparaison import comparer, ecrire_comparaison
    from .export_clover import lire_export

    jour = date.fromisoformat(args.date)
    export = lire_export(Path(args.export), jour, jour)
    api = ClientClover(charger_config(Path(args.config))).rapport(jour, jour)
    afficher(export)
    afficher(api)
    ecarts = comparer(export, api)
    sortie = ecrire_comparaison(ecarts, RACINE / "sortie" / f"comparaison_{jour}.xlsx")
    if ecarts:
        print(f"\n{len(ecarts)} article(s) en écart. Détail : {sortie}")
    else:
        print(f"\nAucun écart : l'API et l'export concordent au cent près. Détail : {sortie}")


def commande_correspondance(args: argparse.Namespace) -> None:
    from decimal import Decimal

    from .api_clover import SANS_CATEGORIE, ClientClover
    from .articles_sage import lire_articles_sage
    from .correspondance import (AUCUN, AUTOMATIQUE, A_CONFIRMER, CONFIRME, ArticleClover,
                                 ecrire_correspondance, lire_confirmes, rapprocher)

    config_toml = tomllib.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
    chemin_sage = Path(args.sage or config_toml.get("sage", {}).get("articles", "donnees/Article.txt"))
    if not chemin_sage.is_absolute():
        chemin_sage = RACINE / chemin_sage
    if not chemin_sage.is_file():
        sys.exit("Liste des articles Sage introuvable : indiquez-la avec --sage ou dans config.toml ([sage] articles).")
    sage = lire_articles_sage(chemin_sage)
    # Un export abîmé remplace les lettres accentuées par des espaces (« Coupé » -> « Coup ») :
    # on vérifie la présence de vraies lettres accentuées dans le fichier brut.
    accents = sum(chemin_sage.read_text(encoding="cp1252").count(c) for c in "éèàçêô")
    if len(sage) > 100 and accents == 0:
        sys.exit(f"La liste Sage {chemin_sage} ne contient aucun accent : l'export semble abîmé "
                 "(« Coupé » devient « Coup »). Réexportez la liste depuis Sage, puis relancez la commande.")

    client = ClientClover(charger_config(Path(args.config)))
    print("Lecture du catalogue Clover…")
    catalogue = client.articles()
    print("Lecture des ventes des 30 derniers jours (pour trier par importance)…")
    fin = date.today() - timedelta(days=1)
    ventes: dict[str, Decimal] = {}
    for ligne in client.rapport(fin - timedelta(days=29), fin).lignes:
        ventes[ligne.nom] = ventes.get(ligne.nom, Decimal("0")) + ligne.ventes_nettes

    clover = [
        ArticleClover(
            id=a["id"], nom=(a.get("name") or "").strip(),
            categorie=(((a.get("categories") or {}).get("elements") or [{}])[0]).get("name", SANS_CATEGORIE),
            code=(a.get("code") or "").strip(), ventes_30j=ventes.get((a.get("name") or "").strip(), Decimal("0")),
        )
        for a in catalogue
    ]
    chemin = Path(args.fichier)
    confirmes = lire_confirmes(chemin)
    if chemin.exists():  # copie de sécurité du fichier validé avant de le régénérer
        import shutil
        from datetime import datetime
        copie = chemin.parent / "sauvegardes" / f"{chemin.stem}_{datetime.now():%Y%m%d-%H%M%S}{chemin.suffix}"
        copie.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(chemin, copie)
        print(f"Copie de sécurité : {copie}")
    resultat = rapprocher(clover, sage, confirmes)
    try:
        ecrire_correspondance(resultat, chemin)
    except PermissionError:
        sys.exit(f"Impossible d'enregistrer {chemin.name} : fermez-le dans Excel, puis relancez la commande.")

    compte = {s: sum(1 for c in resultat if c.statut == s) for s in (CONFIRME, AUTOMATIQUE, A_CONFIRMER, AUCUN)}
    vendus = [c for c in resultat if c.ventes_30j]
    print(f"\nArticles Sage lus : {len(sage)} — articles Clover : {len(clover)}")
    for statut, nombre in compte.items():
        print(f"  {statut:<12}: {nombre:>5}   (dont vendus ces 30 jours : "
              f"{sum(1 for c in vendus if c.statut == statut)})")
    print(f"\nFichier à vérifier : {chemin}")


def main(argv: list[str] | None = None) -> None:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8", errors="replace")
    parseur = argparse.ArgumentParser(prog="mvogmbi_sync", description="Synchronisation Clover → Sage 50")
    sous = parseur.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("rapport", help="Cumul des ventes par article pour un jour, une semaine ou un mois")
    p.add_argument("--periode", choices=[t.value for t in TypePeriode], default="jour")
    p.add_argument("--date", default=date.today().isoformat(),
                   help="Un jour compris dans la période (AAAA-MM-JJ). Par défaut : aujourd'hui.")
    p.add_argument("--par-jour", action="store_true", help="Un cumul séparé pour chaque jour de la période")
    p.add_argument("--export", help="Lire un export Excel Clover au lieu de l'API")
    p.add_argument("--config", default=str(RACINE / "config.toml"))
    p.set_defaults(fonction=commande_rapport)

    p = sous.add_parser("verifier", help="Vérifier la connexion à Clover (config.toml)")
    p.add_argument("--config", default=str(RACINE / "config.toml"))
    p.set_defaults(fonction=commande_verifier)

    p = sous.add_parser("comparer", help="Comparer l'API Clover avec un export journalier de la même date")
    p.add_argument("--date", required=True, help="Jour de l'export (AAAA-MM-JJ)")
    p.add_argument("--export", required=True, help="Export Excel Clover « Ventes d'articles » de ce jour")
    p.add_argument("--config", default=str(RACINE / "config.toml"))
    p.set_defaults(fonction=commande_comparer)

    p = sous.add_parser("correspondance", help="Créer ou mettre à jour la correspondance articles Clover -> Sage")
    p.add_argument("--sage", help="Liste des articles exportée de Sage (ex. E:\\Article.txt)")
    p.add_argument("--fichier", default=str(RACINE / "donnees" / "correspondance_articles.xlsx"))
    p.add_argument("--config", default=str(RACINE / "config.toml"))
    p.set_defaults(fonction=commande_correspondance)

    args = parseur.parse_args(argv)
    args.fonction(args)


if __name__ == "__main__":
    main()

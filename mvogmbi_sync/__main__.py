"""Ligne de commande.

Exemples :
    python -m mvogmbi_sync rapport --periode jour --date 2026-01-15
    python -m mvogmbi_sync rapport --periode semaine --date 2026-01-15 --par-jour
    python -m mvogmbi_sync rapport --periode mois --date 2026-01-01 --export "Ventes Janvier.xlsx"
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import date
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


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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

    args = parseur.parse_args(argv)
    args.fonction(args)


if __name__ == "__main__":
    main()

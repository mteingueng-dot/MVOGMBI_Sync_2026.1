"""Dépôts (sites) du marché (demande du propriétaire du 2026-11-05 : « ajoute la sélection des dépôts dans les
factures client / fournisseur avec la gestion de plusieurs sites ; l'import des factures se fait dans les dépôts
respectifs ; plusieurs cédules pour le nombre de dépôts, chaque employé affecté à un dépôt ; dans les états, tous les
dépôts à la fois ou un dépôt, avec « sélectionner tout »).

Choix du propriétaire du même jour :
- un dépôt = un emplacement d'inventaire de Sage (tinvloc) ; il a un ou plusieurs points de vente Clover
  (`points_vente.depot_sage`), ou aucun (entrepôt, réserve : [sage] depots_sans_clover = "Entrepôt; Réserve") ;
- Sage n'a pas d'emplacement dans son fichier d'import : la facture s'importe dans « Emplacement par défaut », puis
  l'application fait aussitôt le transfert entre emplacements (`apres_import`, robot_transferts déjà validé ; aucune
  écriture comptable de plus). Vente / retour : du dépôt vers l'emplacement par défaut ; achat : de l'emplacement
  par défaut vers le dépôt. Source du transfert « DP <n° de facture> » : jamais fait deux fois (titrec) ;
- un employé a un dépôt principal (`paie_temps.Employe.depot`) et peut être planifié un jour dans un autre
  (`planning.Quart.depot`) ;
- états : filtre « Dépôt » à choix multiples, « Tout sélectionner » = tous les dépôts (`TOUS`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from .points_vente import DEPOT_DEFAUT, points_de_vente

TOUS = "Tous les dépôts"
PREFIXE_TRANSFERT = "DP "
LONGUEUR_REFERENCE = 16  # source Sage de 20 caractères, « -2 » ajouté aux lots suivants


@dataclass
class Depot:
    nom: str                                   # emplacement d'inventaire de Sage
    points_vente: list[str] = field(default_factory=list)  # codes des points de vente Clover de ce dépôt

    @property
    def par_defaut(self) -> bool:
        return est_defaut(self.nom)

    @property
    def avec_clover(self) -> bool:
        return bool(self.points_vente)

    @property
    def libelle(self) -> str:
        return self.nom


def est_defaut(nom: str | None) -> bool:
    return (nom or "").strip().lower() in ("", DEPOT_DEFAUT.lower(), "primary location for all")


def sans_clover(config_toml: dict) -> list[str]:
    valeur = config_toml.get("sage", {}).get("depots_sans_clover", "")
    liste = valeur if isinstance(valeur, list) else str(valeur).split(";")
    return [str(v).strip() for v in liste if str(v).strip()]


def liste(config_toml: dict) -> list[Depot]:
    """Dépôts des points de vente actifs (dans l'ordre), puis dépôts sans Clover ; « Emplacement par défaut »
    toujours présent."""
    par_nom: dict[str, Depot] = {}
    for p in points_de_vente(config_toml, actifs=True):
        nom = DEPOT_DEFAUT if est_defaut(p.depot_sage) else p.depot_sage.strip()
        par_nom.setdefault(nom.lower(), Depot(nom)).points_vente.append(p.code)
    par_nom.setdefault(DEPOT_DEFAUT.lower(), Depot(DEPOT_DEFAUT))
    for nom in sans_clover(config_toml):
        par_nom.setdefault(nom.lower(), Depot(nom))
    return list(par_nom.values())


def noms(config_toml: dict) -> list[str]:
    return [d.nom for d in liste(config_toml)]


def du_point_de_vente(config_toml: dict, code: str | None) -> str:
    for d in liste(config_toml):
        if (code or "1") in d.points_vente:
            return d.nom
    return DEPOT_DEFAUT


def points_vente_des(config_toml: dict, depots_choisis: list[str] | None) -> list[str] | None:
    """Codes des points de vente des dépôts choisis (None = tous)."""
    if not depots_choisis or TOUS in depots_choisis:
        return None
    choisis = {d.lower() for d in depots_choisis}
    return [c for d in liste(config_toml) if d.nom.lower() in choisis for c in d.points_vente]


def choisis(valeur: str | list[str] | None) -> list[str] | None:
    """Valeur d'un filtre « Dépôt » (« A | B » ou liste) -> dépôts choisis ; None = tous (« Tout sélectionner »)."""
    if valeur is None:
        return None
    morceaux = valeur if isinstance(valeur, list) else [v for v in str(valeur).split("|")]
    morceaux = [m.strip() for m in morceaux if m.strip()]
    if not morceaux or TOUS in morceaux:
        return None
    return morceaux


def garde(depot: str | None, filtre: list[str] | None) -> bool:
    """Ligne d'un état gardée par le filtre « Dépôt » (None = tous ; vide = emplacement par défaut)."""
    if filtre is None:
        return True
    nom = DEPOT_DEFAUT if est_defaut(depot) else str(depot).strip()
    return nom.lower() in {f.lower() for f in filtre}


# --------------------------------------------------------------------------------------------- import + transfert
def reference(numero_facture: str) -> str:
    return (PREFIXE_TRANSFERT + str(numero_facture).strip())[:LONGUEUR_REFERENCE]


def mouvements(depot: str, lignes: list[tuple[str, Decimal]], vente: bool) -> list[tuple[str, str, list]]:
    """[(de, vers, [(n° Sage, quantité > 0)])] : ce qui doit passer entre l'emplacement par défaut et le dépôt après
    l'import (vente / retour fournisseur : le stock sort du dépôt ; achat : il y entre). Quantités regroupées par
    article ; une quantité nette négative (remboursement) part dans l'autre sens."""
    if est_defaut(depot):
        return []
    par_article: dict[str, Decimal] = {}
    for numero, quantite in lignes:
        if numero:
            par_article[numero] = par_article.get(numero, Decimal(0)) + Decimal(str(quantite))
    sortie = [(n, q) for n, q in par_article.items() if q > 0]
    entree = [(n, -q) for n, q in par_article.items() if q < 0]
    if not vente:
        sortie, entree = entree, sortie
    resultat = []
    if sortie:
        resultat.append((depot, DEPOT_DEFAUT, sortie))
    if entree:
        resultat.append((DEPOT_DEFAUT, depot, entree))
    return resultat


def apres_import(racine: Path, config_toml: dict, numero_facture: str, depot: str, lignes, vente: bool,
                 jour: str | None = None, journal=print) -> list[str]:
    """Transfert entre l'emplacement par défaut et le dépôt de la facture, juste après son import vérifié. Renvoie
    les messages (rien si le dépôt est l'emplacement par défaut)."""
    from .transferts import transferer_dans_sage

    messages = []
    for n, (de, vers, groupe) in enumerate(mouvements(depot, lignes, vente)):
        ref = reference(numero_facture) + ("R" if n else "")
        try:
            resultats = transferer_dans_sage(racine, config_toml, ref, de, vers, groupe, jour or date.today().isoformat(),
                                             f"Facture {numero_facture} — dépôt {depot}")
            faits = sum(1 for r in resultats if r.get("fait"))
            messages.append(f"Dépôt « {depot} » : {sum(len(r.get('lignes', [])) for r in resultats)} ligne(s) "
                            f"transférée(s) de « {de} » vers « {vers} » ({faits}/{len(resultats)} lot(s) dans Sage).")
            for r in resultats:
                if not r.get("fait"):
                    messages += [f"Transfert {r.get('source')} : {m}" for m in r.get("messages", [])]
        except Exception as exc:  # noqa: BLE001 — la facture est importée : le transfert se refait (même source)
            messages.append(f"Dépôt « {depot} » : transfert de stock non fait ({exc}) — à refaire (Stock > "
                            f"Transferts), source {ref}.")
        journal(messages[-1])
    return messages


def du_nom(config_toml: dict, nom: str | None) -> Depot:
    """Dépôt de ce nom (vide = emplacement par défaut) ; inconnu = dépôt sans Clover de ce nom."""
    cible = DEPOT_DEFAUT if est_defaut(nom) else str(nom).strip()
    return next((d for d in liste(config_toml) if d.nom.lower() == cible.lower()), Depot(cible))

"""Mémoire des lectures de Sage et de Clover, partagée par toutes les pages (demande du propriétaire du 2026-10-29 :
« le plus rapide possible »).

Les requêtes elles-mêmes sont rapides (0,01 à 0,16 s, mesuré le 2026-10-29) ; le temps perdu venait de l'ouverture
de Sage quand il est fermé (plusieurs secondes par lecture) et des relectures des mêmes données (catalogue Clover de
2 500 articles, listes de clients, d'articles, de stocks). Une lecture est gardée `DUREE` secondes ; « Actualiser »
relit toujours (`forcer`) ; toute écriture dans Sage vide la mémoire (`vider`). Au démarrage de l'application, les
listes principales sont lues d'avance si Sage répond déjà (aucune ouverture de Sage pour cela).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

DUREE = 300  # secondes
_MEMOIRE: dict[str, tuple[float, object]] = {}
_VERROU = threading.RLock()


def lire(cle: str, fonction, duree: float = DUREE, forcer: bool = False):
    """Valeur gardée de `cle` si elle a moins de `duree` secondes, sinon fonction() (gardée ensuite)."""
    with _VERROU:
        deja = _MEMOIRE.get(cle)
        if deja and not forcer and time.time() - deja[0] < duree:
            return deja[1]
    valeur = fonction()
    with _VERROU:
        _MEMOIRE[cle] = (time.time(), valeur)
    return valeur


def connue(cle: str, duree: float = DUREE):
    """Valeur gardée encore fraîche, sinon None (affichage immédiat sans lecture)."""
    with _VERROU:
        deja = _MEMOIRE.get(cle)
        return deja[1] if deja and time.time() - deja[0] < duree else None


def garder(cle: str, valeur) -> None:
    with _VERROU:
        _MEMOIRE[cle] = (time.time(), valeur)


def vider(prefixe: str = "") -> None:
    """Après une écriture dans Sage (import, ajustement…) : les lectures gardées ne sont plus sûres."""
    with _VERROU:
        for cle in [c for c in _MEMOIRE if c.startswith(prefixe)]:
            del _MEMOIRE[cle]


def vide_apres(fonction):
    """Décorateur des fonctions qui écrivent dans Sage ou dans Clover : la mémoire est vidée après (même en cas
    d'erreur : une partie a pu être écrite)."""
    import functools

    @functools.wraps(fonction)
    def enveloppe(*arguments, **options):
        try:
            return fonction(*arguments, **options)
        finally:
            vider()

    return enveloppe


def inventaire_clover(racine: Path):
    """Catalogue Clover (stock, coût, prix, catégories), lu au plus une fois par période de DUREE secondes."""
    from .__main__ import charger_config
    from .api_clover import ClientClover

    return lire("clover:inventaire",
                lambda: ClientClover(charger_config(Path(racine) / "config.toml")).inventaire())


def precharger(racine: Path) -> None:
    """Listes principales lues d'avance, seulement si Sage répond déjà (connexion gardée) : jamais d'ouverture de
    Sage pour cela. Silencieux en cas d'échec."""
    try:
        import tomllib

        from .__main__ import base_partagee
        from .fenetre_gestion import LECTURES

        chemin = Path(racine) / "config.toml"
        config = tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
        fichier = config.get("sage_import", {}).get("fichier_entreprise")
        base = base_partagee(config, fichier)  # erreur si Sage ne sert pas le fichier : rien n'est lu
        for genre, lecture in LECTURES.items():
            garder(f"liste:{genre}:None:None", lecture(Path(racine))(base, None, None))
    except Exception:
        pass

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


def inventaire_clover(racine: Path, pv=None):
    """Catalogue Clover (stock, coût, prix, catégories) du point de vente (n° 1 par défaut), lu au plus une fois par
    période de DUREE secondes."""
    from .points_vente import PRINCIPAL, client

    cle = "clover:inventaire" if pv is None or pv.principal else f"clover:inventaire:{pv.code}"
    return lire(cle, lambda: client(racine, pv).inventaire())


def precharger(racine: Path) -> None:
    """Au démarrage : catalogue Clover et ventes par article des 365 derniers jours (résumés par jour) lus d'avance
    — le premier clic n'attend plus Clover (1,7 s et 1,5 s, mesuré le 2026-10-30) — puis listes principales de Sage
    (Sage fermé : base ouverte par l'outil d'import et gardée ; jamais d'ouverture de Sage lui-même pour cela).
    Silencieux en cas d'échec."""
    try:
        from datetime import date, timedelta

        from .__main__ import charger_config
        from .api_clover import ClientClover
        from .previsions import ventes_par_article_rapide

        inventaire_clover(racine)
        aujourdhui = date.today()
        ventes_par_article_rapide(ClientClover(charger_config(Path(racine) / "config.toml")),
                                  aujourdhui - timedelta(days=365), aujourdhui, Path(racine) / "donnees" / "cache_clover")
    except BaseException:  # SystemExit compris (jeton absent)
        pass
    try:
        import tomllib

        from .__main__ import lire_sage
        from .fenetre_gestion import LECTURES

        chemin = Path(racine) / "config.toml"
        config = tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
        fichier = config.get("sage_import", {}).get("fichier_entreprise")

        def tout(base):
            return {genre: lecture(Path(racine))(base, None, None) for genre, lecture in LECTURES.items()}

        # Sage fermé : base ouverte par l'outil d'import et gardée (DUREE_GARDE) -> le premier clic n'attend plus
        # les ~10 s d'ouverture (2026-10-30) ; jamais d'ouverture de Sage lui-même pour cela (ouvrir=False)
        for genre, lu in lire_sage(config, tout, fichier, ouvrir=False).items():
            garder(f"liste:{genre}:None:None", lu)
    except Exception:
        pass

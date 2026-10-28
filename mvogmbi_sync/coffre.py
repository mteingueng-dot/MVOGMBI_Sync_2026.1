"""Secrets de l'application dans le Gestionnaire d'identification de Windows (coffre-fort Windows).

Rien n'est écrit en clair : le jeton Clover et les mots de passe sont saisis dans l'interface d'installation
et lus ici au moment du traitement. Pour compatibilité, une valeur encore présente dans config.toml est utilisée
si le coffre ne contient rien.
"""

from __future__ import annotations

import keyring
from keyring.errors import PasswordDeleteError

SERVICE = "MVOGMBI_Sync"

CLOVER_JETON = "clover_jeton"
SAGE_LECTURE = "sage_lecture"   # utilisateur Sage « accès par des tiers » (lecture de la base)
SAGE_IMPORT = "sage_import"     # mot de passe demandé par l'outil d'import de Sage (ex. sysadmin)
COURRIEL = "courriel"           # mot de passe du compte d'envoi des alertes
BOITE_PAIEMENTS = "boite_paiements"  # mot de passe de la boîte où arrivent les avis de paiement (IMAP)

LIBELLES = {
    CLOVER_JETON: "Jeton API Clover",
    SAGE_LECTURE: "Mot de passe Sage (lecture)",
    SAGE_IMPORT: "Mot de passe Sage (import)",
    COURRIEL: "Mot de passe du courriel d'envoi",
    BOITE_PAIEMENTS: "Mot de passe de la boîte des avis de paiement",
}


_LUS: dict[str, str | None] = {}  # secrets déjà lus pendant cette exécution (le coffre de Windows est lent)


def lire(cle: str, secours: str | None = None) -> str:
    if cle not in _LUS:
        _LUS[cle] = keyring.get_password(SERVICE, cle)
    valeur = _LUS[cle]
    return valeur if valeur else (secours or "")


def ecrire(cle: str, valeur: str) -> None:
    if valeur:
        keyring.set_password(SERVICE, cle, valeur)
        _LUS[cle] = valeur


def supprimer(cle: str) -> None:
    _LUS.pop(cle, None)
    try:
        keyring.delete_password(SERVICE, cle)
    except PasswordDeleteError:
        pass


def present(cle: str) -> bool:
    return bool(keyring.get_password(SERVICE, cle))

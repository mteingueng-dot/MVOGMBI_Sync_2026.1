"""Point d'entrée de MVOGMBI_Sync_Serveur.exe : serveur de l'application web (SERVDCSAGE).
Options : --adresse A --port P (sinon [web] adresse / port de config.toml).

Demande du propriétaire du 2026-11-05 : le serveur tourne en arrière-plan, sans fenêtre (programme sans console,
visible dans les processus du Gestionnaire des tâches) ; démarré à la fin de l'installation et à chaque ouverture
de session (raccourci du dossier Démarrage). Une seule copie à la fois (verrou nommé de Windows) : une 2e copie
s'arrête d'elle-même. Les erreurs vont dans donnees/journal_web.log (aucune boîte d'erreur)."""
import sys

from mvogmbi_sync.__main__ import main

VERROU = "Local\MVOGMBI_Sync_Serveur_web"


def deja_lance() -> bool:
    try:
        import ctypes

        noyau = ctypes.windll.kernel32
        noyau.CreateMutexW(None, False, VERROU)  # gardé ouvert jusqu'à la fin du programme
        return noyau.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    except (AttributeError, OSError):
        return False


if __name__ == "__main__":
    if deja_lance():
        sys.exit(0)
    try:
        main(["web"] + sys.argv[1:])
    except BaseException:  # noqa: BLE001 — sans console : l'échec est déjà noté dans journal_web.log
        sys.exit(1)

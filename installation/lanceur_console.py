"""Point d'entrée de MVOGMBI_Sync_console.exe : moteur en ligne de commande (tâche planifiée : « auto »)."""
import sys

from mvogmbi_sync.__main__ import main

if __name__ == "__main__":
    main(sys.argv[1:] or ["--help"])

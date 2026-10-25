"""Point d'entrée de MVOGMBI_Sync.exe : application de configuration et de suivi (sans console)."""
import sys

from mvogmbi_sync.__main__ import main

if __name__ == "__main__":
    main(sys.argv[1:] or ["interface"])

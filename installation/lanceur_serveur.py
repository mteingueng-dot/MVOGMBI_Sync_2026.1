"""Point d'entrée de MVOGMBI_Sync_Serveur.exe : serveur de l'application web (SERVDC01 ; tâche « MVOGMBI_Sync Web »).
Options : --adresse A --port P (sinon [web] adresse / port de config.toml)."""
import sys

from mvogmbi_sync.__main__ import main

if __name__ == "__main__":
    main(["web"] + sys.argv[1:])

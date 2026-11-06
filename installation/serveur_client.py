r"""Fabrication : serveur.json de l'installateur du client (demande du propriétaire du 2026-11-05 : « intégrer
directement les adresses du serveur afin que celles-ci ne soient plus demandées à la première connexion »).
Lu dans config.toml ([serveur] / [web], « Administration > Automatisation > Serveur de l'application ») ; sans
config.toml : https://app.marchemvogmbi.com. Écrit dans build\client\serveur.json (jamais publié).

    python serveur_client.py [config.toml]
"""
import json
import sys
import tomllib
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))

from mvogmbi_sync import serveur_appli  # noqa: E402

source = Path(sys.argv[1]) if len(sys.argv) > 1 else ICI.parent / "config.toml"
sortie = ICI.parent / "build" / "client" / "serveur.json"
sortie.parent.mkdir(parents=True, exist_ok=True)
try:
    contenu = serveur_appli.fichier_client(tomllib.loads(source.read_text(encoding="utf-8")))
except (OSError, ValueError):
    contenu = json.dumps({"noms": {"app.marchemvogmbi.com": "https://app.marchemvogmbi.com"},
                          "adresse": "https://app.marchemvogmbi.com"}, indent=1).encode("utf-8")
# le nom public a son certificat HTTPS (port 443, Let's Encrypt) : il passe devant l'adresse du config.toml du
# poste de fabrication si celui-ci n'a pas le certificat (le client essaie aussi les autres adresses)
donnees = json.loads(contenu)
nom = next((n for n in donnees.get("noms", {}) if n.count(".") >= 2), "")
if nom and not str(donnees.get("adresse", "")).startswith("https://"):
    donnees["secours"] = donnees.get("adresse", "")
    donnees["adresse"] = f"https://{nom}"
    donnees["noms"] = {k: donnees["adresse"] for k in donnees["noms"]}
    contenu = json.dumps(donnees, ensure_ascii=False, indent=1).encode("utf-8")
sortie.write_bytes(contenu)
print(f"serveur.json du client : {json.loads(contenu)['adresse']}")

#!/bin/bash
# Fabrique le client Mac : dist/MVOGMBI_Sync_Client_<version>.dmg (application MVOGMBI_Sync_Client.app à glisser
# dans Applications). À lancer SUR UN MAC (macOS 11 ou plus, Python 3.11+ de python.org avec Tk), depuis la racine
# du projet :   bash installation/mac/fabriquer_mac.sh
# Ou par GitHub : onglet Actions > « Client Mac » > Run workflow (.github/workflows/client_mac.yml).
# Facultatif : ADRESSE_LOCALE=192.168.2.62 bash installation/mac/fabriquer_mac.sh  (réseau local sans Tailscale).
set -euo pipefail
cd "$(dirname "$0")/../.."
ICI=installation/mac
PYTHON=${PYTHON:-python3}

VERSION=$($PYTHON -c "import re;print(re.search(r'VERSION = \"([^\"]+)\"', open('mvogmbi_sync/aide.py', encoding='utf-8').read()).group(1))")
echo "Client Mac $VERSION"
echo "$VERSION" > "$ICI/VERSION"

# adresse du serveur (comme serveur.json de l'installateur Windows) : nom public, et adresse locale si donnée
$PYTHON - "$ICI/serveur.json" "${ADRESSE_LOCALE:-}" <<'FIN'
import json, sys
nom = "app.marchemvogmbi.com"
donnees = {"noms": {nom: f"https://{nom}", "marchemvogmbi.com": f"https://{nom}"}, "adresse": f"https://{nom}"}
if sys.argv[2]:
    donnees["adresse_locale"] = sys.argv[2]
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(donnees, ensure_ascii=False, indent=1))
FIN

# icône .icns d'après l'emblème du marché
if [ -f ressources/embleme.png ]; then
  ICONSET=$(mktemp -d)/MVOGMBI_Sync.iconset
  mkdir -p "$ICONSET"
  for t in 16 32 128 256 512; do
    sips -z $t $t ressources/embleme.png --out "$ICONSET/icon_${t}x${t}.png" >/dev/null
    sips -z $((t*2)) $((t*2)) ressources/embleme.png --out "$ICONSET/icon_${t}x${t}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$ICI/MVOGMBI_Sync.icns"
fi

$PYTHON -m pip install --quiet --upgrade pyinstaller
$PYTHON -m PyInstaller --noconfirm --clean --distpath dist/mac --workpath build/mac "$ICI/MVOGMBI_Sync_Client_mac.spec"

# image disque : l'application + un raccourci vers Applications
DMG_DOSSIER=$(mktemp -d)
cp -R dist/mac/MVOGMBI_Sync_Client.app "$DMG_DOSSIER/"
ln -s /Applications "$DMG_DOSSIER/Applications"
rm -f "dist/MVOGMBI_Sync_Client_$VERSION.dmg"
hdiutil create -volname "MVOGMBI_Sync $VERSION" -srcfolder "$DMG_DOSSIER" -ov -format UDZO \
  "dist/MVOGMBI_Sync_Client_$VERSION.dmg"
echo "Fait : dist/MVOGMBI_Sync_Client_$VERSION.dmg"

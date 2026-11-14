# Recette PyInstaller du client pour Mac : dist/MVOGMBI_Sync_Client.app (à fabriquer SUR un Mac ou par la
# fabrication automatique de GitHub, .github/workflows/client_mac.yml : PyInstaller ne fabrique pas pour Mac depuis
# Windows). Bibliothèque standard seulement (tkinter, urllib), comme le client Windows.
import os

racine = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
version = open(os.path.join(SPECPATH, "VERSION")).read().strip() if os.path.exists(
    os.path.join(SPECPATH, "VERSION")) else "1.0.0"
donnees = [(os.path.join(SPECPATH, "serveur.json"), ".")] if os.path.exists(os.path.join(SPECPATH, "serveur.json")) else []
icone = os.path.join(SPECPATH, "MVOGMBI_Sync.icns")

a = Analysis([os.path.join(racine, "installation", "lanceur_client.py")], pathex=[racine], hiddenimports=[],
             datas=donnees,
             excludes=["pytest", "matplotlib", "numpy", "PIL", "openpyxl", "pdfplumber", "pypdf", "fpdf", "pymysql",
                       "keyring", "rapidfuzz", "requests", "sv_ttk"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="MVOGMBI_Sync_Client", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="MVOGMBI_Sync_Client")
app = BUNDLE(coll, name="MVOGMBI_Sync_Client.app", icon=icone if os.path.exists(icone) else None,
             bundle_identifier="com.marchemvogmbi.mvogmbisync.client",
             info_plist={"CFBundleName": "MVOGMBI_Sync", "CFBundleDisplayName": "MVOGMBI_Sync",
                         "CFBundleShortVersionString": version, "CFBundleVersion": version,
                         "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0"})

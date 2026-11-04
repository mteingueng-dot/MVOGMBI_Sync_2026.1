# Recette PyInstaller du client des postes : dist\MVOGMBI_Sync_Client.exe, un seul fichier, sans console.
# Bibliothèque standard seulement (tkinter, urllib) : le reste de l'application n'est pas embarqué.
racine = SPECPATH + "\\.."
a = Analysis([SPECPATH + "\\lanceur_client.py"], pathex=[racine], hiddenimports=[], datas=[],
             excludes=["pytest", "matplotlib", "numpy", "PIL", "openpyxl", "pdfplumber", "pypdf", "fpdf", "pymysql",
                       "keyring", "rapidfuzz", "requests", "sv_ttk"], noarchive=False)
EXE(PYZ(a.pure), a.scripts, a.binaries, a.datas, [], name="MVOGMBI_Sync_Client", console=False,
    icon=SPECPATH + "\\MVOGMBI_Sync.ico", version=SPECPATH + "\\version_info.txt")

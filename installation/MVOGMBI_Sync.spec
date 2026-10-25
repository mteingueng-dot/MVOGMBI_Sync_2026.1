# Recette PyInstaller : deux programmes dans un même dossier (dist\MVOGMBI_Sync).
#   MVOGMBI_Sync.exe          application de configuration et de suivi (fenêtres, sans console)
#   MVOGMBI_Sync_console.exe  moteur en ligne de commande, lancé par la tâche planifiée
# Fabrication : installation\fabriquer.cmd
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

racine = SPECPATH + "\\.."
cachees = ["keyring.backends.Windows", "keyring.backends.fail", "pymysql", "tzdata", "PIL.ImageTk", "sv_ttk"]
donnees = (copy_metadata("keyring") + collect_data_files("tzdata") + collect_data_files("sv_ttk")
           + [(racine + "\\config.example.toml", "."),
              (racine + "\\mvogmbi_sync\\ressources", "mvogmbi_sync\\ressources")])


def analyse(script):
    return Analysis([script], pathex=[racine], hiddenimports=cachees, datas=donnees,
                    excludes=["pytest", "matplotlib", "numpy"], noarchive=False)


a_gui = analyse(SPECPATH + "\\lanceur_interface.py")
a_cli = analyse(SPECPATH + "\\lanceur_console.py")

exe_gui = EXE(PYZ(a_gui.pure), a_gui.scripts, [], exclude_binaries=True, name="MVOGMBI_Sync",
              console=False, icon=SPECPATH + "\\MVOGMBI_Sync.ico", version=SPECPATH + "\\version_info.txt")
exe_cli = EXE(PYZ(a_cli.pure), a_cli.scripts, [], exclude_binaries=True, name="MVOGMBI_Sync_console",
              console=True, icon=SPECPATH + "\\MVOGMBI_Sync.ico", version=SPECPATH + "\\version_info.txt")

COLLECT(exe_gui, a_gui.binaries, a_gui.datas, exe_cli, a_cli.binaries, a_cli.datas,
        name="MVOGMBI_Sync")

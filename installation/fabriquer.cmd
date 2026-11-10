@echo off
rem Fabrique dist\MVOGMBI_Sync\ (programmes) puis dist\Installer_MVOGMBI_Sync_x.y.z.exe (installateur).
cd /d "%~dp0"
python creer_icone.py || goto erreur
rem Manuel d'utilisation (PDF) refait a partir des captures et des textes de l'aide
if exist ..\documentation\captures\00_accueil.png python ..\documentation\creer_manuel.py
rem Documents du projet (PDF) : architecture, documentation fonctionnelle, tests, projet, workflows, processus ;
rem sans Internet (diagrammes), les anciens PDF sont gardes
python ..\documentation\creer_documents.py
rem Les memes documents et les manuels au format Word (documentation\Word\*.docx, Microsoft Word requis)
python ..\documentation\creer_word.py
python -m PyInstaller --noconfirm --clean --distpath ..\dist --workpath ..\build MVOGMBI_Sync.spec || goto erreur
rem Client des postes (un seul fichier, copie aussi dans l'installateur)
python -m PyInstaller --noconfirm --clean --distpath ..\dist --workpath ..\build\client MVOGMBI_Sync_Client.spec || goto erreur
rem Adresse du serveur pour l'installateur du client (build\client\serveur.json, d'apres config.toml)
python serveur_client.py || goto erreur
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
"%ISCC%" MVOGMBI_Sync.iss || goto erreur
"%ISCC%" MVOGMBI_Sync_Client.iss || goto erreur
echo.
echo Installateur pret dans le dossier dist.
exit /b 0
:erreur
echo ECHEC de la fabrication.
exit /b 1

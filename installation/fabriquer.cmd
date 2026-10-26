@echo off
rem Fabrique dist\MVOGMBI_Sync\ (programmes) puis dist\Installer_MVOGMBI_Sync_x.y.z.exe (installateur).
cd /d "%~dp0"
python creer_icone.py || goto erreur
rem Manuel d'utilisation (PDF) refait a partir des captures et des textes de l'aide
if exist ..\documentation\captures\00_accueil.png python ..\documentation\creer_manuel.py
python -m PyInstaller --noconfirm --clean --distpath ..\dist --workpath ..\build MVOGMBI_Sync.spec || goto erreur
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
"%ISCC%" MVOGMBI_Sync.iss || goto erreur
echo.
echo Installateur pret dans le dossier dist.
exit /b 0
:erreur
echo ECHEC de la fabrication.
exit /b 1

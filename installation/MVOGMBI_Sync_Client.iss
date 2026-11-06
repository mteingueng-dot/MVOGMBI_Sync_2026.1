; Installateur du client des postes (demande du propriétaire du 2026-11-05 : « fais aussi un installeur pour le client
; en intégrant directement les adresses du serveur afin que celles-ci ne soient plus demandées à la première
; connexion »). Sans droits d'administrateur. serveur.json (adresse du serveur) est écrit à la fabrication par
; serveur_client.py d'après config.toml ([serveur] / [web]) : le client ouvre l'application web tout de suite.
; Fabrication : installation\fabriquer.cmd

#define Nom "MVOGMBI_Sync_Client"
#define Version "2.24.0"
#define Editeur "Concept Informatique inc."

[Setup]
AppId={{B3F1D7A4-5C2E-4E8B-9A61-7D0C4F2E9B35}
AppName=MVOGMBI_Sync Client
AppVersion={#Version}
AppVerName=MVOGMBI_Sync Client {#Version}
AppPublisher={#Editeur}
AppCopyright=© 2026 {#Editeur}. Tous droits réservés. / All rights reserved.
VersionInfoVersion={#Version}
VersionInfoCompany={#Editeur}
VersionInfoDescription=Client de l'application web MVOGMBI_Sync (Marché MVOG-MBI Sherbrooke)
DefaultDirName={localappdata}\Programs\{#Nom}
DefaultGroupName=MVOGMBI_Sync
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Installer_{#Nom}_{#Version}
SetupIconFile=MVOGMBI_Sync.ico
WizardImageFile=assistant_grand.bmp
WizardSmallImageFile=assistant_petit.bmp
UninstallDisplayIcon={app}\MVOGMBI_Sync_Client.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
DisableDirPage=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.Application=MVOGMBI_Sync (application web)
en.Application=MVOGMBI_Sync (web application)
fr.Complete=MVOGMBI_Sync (application complète, Bureau à distance)
en.Complete=MVOGMBI_Sync (full application, Remote Desktop)
fr.Reglages=MVOGMBI_Sync (adresse du serveur)
en.Reglages=MVOGMBI_Sync (server address)
fr.TacheBureau=Créer un raccourci sur le Bureau
en.TacheBureau=Create a desktop shortcut
fr.Ouvrir=Ouvrir MVOGMBI_Sync
en.Ouvrir=Open MVOGMBI_Sync

[Tasks]
Name: "bureau"; Description: "{cm:TacheBureau}"

[Files]
Source: "..\dist\MVOGMBI_Sync_Client.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\client\serveur.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{cm:Application}"; Filename: "{app}\MVOGMBI_Sync_Client.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:Complete}"; Filename: "{app}\MVOGMBI_Sync_Client.exe"; Parameters: "--bureau"; WorkingDir: "{app}"
Name: "{group}\{cm:Reglages}"; Filename: "{app}\MVOGMBI_Sync_Client.exe"; Parameters: "--reglages"; WorkingDir: "{app}"
Name: "{userdesktop}\MVOGMBI_Sync"; Filename: "{app}\MVOGMBI_Sync_Client.exe"; WorkingDir: "{app}"; Tasks: bureau

[Run]
Filename: "{app}\MVOGMBI_Sync_Client.exe"; Description: "{cm:Ouvrir}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

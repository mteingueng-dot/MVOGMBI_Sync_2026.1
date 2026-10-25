; Installateur Windows de MVOGMBI_Sync (Inno Setup 6).
; Installation pour l'utilisateur courant, sans droits d'administrateur, dans un dossier où l'application
; peut écrire sa configuration et ses journaux. Fabrication : installation\fabriquer.cmd

#define Nom "MVOGMBI_Sync"
#define Version "1.0.0"

[Setup]
AppId={{6E4B0C2A-2E54-4F0F-9C8B-5D1C2B8F4A11}
AppName={#Nom}
AppVersion={#Version}
AppVerName={#Nom} {#Version}
AppPublisher=Marché MVOG-MBI Sherbrooke
DefaultDirName={localappdata}\Programs\{#Nom}
DefaultGroupName={#Nom}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Installer_{#Nom}_{#Version}
SetupIconFile=MVOGMBI_Sync.ico
UninstallDisplayIcon={app}\MVOGMBI_Sync.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "..\dist\MVOGMBI_Sync\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; La configuration et les données existantes ne sont jamais écrasées lors d'une mise à jour.

[Dirs]
Name: "{app}\donnees"

[Icons]
Name: "{group}\MVOGMBI_Sync"; Filename: "{app}\MVOGMBI_Sync.exe"; WorkingDir: "{app}"
Name: "{group}\Journal du traitement"; Filename: "{app}\donnees\journal_automatique.log"
Name: "{group}\Désinstaller MVOGMBI_Sync"; Filename: "{uninstallexe}"
Name: "{userdesktop}\MVOGMBI_Sync"; Filename: "{app}\MVOGMBI_Sync.exe"; WorkingDir: "{app}"; Tasks: bureau

[Run]
Filename: "{app}\MVOGMBI_Sync.exe"; Description: "Ouvrir MVOGMBI_Sync pour la configuration"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Retire la tâche planifiée de 1 h (les données et la configuration restent dans le dossier).
Filename: "{app}\MVOGMBI_Sync_console.exe"; Parameters: "planifier --retirer"; Flags: runhidden; RunOnceId: "RetirerTache"

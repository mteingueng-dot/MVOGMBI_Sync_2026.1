; Installateur Windows de MVOGMBI_Sync (Inno Setup 6).
; Installation pour l'utilisateur courant, sans droits d'administrateur, dans un dossier où l'application
; peut écrire sa configuration et ses journaux. Fabrication : installation\fabriquer.cmd

#define Nom "MVOGMBI_Sync"
#define Version "1.0.16"
#define Editeur "Concept Informatique inc."

[Setup]
AppId={{6E4B0C2A-2E54-4F0F-9C8B-5D1C2B8F4A11}
AppName={#Nom}
AppVersion={#Version}
AppVerName={#Nom} {#Version}
AppPublisher={#Editeur}
AppCopyright=© 2026 {#Editeur}. Tous droits réservés. / All rights reserved.
VersionInfoVersion={#Version}
VersionInfoCompany={#Editeur}
VersionInfoCopyright=© 2026 {#Editeur}
VersionInfoDescription=Installation de MVOGMBI_Sync (Clover -> Sage 50) pour le Marché MVOG-MBI Sherbrooke
DefaultDirName={localappdata}\Programs\{#Nom}
DefaultGroupName={#Nom}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Installer_{#Nom}_{#Version}
SetupIconFile=MVOGMBI_Sync.ico
WizardImageFile=assistant_grand.bmp
WizardSmallImageFile=assistant_petit.bmp
UninstallDisplayIcon={app}\MVOGMBI_Sync.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
; Choix de la langue au lancement de l'installateur ; elle devient aussi la langue de l'application.
ShowLanguageDialog=yes
UsePreviousLanguage=no

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.TacheBureau=Créer un raccourci sur le Bureau
en.TacheBureau=Create a desktop shortcut
fr.OuvrirApplication=Ouvrir MVOGMBI_Sync pour la configuration
en.OuvrirApplication=Open MVOGMBI_Sync to configure it
fr.JournalTraitement=Journal du traitement
en.JournalTraitement=Run log
fr.Manuel=Manuel d'utilisation
en.Manuel=User manual
fr.Architecture=Document d'architecture
en.Architecture=Architecture document (French)
fr.GuideAdmin=Guide de l'administrateur
en.GuideAdmin=Administrator guide (French)
fr.Documents=Documents du projet
en.Documents=Project documents (French)
fr.Pointage=Pointage des employés
en.Pointage=Employee time clock
fr.ServeurWeb=Serveur de l'application web
fr.TacheServeurWeb=Démarrer le serveur de l'application web en arrière-plan (à chaque ouverture de session)
en.TacheServeurWeb=Start the web application server in the background (at each sign-in)
fr.DemarrageServeur=Démarrage du serveur de l'application web…
en.DemarrageServeur=Starting the web application server…
en.ServeurWeb=Web application server
fr.ClientWeb=Client MVOGMBI_Sync (application web)
en.ClientWeb=MVOGMBI_Sync client (web application)
fr.Desinstaller=Désinstaller MVOGMBI_Sync
en.Desinstaller=Uninstall MVOGMBI_Sync
fr.ReglageLangue=Réglage de la langue de l'application…
en.ReglageLangue=Setting the application language…
fr.TitreLangue=Langue de l'application
en.TitreLangue=Application language
fr.DescriptionLangue=Dans quelle langue MVOGMBI_Sync doit-il s'afficher ?
en.DescriptionLangue=Which language should MVOGMBI_Sync use?
fr.ChoixLangue=Choisissez la langue de l'application (modifiable ensuite dans l'application) :
en.ChoixLangue=Choose the application language (can be changed later in the application):

[Files]
Source: "..\dist\MVOGMBI_Sync\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\documentation\Manuel_MVOGMBI_Sync.pdf"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\User_Manual_MVOGMBI_Sync.pdf"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Architecture_MVOGMBI_Sync.pdf"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Guide_administrateur_MVOGMBI_Sync.pdf"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; documents du projet (version 1.0.0) : documentation fonctionnelle, tests, projet, workflows, processus, présentation
Source: "..\documentation\Documentation_fonctionnelle_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Plan_de_test_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Diagramme_de_projet_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Workflows_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Processus_BPM_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Regles_affaires_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Catalogue_reporting_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Notes_de_version_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Analyse_securite_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Presentation_services_MVOGMBI_Sync.pdf"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\Presentation_MVOGMBI_Sync.pptx"; DestDir: "{app}\documentation"; Flags: ignoreversion skipifsourcedoesntexist
; chaque document aussi au format Word (demande du propriétaire du 2026-11-09)
Source: "..\documentation\Word\*.docx"; DestDir: "{app}\documentation\Word"; Flags: ignoreversion skipifsourcedoesntexist
; manuel du profil : page HTML du manuel et captures (l'application en retire les chapitres non permis)
Source: "..\documentation\Manuel_MVOGMBI_Sync.html"; DestDir: "{app}\manuel"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\User_Manual_MVOGMBI_Sync.html"; DestDir: "{app}\manuel"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\documentation\captures\*"; DestDir: "{app}\manuel\captures"; Flags: recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist
; application web : mise en service sur le serveur, lancée par le propriétaire (version 1.1.0)
Source: "installer_web.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "certificat_https.ps1"; DestDir: "{app}"; Flags: ignoreversion
; client des postes (version 1.2.0) : à copier sur chaque poste, rien à installer
Source: "..\dist\MVOGMBI_Sync_Client.exe"; DestDir: "{app}\client"; Flags: ignoreversion
; La configuration et les données existantes ne sont jamais écrasées lors d'une mise à jour.

[Dirs]
Name: "{app}\donnees"

[Icons]
Name: "{group}\MVOGMBI_Sync"; Filename: "{app}\MVOGMBI_Sync.exe"; WorkingDir: "{app}"; AppUserModelID: "ConceptInformatique.MVOGMBI_Sync"
Name: "{group}\{cm:Pointage}"; Filename: "{app}\MVOGMBI_Sync.exe"; Parameters: "pointage"; WorkingDir: "{app}"
Name: "{group}\{cm:ServeurWeb}"; Filename: "{app}\MVOGMBI_Sync_Serveur.exe"; WorkingDir: "{app}"
Name: "{userstartup}\MVOGMBI_Sync Serveur web"; Filename: "{app}\MVOGMBI_Sync_Serveur.exe"; WorkingDir: "{app}"; Tasks: serveurweb
Name: "{group}\{cm:ClientWeb}"; Filename: "{app}\client\MVOGMBI_Sync_Client.exe"; WorkingDir: "{app}\client"
Name: "{group}\{cm:Manuel}"; Filename: "{app}\Manuel_MVOGMBI_Sync.pdf"; Languages: fr
Name: "{group}\{cm:Manuel}"; Filename: "{app}\User_Manual_MVOGMBI_Sync.pdf"; Languages: en
Name: "{group}\{cm:Architecture}"; Filename: "{app}\Architecture_MVOGMBI_Sync.pdf"
Name: "{group}\{cm:GuideAdmin}"; Filename: "{app}\Guide_administrateur_MVOGMBI_Sync.pdf"
Name: "{group}\{cm:Documents}"; Filename: "{app}\documentation"
Name: "{group}\{cm:JournalTraitement}"; Filename: "{app}\donnees\journal_automatique.log"
Name: "{group}\{cm:Desinstaller}"; Filename: "{uninstallexe}"

[Tasks]
; Serveur de l'application web en arrière-plan (demande du propriétaire du 2026-11-05) : sans fenêtre, démarré à la
; fin de l'installation et à chaque ouverture de session (dossier Démarrage de la personne)
Name: "serveurweb"; Description: "{cm:TacheServeurWeb}"

[Run]
; Langue de l'installation enregistrée dans config.toml ([general] langue = fr | en)
Filename: "{app}\MVOGMBI_Sync_console.exe"; Parameters: "langue {code:LangueApplication}"; WorkingDir: "{app}"; StatusMsg: "{cm:ReglageLangue}"; Flags: runhidden waituntilterminated
; Dernière page : case « Créer un raccourci sur le Bureau » (le raccourci est créé par CreerRaccourciBureau)
Filename: "{cmd}"; Parameters: "/c exit 0"; Description: "{cm:TacheBureau}"; Flags: runhidden postinstall skipifsilent; AfterInstall: CreerRaccourciBureau
Filename: "{app}\MVOGMBI_Sync.exe"; Description: "{cm:OuvrirApplication}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\MVOGMBI_Sync_Serveur.exe"; WorkingDir: "{app}"; StatusMsg: "{cm:DemarrageServeur}"; Tasks: serveurweb; Flags: nowait runhidden

[UninstallDelete]
Type: files; Name: "{userdesktop}\MVOGMBI_Sync.lnk"

[UninstallRun]
; Retire la tâche planifiée de 1 h (les données et la configuration restent dans le dossier).
Filename: "{app}\MVOGMBI_Sync_console.exe"; Parameters: "planifier --retirer"; Flags: runhidden; RunOnceId: "RetirerTache"
; Sage gardé ouvert refermé proprement, puis serveur web arrêté avant la désinstallation
Filename: "{app}\MVOGMBI_Sync_console.exe"; Parameters: "liberer-sage"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "LibererSage"
Filename: "{sys}\taskkill.exe"; Parameters: "/IM MVOGMBI_Sync_Serveur.exe /F"; Flags: runhidden; RunOnceId: "ArreterServeurWeb"

[Code]
{ Page « Langue de l'application » : liste déroulante des langues acceptées par l'application. }
var
  PageLangue: TWizardPage;
  ListeLangues: TNewComboBox;

procedure InitializeWizard;
var
  Etiquette: TNewStaticText;
begin
  PageLangue := CreateCustomPage(wpSelectTasks, CustomMessage('TitreLangue'), CustomMessage('DescriptionLangue'));
  Etiquette := TNewStaticText.Create(PageLangue);
  Etiquette.Parent := PageLangue.Surface;
  Etiquette.Caption := CustomMessage('ChoixLangue');
  Etiquette.AutoSize := True;
  ListeLangues := TNewComboBox.Create(PageLangue);
  ListeLangues.Parent := PageLangue.Surface;
  ListeLangues.Style := csDropDownList;
  ListeLangues.Top := Etiquette.Top + Etiquette.Height + ScaleY(10);
  ListeLangues.Width := ScaleX(260);
  ListeLangues.Items.Add('Français');
  ListeLangues.Items.Add('English');
  if ActiveLanguage = 'en' then
    ListeLangues.ItemIndex := 1
  else
    ListeLangues.ItemIndex := 0;
end;

function LangueApplication(Param: String): String;
begin
  if ListeLangues.ItemIndex = 1 then
    Result := 'en'
  else
    Result := 'fr';
end;

{ Serveur web en marche : arrêté avant la copie des fichiers (sinon MVOGMBI_Sync_Serveur.exe ne se remplace pas),
  redémarré à la fin par [Run]. Avant : le Sage gardé ouvert pour la journée est refermé proprement (liberer-sage),
  sinon l'arrêt coupe le programme qui le garde et Sage reste seul sur le bureau caché (constat du 2026-11-06). }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  if FileExists(ExpandConstant('{app}\MVOGMBI_Sync_console.exe')) then
    Exec(ExpandConstant('{app}\MVOGMBI_Sync_console.exe'), 'liberer-sage', ExpandConstant('{app}'), SW_HIDE,
      ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM MVOGMBI_Sync_Serveur.exe /F', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;

procedure CreerRaccourciBureau;
begin
  CreateShellLink(ExpandConstant('{userdesktop}\MVOGMBI_Sync.lnk'), 'MVOGMBI_Sync',
    ExpandConstant('{app}\MVOGMBI_Sync.exe'), '', ExpandConstant('{app}'), '', 0, SW_SHOWNORMAL);
end;

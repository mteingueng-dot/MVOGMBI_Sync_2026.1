; Installateur Windows de MVOGMBI_Sync (Inno Setup 6).
; Installation pour l'utilisateur courant, sans droits d'administrateur, dans un dossier où l'application
; peut écrire sa configuration et ses journaux. Fabrication : installation\fabriquer.cmd

#define Nom "MVOGMBI_Sync"
#define Version "1.22.3"
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
; La configuration et les données existantes ne sont jamais écrasées lors d'une mise à jour.

[Dirs]
Name: "{app}\donnees"

[Icons]
Name: "{group}\MVOGMBI_Sync"; Filename: "{app}\MVOGMBI_Sync.exe"; WorkingDir: "{app}"; AppUserModelID: "ConceptInformatique.MVOGMBI_Sync"
Name: "{group}\{cm:Manuel}"; Filename: "{app}\Manuel_MVOGMBI_Sync.pdf"; Languages: fr
Name: "{group}\{cm:Manuel}"; Filename: "{app}\User_Manual_MVOGMBI_Sync.pdf"; Languages: en
Name: "{group}\{cm:Architecture}"; Filename: "{app}\Architecture_MVOGMBI_Sync.pdf"
Name: "{group}\{cm:JournalTraitement}"; Filename: "{app}\donnees\journal_automatique.log"
Name: "{group}\{cm:Desinstaller}"; Filename: "{uninstallexe}"

[Run]
; Langue de l'installation enregistrée dans config.toml ([general] langue = fr | en)
Filename: "{app}\MVOGMBI_Sync_console.exe"; Parameters: "langue {code:LangueApplication}"; WorkingDir: "{app}"; StatusMsg: "{cm:ReglageLangue}"; Flags: runhidden waituntilterminated
; Dernière page : case « Créer un raccourci sur le Bureau » (le raccourci est créé par CreerRaccourciBureau)
Filename: "{cmd}"; Parameters: "/c exit 0"; Description: "{cm:TacheBureau}"; Flags: runhidden postinstall skipifsilent; AfterInstall: CreerRaccourciBureau
Filename: "{app}\MVOGMBI_Sync.exe"; Description: "{cm:OuvrirApplication}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{userdesktop}\MVOGMBI_Sync.lnk"

[UninstallRun]
; Retire la tâche planifiée de 1 h (les données et la configuration restent dans le dossier).
Filename: "{app}\MVOGMBI_Sync_console.exe"; Parameters: "planifier --retirer"; Flags: runhidden; RunOnceId: "RetirerTache"

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

procedure CreerRaccourciBureau;
begin
  CreateShellLink(ExpandConstant('{userdesktop}\MVOGMBI_Sync.lnk'), 'MVOGMBI_Sync',
    ExpandConstant('{app}\MVOGMBI_Sync.exe'), '', ExpandConstant('{app}'), '', 0, SW_SHOWNORMAL);
end;

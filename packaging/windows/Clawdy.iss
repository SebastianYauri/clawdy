; Windows installer (Inno Setup 6).
; Build with:  iscc /DAppVersion=1.0.0 packaging\windows\Clawdy.iss
; Per-user install: no administrator rights needed.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B6C1E0A4-6F2E-4C7A-9C1E-2F7D5A3C8E11}
AppName=Clawdy
AppVersion={#AppVersion}
AppVerName=Clawdy {#AppVersion}
AppPublisher=SebastianYauri
AppPublisherURL=https://github.com/SebastianYauri/clawdy
AppSupportURL=https://github.com/SebastianYauri/clawdy/issues
DefaultDirName={localappdata}\Programs\Clawdy
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=Clawdy-Setup
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\Clawdy.exe
UninstallDisplayName=Clawdy
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto
CloseApplications=force
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\Clawdy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Leftovers from a previous version.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Clawdy"; Filename: "{app}\Clawdy.exe"
Name: "{autodesktop}\Clawdy"; Filename: "{app}\Clawdy.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Clawdy.exe"; Description: "{cm:LaunchProgram,Clawdy}"; Flags: nowait postinstall skipifsilent
; After a self-update (the app runs this installer with /autoupdate=1), reopen it
Filename: "{app}\Clawdy.exe"; Flags: nowait; Check: IsAutoUpdate

[UninstallRun]
; Close the widget and remove the Claude Code hooks and start at login.
Filename: "{app}\Clawdy.exe"; Parameters: "--uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "ClawdyUninstall"

[Code]
function IsAutoUpdate: Boolean;
begin
  Result := ExpandConstant('{param:autoupdate|0}') = '1';
end;

// When updating, close the running copy before replacing its files.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  if FileExists(ExpandConstant('{app}\Clawdy.exe')) then
    Exec(ExpandConstant('{app}\Clawdy.exe'), '--quit', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;

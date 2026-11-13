; Framewring installer (Inno Setup 6). Built by packaging\release.py,
; which passes the version: ISCC /DAppVer=X.Y.Z framewring.iss
; Installs for the current user without administrator rights
; (%LOCALAPPDATA%\Programs\Framewring); data - in %APPDATA%\Framewring.

#ifndef AppVer
  #define AppVer "0.0.0"
#endif
#define Src "..\build\dist\Framewring"

[Setup]
AppId={{8F3C2A61-5D7E-4B9A-9C1E-6A2F0D4B7E35}
AppName={cm:AppTitle}
AppVersion={#AppVer}
AppVerName={cm:AppTitle} {#AppVer}
AppPublisher=Framewring
AppPublisherURL=https://github.com/remrem23/framewring
AppSupportURL=https://github.com/remrem23/framewring
DefaultDirName={autopf}\Framewring
DefaultGroupName=Framewring
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\build\release
OutputBaseFilename=Framewring-{#AppVer}-setup
SetupIconFile=framewring.ico
UninstallDisplayIcon={app}\Framewring.exe
UninstallDisplayName={cm:AppTitle}
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=2
LZMAUseSeparateProcess=yes
WizardStyle=modern
VersionInfoVersion={#AppVer}
VersionInfoProductName=Framewring
VersionInfoProductVersion={#AppVer}
VersionInfoDescription=Framewring Setup
VersionInfoCompany=Framewring
AppMutex=FramewringRunning
CloseApplications=yes
RestartApplications=no

[Languages]
; the first one is the fallback if the Windows language is not in the list
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
; Chinese (Simplified) - unofficial Inno Setup translation, kept next to this file
Name: "zh"; MessagesFile: "ChineseSimplified.isl"

[CustomMessages]
AppTitle=Framewring
ru.AppTitle=Framewring Жмых

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; on update remove old libraries so they do not mix with the new ones
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{cm:AppTitle}"; Filename: "{app}\Framewring.exe"
Name: "{autodesktop}\{cm:AppTitle}"; Filename: "{app}\Framewring.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Framewring.exe"; Description: "{cm:LaunchProgram,{cm:AppTitle}}"; Flags: nowait postinstall skipifsilent
; update from the program itself (silent, with /FWUPDATE=1) - start the new version right away
Filename: "{app}\Framewring.exe"; Flags: nowait skipifnotsilent; Check: IsSelfUpdate

; Settings, queue and history (%APPDATA%\Framewring) are not touched on uninstall:
; a reinstall must not lose the compression history.

[Code]
function IsSelfUpdate: Boolean;
begin
  Result := ExpandConstant('{param:FWUPDATE|0}') = '1';
end;

; Установщик Framewring (Inno Setup 6). Собирается из packaging\release.py,
; который передаёт версию: ISCC /DAppVer=0.9.0 framewring.iss
; Ставится для текущего пользователя без прав администратора
; (%LOCALAPPDATA%\Programs\Framewring); данные — в %APPDATA%\Framewring.

#ifndef AppVer
  #define AppVer "0.0.0"
#endif
#define Src "..\build\dist\Framewring"

[Setup]
AppId={{8F3C2A61-5D7E-4B9A-9C1E-6A2F0D4B7E35}
AppName=Framewring Жмых
AppVersion={#AppVer}
AppVerName=Framewring Жмых {#AppVer}
AppPublisher=Framewring
AppPublisherURL=https://github.com/framewring
AppSupportURL=https://github.com/framewring
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
UninstallDisplayName=Framewring Жмых
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=2
LZMAUseSeparateProcess=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Framewring Жмых"; Filename: "{app}\Framewring.exe"
Name: "{autodesktop}\Framewring Жмых"; Filename: "{app}\Framewring.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Framewring.exe"; Description: "{cm:LaunchProgram,Framewring Жмых}"; Flags: nowait postinstall skipifsilent

; Настройки, очередь и история (%APPDATA%\Framewring) при удалении не трогаем:
; переустановка не должна терять историю сжатия.

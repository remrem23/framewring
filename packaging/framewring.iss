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
AppMutex=FramewringRunning
CloseApplications=yes
RestartApplications=no

[Languages]
; первый — запасной, если язык Windows не из списка
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
; китайский (упрощённый) — неофициальный перевод Inno Setup, лежит рядом
Name: "zh"; MessagesFile: "ChineseSimplified.isl"

[CustomMessages]
AppTitle=Framewring
ru.AppTitle=Framewring Жмых

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; при обновлении убираем старые библиотеки, чтобы не смешались с новыми
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{cm:AppTitle}"; Filename: "{app}\Framewring.exe"
Name: "{autodesktop}\{cm:AppTitle}"; Filename: "{app}\Framewring.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Framewring.exe"; Description: "{cm:LaunchProgram,{cm:AppTitle}}"; Flags: nowait postinstall skipifsilent

; Настройки, очередь и история (%APPDATA%\Framewring) при удалении не трогаем:
; переустановка не должна терять историю сжатия.

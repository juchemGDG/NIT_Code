; Inno-Setup-Skript fuer NIT_Code (Windows-Installer, "Setup.exe").
;
; Erzeugt aus dem PyInstaller-One-Folder-Build (dist\NIT_Code) ein klassisches
; Setup, das pro Benutzer ohne Admin-Rechte installiert (wie Thonny).
;
; Kompiliert wird ueber release\scripts\build_windows.ps1, das die Versionsnummer
; aus nit_code/config.py liest und hier als /DAppVersion uebergibt.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "NIT_Code"
#define AppPublisher "NIT"
#define AppExeName "NIT_Code.exe"

[Setup]
; AppId fix lassen, damit Updates die alte Version sauber ersetzen.
AppId={{8F4D2A1C-7B3E-4C9A-9D2F-1E5A6B7C8D90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}

; --- Per-User-Installation ohne Admin-Rechte (wie Thonny) ---
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}

OutputDir=downloads\windows
OutputBaseFilename=NIT_Code-Setup
SetupIconFile=NIT_Code.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; x64compatible deckt natives x64 UND ARM64-Windows (x64-Emulation) ab.
; NICHT "x64" verwenden: Inno Setup >=6.3 deutet das in das restriktive "x64os"
; um, das ARM64-Windows-11-Geraete ausschliesst.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associatepy"; Description: "Python-Dateien (.py) mit {#AppName} oeffnen"; Flags: unchecked

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; .py-Dateizuordnung, nur pro Benutzer (HKCU) und nur wenn der Nutzer es waehlt.
; Ueberschreibt nicht den globalen Standard, sondern setzt die User-Wahl.
Root: HKCU; Subkey: "Software\Classes\.py\OpenWithProgids"; ValueType: string; ValueName: "{#AppName}.pyfile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatepy
Root: HKCU; Subkey: "Software\Classes\{#AppName}.pyfile"; ValueType: string; ValueName: ""; ValueData: "Python-Datei"; Flags: uninsdeletekey; Tasks: associatepy
Root: HKCU; Subkey: "Software\Classes\{#AppName}.pyfile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associatepy
Root: HKCU; Subkey: "Software\Classes\{#AppName}.pyfile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associatepy

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

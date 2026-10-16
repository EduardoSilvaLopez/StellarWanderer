; Inno Setup script: packs temp\dist\StellarWanderer (built by StellarWanderer.spec) into a Windows installer.
; Build with tools\build_windows.ps1, or compile this file with the Inno Setup compiler (ISCC.exe).
; Paths here are relative to this file's folder (tools), so the project folder is "..".

#define AppName "Stellar Wanderer"
#define AppVersion "0.1.0"
#define AppExe "StellarWanderer.exe"

[Setup]
; Keep this GUID fixed across releases so upgrades replace the old version.
AppId={{6F3C2B1E-8A4D-4C7B-9E21-5D0A7B3F4C18}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Eduardo Silva Lopez
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=StellarWanderer-Setup-{#AppVersion}
SetupIconFile=..\common\resources\presentation\game_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\temp\dist\StellarWanderer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; Savefiles and logs live in %LOCALAPPDATA%\StellarWanderer, not here, so they are kept on uninstall.

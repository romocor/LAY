; Instalador de LAY (Inno Setup 6) -> dist/LAY_Setup_<ver>.exe
#define Ver GetEnv("LAY_VERSION")
#if Ver == ""
  #define Ver "2.4.0"
#endif

[Setup]
AppName=LAY
AppVersion={#Ver}
AppPublisher=Robert
DefaultDirName={localappdata}\Programs\LAY
DefaultGroupName=LAY
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=LAY_Setup_{#Ver}
SetupIconFile=lay.ico
UninstallDisplayIcon={app}\LAY.exe
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Acceso directo en el escritorio"
Name: "inicio"; Description: "Iniciar LAY con Windows"; Flags: unchecked

[Files]
Source: "..\dist\LAY\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\LAY"; Filename: "{app}\LAY.exe"
Name: "{group}\LAY (modo texto)"; Filename: "{app}\LAY-cli.exe"; Parameters: "--texto"
Name: "{group}\Configuración de LAY"; Filename: "{%USERPROFILE}\.lay"
Name: "{autodesktop}\LAY"; Filename: "{app}\LAY.exe"; Tasks: escritorio
Name: "{userstartup}\LAY"; Filename: "{app}\LAY.exe"; Tasks: inicio

[Run]
Filename: "{app}\LAY.exe"; Description: "Abrir LAY ahora"; Flags: nowait postinstall skipifsilent

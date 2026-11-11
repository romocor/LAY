; Instalador de LAY (Inno Setup 6) -> dist/LAY_Setup_<ver>.exe
#define Ver GetEnv("LAY_VERSION")
#if Ver == ""
  #define Ver "2.6.0"
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
Name: "ia"; Description: "Instalar IA GRATUITA local (Ollama + modelo adecuado a esta PC, descarga de 1-7 GB)"
Name: "aplausos"; Description: "Abrir LAY con dos palmadas (detector liviano al iniciar Windows)"
Name: "escritorio"; Description: "Acceso directo en el escritorio"
Name: "inicio"; Description: "Abrir LAY completo al iniciar Windows"; Flags: unchecked

[Files]
Source: "..\dist\LAY\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\LAY"; Filename: "{app}\LAY.exe"
Name: "{group}\LAY (modo texto)"; Filename: "{app}\LAY-cli.exe"; Parameters: "--texto"
Name: "{group}\Configuración de LAY"; Filename: "{%USERPROFILE}\.lay"
Name: "{autodesktop}\LAY"; Filename: "{app}\LAY.exe"; Tasks: escritorio
Name: "{userstartup}\LAY"; Filename: "{app}\LAY.exe"; Tasks: inicio
Name: "{userstartup}\LAY Palmadas"; Filename: "{app}\LAY.exe"; Parameters: "--rol aplausos"; Tasks: aplausos

[Run]
; IA local: ventana con barra de progreso (detecta RAM/GPU y elige el modelo). Si falla, LAY ofrece reintentar en Configuración.
Filename: "{app}\LAY-cli.exe"; Parameters: "--rol instalar-ia"; Tasks: ia; StatusMsg: "Instalando la IA gratuita local (puede tardar unos minutos)..."; Flags: waituntilterminated
Filename: "{app}\LAY.exe"; Parameters: "--rol aplausos"; Tasks: aplausos; Flags: nowait runhidden
Filename: "{app}\LAY.exe"; Description: "Abrir LAY ahora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM LAY.exe /T"; Flags: runhidden; RunOnceId: "CerrarLAY"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM LAY-cli.exe /T"; Flags: runhidden; RunOnceId: "CerrarLAYcli"

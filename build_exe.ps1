<#  Empaqueta LAY en .exe (Windows).
    Uso:  powershell -ExecutionPolicy Bypass -File build_exe.ps1
    Salida:
      dist\LAY\LAY.exe              app portable (carpeta)
      dist\LAY_portable_<ver>.zip   la carpeta comprimida
      dist\LAY_Setup_<ver>.exe      instalador (si Inno Setup está instalado)
#>
param([string]$Version = "2.3.0", [switch]$SinTests)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -q --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt pyinstaller==6.11.1

if (-not $SinTests) {
  & .\.venv\Scripts\python.exe -m pytest -q
  if ($LASTEXITCODE -ne 0) { throw "Tests en rojo: no se empaqueta." }
}

# Modelo de voz offline (Vosk small-es, ~39 MB) para que el exe funcione sin internet para la palabra clave
$vosk = "packaging\models\vosk-es"
if (-not (Test-Path "$vosk\am")) {
  New-Item -ItemType Directory -Force packaging\models | Out-Null
  Write-Host "Descargando modelo de voz Vosk..." -ForegroundColor Cyan
  Invoke-WebRequest "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip" -OutFile packaging\models\vosk.zip
  Expand-Archive packaging\models\vosk.zip -DestinationPath packaging\models -Force
  Rename-Item packaging\models\vosk-model-small-es-0.42 vosk-es
  Remove-Item packaging\models\vosk.zip
}

Push-Location packaging
& ..\.venv\Scripts\pyinstaller.exe lay.spec --noconfirm --clean --distpath ..\dist --workpath ..\build
Pop-Location
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló." }

# Humo: el exe arranca y el MCP lista herramientas
& .\dist\LAY\LAY-cli.exe --version
if ($LASTEXITCODE -ne 0) { throw "LAY-cli.exe no arranca." }

Compress-Archive -Path dist\LAY\* -DestinationPath "dist\LAY_portable_$Version.zip" -Force

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
  $env:LAY_VERSION = $Version
  & $iscc packaging\lay.iss | Out-Null
  Write-Host "Instalador: dist\LAY_Setup_$Version.exe" -ForegroundColor Cyan
} else {
  Write-Host "Inno Setup no encontrado (winget install JRSoftware.InnoSetup). Quedó el portable." -ForegroundColor Yellow
}
Write-Host "Listo: dist\LAY\LAY.exe" -ForegroundColor Green

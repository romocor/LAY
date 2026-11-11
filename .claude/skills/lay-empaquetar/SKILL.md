---
name: lay-empaquetar
description: Cómo empaquetar LAY como .exe de Windows (PyInstaller + Inno Setup + GitHub Actions). Robert SIEMPRE recibe la entrega como .exe; usar al cerrar cada fase o al pedir "entrégamelo".
---
# Empaquetar LAY

**Regla de entrega:** toda fase o cambio que Robert vaya a usar se entrega como `LAY_Setup_<ver>.exe` (instalador) + `LAY_portable_<ver>.zip`. Nunca solo código fuente.

## Piezas
- `lay.py` = entrada única. `LAY.exe` (sin consola) lanza todo; `LAY-cli.exe` (con consola) corre `--rol mcp|hub|gestos|voz`. Los loops se relanzan con `LAY-cli.exe --rol X` (`comando_rol`), nunca con `python -m`.
- `packaging/lay.spec`: dos EXE + un COLLECT (one-folder; MediaPipe en one-file arranca demasiado lento).
- `packaging/lay.iss`: instalador por usuario (sin admin), acceso directo, inicio con Windows opcional.
- `build_exe.ps1`: venv → tests → PyInstaller → humo → zip → Inno Setup.
- `.github/workflows/build-exe.yml`: lo mismo en `windows-latest`; tag `vX.Y.Z` = Release.

## Rutas en el exe
- Recursos empaquetados (overlay, config por defecto): `sys._MEIPASS` → `lay_core.config.ROOT`.
- Editables del usuario: `%USERPROFILE%\.lay\lay.json` y `%USERPROFILE%\.lay\.env` (se copian la primera vez).
- Nunca escribir junto al exe (puede estar en una carpeta sin permisos).

## Al agregar dependencias
Si es un paquete con datos o imports dinámicos, agregarlo al `collect_all(...)` o a `hiddenimports` del spec y reconstruir.

## Versionado
`2.<fase>.<parche>`. Subir versión en `build_exe.ps1 -Version`, `packaging/version.txt` y `lay.py --version`.

## Claude Desktop con el exe
```json
{"mcpServers": {"lay-pc": {"command": "C:\\Users\\<tú>\\AppData\\Local\\Programs\\LAY\\LAY-cli.exe", "args": ["--rol", "mcp"]}}}
```

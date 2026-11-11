---
description: Empaqueta LAY en .exe (portable + instalador) y verifica que arranca
model: sonnet
---
Sigue la skill `lay-empaquetar`.
1. Si estás en Windows: `powershell -ExecutionPolicy Bypass -File build_exe.ps1 -Version <versión>`.
   Si no estás en Windows: confirma que el workflow `.github/workflows/build-exe.yml` está al día y
   pídeme permiso para hacer push y disparar el build en GitHub Actions.
2. Prueba de humo: `dist\LAY\LAY-cli.exe --version` y `dist\LAY\LAY-cli.exe --rol mcp` (debe quedarse esperando por stdio).
3. Entrégame la ruta de `dist\LAY_Setup_<ver>.exe` y del portable `.zip`, con el tamaño de cada uno.
Si el build falla por un import faltante, agrégalo a `hiddenimports` en packaging/lay.spec y repite (máx. 3 veces).

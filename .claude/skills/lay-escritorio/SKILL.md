---
name: lay-escritorio
description: Control de Windows en LAY — monitores, ventanas, posiciones, workspaces, apps, teclado y búsqueda de archivos. Usar al tocar lay_core/escritorio.py, archivos.py o config/lay.json.
---
# Escritorio

- Monitores numerados de izquierda a derecha (1, 2, 3) por `x`.
- Proceso DPI-aware per-monitor (se activa al importar escritorio.py en Windows).
- Ventana elegida: visible > coincidencia de título (exacto > empieza/termina > contiene) > tamaño. Excluye títulos de LAY (`TITULOS_PROPIOS`).
- Monitor inexistente → último monitor + `aviso`. `monitor_vecino(direccion)` para gestos.
- Posiciones válidas: maximizada, completa, izquierda, derecha, arriba, abajo, arriba-izquierda, arriba-derecha, abajo-izquierda, abajo-derecha, centro.
- Apps y workspaces viven en `config/lay.json` (alias → comando/URL/ruta). Un workspace es una lista de `{app|abrir, titulo, monitor, posicion}`; `titulo` es el texto que buscará en la barra de título (espera hasta 5 s a que aparezca).
- Búsqueda: si existe `es.exe` (Everything CLI) se usa; si no, `os.walk` acotado a `raices_busqueda` con límite de 15 s.
- Escritura de texto vía portapapeles (soporta tildes/ñ) y restaura el portapapeles.
- Atajos bloqueados: alt+f4, ctrl+alt+delete, shift+delete. Cerrar ventana = sensible.

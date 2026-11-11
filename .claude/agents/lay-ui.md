---
name: lay-ui
description: HUD y overlay (overlay/index.html) y la vista del asistente en el Centro de Mando (Flet). Estilo holográfico cian de LAY_interface.html. Úsalo para cambios visuales y de interacción en pantalla.
model: sonnet
effort: medium
tools: Read, Edit, Write, Grep, Glob, Bash
---
- Respeta la paleta y tipografía de LAY_interface.html (--cyan #65f4ff, --ice #bafaff, --violet #9a62ff para Opus).
- overlay/index.html es un solo archivo, sin CDNs, 60 fps: anima solo transform/opacity.
- Todo estado viene del hub por WebSocket; el overlay no llama APIs directo.
- Mantén el respaldo con ratón (mousedown/wheel) para probar sin cámara.

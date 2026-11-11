---
name: lay-gestos
description: Vocabulario, umbrales y forma de agregar/calibrar gestos de mano en LAY (loops/gestos.py + overlay). Usar para cualquier tarea de gestos, cámara, MediaPipe o modo mouse.
---
# Gestos de LAY

## Vocabulario actual
| Gesto | Detección | Overlay | Modo mouse |
|---|---|---|---|
| PINCH | pulgar–índice < 0,33·mano (suelta > 0,45) | agarrar tarjeta | mouseDown |
| ARRASTRAR | pinch + movimiento | mover tarjeta | drag |
| TAP | pinch < 0,28 s y < 3 % movimiento | abrir/cerrar tarjeta | click |
| DOBLE TAP | 2 taps < 0,45 s | abrir archivo real | doble click (abrir carpeta) |
| QUIETO 1 s | pinch y velocidad < 0,05/s | rotar 3D | — |
| DOS MANOS | ambos pinch, distancia relativa | escalar | — |
| CLAP | palmas (lm 9) < 0,55·mano, dedos arriba | anillo central | — |
| SWIPE | 3+ dedos, vx > 2,2/s | lanzar imagen a otro monitor | — |
| DOS DEDOS | índice+medio estirados, anular+meñique doblados; Δy > 2,5 % | desplazar grilla | rueda (scroll) |
| PALMA 1,5 s | 4 dedos extendidos | alternar modo | alternar modo (HUD se minimiza) |
| PUÑO 0,7 s | 0 dedos | callar a LAY | callar a LAY |
| PUÑO 2 s | 0 dedos | pausa | pausa |

Landmarks MediaPipe: 0 muñeca, 4 pulgar, 8 índice, 12 medio, 16 anular, 20 meñique; bases 5, 9, 13, 17.

## Coordenadas
- `main()` voltea el frame ANTES de MediaPipe (su lateralidad asume selfie). Todo x ya está espejado: no usar `1 - x` en ningún lado.
- Cursor: punto medio pulgar–índice → `OneEuro(0.3, 20)`. Modo mouse: escritorio virtual (`escritorio_virtual()`), margen 15 %, zona muerta 6 px.
- Umbrales en `lay.json -> gestos` (`pinch_on`, `pinch_off`, `swipe_vel`, `complejidad`); `--calibrar` los escribe.

## Reglas
- Umbral siempre relativo a `tam(lm) = dist(0, 9)`. Nunca píxeles.
- Gesto continuo = histéresis; gesto discreto = tiempo mínimo + cooldown.
- Evento nuevo: emitir `{"tipo":"gesto","gesto":"<nombre>", ...}` desde `Clasificador`, manejarlo en `gesto()` de `overlay/index.html`, agregarlo a `#ayuda`, a esta tabla y a `tests/test_gestos.py`.
- Calibrar: `python -m loops.gestos --debug` muestra la cámara con los puntos.
- En modo mouse `pyautogui.FAILSAFE` sigue activo (esquina = abortar).

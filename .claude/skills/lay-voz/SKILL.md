---
name: lay-voz
description: Cómo funciona y se modifica la conversación por voz de LAY (palabra clave Vosk, VAD, STT, TTS en streaming, interrupciones, router Sonnet/Opus, confirmaciones). Usar para loops/voz.py, loops/audio.py, loops/locutor.py, lay_core/cerebro.py o router.py.
---
# Voz de LAY

## Flujo
micrófono (PyAudio 16 kHz, bloques 30 ms) → `DetectorWake` (Vosk, gramática cerrada) → `Segmentador` (VAD por energía, pre-roll 1 s, fin tras 0,8 s de silencio) → Google STT es-PE → `quitar_wake` → `Cerebro.responder(al_texto=...)` en streaming → `Fraseador` → `Locutor` (edge-tts es-PE-AlexNeural; respaldo SAPI offline).

## Estados (HUD)
standby · escuchando · pensando · hablando · abierto (8 s sin repetir "LAY").

## Reglas
- "LAY" = "ley" para el modelo español. Solo cuenta como 1.ª palabra o tras "oye/hola/ok". Vosk: `texto == frase` o `startswith(frase + " ")`; nunca `"[unk] ley"`.
- Mientras `ocupado` (pensando o hablando) el micrófono solo atiende `FRASES_CALLAR`.
- `callar()` sube `turno_id`: todo texto que siga llegando de ese turno se descarta.
- Interrumpir: voz ("LAY, para"), puño 1 s (gesto `pausa`), Esc (`voz.callar` por el hub).
- Latencia = fin de la frase grabada → primer audio (`hud.latencia`). Objetivo < 1,5 s en `rapido`.
- Ajustes en `lay.json`: `confianza_wake` (0,6–0,9), `microfono` (índice PyAudio), `voz_tts`.

## Router
`rapido` Sonnet sin thinking · `normal` Sonnet + 2k · `profundo` Opus + 8k · escala si falla. "Piensa bien…" fuerza Opus.

## Confirmaciones (no negociable)
Tool sensible → `requiere_confirmacion` → LAY pregunta → solo `AFIRMA` en la respuesta habilita `confirmar=true`; `NIEGA` ("no", "cancela") la anula. Nunca relajar.

## Tests
`tests/test_audio.py`, `test_locutor.py`, `test_voz.py`, `test_cerebro_confirmacion.py` (audio sintético y fakes, sin micrófono).

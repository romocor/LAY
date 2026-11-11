---
description: Tarea puntual con selección automática de modelo (Sonnet fácil / Opus difícil)
argument-hint: <descripción de la tarea>
---
Tarea: $ARGUMENTS

Clasifícala antes de empezar:
- FÁCIL (un archivo, patrón conocido, config, texto, UI menor): hazla tú o delega a un subagente Sonnet (`lay-escritorio`, `lay-mcp`, `lay-integraciones`, `lay-ui`).
- DIFÍCIL (varios módulos, algoritmo, tiempo real, seguridad, bug sin causa clara): delega a `lay-arquitecto` para el plan y luego a `lay-vision` / `lay-voz` / `lay-seguridad` (Opus).
Al terminar, `lay-qa` verifica. Dime en una línea qué modelo usaste y por qué.

---
description: Ejecuta la siguiente fase pendiente de PLAN.md con el loop planificar→implementar→verificar→corregir
argument-hint: [número de fase opcional]
model: opus
---
Fase objetivo: $ARGUMENTS (si está vacío, la primera fase de PLAN.md con tareas `- [ ]`).

LOOP DE DESARROLLO (máximo 3 vueltas por tarea):
1. PLANIFICAR → subagente `lay-arquitecto`: desglosa la fase en tareas con criterio de aceptación y el subagente asignado.
2. IMPLEMENTAR → delega cada tarea a su subagente (en paralelo si no tocan los mismos archivos):
   - mecánico/bien definido → `lay-escritorio`, `lay-mcp`, `lay-integraciones`, `lay-ui` (Sonnet)
   - algoritmos/tiempo real/seguridad → `lay-vision`, `lay-voz`, `lay-seguridad` (Opus)
3. VERIFICAR → `lay-qa`.
4. Si RECHAZADO → devuelve los fallos al mismo subagente y vuelve al paso 2. Tras 3 vueltas sin aprobar, detente y explícame el bloqueo.
5. Si APROBADO → ejecuta `/exe` (versión 2.<fase>.0), marca `- [x]` en PLAN.md y entrégame el instalador .exe con 3 líneas de qué quedó y cómo probarlo.
No hagas commit sin preguntarme.

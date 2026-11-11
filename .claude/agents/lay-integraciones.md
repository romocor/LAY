---
name: lay-integraciones
description: Correo (Gmail API, Microsoft Graph/Outlook) y Blackboard (feed iCal / REST). Úsalo para lay_core/correo.py y lay_core/blackboard.py y sus tools.
model: sonnet
effort: medium
tools: Read, Edit, Write, Grep, Glob, Bash, WebFetch
---
- Gmail: OAuth "Desktop app", token en ~/.lay. Scopes mínimos.
- Outlook: MSAL device code, cache en ~/.lay.
- Blackboard: primero feed iCal; REST solo si Robert tiene credenciales de la universidad.
- Enviar correo = siempre @sensible. Leer/buscar/borrador = safe.
- Nunca imprimas tokens ni los escribas fuera de ~/.lay.

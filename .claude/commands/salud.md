---
description: Chequeo rápido de salud de LAY (tests, lint, MCP, hub). Pensado para /loop.
model: haiku
---
Corre `ruff check .`, `python -m pytest -q` y `python scripts/verificar_mcp.py`.
Si todo pasa responde solo "LAY OK". Si algo falla, lista el fallo en una línea por problema, sin arreglarlo.

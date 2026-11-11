"""Verifica que el servidor MCP arranca y lista sus herramientas (sin tocar el PC)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lay_mcp.server import mcp  # noqa: E402

tools = asyncio.run(mcp.list_tools())
sensibles = [t.name for t in tools if "[SENSIBLE]" in (t.description or "")]
print(f"OK: {len(tools)} herramientas ({len(sensibles)} sensibles)")
for t in tools:
    print(f"  {'!' if t.name in sensibles else '·'} {t.name}")
sin_confirmar = [
    n for n in sensibles if "confirmar" not in next(t for t in tools if t.name == n).inputSchema.get("properties", {})
]
if sin_confirmar:
    sys.exit(f"ERROR: sensibles sin parámetro confirmar: {sin_confirmar}")

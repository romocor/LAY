"""Adaptador: registra las herramientas de LAY en el ToolManager existente de
centro_mando, así el panel del asistente (Flet) también controla el PC.

Copiar a centro_mando/ai/tools/lay_pc_tools.py y en el arranque:
    from ai.tools import lay_pc_tools
    tool_manager.register_all(lay_pc_tools.build_tools())
Requiere que la carpeta de LAY esté en PYTHONPATH (o instalada con pip -e).
"""

from __future__ import annotations

import asyncio
import json

from ai.core.tool_manager import Tool


def build_tools() -> list[Tool]:
    from lay_mcp.server import mcp

    tools: list[Tool] = []
    for t in asyncio.run(mcp.list_tools()):
        sensible = "[SENSIBLE]" in (t.description or "")

        def ejecutar(data: dict, _n=t.name, _s=sensible) -> dict:
            if _s:
                data = {**data, "confirmar": True}  # PermissionManager ya preguntó
            res = asyncio.run(mcp.call_tool(_n, data))
            bloques = res[0] if isinstance(res, tuple) else res
            texto = "\n".join(getattr(b, "text", str(b)) for b in bloques)
            try:
                return {"resultado": json.loads(texto)}
            except json.JSONDecodeError:
                return {"resultado": texto}

        schema = dict(t.inputSchema)
        schema.get("properties", {}).pop("confirmar", None)
        tools.append(
            Tool(
                name=t.name,
                description=t.description or "",
                parameters=schema,
                executor=ejecutar,
                permission="sensitive" if sensible else "safe",
                confirmation_title="LAY necesita tu confirmación",
                confirmation_message=lambda d, _n=t.name: f"LAY quiere ejecutar '{_n}' con: {d}. ¿Confirmas?",
            )
        )
    return tools

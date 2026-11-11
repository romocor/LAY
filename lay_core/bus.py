"""Cliente del hub de eventos (loops/hub.py). Cualquier proceso (MCP, voz,
gestos) publica aquí y el overlay/HUD lo recibe por WebSocket."""

from __future__ import annotations

import httpx

from lay_core.config import HUB_TOKEN, HUB_URL


def publicar(tipo: str, **datos) -> dict:
    try:
        r = httpx.post(
            f"{HUB_URL}/evento",
            json={"tipo": tipo, **datos},
            headers={"Authorization": f"Bearer {HUB_TOKEN}"} if HUB_TOKEN else {},
            timeout=3,
        )
        return r.json()
    except httpx.HTTPError as exc:
        return {"error": f"Hub de LAY no disponible ({exc}). Arranca: python -m loops.hub"}

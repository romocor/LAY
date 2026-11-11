"""MCP por HTTP con token Bearer, para usar LAY desde fuera de casa.

Exponer SOLO por Tailscale (red privada), nunca con puerto abierto en el router:
  1. Instala Tailscale en el PC y en el celular.
  2. LAY_MCP_TOKEN=<token largo> python -m lay_mcp.server --http --port 8766
  3. URL: http://<nombre-pc>.<tailnet>.ts.net:8766/mcp  + header Authorization.
"""

from __future__ import annotations

import os
import secrets

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        esperado = os.environ["LAY_MCP_TOKEN"]
        recibido = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not secrets.compare_digest(recibido, esperado):
            return JSONResponse({"error": "no autorizado"}, status_code=401)
        return await call_next(request)


def run_http(mcp, port: int) -> None:
    app = mcp.streamable_http_app()
    app.add_middleware(TokenMiddleware)
    uvicorn.run(app, host=os.getenv("LAY_BIND", "0.0.0.0"), port=port)

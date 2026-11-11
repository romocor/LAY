"""API de Configuración dentro de la app (solo desde esta PC; la guardia del hub bloquea lo remoto).

GET  /api/config                 configuración + qué claves están puestas (nunca sus valores)
POST /api/config                 {"config": {...parcial...}, "secretos": {"GEMINI_API_KEY": "..."}}
POST /api/probar/blackboard      {"url"} -> cuántos eventos y los próximos
POST /api/probar/ia              {"proveedor"} -> responde "hola" y mide la latencia
GET  /api/ia/estado              hardware, recomendación, Ollama, modelos
POST /api/ia/preparar            instala/descarga en segundo plano (progreso por WS "ia.progreso")
POST /api/gmail/credenciales     JSON de "App de escritorio" de Google
GET  /api/remoto/info            IP de Tailscale, URL y si hay token
POST /api/remoto/token           genera un token nuevo (lo muestra UNA vez) y activa el remoto
GET  /api/remoto/qr              QR (SVG) con la URL + token para el celular
"""

from __future__ import annotations

import asyncio
import ipaddress
import secrets
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from lay_core import config as cfg
from lay_core import proveedores

SECRETOS_PERMITIDOS = {
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "ANTHROPIC_API_KEY",
    "BLACKBOARD_ICS_URL",
    "OUTLOOK_CLIENT_ID",
    "LAY_HUB_TOKEN",
}
CONFIG_PERMITIDA = {
    "nombre",
    "usuario",
    "wake_words",
    "confianza_wake",
    "microfono",
    "voz_tts",
    "camara_indice",
    "carpeta_galeria",
    "raices_busqueda",
    "ia",
    "aplausos",
    "remoto",
    "apps",
    "workspaces",
    "gestos",
    "modo_mouse_por_defecto",
}
VOCES = [
    "es-PE-AlexNeural",
    "es-PE-CamilaNeural",
    "es-MX-JorgeNeural",
    "es-MX-DaliaNeural",
    "es-ES-AlvaroNeural",
    "es-CO-GonzaloNeural",
]
_preparando = threading.Lock()


def ip_tailscale() -> str | None:
    import psutil

    red = ipaddress.ip_network("100.64.0.0/10")
    for direcciones in psutil.net_if_addrs().values():
        for d in direcciones:
            try:
                if d.family.name == "AF_INET" and ipaddress.ip_address(d.address) in red:
                    return d.address
            except (ValueError, AttributeError):
                continue
    return None


def estado_config() -> dict:
    import os

    from lay_core.configurar import leer_env

    env = {**leer_env(), **{k: v for k, v in os.environ.items() if k in SECRETOS_PERMITIDOS}}
    c = cfg.CONFIG
    return {
        "config": {k: getattr(c, k) for k in sorted(CONFIG_PERMITIDA)},
        "secretos": {k: bool(env.get(k)) for k in sorted(SECRETOS_PERMITIDOS)},
        "blackboard_url": _ocultar_url(env.get("BLACKBOARD_ICS_URL", "")),
        "gmail_configurado": (cfg.DATA_DIR / "gmail_credentials.json").exists(),
        "proveedores": proveedores.NOMBRES,
        "modelos_defecto": proveedores.MODELOS_DEFECTO,
        "voces": VOCES,
        "version": _version(),
    }


def _ocultar_url(u: str) -> str:
    """El enlace iCal de Blackboard contiene un token personal: solo se muestra el dominio."""
    if not u:
        return ""
    from urllib.parse import urlparse

    return f"{urlparse(u).netloc}/…(configurado)"


def _version() -> str:
    try:
        import tomllib

        return tomllib.loads((cfg.ROOT / "pyproject.toml").read_text())["project"]["version"]
    except Exception:
        return "2.x"


def registrar(app: FastAPI, difundir) -> None:
    @app.get("/api/config")
    async def leer():
        return estado_config()

    @app.post("/api/config")
    async def escribir(body: dict):
        from lay_core.configurar import escribir_env

        cambios = {k: v for k, v in (body.get("config") or {}).items() if k in CONFIG_PERMITIDA}
        secretos = {k: str(v).strip() for k, v in (body.get("secretos") or {}).items() if k in SECRETOS_PERMITIDOS}
        if "BLACKBOARD_ICS_URL" in secretos:
            secretos["BLACKBOARD_ICS_URL"] = secretos["BLACKBOARD_ICS_URL"].replace("webcal://", "https://")
        if secretos:
            escribir_env(secretos, cfg.DATA_DIR / ".env")
        if cambios:
            cfg.guardar(cambios)
        else:
            cfg.recargar()
        await difundir({"tipo": "config.cambiada", "claves": sorted(cambios) + sorted(secretos)})
        return {"ok": True, **estado_config()}

    @app.post("/api/probar/blackboard")
    async def probar_bb(body: dict):
        import httpx

        from lay_core import blackboard

        url = (body.get("url") or __import__("os").environ.get("BLACKBOARD_ICS_URL", "")).replace(
            "webcal://", "https://"
        )
        if not url.startswith("https://"):
            raise HTTPException(400, "Pega el enlace del calendario de Blackboard (empieza con https:// o webcal://)")
        try:
            r = await asyncio.to_thread(lambda: httpx.get(url, timeout=20, follow_redirects=True))
            r.raise_for_status()
            eventos = blackboard.parsear_ics(r.content)
        except Exception as exc:
            return {"ok": False, "error": f"No pude leer el calendario ({type(exc).__name__})."}
        from datetime import datetime, timezone

        ahora = datetime.now(timezone.utc)
        prox = sorted((e for e in eventos if e["fecha"] >= ahora), key=lambda e: e["fecha"])[:3]
        return {
            "ok": True,
            "eventos": len(eventos),
            "proximos": [
                {"titulo": e["titulo"], "fecha": e["fecha"].astimezone().strftime("%d/%m %H:%M")} for e in prox
            ],
        }

    @app.post("/api/probar/ia")
    async def probar_ia(body: dict):
        nombre = body.get("proveedor") or cfg.CONFIG.ia.get("proveedor", "ollama")

        def prueba():
            t0 = time.monotonic()
            prov = proveedores.crear(nombre, cfg.CONFIG.ia)
            t = prov.turno("Responde solo: hola", [{"rol": "usuario", "texto": "hola"}], [], "rapido", 20)
            return {"ok": True, "respuesta": t.texto[:80], "ms": int((time.monotonic() - t0) * 1000)}

        try:
            return await asyncio.to_thread(prueba)
        except proveedores.ProveedorNoDisponible as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}

    @app.post("/api/diagnostico")
    async def diagnostico_api(body: dict | None = None):
        """Corre el diagnóstico completo en segundo plano; el resultado llega como hud.panel."""
        from lay_mcp import server

        return server.diagnostico_ejecutar()

    @app.get("/api/ia/estado")
    async def ia_estado():
        from lay_core import ia_local

        return await asyncio.to_thread(ia_local.estado)

    @app.post("/api/ia/preparar")
    async def ia_preparar(body: dict | None = None):
        from lay_core import ia_local

        if not _preparando.acquire(blocking=False):
            return {"ok": False, "error": "Ya se está instalando."}
        bucle = asyncio.get_running_loop()

        def avisar(etapa: str, pct: float, texto: str) -> None:
            asyncio.run_coroutine_threadsafe(
                difundir({"tipo": "ia.progreso", "etapa": etapa, "pct": round(pct, 1), "texto": texto}), bucle
            )

        def trabajo():
            try:
                r = ia_local.preparar(avisar, (body or {}).get("modelos"))
                asyncio.run_coroutine_threadsafe(difundir({"tipo": "ia.lista", **r}), bucle)
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(difundir({"tipo": "ia.error", "detalle": str(exc)[:300]}), bucle)
            finally:
                _preparando.release()

        threading.Thread(target=trabajo, daemon=True).start()
        return {"ok": True}

    @app.post("/api/gmail/credenciales")
    async def gmail_creds(body: dict):
        import json

        if "installed" not in body:
            raise HTTPException(
                400, "Ese JSON no es de 'App de escritorio'. En Google Cloud elige ese tipo de cliente."
            )
        (cfg.DATA_DIR / "gmail_credentials.json").write_text(json.dumps(body), encoding="utf-8")
        return {"ok": True}

    @app.get("/api/remoto/info")
    async def remoto_info():
        import os

        ip = ip_tailscale()
        return {
            "activo": cfg.CONFIG.remoto.get("activo", False),
            "tailscale_ip": ip,
            "url": f"http://{ip}:{cfg.CONFIG.hub_port}/remoto" if ip else None,
            "token_configurado": bool(os.environ.get("LAY_HUB_TOKEN")),
            "solo_tailscale": cfg.CONFIG.remoto.get("solo_tailscale", True),
        }

    @app.post("/api/remoto/token")
    async def remoto_token():
        import os

        from lay_core.configurar import escribir_env

        token = secrets.token_urlsafe(24)
        escribir_env({"LAY_HUB_TOKEN": token}, cfg.DATA_DIR / ".env")
        os.environ["LAY_HUB_TOKEN"] = token
        cfg.guardar({"remoto": {"activo": True}})
        return {"ok": True, "token": token, "aviso": "Reinicia LAY para que escuche conexiones del celular."}

    @app.get("/api/remoto/qr")
    async def remoto_qr():
        import os

        import qrcode
        import qrcode.image.svg

        ip, token = ip_tailscale(), os.environ.get("LAY_HUB_TOKEN")
        if not (ip and token):
            raise HTTPException(409, "Instala Tailscale y genera el token primero.")
        url = f"http://{ip}:{cfg.CONFIG.hub_port}/remoto#token={token}"
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
        return Response(img.to_string(encoding="unicode"), media_type="image/svg+xml")

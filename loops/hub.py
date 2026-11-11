"""LOOP 0 — Hub de eventos (siempre encendido).

  python -m loops.hub

- WebSocket /ws      -> overlay/HUD se suscribe y recibe todo.
- POST /evento       -> MCP, voz y gestos publican.
- POST /api/comando  -> texto para LAY (local, o remoto desde el celular con token).
- GET  /archivo      -> sirve imágenes locales al overlay (solo rutas permitidas).
- GET  /             -> sirve el overlay (overlay/index.html).
- /api/config, /api/ia/*  -> Configuración dentro de la app (solo desde esta PC).
- GET  /remoto       -> página para el celular (Tailscale + token).

SEGURIDAD: desde esta PC (127.0.0.1) todo está permitido. Desde fuera SOLO /remoto,
/api/comando y /ws en modo lectura, siempre con token, y por defecto solo por Tailscale.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import secrets
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from lay_core.config import CONFIG, ROOT
from lay_core.seguridad import ruta_permitida

app = FastAPI(title="LAY hub")
clientes: set[WebSocket] = set()
remotos: set[WebSocket] = set()  # celulares: solo reciben, nunca envían eventos
cola_comandos: asyncio.Queue = asyncio.Queue()

TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
RUTAS_REMOTAS = {"/remoto", "/api/comando", "/api/remoto/ping"}


def es_local(host: str | None) -> bool:
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return host in ("testclient", "localhost")


def token_valido(recibido: str | None) -> bool:
    esperado = os.environ.get("LAY_HUB_TOKEN", "")
    return bool(esperado) and bool(recibido) and secrets.compare_digest(recibido.strip(), esperado)


def motivo_rechazo_remoto(host: str | None, ruta: str, token: str | None) -> str | None:
    """None si se permite. Reglas para conexiones que NO vienen de esta PC."""
    if not CONFIG.remoto.get("activo"):
        return "El acceso remoto está desactivado (Configuración → Remoto)."
    if CONFIG.remoto.get("solo_tailscale", True):
        try:
            if ipaddress.ip_address(host or "") not in TAILSCALE:
                return "Solo se permite desde Tailscale."
        except ValueError:
            return "Origen desconocido."
    if ruta not in RUTAS_REMOTAS and ruta != "/ws":
        return "Ruta no disponible en remoto."
    if ruta != "/remoto" and not token_valido(token):
        return "Token inválido."
    return None


@app.middleware("http")
async def guardia(request: Request, call_next):
    host = request.client.host if request.client else None
    if not es_local(host):
        token = request.headers.get("authorization", "").removeprefix("Bearer ") or request.query_params.get("token")
        motivo = motivo_rechazo_remoto(host, request.url.path, token)
        if motivo:
            return JSONResponse({"error": motivo}, status_code=403)
    return await call_next(request)


async def difundir(evento: dict) -> None:
    msg = json.dumps(evento, ensure_ascii=False)
    muertos = []
    for ws in clientes:
        try:
            await ws.send_text(msg)
        except Exception:
            muertos.append(ws)
    for ws in muertos:
        clientes.discard(ws)


@app.websocket("/ws")
async def ws(ws: WebSocket):
    host = ws.client.host if ws.client else None
    remoto = not es_local(host)
    if remoto and motivo_rechazo_remoto(host, "/ws", ws.query_params.get("token")):
        await ws.close(code=4403)
        return
    await ws.accept()
    clientes.add(ws)
    if remoto:
        remotos.add(ws)
    try:
        while True:
            # El overlay también publica (ej. "overlay.fling" para mandar imagen a otro monitor)
            texto = await ws.receive_text()
            if remoto:
                continue  # un celular no puede abrir archivos ni mover ventanas por el WS
            try:
                data = json.loads(texto)
                if not isinstance(data, dict) or "tipo" not in data:
                    continue  # basura: se ignora sin tumbar la conexión
                await manejar_evento_overlay(data)
            except Exception as exc:  # un evento que falla (p. ej. abrir un archivo) no desconecta el HUD
                await difundir({"tipo": "hud.error", "detalle": f"{type(exc).__name__}: {exc}"[:200]})
    except WebSocketDisconnect:
        clientes.discard(ws)
        remotos.discard(ws)


async def manejar_evento_overlay(ev: dict) -> None:
    from lay_core import escritorio

    if ev.get("tipo") == "overlay.fling":
        # Gesto SNAP/swipe: abre la imagen de verdad y la manda al monitor destino
        # El monitor destino es el vecino real (izq/der) del monitor donde está el cursor
        monitor = ev.get("monitor") or await asyncio.to_thread(
            escritorio.monitor_vecino, ev.get("direccion", "derecha")
        )
        await asyncio.to_thread(escritorio.abrir, ev["ruta"])
        r = await asyncio.to_thread(
            escritorio.mover_ventana, Path(ev["ruta"]).name, monitor, ev.get("posicion", "maximizada")
        )
        ev = {**ev, "monitor": monitor, "resultado": r}
    elif ev.get("tipo") == "overlay.abrir_archivo":
        await asyncio.to_thread(escritorio.abrir_seguro, ev["ruta"])  # nunca rutas prohibidas
    await difundir(ev)


@app.post("/evento")
async def evento(ev: dict):
    await difundir(ev)
    return {"ok": True, "clientes": len(clientes)}


@app.post("/api/comando")
async def comando(body: dict, request: Request):
    """{"texto": "abre mi workspace de trabajo"}. Lo consume loops/voz.py (la guardia ya validó origen/token)."""
    texto = str(body.get("texto", "")).strip()[:500]
    if not texto:
        raise HTTPException(400, "texto vacío")
    await cola_comandos.put(texto)
    origen = "local" if es_local(request.client.host if request.client else None) else "remoto"
    await difundir({"tipo": "remoto.comando", "texto": texto, "origen": origen})
    return {"ok": True}


@app.get("/api/remoto/ping")
async def remoto_ping():
    return {"ok": True, "nombre": CONFIG.nombre}


@app.get("/api/ping")
async def ping():
    return {"ok": True}


@app.get("/api/comando/siguiente")
async def siguiente():
    try:
        return {"texto": cola_comandos.get_nowait()}
    except asyncio.QueueEmpty:
        return {"texto": None}


EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _imagen_valida(ruta: str) -> Path:
    p = Path(ruta)
    if not (p.is_file() and ruta_permitida(p) and p.suffix.lower() in EXT_IMAGEN):
        raise HTTPException(404)
    return p


@app.get("/api/explorar")
async def explorar(ruta: str | None = None):
    """Explorador holográfico: subcarpetas + imágenes de una carpeta (solo local, lo filtra la guardia)."""
    from lay_core import archivos

    return await asyncio.to_thread(archivos.explorar, ruta)


@app.get("/archivo")
async def archivo(ruta: str):
    return FileResponse(_imagen_valida(ruta))


def miniatura_de(p: Path, ancho: int) -> Path:
    """JPEG reducido y cacheado en ~/.lay/cache (clave: ruta + fecha + ancho).
    24 fotos de 12 MP a tamaño completo traban el HUD; las miniaturas pesan ~40 KB."""
    import hashlib

    from PIL import Image, ImageOps

    from lay_core.config import DATA_DIR

    st = p.stat()
    clave = hashlib.sha1(f"{p.resolve()}|{st.st_mtime_ns}|{ancho}".encode()).hexdigest()[:20]
    destino = DATA_DIR / "cache" / f"{clave}.jpg"
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(p) as im:
            im = ImageOps.exif_transpose(im)  # fotos de celular giradas
            im.thumbnail((ancho, ancho))
            im.convert("RGB").save(destino, "JPEG", quality=82)
    return destino


@app.get("/miniatura")
async def miniatura(ruta: str, w: int = 480):
    p = _imagen_valida(ruta)
    try:
        return FileResponse(await asyncio.to_thread(miniatura_de, p, max(64, min(w, 1600))))
    except Exception:
        return FileResponse(p)  # formato raro: la original


@app.get("/")
async def index():
    return FileResponse(ROOT / "overlay" / "index.html")


@app.get("/remoto")
async def pagina_remota():
    return FileResponse(ROOT / "overlay" / "remoto.html")


@app.on_event("startup")
async def _tareas_de_fondo():
    asyncio.create_task(_recordatorios())


async def _recordatorios():
    """Cada 15 s: lo que toca se dice en voz alta, sale en el HUD y como notificación de Windows."""
    from lay_core import recordatorios

    while True:
        try:
            for r in await asyncio.to_thread(recordatorios.vencidos):
                await difundir({"tipo": "voz.decir", "texto": f"Recordatorio: {r['mensaje']}"})
                await difundir(
                    {
                        "tipo": "hud.panel",
                        "titulo": "Recordatorio",
                        "items": [{"titulo": r["mensaje"], "etiqueta": "ahora"}],
                        "segundos": 60,
                    }
                )
                await asyncio.to_thread(recordatorios.notificar_windows, "LAY · Recordatorio", r["mensaje"])
        except Exception:
            pass
        await asyncio.sleep(15)


from loops import hub_api  # noqa: E402  (registra /api/config, /api/ia/*, /api/remoto/*)

hub_api.registrar(app, difundir)


def direccion_de_escucha() -> str:
    """127.0.0.1 salvo que el remoto esté activo (entonces todas las interfaces; la guardia filtra)."""
    if os.getenv("LAY_BIND"):
        return os.environ["LAY_BIND"]
    return "0.0.0.0" if CONFIG.remoto.get("activo") else CONFIG.hub_host


if __name__ == "__main__":
    uvicorn.run(app, host=direccion_de_escucha(), port=CONFIG.hub_port, log_level="warning")

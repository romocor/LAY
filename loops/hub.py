"""LOOP 0 — Hub de eventos (siempre encendido).

  python -m loops.hub

- WebSocket /ws      -> overlay/HUD se suscribe y recibe todo.
- POST /evento       -> MCP, voz y gestos publican.
- POST /api/comando  -> modo remoto: texto desde el celular (Tailscale + token).
- GET  /archivo      -> sirve imágenes locales al overlay (solo rutas permitidas).
- GET  /             -> sirve el overlay (overlay/index.html).
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from lay_core.config import CONFIG, HUB_TOKEN, ROOT
from lay_core.seguridad import ruta_permitida

app = FastAPI(title="LAY hub")
clientes: set[WebSocket] = set()
cola_comandos: asyncio.Queue = asyncio.Queue()


def _auth(authorization: str | None) -> None:
    if HUB_TOKEN:
        recibido = (authorization or "").removeprefix("Bearer ").strip()
        if not secrets.compare_digest(recibido, HUB_TOKEN):
            raise HTTPException(401, "token inválido")


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
    await ws.accept()
    clientes.add(ws)
    try:
        while True:
            # El overlay también publica (ej. "overlay.fling" para mandar imagen a otro monitor)
            texto = await ws.receive_text()
            try:
                data = json.loads(texto)
                if not isinstance(data, dict) or "tipo" not in data:
                    continue  # basura: se ignora sin tumbar la conexión
                await manejar_evento_overlay(data)
            except Exception as exc:  # un evento que falla (p. ej. abrir un archivo) no desconecta el HUD
                await difundir({"tipo": "hud.error", "detalle": f"{type(exc).__name__}: {exc}"[:200]})
    except WebSocketDisconnect:
        clientes.discard(ws)


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
        await asyncio.to_thread(escritorio.abrir, ev["ruta"])
    await difundir(ev)


@app.post("/evento")
async def evento(ev: dict, authorization: str | None = Header(None)):
    _auth(authorization)
    await difundir(ev)
    return {"ok": True, "clientes": len(clientes)}


@app.post("/api/comando")
async def comando(body: dict, authorization: str | None = Header(None)):
    """Remoto: {"texto": "LAY, abre mi workspace de trabajo"}. Lo consume loops/voz.py."""
    if not HUB_TOKEN:
        raise HTTPException(403, "Define LAY_HUB_TOKEN para habilitar comandos remotos")
    _auth(authorization)
    await cola_comandos.put(body["texto"])
    await difundir({"tipo": "remoto.comando", "texto": body["texto"]})
    return {"ok": True}


@app.get("/api/comando/siguiente")
async def siguiente(authorization: str | None = Header(None)):
    _auth(authorization)
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


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("LAY_BIND", CONFIG.hub_host), port=CONFIG.hub_port, log_level="warning")

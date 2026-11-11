"""Icono de LAY en la bandeja de Windows (junto al reloj) y aviso de versiones nuevas."""

from __future__ import annotations

import threading
from typing import Callable


def iniciar_bandeja(acciones: dict[str, Callable[[], None]], estado: Callable[[], dict]) -> object | None:
    """acciones: abrir, configuracion, camara, microfono, salir. estado() -> {"camara": bool, "microfono": bool}."""
    try:
        import pystray
        from PIL import Image

        from lay_core.config import ROOT
    except ImportError:
        return None
    ico = next((p for p in (ROOT / "lay.ico", ROOT / "packaging" / "lay.ico") if p.exists()), None)
    imagen = Image.open(ico) if ico else Image.new("RGB", (64, 64), (101, 244, 255))

    def accion(nombre):
        return lambda icono, item: acciones[nombre]()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir LAY", accion("abrir"), default=True),
        pystray.MenuItem("Configuración", accion("configuracion")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Cámara (gestos)", accion("camara"), checked=lambda item: estado()["camara"]),
        pystray.MenuItem("Micrófono (voz)", accion("microfono"), checked=lambda item: estado()["microfono"]),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir de LAY", accion("salir")),
    )
    icono = pystray.Icon("LAY", imagen, "LAY · tu asistente", menu)
    icono.run_detached()
    return icono


def version_nueva(actual: str, repo: str) -> dict | None:
    """Consulta el último Release de GitHub. None si no hay nada nuevo o no se puede consultar
    (por ejemplo, si el repositorio es privado)."""
    import httpx

    try:
        r = httpx.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=8,
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code != 200:
            return None
        d = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    ultima = d.get("tag_name", "").lstrip("v")

    def tupla(v: str) -> tuple:
        return tuple(int(x) for x in v.split(".")[:3] if x.isdigit())

    if ultima and tupla(ultima) > tupla(actual):
        exe = next(
            (a["browser_download_url"] for a in d.get("assets", []) if a["name"].endswith(".exe")), d["html_url"]
        )
        return {"version": ultima, "url": exe, "pagina": d["html_url"]}
    return None


def revisar_en_fondo(actual: str, repo: str, avisar: Callable[[dict], None]) -> None:
    def trabajo():
        nueva = version_nueva(actual, repo)
        if nueva:
            avisar(nueva)

    threading.Thread(target=trabajo, daemon=True).start()

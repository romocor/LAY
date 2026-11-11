"""Poner LA canción que Robert pide (no solo play/pausa de lo que ya sonaba).

Spotify (app de escritorio, gratis o Premium, sin API ni claves):
  1. Busca el ID de la canción/artista/álbum/playlist en internet ("site:open.spotify.com").
  2. Abre `spotify:track:ID` en la app. Según la versión, Spotify a veces solo muestra la página:
  3. Verifica por el título de la ventana (Spotify pone "Artista - Canción" al sonar). Si no
     cambió, hace clic en el botón verde "Reproducir" con UI Automation.
  Sin ID: abre la búsqueda de Spotify y le da play al primer resultado.

YouTube: saca el primer video de la búsqueda y abre /watch?v=ID (YouTube lo reproduce solo).
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, quote_plus

ID_SPOTIFY = re.compile(r"open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist|artist)/([A-Za-z0-9]{22})")
ES_WINDOWS = os.name == "nt"


def _plano(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ---------------- Spotify ----------------
def spotify_exe() -> str | None:
    cand = [
        Path(os.environ.get("APPDATA", "")) / "Spotify" / "Spotify.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "Spotify.exe",  # Microsoft Store
    ]
    return next((str(p) for p in cand if p.is_file()), None)


def buscar_id_spotify(consulta: str, tipo: str | None = None) -> tuple[str, str] | None:
    """(tipo, id) del primer resultado de Spotify en internet para esa consulta."""
    from lay_core import informacion

    filtro = f"site:open.spotify.com/{tipo}" if tipo else "site:open.spotify.com"
    for q in (f"{filtro} {consulta}", f"{consulta} spotify"):
        r = informacion.buscar_web(q, maximo=8)
        for item in r.get("resultados", []):
            m = ID_SPOTIFY.search(item.get("url", ""))
            if m and (tipo is None or m.group(1) == tipo):
                return m.group(1), m.group(2)
    return None


def _abrir_uri(uri: str) -> None:
    exe = spotify_exe()
    if exe:
        subprocess.Popen([exe, f"--uri={uri}"])
    elif ES_WINDOWS:
        os.startfile(uri)  # type: ignore[attr-defined]
    else:
        raise RuntimeError("Spotify no está instalado.")


def titulo_spotify() -> str:
    """Título de la ventana principal de Spotify ('Artista - Canción' mientras suena)."""
    if not ES_WINDOWS:
        return ""
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object MainWindowTitle |"
                " Select-Object -First 1).MainWindowTitle",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        ).stdout
        return out.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def suena(titulo: str, consulta: str) -> bool:
    """¿El título de Spotify corresponde a lo pedido? (alguna palabra significativa coincide)."""
    if not titulo or " - " not in titulo:
        return False  # "Spotify Free/Premium" = en pausa
    palabras = [
        p for p in re.findall(r"\w{3,}", _plano(consulta)) if p not in {"de", "del", "las", "los", "con", "una"}
    ]
    t = _plano(titulo)
    return any(p in t for p in palabras)


def _clic_reproducir() -> bool:
    """Botón verde 'Reproducir' de la página abierta en Spotify (UI Automation)."""
    if not ES_WINDOWS:
        return False
    try:
        from pywinauto import Desktop

        ventanas = [
            w
            for w in Desktop(backend="uia").windows(visible_only=True)
            if _proceso(w.element_info.process_id or 0) == "spotify.exe"
        ]
        if not ventanas:
            return False
        w = ventanas[0]
        botones = w.descendants(control_type="Button")
        candidatos = [
            b
            for b in botones
            if re.match(r"^(reproducir|play)\b", (b.element_info.name or ""), re.I)
            and "pausa" not in (b.element_info.name or "").lower()
        ]
        # el de la barra inferior es "Reproducir" a secas; el de la página suele llevar el nombre
        candidatos.sort(key=lambda b: len(b.element_info.name or ""), reverse=True)
        for b in candidatos[:3]:
            try:
                b.invoke()
            except Exception:
                b.click_input()
            return True
    except Exception:
        return False
    return False


def _proceso(pid: int) -> str:
    try:
        import psutil

        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


def spotify_reproducir(consulta: str, tipo: str | None = None) -> dict:
    """Pone en Spotify la canción/artista/álbum/playlist pedida."""
    consulta = consulta.strip()
    if not consulta:
        return {"error": "¿Qué quieres escuchar? Dime la canción o el artista."}
    if not (spotify_exe() or ES_WINDOWS):
        return {"error": "No encontré Spotify instalado."}
    encontrado = buscar_id_spotify(consulta, tipo)
    try:
        if encontrado:
            t, i = encontrado
            # "#0:00" en la URI de canción hace que empiece a sonar (truco documentado por Spotify)
            _abrir_uri(f"spotify:{t}:{i}" + ("#0:00" if t == "track" else ""))
        else:
            _abrir_uri(f"spotify:search:{quote(consulta)}")
    except (OSError, RuntimeError) as exc:
        return {"error": f"No pude abrir Spotify: {exc}"}

    for intento in range(3):  # Spotify tarda en cargar la página, sobre todo si estaba cerrado
        time.sleep(2.5 if intento == 0 else 2)
        if suena(titulo_spotify(), consulta):
            return {"ok": True, "sonando": titulo_spotify(), "como": "uri"}
        if _clic_reproducir():
            time.sleep(1.5)
            if suena(titulo_spotify(), consulta):
                return {"ok": True, "sonando": titulo_spotify(), "como": "boton"}
    titulo = titulo_spotify()
    return {
        "ok": bool(encontrado),
        "sonando": titulo if " - " in titulo else None,
        "aviso": "Abrí lo que pediste en Spotify; si no empezó solo, dale play." if encontrado else None,
        "error": None if encontrado else f"No encontré '{consulta}' en Spotify.",
    }


# ---------------- YouTube ----------------
def primer_video_youtube(consulta: str) -> str | None:
    import httpx

    try:
        html = httpx.get(
            f"https://www.youtube.com/results?search_query={quote_plus(consulta)}&hl=es",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "es-PE,es;q=0.9"},
            timeout=10,
            follow_redirects=True,
        ).text
    except httpx.HTTPError:
        return None
    m = re.search(r'"videoId":"([\w-]{11})"', html)
    return m.group(1) if m else None


def youtube_reproducir(consulta: str, navegador: str | None = None) -> dict:
    """Busca en YouTube y abre el primer video (empieza a sonar solo)."""
    from lay_core import navegador as nav

    vid = primer_video_youtube(consulta)
    destino = (
        f"https://www.youtube.com/watch?v={vid}" if vid else f"youtube.com/results?search_query={quote_plus(consulta)}"
    )
    r = nav.abrir(destino, navegador)
    if "error" in r:
        return r
    return {**r, "video": bool(vid), "consulta": consulta}

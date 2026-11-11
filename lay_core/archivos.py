"""Búsqueda de archivos. Usa Everything (es.exe) si está instalado — instantáneo
en todo el disco — y si no, un recorrido acotado de las raíces configuradas."""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from lay_core.config import CONFIG

IGNORAR = {"node_modules", ".git", "__pycache__", "AppData", ".venv", "venv", "$Recycle.Bin"}
EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _info(p: Path) -> dict:
    st = p.stat()
    return {
        "ruta": str(p),
        "nombre": p.name,
        "carpeta": p.is_dir(),
        "kb": round(st.st_size / 1024, 1),
        "modificado": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
    }


def _everything() -> str | None:
    """Ruta a es.exe (CLI de Everything) si está instalado."""
    cand = [shutil.which("es"), shutil.which("es.exe")]
    for base in (
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
    ):
        if base:
            cand.append(os.path.join(base, "Everything", "es.exe"))
    return next((c for c in cand if c and os.path.isfile(c)), None)


def buscar(
    consulta: str,
    carpeta: str | None = None,
    extension: str | None = None,
    limite: int = 30,
    solo_carpetas: bool = False,
) -> list[dict]:
    es = _everything()
    if es and carpeta is None:
        args = [es, "-n", str(limite), "-sort", "date-modified-descending"]
        if solo_carpetas:
            args.append("/ad")
        q = consulta + (f" ext:{extension.lstrip('.')}" if extension else "")
        out = subprocess.run(args + [q], capture_output=True, text=True, timeout=10).stdout
        return [_info(Path(linea)) for linea in out.splitlines() if linea.strip() and Path(linea).exists()]

    patron = f"*{consulta.lower()}*"
    raices = [carpeta] if carpeta else CONFIG.raices_busqueda
    res: list[dict] = []
    limite_t = time.time() + 15
    for raiz in raices:
        for dirpath, dirnames, filenames in os.walk(os.path.expanduser(raiz)):
            dirnames[:] = [d for d in dirnames if d not in IGNORAR and not d.startswith(".")]
            nombres = dirnames if solo_carpetas else filenames + dirnames
            for n in nombres:
                if fnmatch.fnmatch(n.lower(), patron) and (not extension or n.lower().endswith(extension.lower())):
                    res.append(_info(Path(dirpath) / n))
                    if len(res) >= limite:
                        return res
            if time.time() > limite_t:
                return res
    return res


def mejor_coincidencia(consulta: str, extension: str | None = None) -> dict | None:
    """El resultado más probable: nombre exacto > empieza igual > contiene; desempata el más reciente."""
    res = [r for r in buscar(consulta, extension=extension, limite=40) if "$recycle" not in r["ruta"].lower()]
    if not res:
        return None
    q = consulta.lower()

    def clave(r):
        base = Path(r["nombre"]).stem.lower()
        return (base == q, base.startswith(q), r["modificado"])

    return max(res, key=clave)


def recientes(carpeta: str | None = None, dias: int = 7, limite: int = 20) -> list[dict]:
    base = Path(os.path.expanduser(carpeta or "~/Downloads"))
    corte = time.time() - dias * 86400
    items = [p for p in base.glob("*") if p.stat().st_mtime >= corte]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [_info(p) for p in items[:limite]]


def listar(carpeta: str, limite: int = 100) -> list[dict]:
    base = Path(os.path.expanduser(carpeta))
    return [_info(p) for p in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:limite]]


def imagenes(carpeta: str | None = None, limite: int = 24) -> list[str]:
    base = Path(os.path.expanduser(carpeta or CONFIG.carpeta_galeria))
    imgs = [p for p in base.rglob("*") if p.suffix.lower() in EXT_IMAGEN]
    imgs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in imgs[:limite]]


def explorar(ruta: str | None = None, max_carpetas: int = 40, max_imagenes: int = 48) -> dict:
    """Contenido de una carpeta para el explorador holográfico: subcarpetas e imágenes (sin ocultos ni rutas prohibidas)."""
    from lay_core.seguridad import ruta_permitida

    base = Path(os.path.expanduser(ruta)) if ruta else (resolver_carpeta("imagenes") or Path.home())
    if not ruta and not base.is_dir():
        base = Path.home()
    base = base.resolve()
    if not base.is_dir():
        return {"error": f"No existe la carpeta {base}"}
    if not ruta_permitida(base):
        return {"error": "Esa carpeta está protegida."}
    carpetas, imgs, otros = [], [], 0
    try:
        hijos = sorted(base.iterdir(), key=lambda x: x.name.lower())
    except OSError as e:
        return {"error": f"No pude abrir {base.name}: {e.strerror or e}"}
    for h in hijos:
        if h.name.startswith((".", "$", "~")) or h.name in ("desktop.ini", "Thumbs.db"):
            continue
        try:
            if h.is_dir():
                if ruta_permitida(h) and len(carpetas) < max_carpetas:
                    carpetas.append({"nombre": h.name, "ruta": str(h)})
            elif h.suffix.lower() in EXT_IMAGEN:
                imgs.append(h)
            else:
                otros += 1
        except OSError:
            continue
    imgs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    padre = base.parent if base.parent != base and ruta_permitida(base.parent) else None
    return {
        "ruta": str(base),
        "nombre": base.name or str(base),
        "padre": str(padre) if padre else None,
        "carpetas": carpetas,
        "imagenes": [str(x) for x in imgs[:max_imagenes]],
        "mas_imagenes": max(0, len(imgs) - max_imagenes),
        "otros": otros,
    }


CARPETAS_CONOCIDAS = {
    "descargas": "~/Downloads",
    "documentos": "~/Documents",
    "escritorio": "~/Desktop",
    "imagenes": "~/Pictures",
    "fotos": "~/Pictures",
    "musica": "~/Music",
    "videos": "~/Videos",
    "capturas": "~/Pictures/Screenshots",
    "onedrive": "~/OneDrive",
}


def resolver_carpeta(nombre: str) -> Path | None:
    """'descargas' -> ~/Downloads; si no es conocida, busca una carpeta con ese nombre (la más reciente)."""
    import unicodedata

    clave = unicodedata.normalize("NFKD", nombre.lower()).encode("ascii", "ignore").decode().strip()
    clave = re.sub(r"^(la |las |los |el |mis? |carpeta (de )?)", "", clave).strip()
    for k, ruta in CARPETAS_CONOCIDAS.items():
        if clave == k or clave.startswith(k):
            p = Path(os.path.expanduser(ruta))
            onedrive = Path(os.path.expanduser("~/OneDrive")) / p.name  # Windows con OneDrive mueve estas carpetas
            return p if p.exists() else (onedrive if onedrive.exists() else p)
    p = Path(os.path.expanduser(nombre))
    if p.is_dir():
        return p
    res = buscar(clave, solo_carpetas=True, limite=5)
    return Path(res[0]["ruta"]) if res else None

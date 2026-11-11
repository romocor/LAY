"""Gestos que Robert le enseña a LAY ("entrena un gesto para abrir Spotify").

Cómo aprende (mismo enfoque que Kazuhito00/hand-gesture-recognition-using-mediapipe, pero
sin TensorFlow para no gastar RAM): los 21 puntos de MediaPipe se pasan a coordenadas
relativas a la muñeca y se escalan por el tamaño de la mano -> la pose no depende de dónde
esté la mano ni de qué tan cerca esté de la cámara. La mano izquierda se espeja para que un
mismo gesto valga con cualquier mano. Reconocer = vecino más cercano entre las muestras
grabadas (unas 40 por gesto): entrena al instante y corre en microsegundos.

Acción de un gesto = una ORDEN en texto para LAY ("abre spotify", "pausa la música"), que va
por el mismo camino que la voz (y por lo tanto respeta confirmaciones), o un ATAJO de
teclado ("ctrl+alt+t"). Guardado en ~/.lay/gestos_propios.json.
"""

from __future__ import annotations

import json
import math
import re
import threading

from lay_core.config import DATA_DIR

ARCHIVO = DATA_DIR / "gestos_propios.json"
UMBRAL = 0.42  # distancia máxima (en el espacio normalizado) para aceptar un gesto
MIN_MUESTRAS = 12
_lock = threading.Lock()
_cache: dict = {"mtime": None, "gestos": []}

ATAJO = re.compile(r"^\s*((ctrl|control|alt|shift|mayus|win|tecla)\s*\+\s*)+\w+\s*$", re.I)


def vector(puntos, mano: str = "Right") -> list[float]:
    """21 puntos (x, y[, z]) -> 42 números invariantes a posición, tamaño y mano."""
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    x0, y0 = xs[0], ys[0]
    signo = -1.0 if mano == "Left" else 1.0  # espejo: la izquierda se ve como la derecha
    rel = []
    for x, y in zip(xs, ys):
        rel += [(x - x0) * signo, y - y0]
    escala = max(abs(v) for v in rel) or 1.0
    return [v / escala for v in rel]


def distancia(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)) * 3


def _leer() -> list[dict]:
    try:
        mtime = ARCHIVO.stat().st_mtime
    except OSError:
        return []
    if _cache["mtime"] != mtime:
        try:
            _cache["gestos"] = json.loads(ARCHIVO.read_text(encoding="utf-8")).get("gestos", [])
        except (OSError, ValueError):
            _cache["gestos"] = []
        _cache["mtime"] = mtime
    return _cache["gestos"]


def _escribir(gestos: list[dict]) -> None:
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARCHIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "gestos": gestos}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ARCHIVO)
    _cache["mtime"] = None


def accion_de(orden: str) -> dict:
    orden = orden.strip()
    if ATAJO.match(orden):
        return {"tipo": "teclas", "valor": orden.lower().replace(" ", "")}
    return {"tipo": "orden", "valor": orden}


def guardar(nombre: str, orden: str, muestras: list[list[float]]) -> dict:
    nombre = (nombre or orden).strip()[:40]
    if not nombre or not orden.strip():
        return {"error": "Dime qué debe hacer el gesto, por ejemplo: abre Spotify."}
    if len(muestras) < MIN_MUESTRAS:
        return {
            "error": f"Solo vi tu mano en {len(muestras)} cuadros. Ponla frente a la cámara, con buena luz, y repite."
        }
    with _lock:
        gestos = [g for g in _leer() if g["nombre"].lower() != nombre.lower()]
        aviso = None
        for g in gestos:  # ¿se parece demasiado a otro gesto ya guardado?
            if min(distancia(m, s) for m in muestras[::4] for s in g["muestras"][::4]) < UMBRAL * 0.5:
                aviso = f"Se parece mucho a '{g['nombre']}'; si se confunden, graba uno más distinto."
        gestos.append(
            {"nombre": nombre, "accion": accion_de(orden), "muestras": [[round(v, 3) for v in m] for m in muestras]}
        )
        _escribir(gestos)
    return {"ok": True, "nombre": nombre, "muestras": len(muestras), "accion": accion_de(orden), "aviso": aviso}


def listar() -> dict:
    return {"gestos": [{"nombre": g["nombre"], "accion": g["accion"], "muestras": len(g["muestras"])} for g in _leer()]}


def borrar(nombre: str) -> dict:
    with _lock:
        gestos = _leer()
        quedan = [g for g in gestos if g["nombre"].lower() != nombre.lower().strip()]
        if len(quedan) == len(gestos):
            return {"error": f"No tengo un gesto llamado '{nombre}'.", "disponibles": [g["nombre"] for g in gestos]}
        _escribir(quedan)
    return {"ok": True, "borrado": nombre}


def reconocer(v: list[float]) -> tuple[dict | None, float]:
    """Gesto propio más cercano a la pose v (o None si ninguno pasa el umbral)."""
    mejor, dmin = None, 9.0
    for g in _leer():
        d = min(distancia(v, m) for m in g["muestras"])
        if d < dmin:
            mejor, dmin = g, d
    return (mejor, dmin) if dmin <= UMBRAL else (None, dmin)

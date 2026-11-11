"""Permisos y auditoría. Toda acción que cambia algo pasa por aquí.

Niveles:
  safe      -> se ejecuta directo (leer, listar, buscar, mover ventanas)
  sensitive -> necesita confirmar=True (escribir texto, enviar correo, cerrar apps)
  blocked   -> nunca (borrar archivos del sistema, formatear, etc.)
"""

from __future__ import annotations

import json
import time
from functools import wraps
from pathlib import Path
from typing import Callable

from lay_core.config import AUDIT_LOG

RUTAS_PROHIBIDAS = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "/etc",
    "/bin",
    "/usr",
    "/System",
]


class AccionNoConfirmada(Exception):
    pass


def auditar(accion: str, datos: dict, resultado: str) -> None:
    linea = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "accion": accion, "datos": datos, "resultado": resultado}
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def ruta_permitida(ruta: str | Path) -> bool:
    p = str(Path(ruta).resolve())
    return not any(p.lower().startswith(x.lower()) for x in RUTAS_PROHIBIDAS)


def sensible(descripcion: str) -> Callable:
    """Decorador: la función exige confirmar=True; si no, devuelve una
    solicitud de confirmación en vez de ejecutar."""

    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, confirmar: bool = False, **kwargs):
            if not confirmar:
                return {
                    "requiere_confirmacion": True,
                    "mensaje": f"{descripcion}. Repite la llamada con confirmar=true tras la aprobación de Robert.",
                    "parametros": kwargs,
                }
            try:
                res = fn(*args, **kwargs)
                auditar(fn.__name__, kwargs, "ok")
                return res
            except Exception as exc:
                auditar(fn.__name__, kwargs, f"error: {exc}")
                raise

        wrapper.__lay_sensible__ = True
        return wrapper

    return deco

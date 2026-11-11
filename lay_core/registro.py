"""Registro de errores con detalle técnico en ~/.lay/errores.log (para diagnosticar en cualquier PC)."""

from __future__ import annotations

import time
import traceback

from lay_core.config import DATA_DIR

ARCHIVO = DATA_DIR / "errores.log"


def error(origen: str, exc: BaseException | None = None, detalle: str = "") -> None:
    try:
        if ARCHIVO.exists() and ARCHIVO.stat().st_size > 2_000_000:
            ARCHIVO.write_text("", encoding="utf-8")  # no crecer sin límite
        traza = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else ""
        with ARCHIVO.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} [{origen}] {detalle}\n{traza}")
    except Exception:
        pass


def ultimos(n: int = 30) -> str:
    try:
        return "\n".join(ARCHIVO.read_text(encoding="utf-8").splitlines()[-n:])
    except FileNotFoundError:
        return ""

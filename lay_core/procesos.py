"""Procesos de LAY: relanzarse con otro rol y lanzar programas SIN que aparezca la consola negra.

En Windows, cada vez que un proceso sin consola (LAY.exe) o con consola oculta ejecuta
powershell, ollama, es.exe, taskkill… Windows abre una ventana de cmd que parpadea encima
de todo. `sin_consolas()` hace que todo subprocess de LAY nazca oculto por defecto.
Las apps gráficas (Chrome, Spotify, Explorer) se ven igual: CREATE_NO_WINDOW solo afecta a consolas.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ES_WINDOWS = os.name == "nt"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
CONSOLA_NUEVA = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
_DESACOPLADO = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
_parcheado = False


def sin_consolas() -> None:
    """Todo subprocess sin creationflags explícitos nace sin ventana de consola (solo Windows)."""
    global _parcheado
    if not ES_WINDOWS or _parcheado:
        return
    original = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):  # noqa: N807
        flags = kwargs.get("creationflags", 0) or 0
        if not flags & (CONSOLA_NUEVA | _DESACOPLADO):  # quien pide consola visible la tiene
            kwargs["creationflags"] = flags | SIN_VENTANA
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__  # type: ignore[method-assign]
    _parcheado = True


def comando_rol(rol: str, *args: str) -> list[str]:
    """Cómo relanzar LAY con otro rol (hub, voz, gestos…), congelado o no."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        cli = exe.with_name("LAY-cli.exe" if exe.suffix.lower() == ".exe" else "LAY-cli")
        return [str(cli if cli.exists() else exe), "--rol", rol, *args]
    raiz = Path(__file__).resolve().parent.parent
    return [sys.executable, str(raiz / "lay.py"), "--rol", rol, *args]


def lanzar_rol(rol: str, *args: str) -> subprocess.Popen:
    return subprocess.Popen(comando_rol(rol, *args), creationflags=SIN_VENTANA if ES_WINDOWS else 0)

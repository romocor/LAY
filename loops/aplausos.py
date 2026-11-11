"""Abrir LAY con palmadas. Proceso liviano (~1 % CPU) que arranca con Windows.

  LAY.exe --rol aplausos

  👏👏      (doble)  -> abre LAY; si ya está abierto, lo trae al frente
  👏👏👏    (triple) -> acción configurable (por defecto: workspace "trabajo")

Una palmada se distingue de la voz/música por 3 rasgos, medidos en bloques de 10 ms:
  1. ataque brusco: la energía salta >6x respecto a los 50 ms anteriores
  2. corta: a los ~70 ms ya cayó a menos del 35 % del pico
  3. ruidosa: muchos cruces por cero (banda ancha), a diferencia de vocales (tonales)
"""

from __future__ import annotations

import math
import struct
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field

TASA = 16000
BLOQUE = 160  # 10 ms


def rms(b: bytes) -> float:
    n = len(b) // 2
    if not n:
        return 0.0
    m = struct.unpack(f"<{n}h", b[: n * 2])
    return math.sqrt(sum(x * x for x in m) / n)


def cruces_por_cero(b: bytes) -> float:
    n = len(b) // 2
    m = struct.unpack(f"<{n}h", b[: n * 2])
    return sum(1 for i in range(1, n) if (m[i - 1] >= 0) != (m[i] >= 0)) / max(n - 1, 1)


@dataclass
class DetectorPalmadas:
    """Alimentar con bloques de 10 ms. Devuelve 2 / 3 cuando termina una serie de palmadas."""

    sensibilidad: float = 0.6  # 0 = estricto, 1 = sensible
    previos: deque = field(default_factory=lambda: deque(maxlen=5))  # 50 ms antes del ataque
    candidato: dict | None = None
    palmadas: list = field(default_factory=list)
    t: float = 0.0
    ultimo_disparo: float = -10.0

    @property
    def umbral_abs(self) -> float:
        return 2500 - 1700 * self.sensibilidad  # 2500 (estricto) .. 800 (sensible)

    @property
    def salto(self) -> float:
        return 9 - 4 * self.sensibilidad  # ataque mínimo: 9x .. 5x

    def alimentar(self, bloque: bytes) -> int | None:
        self.t += BLOQUE / TASA
        nivel = rms(bloque)
        fondo = (sum(self.previos) / len(self.previos)) if self.previos else nivel
        resultado = None

        if self.candidato is not None:
            c = self.candidato
            c["bloques"] += 1
            c["pico"] = max(c["pico"], nivel)
            if c["bloques"] == 7:  # 70 ms después del ataque: ¿ya cayó?
                if nivel < c["pico"] * 0.35 and c["zcr"] > 0.18:
                    self.palmadas.append(c["t0"])
                self.candidato = None
        elif nivel > self.umbral_abs and nivel > max(fondo, 60) * self.salto:
            self.candidato = {"t0": self.t, "pico": nivel, "bloques": 0, "zcr": cruces_por_cero(bloque)}

        # cierra la serie: 0,7 s sin nueva palmada
        if self.palmadas and self.t - self.palmadas[-1] > 0.7 and self.candidato is None:
            serie = self.palmadas
            self.palmadas = []
            separaciones = [b - a for a, b in zip(serie, serie[1:])]
            if (
                len(serie) in (2, 3)
                and all(0.12 <= s <= 0.7 for s in separaciones)
                and self.t - self.ultimo_disparo > 2.5
            ):
                self.ultimo_disparo = self.t
                resultado = len(serie)

        if self.candidato is None:
            self.previos.append(nivel)
        return resultado


def lay_abierto() -> bool:
    import httpx

    from lay_core.config import HUB_URL

    try:
        httpx.get(f"{HUB_URL}/api/ping", timeout=1)
        return True
    except httpx.HTTPError:
        return False


def ejecutar(n: int) -> None:
    from lay_core import bus
    from lay_core.config import CONFIG

    abierto = lay_abierto()
    if n == 2:
        if abierto:
            bus.publicar("aplausos", n=2, accion="traer")  # el HUD vuelve al frente
        else:
            exe = sys.executable
            cmd = [exe] if getattr(sys, "frozen", False) else [exe, __import__("lay").__file__]
            subprocess.Popen(cmd, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    elif n == 3:
        accion = CONFIG.aplausos.get("accion_triple", "")
        if accion.startswith("workspace:"):
            from lay_core import escritorio

            escritorio.aplicar_workspace(accion.split(":", 1)[1])
        elif accion.startswith("app:"):
            from lay_core import escritorio

            escritorio.lanzar_app(accion.split(":", 1)[1])
        if abierto:
            bus.publicar("aplausos", n=3, accion=accion)


def una_sola_instancia(nombre: str) -> bool:
    """Mutex con nombre de Windows: evita dos detectores (abrirían LAY dos veces)."""
    if sys.platform != "win32":
        return True
    import ctypes

    ctypes.windll.kernel32.CreateMutexW(None, False, f"Global\\{nombre}")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    import pyaudio

    from lay_core.config import CONFIG, recargar

    if not una_sola_instancia("LAY_Aplausos"):
        return

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=TASA,
        input=True,
        frames_per_buffer=BLOQUE,
        input_device_index=CONFIG.microfono,
    )
    det = DetectorPalmadas(CONFIG.aplausos.get("sensibilidad", 0.6))
    revisado = time.monotonic()
    print("LAY aplausos: doble palmada = abrir LAY, triple = " + CONFIG.aplausos.get("accion_triple", "—"))
    while True:
        if time.monotonic() - revisado > 30:  # toma cambios de Configuración sin reiniciar
            recargar()
            det.sensibilidad = CONFIG.aplausos.get("sensibilidad", 0.6)
            revisado = time.monotonic()
        if not CONFIG.aplausos.get("activo", True):
            time.sleep(1)
            stream.read(stream.get_read_available(), exception_on_overflow=False)
            continue
        n = det.alimentar(stream.read(BLOQUE, exception_on_overflow=False))
        if n:
            try:
                ejecutar(n)
            except Exception as exc:
                print(f"aplausos: {exc}")

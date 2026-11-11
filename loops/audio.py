"""Captura de micrófono + palabra clave offline + segmentación de frases.

Un solo stream de micrófono (16 kHz mono, bloques de 30 ms) alimenta:
  - DetectorWake: Vosk con gramática cerrada ("ley", "oye ley", "ley para"...).
    "LAY" suena /lei/ = "ley" en el modelo español. Offline, sin enviar audio a nadie.
  - Segmentador: VAD por energía con piso de ruido adaptativo y pre-roll, para
    grabar la frase completa ("LAY, abre Spotify" de un tirón no pierde "abre").
La frase grabada se transcribe aparte (Google STT es-PE) en loops/voz.py.
"""

from __future__ import annotations

import collections
import json
import math
import queue
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path

TASA = 16000
BLOQUE = 480  # 30 ms
BYTES_BLOQUE = BLOQUE * 2

FRASES_WAKE = ["ley", "oye ley", "hola ley"]
FRASES_CALLAR = ["ley para", "ley detente", "ley silencio", "ley basta", "ley cállate", "ley cancela"]


def rms(bloque: bytes) -> float:
    n = len(bloque) // 2
    if n == 0:
        return 0.0
    muestras = struct.unpack(f"<{n}h", bloque[: n * 2])
    return math.sqrt(sum(m * m for m in muestras) / n)


# ---------------- micrófono ----------------
class Microfono:
    """Hilo lector de PyAudio -> cola de bloques de 30 ms. Nunca bloquea al consumidor."""

    def __init__(self, dispositivo: int | None = None) -> None:
        import pyaudio

        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=TASA,
            input=True,
            frames_per_buffer=BLOQUE,
            input_device_index=dispositivo,
        )
        self.cola: queue.Queue[bytes] = queue.Queue(maxsize=400)  # ~12 s
        self._vivo = True
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self) -> None:
        while self._vivo:
            datos = self._stream.read(BLOQUE, exception_on_overflow=False)
            try:
                self.cola.put_nowait(datos)
            except queue.Full:
                self.cola.get_nowait()
                self.cola.put_nowait(datos)

    def bloques(self):
        while self._vivo:
            yield self.cola.get()

    def vaciar(self) -> None:
        while not self.cola.empty():
            self.cola.get_nowait()

    def cerrar(self) -> None:
        self._vivo = False
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()


# ---------------- palabra clave ----------------
@dataclass
class Deteccion:
    tipo: str  # "wake" | "callar"
    frase: str
    confianza: float


class DetectorWake:
    """Vosk con gramática restringida: barato (~2 % CPU) y con pocos falsos positivos."""

    def __init__(self, ruta_modelo: str | Path, confianza_min: float = 0.75) -> None:
        import vosk

        vosk.SetLogLevel(-1)
        self.modelo = vosk.Model(str(ruta_modelo))
        self.confianza_min = confianza_min
        self.rec = self._nuevo()

    def _nuevo(self):
        import vosk

        r = vosk.KaldiRecognizer(self.modelo, TASA, json.dumps(FRASES_WAKE + FRASES_CALLAR + ["[unk]"]))
        r.SetWords(True)
        return r

    def alimentar(self, bloque: bytes) -> Deteccion | None:
        if not self.rec.AcceptWaveform(bloque):
            return None
        return interpretar(json.loads(self.rec.Result()), self.confianza_min)

    def reiniciar(self) -> None:
        self.rec = self._nuevo()


def interpretar(resultado: dict, confianza_min: float) -> Deteccion | None:
    """Convierte el JSON de Vosk en una detección. Separado para poder testearlo."""
    texto = resultado.get("text", "").strip()
    palabras = resultado.get("result", [])
    if not texto or texto == "[unk]" or not palabras:
        return None
    conf = min(p.get("conf", 0.0) for p in palabras)
    if conf < confianza_min:
        return None
    for frase in FRASES_CALLAR:
        if frase in texto:
            return Deteccion("callar", frase, conf)
    for frase in FRASES_WAKE:
        # "ley ..." u "oye ley" sí; "[unk] ley" (p. ej. "la ley") no.
        if texto == frase or texto.startswith(frase + " "):
            return Deteccion("wake", frase, conf)
    return None


# ---------------- segmentación de frase ----------------
class Segmentador:
    """Graba desde un pre-roll hasta que haya silencio sostenido.

    piso de ruido = media móvil del RMS en reposo; voz = RMS > piso * factor.
    """

    def __init__(
        self,
        pre_roll_s: float = 1.0,
        silencio_fin_s: float = 0.8,
        max_s: float = 12.0,
        factor: float = 2.8,
        rms_min: float = 250.0,
    ) -> None:
        self.pre = collections.deque(maxlen=int(pre_roll_s * 1000 / 30))
        self.bloques_silencio = int(silencio_fin_s * 1000 / 30)
        self.max_bloques = int(max_s * 1000 / 30)
        self.factor, self.rms_min = factor, rms_min
        self.piso = 300.0

    def es_voz(self, nivel: float) -> bool:
        return nivel > max(self.piso * self.factor, self.rms_min)

    def reposo(self, bloque: bytes) -> None:
        """Llamar con cada bloque mientras no se graba: mantiene pre-roll y piso de ruido."""
        self.pre.append(bloque)
        nivel = rms(bloque)
        if not self.es_voz(nivel):
            self.piso = self.piso * 0.97 + nivel * 0.03

    def grabar(self, bloques, esperar_voz_s: float = 4.0) -> bytes | None:
        """Consume bloques hasta fin de frase. None si nadie habló en `esperar_voz_s`."""
        audio = list(self.pre)
        hubo_voz = any(self.es_voz(rms(b)) for b in audio[-10:])
        silencio = 0
        t0 = time.monotonic()
        for i, b in enumerate(bloques):
            audio.append(b)
            if self.es_voz(rms(b)):
                hubo_voz, silencio = True, 0
            else:
                silencio += 1
            if not hubo_voz and time.monotonic() - t0 > esperar_voz_s:
                return None
            if hubo_voz and silencio >= self.bloques_silencio:
                break
            if i >= self.max_bloques:
                break
        self.pre.clear()
        return b"".join(audio) if hubo_voz else None


def ruta_modelo_vosk() -> Path | None:
    """Busca el modelo en ~/.lay/models/vosk-es (instalado) o en el paquete (exe)."""
    from lay_core.config import DATA_DIR, ROOT

    for base in (DATA_DIR / "models" / "vosk-es", ROOT / "models" / "vosk-es"):
        if (base / "am").exists() or (base / "conf").exists():
            return base
    return None


def descargar_modelo_vosk() -> Path:
    """Primera ejecución sin modelo empaquetado: descarga el small-es (~39 MB)."""
    import io
    import zipfile

    import httpx

    from lay_core.config import DATA_DIR

    url = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
    destino = DATA_DIR / "models"
    destino.mkdir(parents=True, exist_ok=True)
    datos = httpx.get(url, timeout=300, follow_redirects=True).content
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        z.extractall(destino)
    (destino / "vosk-model-small-es-0.42").rename(destino / "vosk-es")
    return destino / "vosk-es"

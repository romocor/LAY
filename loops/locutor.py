"""Voz de salida de LAY con baja latencia.

  texto en streaming -> Fraseador -> cola -> [hilo síntesis] -> cola audio -> [hilo reproducción]

Mientras suena la frase N se sintetiza la N+1. `callar()` corta al instante
(interrupción por voz, puño o Esc) y descarta lo que estaba en camino.
"""

from __future__ import annotations

import asyncio
import io
import queue
import re
import threading
import time
from typing import Callable

FIN_FRASE = re.compile(r"(?<=[.!?;:…])\s+|\n+")


class Fraseador:
    """Corta el texto que llega en trozos en frases decibles.
    Primera frase corta a propósito (mín. 12 car.) para empezar a hablar cuanto antes."""

    def __init__(self, emitir: Callable[[str], None], minimo_primera: int = 12, minimo: int = 40) -> None:
        self.emitir, self.buffer = emitir, ""
        self.minimo_primera, self.minimo = minimo_primera, minimo
        self.emitidas = 0

    def agregar(self, trozo: str) -> None:
        self.buffer += trozo
        while True:
            m = None
            minimo = self.minimo_primera if self.emitidas == 0 else self.minimo
            for cand in FIN_FRASE.finditer(self.buffer):
                if cand.start() >= minimo:
                    m = cand
                    break
            if not m:
                return
            frase, self.buffer = self.buffer[: m.start()].strip(), self.buffer[m.end() :]
            self._emitir(frase)

    def cerrar(self) -> None:
        if self.buffer.strip():
            self._emitir(self.buffer.strip())
        self.buffer = ""

    def _emitir(self, frase: str) -> None:
        frase = re.sub(r"[*_#`>]+", "", frase).strip()  # por si el modelo usa markdown
        if frase:
            self.emitidas += 1
            self.emitir(frase)


class Locutor:
    def __init__(
        self,
        voz: str,
        sintetizar: Callable[[str, str], bytes] | None = None,
        reproducir: Callable[[bytes], None] | None = None,
        detener: Callable[[], None] | None = None,
        al_empezar: Callable[[str], None] | None = None,
        al_terminar: Callable[[], None] | None = None,
    ) -> None:
        self.voz = voz
        self._sintetizar = sintetizar or sintetizar_edge
        self._reproducir = reproducir or reproducir_pygame
        self._detener = detener or detener_pygame
        self.al_empezar, self.al_terminar = al_empezar, al_terminar
        self._textos: queue.Queue = queue.Queue()
        self._audios: queue.Queue = queue.Queue(maxsize=3)
        self._generacion = 0
        self._pendientes = 0
        self._lock = threading.Lock()
        self._libre = threading.Event()
        self._libre.set()
        self.t_primer_audio: float | None = None
        threading.Thread(target=self._hilo_sintesis, daemon=True).start()
        threading.Thread(target=self._hilo_reproduccion, daemon=True).start()

    # --- API ---
    def decir(self, frase: str) -> None:
        with self._lock:
            self._pendientes += 1
            self._libre.clear()
            self._textos.put((self._generacion, frase))

    def hablando(self) -> bool:
        return not self._libre.is_set()

    def esperar(self, timeout: float | None = None) -> bool:
        return self._libre.wait(timeout)

    def callar(self) -> None:
        with self._lock:
            self._generacion += 1
            self._pendientes = 0
            for q in (self._textos, self._audios):
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
            self._libre.set()
        try:
            self._detener()
        except Exception:
            pass
        if self.al_terminar:
            self.al_terminar()

    # --- hilos ---
    def _hilo_sintesis(self) -> None:
        while True:
            gen, frase = self._textos.get()
            if gen != self._generacion:
                continue
            try:
                audio = self._sintetizar(frase, self.voz)
            except Exception:
                audio = b""
                _respaldo_offline(frase)
            if gen == self._generacion:
                self._audios.put((gen, frase, audio))

    def _hilo_reproduccion(self) -> None:
        while True:
            gen, frase, audio = self._audios.get()
            if gen != self._generacion:
                continue
            if self.t_primer_audio is None:
                self.t_primer_audio = time.monotonic()
            if self.al_empezar:
                self.al_empezar(frase)
            if audio:
                self._reproducir(audio)
            with self._lock:
                if gen != self._generacion:
                    continue
                self._pendientes = max(self._pendientes - 1, 0)
                if self._pendientes == 0:
                    self._libre.set()
                    termino = True
                else:
                    termino = False
            if termino and self.al_terminar:
                self.al_terminar()


# ---------------- backends ----------------
def sintetizar_edge(texto: str, voz: str) -> bytes:
    import edge_tts

    async def _go() -> bytes:
        buf = io.BytesIO()
        async for ch in edge_tts.Communicate(texto, voz, rate="+8%").stream():
            if ch["type"] == "audio":
                buf.write(ch["data"])
        return buf.getvalue()

    return asyncio.run(_go())


_mixer_ok = False


def _mixer():
    global _mixer_ok
    import pygame

    if not _mixer_ok:
        pygame.mixer.init()
        _mixer_ok = True
    return pygame.mixer


def reproducir_pygame(mp3: bytes) -> None:
    m = _mixer()
    m.music.load(io.BytesIO(mp3), "mp3")
    m.music.play()
    while m.music.get_busy():
        time.sleep(0.02)
    m.music.unload()


def detener_pygame() -> None:
    if _mixer_ok:
        _mixer().music.stop()


def _respaldo_offline(frase: str) -> None:
    """Sin internet: voz SAPI de Windows (más robótica, pero funciona)."""
    try:
        import pyttsx3

        eng = pyttsx3.init()
        eng.say(frase)
        eng.runAndWait()
    except Exception:
        pass

"""LOOP 2 — Conversación por voz.

  LAY-cli --rol voz            # micrófono
  LAY-cli --rol voz --texto    # teclado (pruebas sin micro)

Estados (se ven en el HUD):
  standby     Vosk escucha solo la palabra clave, offline.
  escuchando  graba la frase (con 1 s de pre-roll: "LAY, abre Spotify" de un tirón funciona).
  pensando    Claude (Sonnet/Opus según router) responde en streaming.
  hablando    LAY habla frase por frase; "LAY, para" / puño / Esc lo interrumpen.
  abierto     8 s tras responder: puedes seguir sin repetir "LAY".

Sin modelo Vosk cae al modo anterior (Google STT continuo), avisando en consola.
"""

from __future__ import annotations

import argparse
import json
import threading
import time

import httpx

from lay_core import bus
from lay_core.cerebro import Cerebro
from lay_core.config import CONFIG, HUB_TOKEN, HUB_URL
from loops import audio
from loops.locutor import Fraseador, Locutor

VENTANA_ABIERTA_S = 8.0


def estado(nombre: str, **extra) -> None:
    bus.publicar("voz.estado", estado=nombre, **extra)


def quitar_wake(texto: str) -> str | None:
    """'Oye LAY, abre Spotify' -> 'abre Spotify'. None si no la llamaron.
    "LAY" debe ser la 1.ª palabra o ir tras un saludo ("oye", "hola", "ok"): así
    "la ley de contrataciones dice..." no se toma como una orden."""
    palabras = texto.strip().split()
    limpias = [p.lower().strip(",.¡!¿?") for p in palabras]
    claves = {w.split()[-1] for w in CONFIG.wake_words} | {"ley", "lay", "lei"}
    saludos = {"oye", "hola", "ok", "okay", "hey", "ey"}
    i = 1 if limpias and limpias[0] in saludos else 0
    if len(limpias) > i and limpias[i] in claves:
        return " ".join(palabras[i + 1 :]).strip(" ,.")
    return None


def transcribir(pcm: bytes) -> str | None:
    import speech_recognition as sr

    try:
        return sr.Recognizer().recognize_google(sr.AudioData(pcm, audio.TASA, 2), language=CONFIG.idioma)
    except (sr.UnknownValueError, sr.RequestError):
        return None


class Conversacion:
    def __init__(self, texto: bool = False) -> None:
        self.cerebro = Cerebro()
        self.locutor = Locutor(
            CONFIG.voz_tts,
            al_empezar=lambda f: estado("hablando", texto=f),
            al_terminar=self._al_terminar_de_hablar,
        )
        self.modo_texto = texto
        self.mic_pausado = False  # desde la bandeja: LAY deja de escuchar
        self.turno_id = 0  # cambia al interrumpir: lo que siga llegando del modelo se descarta
        self.ocupado = threading.Event()  # pensando o hablando
        self.cola_remota: list[str] = []
        self.lock = threading.Lock()
        threading.Thread(target=self._hilo_remoto, daemon=True).start()
        threading.Thread(target=self._hilo_hub, daemon=True).start()

    # ---------- un turno ----------
    def turno(self, texto: str, t_fin_habla: float | None = None) -> None:
        """Procesa un pedido completo. Bloquea hasta terminar de pensar (no de hablar)."""
        mi_id = self.turno_id
        self.ocupado.set()
        bus.publicar("voz.transcripcion", texto=texto)
        estado("pensando")
        self.locutor.t_primer_audio = None

        def decir(frase: str) -> None:
            if self.turno_id == mi_id:
                self.locutor.decir(frase)

        fr = Fraseador(decir)
        if t_fin_habla is not None:
            threading.Thread(target=self._medir, args=(t_fin_habla,), daemon=True).start()
        try:
            respuesta = self.cerebro.responder(texto, al_texto=fr.agregar)
            fr.cerrar()
            if fr.emitidas == 0 and respuesta:  # respaldo (cliente sin streaming)
                decir(respuesta)
            print(f"LAY> {respuesta}")
        finally:
            if not self.locutor.hablando():
                self.ocupado.clear()
                estado("standby")

    def turno_en_hilo(self, texto: str, t_fin_habla: float | None = None) -> None:
        self.ocupado.set()
        threading.Thread(target=self.turno, args=(texto, t_fin_habla), daemon=True).start()

    def _al_terminar_de_hablar(self) -> None:
        self.ocupado.clear()
        estado("standby")

    def _medir(self, t0: float) -> None:
        for _ in range(200):
            if self.locutor.t_primer_audio:
                ms = int((self.locutor.t_primer_audio - t0) * 1000)
                bus.publicar("hud.latencia", ms=ms)
                return
            time.sleep(0.05)

    def callar(self) -> None:
        """Interrumpe: corta la voz y descarta lo que el modelo siga generando."""
        self.turno_id += 1
        self.locutor.callar()
        self.ocupado.clear()
        estado("standby")

    # ---------- hilos auxiliares ----------
    def _hilo_remoto(self) -> None:
        h = {"Authorization": f"Bearer {HUB_TOKEN}"} if HUB_TOKEN else {}
        while True:
            try:
                t = httpx.get(f"{HUB_URL}/api/comando/siguiente", headers=h, timeout=3).json().get("texto")
                if t:
                    with self.lock:
                        self.cola_remota.append(t)
            except Exception:
                pass
            time.sleep(1)

    def _hilo_hub(self) -> None:
        """voz.decir (del MCP), voz.callar (Esc en el HUD) y puño (gesto pausa) mientras habla."""
        from websockets.sync.client import connect

        while True:
            try:
                # solo lo que la voz usa: sin los 30 cuadros/s de manos
                url = f"ws://{CONFIG.hub_host}:{CONFIG.hub_port}/ws?tipos=voz.,config.,gesto"
                with connect(url) as ws:
                    for msg in ws:
                        ev = json.loads(msg)
                        if ev.get("tipo") == "voz.microfono":
                            self.mic_pausado = not ev.get("activo", True)
                            estado("pausado" if self.mic_pausado else "standby")
                        elif ev.get("tipo") == "config.cambiada":
                            from lay_core.config import recargar

                            recargar()  # nueva IA, voz o sensibilidad sin reiniciar LAY
                            self.locutor.voz = CONFIG.voz_tts
                        elif ev.get("tipo") == "voz.decir":
                            self.locutor.decir(ev["texto"])
                        elif ev.get("tipo") == "voz.callar" or (
                            ev.get("tipo") == "gesto" and ev.get("gesto") == "puno" and self.ocupado.is_set()
                        ):
                            self.callar()
            except Exception:
                time.sleep(2)

    def remoto_pendiente(self) -> str | None:
        with self.lock:
            return self.cola_remota.pop(0) if self.cola_remota else None

    # ---------- bucles ----------
    def bucle_texto(self) -> None:
        self.locutor.decir("LAY en línea.")
        while True:
            try:
                texto = self.remoto_pendiente() or input("tú> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.locutor.callar()
                return
            if texto:
                self.turno(texto)
                self.locutor.esperar(timeout=120)

    def bucle_microfono(self) -> None:
        ruta = audio.ruta_modelo_vosk()
        if ruta is None:
            try:
                print("Descargando modelo de voz offline (una sola vez, ~39 MB)...")
                ruta = audio.descargar_modelo_vosk()
            except Exception as exc:
                print(f"Sin modelo Vosk ({exc}). Modo simple: Google STT continuo.")
                return self.bucle_simple()

        mic = audio.Microfono(CONFIG.microfono)
        detector = audio.DetectorWake(ruta, CONFIG.confianza_wake)
        seg = audio.Segmentador()
        abierto_hasta = 0.0
        self.ocupado.set()
        self.locutor.decir("LAY en línea. Te escucho.")

        estaba_ocupado = False
        for bloque in mic.bloques():
            if self.mic_pausado:
                continue
            det = detector.alimentar(bloque)

            if self.ocupado.is_set():
                # Pensando o hablando: solo vale interrumpir ("LAY, para").
                # Su propia voz no debe activarla como si fuera un pedido nuevo.
                estaba_ocupado = True
                if det and det.tipo == "callar":
                    self.callar()
                    detector.reiniciar()
                seg.reposo(bloque)
                continue
            if estaba_ocupado:  # acaba de terminar de responder: ventana abierta
                estaba_ocupado = False
                mic.vaciar()
                detector.reiniciar()
                abierto_hasta = time.monotonic() + VENTANA_ABIERTA_S
                estado("abierto")
                continue

            remoto = self.remoto_pendiente()
            if remoto:
                self.turno_en_hilo(remoto)
                continue

            ventana_abierta = time.monotonic() < abierto_hasta
            empieza = (det and det.tipo == "wake") or (ventana_abierta and seg.es_voz(audio.rms(bloque)))
            if not empieza:
                seg.reposo(bloque)
                continue

            estado("escuchando")
            pcm = seg.grabar(mic.bloques(), esperar_voz_s=5 if det else 1.5)
            t_fin = time.monotonic()
            detector.reiniciar()
            if pcm is None:
                estado("standby")
                continue
            texto = transcribir(pcm)
            if not texto:
                estado("standby")
                continue
            comando = quitar_wake(texto)
            if comando is None:
                comando = texto if (ventana_abierta or det) else None
            if not comando:
                if det:  # solo dijo "LAY": contesta y, al terminar, se abre la ventana
                    self.ocupado.set()
                    self.locutor.decir("¿Sí?")
                else:
                    estado("standby")
                continue
            self.turno_en_hilo(comando, t_fin_habla=t_fin)

    def bucle_simple(self) -> None:
        """Respaldo sin Vosk: Google STT para todo (más lento, sin interrupción por voz)."""
        import speech_recognition as sr

        rec, mic = sr.Recognizer(), sr.Microphone()
        rec.pause_threshold = 0.7
        with mic as f:
            rec.adjust_for_ambient_noise(f, duration=1)
        abierto_hasta = 0.0
        while True:
            with mic as f:
                try:
                    a = rec.listen(f, timeout=2, phrase_time_limit=12)
                except sr.WaitTimeoutError:
                    continue
            try:
                texto = rec.recognize_google(a, language=CONFIG.idioma)
            except (sr.UnknownValueError, sr.RequestError):
                continue
            comando = texto if time.monotonic() < abierto_hasta else quitar_wake(texto)
            if comando:
                self.turno(comando)
                self.locutor.esperar(timeout=60)
                abierto_hasta = time.monotonic() + VENTANA_ABIERTA_S


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--texto", action="store_true")
    a = ap.parse_args()
    c = Conversacion(texto=a.texto)
    c.bucle_texto() if a.texto else c.bucle_microfono()


if __name__ == "__main__":
    main()

"""LOOP 1 — Percepción de manos (≈30 fps).

  python -m loops.gestos            # modo overlay (tarjetas holográficas)
  python -m loops.gestos --mouse    # modo mouse: controla el escritorio real

Cámara -> MediaPipe Hands (21 puntos por mano) -> clasificador -> eventos al hub.

Vocabulario (igual a la referencia + extras):
  PINCH sobre tarjeta      -> abrir / expandir
  PINCH + arrastrar        -> mover
  quieto 1 s pellizcando   -> rotar 3D
  DOS MANOS pellizcando    -> escalar (distancia entre manos)
  TAP (pinch corto)        -> cerrar el ítem abierto / click en modo mouse
  DOBLE TAP                -> doble click (abrir carpeta/archivo en modo mouse)
  CLAP (palmas juntas)     -> traer al anillo central
  SWIPE rápido (3+ dedos)  -> lanzar la imagen al monitor de izq/der/arriba/abajo
  DOS DEDOS arriba/abajo   -> scroll (en modo mouse, la rueda real)
  PALMA ABIERTA 1,5 s      -> alternar modo overlay <-> mouse
  DOS PALMAS 1,2 s         -> escaneo tipo Tony Stark: abre el explorador holográfico
  PUÑO 0,7 s               -> callar a LAY si está hablando
  PUÑO 2 s                 -> pausar / reanudar seguimiento
"""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import cv2
import mediapipe as mp
from websockets.sync.client import connect

from lay_core.config import CONFIG

PUNTA = {"pulgar": 4, "indice": 8, "medio": 12, "anular": 16, "menique": 20}
BASE = {"indice": 5, "medio": 9, "anular": 13, "menique": 17}

# Umbrales por defecto; `--calibrar` los ajusta a tu mano y cámara (lay.json -> "gestos")
_G = {"pinch_on": 0.33, "pinch_off": 0.45, "swipe_vel": 2.2, "complejidad": 1, **getattr(CONFIG, "gestos", {})}
ESCANEO_SEG = 1.2
PINCH_ON, PINCH_OFF = _G["pinch_on"], _G["pinch_off"]  # histéresis, relativo al tamaño de la mano
SWIPE_VEL = _G["swipe_vel"]
TAP_MAX_S, DOBLE_TAP_S = 0.28, 0.45


class OneEuro:
    """Filtro One Euro (Casiez 2012): quieto = muy suave (sin temblor), rápido = sin retraso.
    Mucho mejor que un promedio exponencial fijo para un cursor controlado por la mano."""

    def __init__(self, min_cutoff: float = 0.3, beta: float = 20.0, d_cutoff: float = 1.0) -> None:
        # Afinado con ruido realista de MediaPipe (±0,4 %): ~20 px de temblor en 3 monitores, sin retraso al mover rápido
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x = self.dx = self.t = None

    @staticmethod
    def _alfa(cutoff: float, dt: float) -> float:
        tau = 1 / (2 * math.pi * cutoff)
        return 1 / (1 + tau / dt)

    def __call__(self, x: float, t: float) -> float:
        if self.t is None:
            self.x, self.dx, self.t = x, 0.0, t
            return x
        dt = max(t - self.t, 1e-3)
        dx = (x - self.x) / dt
        a_d = self._alfa(self.d_cutoff, dt)
        self.dx = a_d * dx + (1 - a_d) * self.dx
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        a = self._alfa(cutoff, dt)
        self.x, self.t = a * x + (1 - a) * self.x, t
        return self.x


def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


@dataclass
class EstadoMano:
    pinch: bool = False
    t_pinch: float = 0.0
    origen: tuple[float, float] = (0, 0)
    muneca: tuple[float, float] = (0, 0)
    origen_muneca: tuple[float, float] = (0, 0)
    cursor: tuple[float, float] = (0.5, 0.5)
    historial: deque = field(default_factory=lambda: deque(maxlen=8))
    t_palma: float | None = None
    t_puno: float | None = None
    t_quieto: float | None = None
    ultimo_tap: float = float("-inf")
    fx: OneEuro = field(default_factory=OneEuro)
    fy: OneEuro = field(default_factory=OneEuro)
    y_scroll: float | None = None
    puno_avisado: bool = False


class Clasificador:
    def __init__(self, emitir) -> None:
        self.emitir = emitir
        self.manos: dict[str, EstadoMano] = {"Left": EstadoMano(), "Right": EstadoMano()}
        self.dist_dos_manos: float | None = None
        self.t_clap = 0.0
        self.t_escaneo: float | None = None  # dos palmas abiertas: escaneo tipo Tony Stark
        self.t_escaneo_fin = -10.0
        self.pct_escaneo = -1
        self.modo_mouse = CONFIG.modo_mouse_por_defecto
        self.pausado = False

    # --- utilidades de pose ---
    @staticmethod
    def tam(lm) -> float:
        return dist(lm[0], lm[9]) + 1e-6

    @staticmethod
    def extendido(lm, dedo: str) -> bool:
        return dist(lm[0], lm[PUNTA[dedo]]) > dist(lm[0], lm[BASE[dedo]]) * 1.6

    @classmethod
    def dedos_extendidos(cls, lm) -> int:
        return sum(1 for d in ("indice", "medio", "anular", "menique") if cls.extendido(lm, d))

    @classmethod
    def dos_dedos(cls, lm) -> bool:
        """Índice y medio estirados, anular y meñique doblados (gesto de scroll)."""
        return (
            cls.extendido(lm, "indice")
            and cls.extendido(lm, "medio")
            and not cls.extendido(lm, "anular")
            and not cls.extendido(lm, "menique")
        )

    def procesar(self, resultados, t: float) -> None:
        vistas = {}
        if resultados.multi_hand_landmarks:
            for lm, hd in zip(resultados.multi_hand_landmarks, resultados.multi_handedness):
                vistas[hd.classification[0].label] = lm.landmark

        self.emitir({"tipo": "manos", "manos": {k: [[p.x, p.y, p.z] for p in v] for k, v in vistas.items()}})

        self._escaneo(vistas, t)
        for lado, lm in vistas.items():
            self._mano(lado, lm, t)
        for lado in set(self.manos) - set(vistas):
            if self.manos[lado].pinch:
                self._soltar(lado, t)

        if len(vistas) == 2:
            self._dos_manos(vistas["Left"], vistas["Right"], t)
        else:
            self.dist_dos_manos = None

    @classmethod
    def palma_abierta(cls, lm) -> bool:
        return cls.dedos_extendidos(lm) == 4 and dist(lm[4], lm[8]) / cls.tam(lm) > 0.8

    def _escaneo(self, vistas: dict, t: float) -> None:
        """Las dos palmas abiertas mirando a la cámara durante ESCANEO_SEG -> 'escaneo' (abre el explorador)."""
        ambas = len(vistas) == 2 and all(self.palma_abierta(v) for v in vistas.values())
        if ambas and t - self.t_escaneo_fin > 2.5:
            # separadas (no es un aplauso) y a una altura parecida
            izq, der = vistas.get("Left"), vistas.get("Right")
            separadas = izq is not None and der is not None and abs(izq[9].x - der[9].x) > 0.2
            if not separadas:
                return
            self.t_escaneo = self.t_escaneo or t
            for e in self.manos.values():
                e.t_palma = None  # que no cambie a modo mouse mientras escanea
            pct = min(100, int((t - self.t_escaneo) / ESCANEO_SEG * 100))
            if pct // 10 != self.pct_escaneo // 10:
                self.pct_escaneo = pct
                self.emitir(
                    {
                        "tipo": "gesto",
                        "gesto": "escaneo_progreso",
                        "pct": pct,
                        "manos": [[izq[9].x, izq[9].y], [der[9].x, der[9].y]],
                    }
                )
            if pct >= 100:
                self.t_escaneo, self.t_escaneo_fin, self.pct_escaneo = None, t, -1
                self.emitir({"tipo": "gesto", "gesto": "escaneo"})
            return
        if self.t_escaneo is not None:
            self.emitir({"tipo": "gesto", "gesto": "escaneo_cancelado"})
        self.t_escaneo, self.pct_escaneo = None, -1

    def _mano(self, lado: str, lm, t: float) -> None:
        e = self.manos[lado]
        s = self.tam(lm)
        d_pinch = dist(lm[4], lm[8]) / s
        ext = self.dedos_extendidos(lm)

        # Cursor = punto medio pulgar-índice, filtrado One Euro. El frame ya llega
        # espejado (main() hace flip), así que x crece hacia la derecha de Robert.
        cx, cy = (lm[4].x + lm[8].x) / 2, (lm[4].y + lm[8].y) / 2
        e.cursor = (e.fx(cx, t), e.fy(cy, t))
        e.historial.append((t, *e.cursor))
        e.muneca = (lm[0].x, lm[0].y)  # estable al pellizcar: sirve para distinguir tap de arrastre

        # Puño 0,7 s -> "puno" (calla a LAY) · puño 2 s -> pausa/reanuda el seguimiento
        if ext == 0 and d_pinch > PINCH_OFF:
            if e.t_puno is None:
                e.t_puno, e.puno_avisado = t, False
            if t - e.t_puno > 0.7 and not e.puno_avisado:
                e.puno_avisado = True
                self.emitir({"tipo": "gesto", "gesto": "puno"})
            if t - e.t_puno > 2.0:
                self.pausado = not self.pausado
                self.emitir({"tipo": "gesto", "gesto": "pausa", "activo": self.pausado})
                e.t_puno = None
        else:
            e.t_puno = None
        if self.pausado:
            return

        # Palma abierta 1,5 s -> cambiar modo (no durante el escaneo de dos manos)
        if ext == 4 and d_pinch > 0.8 and self.t_escaneo is None and t - self.t_escaneo_fin > 3:
            e.t_palma = e.t_palma or t
            if t - e.t_palma > 1.5:
                self.modo_mouse = not self.modo_mouse
                self.emitir({"tipo": "gesto", "gesto": "modo", "mouse": self.modo_mouse})
                e.t_palma = None
        else:
            e.t_palma = None

        self.emitir({"tipo": "cursor", "mano": lado, "x": e.cursor[0], "y": e.cursor[1], "pinch": e.pinch})
        if self.modo_mouse and lado == "Right":
            self._mouse_mover(e.cursor)

        # Pinch con histéresis
        if not e.pinch and d_pinch < PINCH_ON:
            e.pinch, e.t_pinch, e.origen, e.origen_muneca = True, t, e.cursor, e.muneca
            self.emitir({"tipo": "gesto", "gesto": "pinch_inicio", "mano": lado, "x": e.cursor[0], "y": e.cursor[1]})
            if self.modo_mouse:
                self._mouse_presionar()
        elif e.pinch and d_pinch > PINCH_OFF:
            self._soltar(lado, t)
        elif e.pinch:
            dx, dy = e.cursor[0] - e.origen[0], e.cursor[1] - e.origen[1]
            self.emitir(
                {
                    "tipo": "gesto",
                    "gesto": "arrastrar",
                    "mano": lado,
                    "x": e.cursor[0],
                    "y": e.cursor[1],
                    "dx": dx,
                    "dy": dy,
                }
            )
            # Quieto 1 s pellizcando -> rotación 3D
            vel = self._velocidad(e)
            if vel < 0.05:
                e.t_quieto = e.t_quieto or t
                if t - e.t_quieto > 1.0:
                    self.emitir({"tipo": "gesto", "gesto": "rotar3d", "mano": lado})
                    e.t_quieto = t + 10  # no repetir
            else:
                e.t_quieto = None

        # Scroll: dos dedos (índice + medio) y mover la mano arriba/abajo
        if not e.pinch and self.dos_dedos(lm):
            if e.y_scroll is not None:
                dy = e.cursor[1] - e.y_scroll
                if abs(dy) > 0.025:
                    pasos = int(dy / 0.025)
                    self.emitir({"tipo": "gesto", "gesto": "scroll", "mano": lado, "pasos": pasos})
                    if self.modo_mouse:
                        self._mouse_scroll(-pasos)  # mano abajo = contenido baja (como el touchpad)
                    e.y_scroll = e.cursor[1]
            else:
                e.y_scroll = e.cursor[1]
            return
        e.y_scroll = None

        # Swipe/snap rápido sin pinch -> lanzar a monitor
        if not e.pinch and ext >= 3:
            vx, vy = self._velocidad(e, eje=0), self._velocidad(e, eje=1)
            if max(abs(vx), abs(vy)) > SWIPE_VEL:
                if abs(vx) >= abs(vy):
                    direccion = "derecha" if vx > 0 else "izquierda"
                else:
                    direccion = "abajo" if vy > 0 else "arriba"  # p. ej. el monitor sobre la laptop
                self.emitir(
                    {"tipo": "gesto", "gesto": "lanzar", "direccion": direccion, "x": e.cursor[0], "y": e.cursor[1]}
                )
                e.historial.clear()

    def _soltar(self, lado: str, t: float) -> None:
        e = self.manos[lado]
        dur = t - e.t_pinch
        movido = math.hypot(e.muneca[0] - e.origen_muneca[0], e.muneca[1] - e.origen_muneca[1])
        e.pinch, e.t_quieto = False, None
        if self.modo_mouse:
            self._mouse_soltar()
        if dur < TAP_MAX_S and movido < 0.03:
            doble = t - e.ultimo_tap < DOBLE_TAP_S
            e.ultimo_tap = t
            self.emitir(
                {
                    "tipo": "gesto",
                    "gesto": "doble_tap" if doble else "tap",
                    "mano": lado,
                    "x": e.cursor[0],
                    "y": e.cursor[1],
                }
            )
            # En modo mouse, dos taps seguidos ya son mouseDown/Up x2 = doble click nativo
        else:
            self.emitir({"tipo": "gesto", "gesto": "pinch_fin", "mano": lado, "x": e.cursor[0], "y": e.cursor[1]})

    def _dos_manos(self, izq, der, t: float) -> None:
        a, b = self.manos["Left"], self.manos["Right"]
        # Escala con dos pinch
        if a.pinch and b.pinch:
            d = math.hypot(a.cursor[0] - b.cursor[0], a.cursor[1] - b.cursor[1])
            if self.dist_dos_manos:
                self.emitir(
                    {
                        "tipo": "gesto",
                        "gesto": "escalar",
                        "factor": d / self.dist_dos_manos,
                        "x": (a.cursor[0] + b.cursor[0]) / 2,
                        "y": (a.cursor[1] + b.cursor[1]) / 2,
                    }
                )
            self.dist_dos_manos = d
            return
        self.dist_dos_manos = None
        # Clap: muñecas y palmas muy cerca, dedos arriba
        palmas = dist(izq[9], der[9]) / ((self.tam(izq) + self.tam(der)) / 2)
        if palmas < 0.55 and izq[12].y < izq[0].y and der[12].y < der[0].y and t - self.t_clap > 1.0:
            self.t_clap = t
            self.emitir({"tipo": "gesto", "gesto": "clap"})

    @staticmethod
    def _velocidad(e: EstadoMano, eje: int | None = None) -> float:
        if len(e.historial) < 3:
            return 0.0
        t0, x0, y0 = e.historial[0]
        t1, x1, y1 = e.historial[-1]
        dt = max(t1 - t0, 1e-3)
        if eje == 0:
            return (x1 - x0) / dt
        if eje == 1:
            return (y1 - y0) / dt
        return math.hypot(x1 - x0, y1 - y0) / dt

    # --- modo mouse ---
    _escritorio: tuple[int, int, int, int] | None = None

    @classmethod
    def escritorio_virtual(cls) -> tuple[int, int, int, int]:
        """(x, y, ancho, alto) que abarca TODOS los monitores. pyautogui.size() solo da el principal."""
        if cls._escritorio is None:
            try:
                from lay_core.escritorio import monitores

                ms = monitores()
                x0, y0 = min(m["x"] for m in ms), min(m["y"] for m in ms)
                x1 = max(m["x"] + m["ancho"] for m in ms)
                y1 = max(m["y"] + m["alto"] for m in ms)
                cls._escritorio = (x0, y0, x1 - x0, y1 - y0)
            except Exception:
                import pyautogui

                w, h = pyautogui.size()
                cls._escritorio = (0, 0, w, h)
        return cls._escritorio

    def _mouse_mover(self, c) -> None:
        import pyautogui

        x0, y0, w, h = self.escritorio_virtual()
        # margen: el 15 % del borde del cuadro de cámara mapea al borde del escritorio
        x = int(x0 + min(max((c[0] - 0.15) / 0.7, 0), 1) * (w - 1))
        y = int(y0 + min(max((c[1] - 0.15) / 0.7, 0), 1) * (h - 1))
        ultimo = getattr(self, "_ultimo_mouse", None)
        if ultimo and abs(x - ultimo[0]) < 6 and abs(y - ultimo[1]) < 6:
            return  # zona muerta: el cursor no baila mientras apuntas para hacer clic
        self._ultimo_mouse = (x, y)
        pyautogui.moveTo(x, y, _pause=False)

    def _mouse_scroll(self, pasos: int) -> None:
        import pyautogui

        pyautogui.scroll(pasos * 120, _pause=False)

    def _mouse_presionar(self) -> None:
        import pyautogui

        pyautogui.mouseDown(_pause=False)

    def _mouse_soltar(self) -> None:
        import pyautogui

        pyautogui.mouseUp(_pause=False)


class Emisor:
    """WebSocket persistente al hub, con reconexión. Descarta frames si el hub cae."""

    def __init__(self, url: str) -> None:
        self.url, self.ws, self.lock = url, None, threading.Lock()

    def __call__(self, ev: dict) -> None:
        with self.lock:
            try:
                if self.ws is None:
                    self.ws = connect(self.url, open_timeout=1)
                self.ws.send(json.dumps(ev))
            except Exception:
                self.ws = None


def main() -> None:
    import pyautogui

    pyautogui.FAILSAFE = True  # mover el mouse a una esquina aborta

    ap = argparse.ArgumentParser()
    ap.add_argument("--mouse", action="store_true")
    ap.add_argument("--debug", action="store_true", help="ventana con la cámara y los puntos")
    ap.add_argument("--calibrar", action="store_true", help="ajusta los umbrales a tu mano (30 s)")
    a = ap.parse_args()
    if a.calibrar:
        return calibrar()

    emitir = Emisor(f"ws://{CONFIG.hub_host}:{CONFIG.hub_port}/ws")
    clf = Clasificador(emitir)
    clf.modo_mouse = a.mouse or clf.modo_mouse

    cap = abrir_camara()
    hands = mp.solutions.hands.Hands(
        max_num_hands=2,
        model_complexity=int(_G["complejidad"]),
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    dibujar = mp.solutions.drawing_utils
    print("LAY gestos activo. Palma abierta 1,5 s = cambiar modo. Puño 1 s = pausa. Ctrl+C para salir.")
    fallos, cuadros, t_fps = 0, 0, time.monotonic()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                fallos += 1
                if fallos > 60:  # ~3 s sin imagen: cámara desconectada o tomada por otra app
                    emitir({"tipo": "hud.camara", "ok": False})
                    cap.release()
                    time.sleep(2)
                    cap, fallos = abrir_camara(), 0
                time.sleep(0.05)
                continue
            if fallos:
                emitir({"tipo": "hud.camara", "ok": True})
            fallos = 0
            # Espejo ANTES de MediaPipe: su lateralidad (Left/Right) asume imagen tipo selfie.
            frame = cv2.flip(frame, 1)
            res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            clf.procesar(res, time.time())
            cuadros += 1
            if time.monotonic() - t_fps >= 1:
                emitir({"tipo": "hud.fps", "fps": cuadros})
                cuadros, t_fps = 0, time.monotonic()
            if a.debug:
                if res.multi_hand_landmarks:
                    for lm in res.multi_hand_landmarks:
                        dibujar.draw_landmarks(frame, lm, mp.solutions.hands.HAND_CONNECTIONS)
                cv2.imshow("LAY gestos (debug)", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def abrir_camara():
    cap = cv2.VideoCapture(CONFIG.camara_indice, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
    return cap


def umbrales_desde_muestras(abierta: list[float], pinch: list[float]) -> dict:
    """Con tus distancias reales (mano abierta vs pellizco) fija la histéresis:
    pinch_on al 35 % del camino y pinch_off al 55 %, para que no parpadee."""
    a = sorted(abierta)[len(abierta) // 2]
    p = sorted(pinch)[int(len(pinch) * 0.9)]  # percentil 90: tolera pellizcos flojos
    if a - p < 0.15:
        raise ValueError("No distinguí bien mano abierta de pellizco; repite con más luz y la mano de frente.")
    return {"pinch_on": round(p + (a - p) * 0.35, 3), "pinch_off": round(p + (a - p) * 0.55, 3)}


def calibrar() -> None:
    """Asistente de calibración en consola: 2 poses x 5 s. Guarda en ~/.lay/lay.json."""
    from lay_core.config import CONFIG_FILE

    cap = abrir_camara()
    hands = mp.solutions.hands.Hands(max_num_hands=1, model_complexity=1, min_detection_confidence=0.6)
    muestras: dict[str, list[float]] = {}
    for clave, instruccion in (("abierta", "MANO ABIERTA, dedos separados"), ("pinch", "PELLIZCO pulgar-índice")):
        input(f"\nPon la mano derecha frente a la cámara: {instruccion}. Enter para empezar (5 s)...")
        datos, fin = [], time.monotonic() + 5
        while time.monotonic() < fin:
            ok, frame = cap.read()
            if not ok:
                continue
            res = hands.process(cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB))
            if res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0].landmark
                datos.append(dist(lm[4], lm[8]) / Clasificador.tam(lm))
        print(f"  {len(datos)} muestras")
        muestras[clave] = datos or [0.0]
    cap.release()
    nuevos = umbrales_desde_muestras(muestras["abierta"], muestras["pinch"])
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    cfg["gestos"] = {**cfg.get("gestos", {}), **nuevos}
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nListo: {nuevos} guardado en {CONFIG_FILE}. Reinicia LAY.")


if __name__ == "__main__":
    main()

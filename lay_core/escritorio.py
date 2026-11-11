"""Control del escritorio: monitores, ventanas, apps, teclado, capturas.

Pensado para Windows 11 (pygetwindow + pyautogui + screeninfo). En otros SO
degrada con errores claros en lugar de romper.
"""

from __future__ import annotations

import os
import platform
import subprocess
import time
from pathlib import Path

from lay_core.config import CONFIG, DATA_DIR
from lay_core.seguridad import ruta_permitida, sensible

ES_WINDOWS = platform.system() == "Windows"

if ES_WINDOWS:
    # Sin esto, con escala 125-150 % (laptops) las coordenadas salen escaladas y las
    # ventanas quedan corridas o recortadas en monitores con distinto DPI.
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

TITULOS_PROPIOS = ("LAY — Interfaz", "LAY dev")  # nunca mover/cerrar el HUD de LAY por accidente

POSICIONES = {
    # (x, y, ancho, alto) como fracción del monitor
    "completa": (0, 0, 1, 1),
    "izquierda": (0, 0, 0.5, 1),
    "derecha": (0.5, 0, 0.5, 1),
    "arriba": (0, 0, 1, 0.5),
    "abajo": (0, 0.5, 1, 0.5),
    "arriba-izquierda": (0, 0, 0.5, 0.5),
    "arriba-derecha": (0.5, 0, 0.5, 0.5),
    "abajo-izquierda": (0, 0.5, 0.5, 0.5),
    "abajo-derecha": (0.5, 0.5, 0.5, 0.5),
    "centro": (0.2, 0.15, 0.6, 0.7),
    "maximizada": (0, 0, 1, 1),  # mueve al monitor y maximiza (respeta la barra de tareas)
}


def _gw():
    import pygetwindow as gw  # solo Windows/mac

    return gw


def monitores() -> list[dict]:
    from screeninfo import get_monitors

    out = []
    for i, m in enumerate(sorted(get_monitors(), key=lambda m: m.x)):
        out.append(
            {
                "indice": i + 1,
                "x": m.x,
                "y": m.y,
                "ancho": m.width,
                "alto": m.height,
                "principal": bool(getattr(m, "is_primary", False)),
                "nombre": m.name,
            }
        )
    return out


def ventanas() -> list[dict]:
    gw = _gw()
    res = []
    for w in gw.getAllWindows():
        if w.title.strip() and w.width > 50:
            res.append(
                {
                    "titulo": w.title,
                    "x": w.left,
                    "y": w.top,
                    "ancho": w.width,
                    "alto": w.height,
                    "minimizada": w.isMinimized,
                }
            )
    return res


def _puntaje(w, buscado: str) -> tuple:
    """Orden de preferencia: visible > coincidencia de título > tamaño."""
    t = w.title.lower()
    coincide = 3 if t == buscado else 2 if t.endswith(buscado) or t.startswith(buscado) else 1
    return (not w.isMinimized, coincide, min(w.width * w.height, 4_000_000))


def _buscar_ventana(titulo: str, espera: float = 0):
    """Mejor ventana cuyo título contenga `titulo` (sin distinguir mayúsculas).
    Espera hasta `espera` s a que aparezca (apps recién lanzadas)."""
    gw = _gw()
    buscado = titulo.lower().strip()
    limite = time.time() + espera
    while True:
        cand = [
            w
            for w in gw.getAllWindows()
            if w.title.strip()
            and buscado in w.title.lower()
            and w.width > 50
            and not w.title.startswith(TITULOS_PROPIOS)
        ]
        if cand or time.time() >= limite:
            return max(cand, key=lambda w: _puntaje(w, buscado)) if cand else None
        time.sleep(0.3)


def monitor_de_punto(x: int, y: int) -> int:
    for m in monitores():
        if m["x"] <= x < m["x"] + m["ancho"] and m["y"] <= y < m["y"] + m["alto"]:
            return m["indice"]
    return 1


def monitor_vecino(direccion: str, desde: int | None = None) -> int:
    """Monitor a la izquierda/derecha del actual (el del cursor si no se indica).
    En los extremos se queda en el mismo (no da la vuelta)."""
    mons = monitores()
    if desde is None:
        try:
            import pyautogui

            desde = monitor_de_punto(*pyautogui.position())
        except Exception:
            desde = 1
    paso = 1 if direccion == "derecha" else -1
    return min(max(desde + paso, 1), len(mons)) if mons else 1


def mover_ventana(titulo: str, monitor: int = 1, posicion: str = "completa") -> dict:
    w = _buscar_ventana(titulo, espera=5)
    if w is None:
        return {"error": f"No encontré una ventana que contenga '{titulo}'"}
    if posicion not in POSICIONES:
        return {"error": f"Posición '{posicion}' no válida", "validas": sorted(POSICIONES)}
    mons = monitores()
    aviso = None
    if not 1 <= monitor <= len(mons):
        # Config pensada para 3 monitores usada con la laptop sola: no fallar, usar el último
        aviso = f"Monitor {monitor} no está conectado; usé el {len(mons)}."
        monitor = len(mons)
    m = mons[monitor - 1]
    fx, fy, fw, fh = POSICIONES[posicion]
    if w.isMinimized or w.isMaximized:
        w.restore()
    w.moveTo(int(m["x"] + fx * m["ancho"]), int(m["y"] + fy * m["alto"]))
    if posicion == "maximizada":
        w.maximize()
    else:
        w.resizeTo(int(fw * m["ancho"]), int(fh * m["alto"]))
    try:
        w.activate()
    except Exception:
        pass
    res = {"ok": True, "ventana": w.title, "monitor": monitor, "posicion": posicion}
    if aviso:
        res["aviso"] = aviso
    return res


def enfocar_ventana(titulo: str) -> dict:
    w = _buscar_ventana(titulo)
    if w is None:
        return {"error": f"No encontré '{titulo}'"}
    if w.isMinimized:
        w.restore()
    w.activate()
    return {"ok": True, "ventana": w.title}


def abrir(ruta_o_url: str) -> dict:
    """Abre archivo, carpeta o URL con la app por defecto."""
    es_url = ruta_o_url.startswith(("http://", "https://"))
    if not es_url:
        p = Path(os.path.expandvars(os.path.expanduser(ruta_o_url)))
        if not p.exists():
            return {"error": f"No existe: {p}"}
        ruta_o_url = str(p)
    if ES_WINDOWS:
        os.startfile(ruta_o_url)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", ruta_o_url])
    else:
        subprocess.Popen(["xdg-open", ruta_o_url])
    return {"ok": True, "abierto": ruta_o_url}


def lanzar_app(nombre: str) -> dict:
    """Lanza una app por alias configurado en config/lay.json -> apps."""
    destino = CONFIG.apps.get(nombre.lower())
    if destino is None:
        return {"error": f"App '{nombre}' no configurada", "disponibles": sorted(CONFIG.apps)}
    if destino.startswith(("http://", "https://")) or Path(os.path.expandvars(destino)).exists():
        return abrir(os.path.expandvars(destino))
    subprocess.Popen(destino, shell=True)
    return {"ok": True, "lanzado": destino}


def aplicar_workspace(nombre: str) -> dict:
    """Abre un conjunto de apps y las reparte por monitores (video de referencia 1)."""
    items = CONFIG.workspaces.get(nombre.lower())
    if not items:
        return {"error": f"Workspace '{nombre}' no existe", "disponibles": sorted(CONFIG.workspaces)}
    from concurrent.futures import ThreadPoolExecutor

    # 1) lanzar todo de una vez (las apps arrancan en paralelo)
    lanzados = []
    for it in items:
        r = lanzar_app(it["app"]) if it.get("app") else abrir(it["abrir"])
        lanzados.append(r)

    # 2) acomodar cada ventana apenas aparezca (espera máx. 12 s c/u, en paralelo)
    def acomodar(par):
        it, lanzado = par
        if "error" in lanzado:
            return {"item": it.get("app") or it.get("abrir"), **lanzado}
        w = _buscar_ventana(it["titulo"], espera=12)
        if w is None:
            return {"item": it["titulo"], "error": "la ventana no apareció en 12 s"}
        return mover_ventana(it["titulo"], it.get("monitor", 1), it.get("posicion", "completa"))

    with ThreadPoolExecutor(max_workers=len(items)) as ex:
        detalle = list(ex.map(acomodar, zip(items, lanzados)))
    fallos = [d for d in detalle if "error" in d]
    return {
        "ok": not fallos,
        "workspace": nombre,
        "acomodadas": len(items) - len(fallos),
        "total": len(items),
        "detalle": detalle,
    }


def captura(monitor: int = 0) -> dict:
    """Captura de pantalla. monitor=0 -> todos."""
    import mss
    import mss.tools

    destino = DATA_DIR / f"captura_{int(time.time())}.png"
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[monitor])
        mss.tools.to_png(shot.rgb, shot.size, output=str(destino))
    return {"ok": True, "ruta": str(destino)}


def atajo(teclas: str) -> dict:
    """Ej: 'ctrl+s', 'win+d', 'alt+tab'. Atajos destructivos se bloquean."""
    bloqueados = {"alt+f4", "ctrl+alt+delete", "ctrl+shift+delete", "shift+delete"}
    if teclas.lower().replace(" ", "") in bloqueados:
        return {"error": f"Atajo '{teclas}' bloqueado; pídelo como acción explícita."}
    import pyautogui

    pyautogui.hotkey(*[t.strip() for t in teclas.lower().split("+")])
    return {"ok": True, "atajo": teclas}


@sensible("LAY va a escribir texto en la ventana activa")
def escribir(texto: str, ventana: str | None = None) -> dict:
    import pyautogui
    import pyperclip

    if ventana:
        r = enfocar_ventana(ventana)
        if "error" in r:
            return r
        time.sleep(0.3)
    # Pegado vía portapapeles: soporta tildes y ñ (pyautogui.write no)
    previo = pyperclip.paste()
    pyperclip.copy(texto)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.2)
    pyperclip.copy(previo)
    return {"ok": True, "caracteres": len(texto)}


@sensible("LAY va a cerrar una ventana (puede perder cambios sin guardar)")
def cerrar_ventana(titulo: str) -> dict:
    w = _buscar_ventana(titulo)  # excluye el HUD de LAY
    if w is None:
        return {"error": f"No encontré '{titulo}'"}
    w.close()
    return {"ok": True, "cerrada": w.title}


def mover_mouse(x: int, y: int) -> None:
    import pyautogui

    pyautogui.moveTo(x, y, _pause=False)


def click(boton: str = "left", doble: bool = False) -> None:
    import pyautogui

    pyautogui.click(button=boton, clicks=2 if doble else 1, _pause=False)


def abrir_seguro(ruta: str) -> dict:
    if not ruta.startswith("http") and not ruta_permitida(ruta):
        return {"error": "Ruta protegida del sistema"}
    return abrir(ruta)

"""Diagnóstico de LAY: prueba DE VERDAD cada parte (como queda en el .exe) y dice qué falla y por qué.

  LAY-cli.exe --rol diagnostico          en tu PC (también: Configuración → Diagnóstico)
  LAY-cli.exe --rol diagnostico --ci     en GitHub Actions (Windows real, sin cámara ni micrófono)

Resultado en pantalla y en ~/.lay/diagnostico.txt.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import threading
import time
from typing import Callable

from lay_core.config import DATA_DIR

ES_WINDOWS = platform.system() == "Windows"


def _con_limite(fn: Callable[[], str], segundos: float) -> str:
    """Corre fn con tope de tiempo (algunas pruebas pueden colgarse en PCs raras)."""
    res: dict = {}

    def correr():
        try:
            res["ok"] = fn()
        except BaseException as exc:  # noqa: BLE001
            res["error"] = exc

    t = threading.Thread(target=correr, daemon=True)
    t.start()
    t.join(segundos)
    if t.is_alive():
        raise TimeoutError(f"no respondió en {segundos:.0f} s")
    if "error" in res:
        raise res["error"]
    return res.get("ok", "")


# ---------------- pruebas ----------------
def p_manos_import() -> str:
    import mediapipe as mp

    h = mp.solutions.hands.Hands(max_num_hands=2, model_complexity=0)  # carga el modelo .tflite
    h.close()
    return f"MediaPipe {mp.__version__} y su modelo de manos cargan"


def p_camara() -> str:
    import cv2

    from lay_core.config import CONFIG

    cap = cv2.VideoCapture(CONFIG.camara_indice, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError(
            f"la cámara {CONFIG.camara_indice} no entrega imagen (¿la usa otra app? ¿permiso de cámara?)"
        )
    return f"cámara {CONFIG.camara_indice}: {frame.shape[1]}x{frame.shape[0]}"


def p_microfono() -> str:
    import pyaudio

    pa = pyaudio.PyAudio()
    n = sum(1 for i in range(pa.get_device_count()) if pa.get_device_info_by_index(i).get("maxInputChannels", 0) > 0)
    pa.terminate()
    if not n:
        raise RuntimeError("no hay micrófonos")
    return f"{n} entradas de audio"


def p_vosk() -> str:
    from loops import audio

    ruta = audio.ruta_modelo_vosk()
    if ruta is None:
        raise RuntimeError("falta el modelo de voz offline (se descarga al primer uso)")
    import vosk

    vosk.SetLogLevel(-1)
    vosk.Model(str(ruta))
    return f"modelo de palabra clave en {ruta.name}"


def p_voz_tts() -> str:
    from lay_core.config import CONFIG
    from loops.locutor import sintetizar_edge

    mp3 = sintetizar_edge("Hola, soy LAY.", CONFIG.voz_tts)
    if len(mp3) < 1000:
        raise RuntimeError("la voz no generó audio")
    return f"voz {CONFIG.voz_tts}: {len(mp3) // 1024} KB"


def p_nucleo() -> str:
    from lay_core import nucleo

    r = nucleo.entender("sube el volumen al 40")
    if r.intencion != "volumen":
        raise RuntimeError(f"entendió '{r.intencion}'")
    return f"LAY Núcleo listo ({len(nucleo.cargar_modelo().etiquetas)} intenciones)"


def p_ia() -> str:
    from lay_core import proveedores
    from lay_core.config import CONFIG

    nombre = CONFIG.ia.get("proveedor", "ollama")
    if nombre == "nucleo":
        return "IA: LAY Núcleo (no necesita modelo)"
    prov = proveedores.crear(nombre, CONFIG.ia)
    t0 = time.monotonic()
    t = prov.turno("Responde solo: hola", [{"rol": "usuario", "texto": "hola"}], [], "rapido", 20)
    return f"{proveedores.NOMBRES.get(nombre, nombre)} responde en {time.monotonic() - t0:.1f} s: {t.texto[:40]!r}"


def p_web() -> str:
    from lay_core import informacion

    r = informacion.buscar_web("Lima Perú", 3)
    if "error" in r:
        raise RuntimeError(r["error"])
    return f"búsqueda web: {len(r['resultados'])} resultados"


def p_navegador() -> str:
    from lay_core import navegador

    disp = navegador.rutas_navegadores()
    if not disp:
        raise RuntimeError("no hay Brave, Chrome ni Edge")
    from lay_core.config import CONFIG

    CONFIG.navegador_perfil = "lay"  # aquí se prueba el control por dentro (Playwright)
    r = navegador.abrir("https://example.com")
    if "error" in r:
        raise RuntimeError(r["error"])
    leido = navegador.leer(300)
    els = navegador.elementos(10)
    pest = navegador.pestanas().get("pestanas") or []
    if pest:
        navegador.cerrar_pestana(len(pest) - 1)
    if "Example" not in leido.get("titulo", "") + leido.get("texto", ""):
        raise RuntimeError(f"abrió pero no pudo leer la página ({leido})")
    return f"{r['navegador']}: abre, lee y ve {len(els.get('elementos', []))} elementos"


def p_windows_ui() -> str:
    from lay_core import windows

    proc = subprocess.Popen(["notepad.exe"])
    try:
        time.sleep(2.5)
        titulo = next(t for t in ("Bloc de notas", "Notepad", "Sin título", "Untitled") if _hay_ventana(t))
        els = windows.elementos(titulo, 40)
        if not els["elementos"]:
            raise RuntimeError("leyó la ventana pero sin elementos")
        return f"UI Automation: {len(els['elementos'])} elementos en '{els['ventana']}'"
    finally:
        proc.kill()
        subprocess.run(["taskkill", "/F", "/IM", "notepad.exe"], capture_output=True)


def _hay_ventana(t: str) -> bool:
    try:
        from lay_core import windows

        windows._ventana(t)
        return True
    except Exception:
        return False


def p_apps() -> str:
    from lay_core import windows

    apps = windows.apps_instaladas()
    if not apps:
        raise RuntimeError("Get-StartApps no devolvió apps")
    return f"{len(apps)} apps instaladas detectadas (p. ej. {apps[0]['nombre']})"


def p_volumen() -> str:
    from lay_core import windows

    r = windows.volumen("consultar")
    if "error" in r:
        raise RuntimeError(r["error"])
    return f"volumen {r.get('volumen', '?')} %"


def p_musica() -> str:
    from lay_core import musica

    sp = musica.buscar_id_spotify("Nadie Sabe Bad Bunny", "track")
    yt = musica.primer_video_youtube("Nadie Sabe Bad Bunny")
    if not sp and not yt:
        raise RuntimeError("no encontré la canción ni en Spotify ni en YouTube")
    app = "app Spotify instalada" if musica.spotify_exe() else "Spotify no instalado (usa la web)"
    return f"Spotify: {'ID ' + sp[1] if sp else 'sin ID'} · YouTube: {'video ' + yt if yt else 'sin video'} · {app}"


def p_ventana_activa() -> str:
    from lay_core import windows

    proc = subprocess.Popen(["notepad.exe"])
    try:
        time.sleep(2.5)
        w = windows._ventana("activa")
        return f"ventana activa: '{w.window_text()[:40]}'"
    finally:
        proc.terminate()


def p_permisos() -> str:
    """Restricciones de Windows. No falla: informa qué limita a LAY y cómo arreglarlo."""
    from lay_core import permisos

    e = permisos.estado()
    if not e.get("windows"):
        return "no es Windows"
    if e["avisos"]:
        return "limitaciones: " + " · ".join(a.split(":")[0] for a in e["avisos"])
    return "sin restricciones" + (" (LAY corre como administrador)" if e["es_admin"] else "")


def p_aprendizaje() -> str:
    from lay_core.nucleo import aprendizaje

    e = aprendizaje.estado()
    return f"{e['frases_aprendidas']} frases aprendidas · {e['atajos']} atajos · modelo personal: {'sí' if e['modelo_personal'] else 'no'}"


PRUEBAS: list[tuple[str, str, Callable[[], str], float, bool]] = [
    # (clave, nombre, función, límite s, se prueba en CI)
    ("manos", "Manos (MediaPipe)", p_manos_import, 60, True),
    ("camara", "Cámara", p_camara, 15, False),
    ("microfono", "Micrófono", p_microfono, 10, False),
    ("vosk", "Palabra clave offline", p_vosk, 30, False),
    ("voz", "Voz de LAY", p_voz_tts, 25, True),
    ("nucleo", "LAY Núcleo (IA propia)", p_nucleo, 15, True),
    ("ia", "IA conversacional", p_ia, 90, False),
    ("web", "Búsqueda en internet", p_web, 30, True),
    ("navegador", "Control del navegador", p_navegador, 90, True),
    ("windows_ui", "Control de apps de Windows", p_windows_ui, 45, True),
    ("apps", "Apps instaladas", p_apps, 30, True),
    ("musica", "Poner canciones (Spotify/YouTube)", p_musica, 40, True),
    ("ventana_activa", "Clic en la app que tienes al frente", p_ventana_activa, 30, True),
    ("permisos", "Restricciones de Windows", p_permisos, 30, True),
    ("aprendizaje", "Aprendizaje de LAY", p_aprendizaje, 10, True),
    ("volumen", "Volumen", p_volumen, 10, False),
]


def ejecutar(ci: bool = False, avisar: Callable[[dict], None] | None = None) -> list[dict]:
    resultados = []
    for clave, nombre, fn, limite, en_ci in PRUEBAS:
        if ci and not en_ci:
            continue
        if not ES_WINDOWS and clave in ("windows_ui", "apps", "volumen"):
            continue
        t0 = time.monotonic()
        try:
            detalle, ok = _con_limite(fn, limite), True
        except BaseException as exc:  # noqa: BLE001
            from lay_core import registro

            registro.error(f"diagnostico:{clave}", exc if isinstance(exc, Exception) else None)
            detalle, ok = f"{type(exc).__name__}: {exc}"[:300], False
        r = {"clave": clave, "nombre": nombre, "ok": ok, "detalle": detalle, "seg": round(time.monotonic() - t0, 1)}
        resultados.append(r)
        if avisar:
            avisar(r)
    texto = "\n".join(
        f"{'OK ' if r['ok'] else 'FALLA'}  {r['nombre']:<30} {r['detalle']}  ({r['seg']} s)" for r in resultados
    )
    (DATA_DIR / "diagnostico.txt").write_text(time.strftime("%Y-%m-%d %H:%M\n") + texto + "\n", encoding="utf-8")
    return resultados


def main() -> None:
    ci = "--ci" in sys.argv
    print("=" * 70 + "\n  LAY · Diagnóstico" + (" (CI)" if ci else "") + "\n" + "=" * 70, flush=True)

    def mostrar(r: dict) -> None:
        try:
            print(f"  {'OK   ' if r['ok'] else 'FALLA'} {r['nombre']:<30} {r['detalle']}", flush=True)
        except Exception:  # noqa: BLE001 — una consola rara nunca debe tumbar el diagnóstico
            pass

    res = ejecutar(ci, mostrar)
    fallas = [r for r in res if not r["ok"]]
    print(f"\n  {len(res) - len(fallas)}/{len(res)} correctas. Detalle: {DATA_DIR / 'diagnostico.txt'}")
    if ci:
        (DATA_DIR / "diagnostico.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        sys.exit(1 if fallas else 0)
    time.sleep(3)

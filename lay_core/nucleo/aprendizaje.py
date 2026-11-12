"""LAY aprende de Robert mientras la usa.

Tres fuentes, todas locales (~/.lay/nucleo/):
  1. AUTOMÁTICO — cuando el Núcleo no entendió una orden pero la IA grande la resolvió con una
     herramienta que funcionó, esa frase queda como ejemplo de la intención correcta.
  2. CORRECCIÓN — "LAY, eso era para poner música": la última frase se vuelve a etiquetar.
  3. ENSEÑADO — "LAY, cuando diga 'modo obra' abre Revit y luego abre Excel": un atajo de voz
     (frase exacta o parecida -> una o varias órdenes). Funciona al instante, sin reentrenar.

Con 5 ejemplos nuevos el Núcleo se reentrena solo en segundo plano (unos 15 s con numpy) y el
modelo personal se guarda en ~/.lay/nucleo/modelo_nucleo.npz, que tiene prioridad sobre el de fábrica.
"""

from __future__ import annotations

import difflib
import json
import re
import threading
import time
from pathlib import Path

from lay_core.config import DATA_DIR

CARPETA = DATA_DIR / "nucleo"
EJEMPLOS = CARPETA / "aprendidas.jsonl"
ATAJOS = CARPETA / "atajos.json"
REENTRENAR_CADA = 5
MAX_EJEMPLOS = 5000
PESO = 6  # cada frase real de Robert vale como 6 sintéticas al entrenar

# Herramienta que usó la IA grande -> intención del Núcleo (para aprender de ella)
HERRAMIENTA_A_INTENCION = {
    "spotify_reproducir": "reproducir",
    "youtube_reproducir": "reproducir",
    "app_abrir": "abrir_app",
    "carpeta_abrir": "abrir_carpeta",
    "archivos_buscar": "buscar_archivo",
    "navegador_abrir": "abrir_web",
    "web_buscar": "pregunta_info",
    "clima": "clima",
    "volumen": "volumen",
    "multimedia": "musica",
    "brillo": "brillo",
    "ajustes_abrir": "ajustes",
    "ventana_mover_a": "mover_ventana",
    "pantalla_capturar": "captura",
    "recordatorio_crear": "recordatorio",
    "sistema_estado": "estado_pc",
    "sistema_procesos": "procesos",
    "app_buscar": "buscar_en_app",
    "ui_click": "clic",
    "camara": "camara",
    "manos_activar": "modo_manos",
    "gesto_entrenar": "entrenar_gesto",
    "correo_resumen": "correos",
    "blackboard_pendientes": "blackboard",
}

_lock = threading.Lock()
_estado: dict = {"pendientes": 0, "entrenando": False, "ultima": None}


def _norm(t: str) -> str:
    from lay_core.nucleo.modelo import normalizar

    return normalizar(t)


# ---------------- ejemplos ----------------
def ejemplos() -> list[dict]:
    try:
        return [json.loads(x) for x in EJEMPLOS.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


def registrar(texto: str, intencion: str, origen: str = "auto") -> bool:
    """Guarda una frase real de Robert con su intención. Devuelve True si era nueva."""
    texto = texto.strip()
    if not texto or len(texto) > 200 or intencion in ("charla", "confirmar", "negar"):
        return False
    with _lock:
        previos = ejemplos()
        clave = _norm(texto)
        previos = [e for e in previos if _norm(e["texto"]) != clave]  # una corrección reemplaza
        previos.append({"texto": texto, "intencion": intencion, "origen": origen, "t": int(time.time())})
        CARPETA.mkdir(parents=True, exist_ok=True)
        EJEMPLOS.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in previos[-MAX_EJEMPLOS:]) + "\n", encoding="utf-8"
        )
        _estado["pendientes"] += 1
        pendientes = _estado["pendientes"]
    if pendientes >= REENTRENAR_CADA:
        reentrenar_en_fondo()
    return True


def aprender_de_herramienta(texto: str, herramienta: str, resultado: object) -> bool:
    """La IA grande resolvió 'texto' con 'herramienta' y salió bien: el Núcleo lo aprende."""
    intencion = HERRAMIENTA_A_INTENCION.get(herramienta)
    ok = isinstance(resultado, dict) and not resultado.get("error") and not resultado.get("requiere_confirmacion")
    if not intencion or not ok:
        return False
    return registrar(texto, intencion, "auto")


def corregir(texto: str, intencion: str) -> dict:
    from lay_core.nucleo import datos

    if intencion not in datos.P:
        return {"error": f"No conozco la intención '{intencion}'.", "intenciones": sorted(datos.P)}
    registrar(texto, intencion, "correccion")
    reentrenar_en_fondo()
    return {"ok": True, "frase": texto, "ahora_es": intencion}


# ---------------- atajos de voz ----------------
def atajos() -> dict[str, list[str]]:
    try:
        return json.loads(ATAJOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def dividir_ordenes(texto: str) -> list[str]:
    partes = re.split(
        r"\s*(?:;|,?\s+y luego\s+|,?\s+y despu[eé]s\s+|,?\s+luego\s+|\s+y\s+(?=abre|pon|busca|cierra|mueve|sube|baja))\s*",
        texto,
    )
    return [p.strip() for p in partes if p and p.strip()]


def ensenar(frase: str, ordenes: str | list[str]) -> dict:
    frase = frase.strip().strip("'\"")
    lista = dividir_ordenes(ordenes) if isinstance(ordenes, str) else [o.strip() for o in ordenes if o.strip()]
    if not frase or not lista:
        return {
            "error": "Dime la frase y qué debo hacer, por ejemplo: cuando diga 'modo obra' abre Revit y luego abre Excel."
        }
    if len(lista) > 8:
        return {"error": "Máximo 8 órdenes por atajo."}
    with _lock:
        a = atajos()
        a[_norm(frase)] = lista
        CARPETA.mkdir(parents=True, exist_ok=True)
        ATAJOS.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "frase": frase, "ordenes": lista}


def olvidar_atajo(frase: str) -> dict:
    with _lock:
        a = atajos()
        if a.pop(_norm(frase), None) is None:
            return {"error": f"No tengo el atajo '{frase}'.", "atajos": list(a)}
        ATAJOS.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "olvidado": frase}


def buscar_atajo(texto: str) -> list[str] | None:
    a = atajos()
    if not a:
        return None
    t = _norm(texto)
    t = re.sub(r"^(lay|ley|oye lay)\s+", "", t)
    if t in a:
        return a[t]
    cerca = difflib.get_close_matches(t, list(a), n=1, cutoff=0.88)
    return a[cerca[0]] if cerca else None


# ---------------- reentrenar ----------------
def huella_datos() -> str:
    """Cambia cuando una versión nueva de LAY trae intenciones o frases nuevas."""
    import hashlib

    from lay_core.nucleo import datos

    base = "|".join(f"{k}:{len(v)}" for k, v in sorted(datos.P.items()))
    return hashlib.md5(base.encode()).hexdigest()[:12]


def reentrenar() -> dict:
    from lay_core import nucleo
    from lay_core.nucleo import datos, modelo

    t0 = time.time()
    propias = [(e["texto"], e["intencion"]) for e in ejemplos() if e["intencion"] in datos.P]
    m = modelo.entrenar(datos.generar() + propias * PESO)
    acc, _ = modelo.precision(m, datos.PRUEBA)
    destino = CARPETA / "modelo_nucleo.npz"
    CARPETA.mkdir(parents=True, exist_ok=True)
    m.guardar(destino, huella=huella_datos())
    nucleo.recargar_modelo()
    _estado.update(pendientes=0, ultima=int(time.time()))
    return {
        "ok": True,
        "frases_propias": len(propias),
        "precision_prueba": round(acc * 100, 1),
        "segundos": round(time.time() - t0, 1),
    }


def reentrenar_en_fondo() -> bool:
    if _estado["entrenando"]:
        return False

    def correr():
        _estado["entrenando"] = True
        try:
            r = reentrenar()
            try:
                from lay_core import bus

                bus.publicar("hud.aviso", texto=f"LAY aprendió {r['frases_propias']} frases tuyas")
            except Exception:  # noqa: BLE001
                pass
        finally:
            _estado["entrenando"] = False

    threading.Thread(target=correr, daemon=True, name="lay-aprender").start()
    return True


def estado() -> dict:
    ej = ejemplos()
    por_origen: dict[str, int] = {}
    for e in ej:
        por_origen[e["origen"]] = por_origen.get(e["origen"], 0) + 1
    return {
        "frases_aprendidas": len(ej),
        "por_origen": por_origen,
        "atajos": len(atajos()),
        "entrenando": _estado["entrenando"],
        "ultimo_entrenamiento": _estado["ultima"],
        "modelo_personal": (CARPETA / "modelo_nucleo.npz").exists(),
    }


def existe(ruta: Path) -> bool:
    return ruta.exists()

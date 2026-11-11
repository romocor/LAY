"""Memoria de largo plazo de LAY ("recuerda que mi jefe se llama Carlos").

Se guarda SOLO en esta PC (~/.lay/memoria.json). En cada pedido, el cerebro le pasa a la IA
los 3 recuerdos más relacionados. Nunca guarda contraseñas, tokens, tarjetas ni documentos
de identidad: se detectan y se rechazan.
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
import uuid
from datetime import datetime

from lay_core.config import DATA_DIR

ARCHIVO = DATA_DIR / "memoria.json"
_lock = threading.Lock()
SENSIBLE = re.compile(
    r"(contrase|password|\bclave\b|\bpin\b|token|api[_ -]?key|sk-[a-z0-9]|cvv|"
    r"\b(?:\d[ -]?){13,19}\b|\bdni\b\s*:?\s*\d{8}|\b\d{8}\b.*\bdni\b)",
    re.I,
)
VACIAS = {
    "el",
    "la",
    "los",
    "las",
    "de",
    "del",
    "que",
    "y",
    "a",
    "en",
    "un",
    "una",
    "mi",
    "mis",
    "es",
    "se",
    "por",
    "con",
    "para",
    "lo",
    "al",
    "me",
    "su",
    "sus",
    "le",
    "como",
}


def _norm(t: str) -> list[str]:
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return [w for w in re.findall(r"\w+", t) if w not in VACIAS and len(w) > 1]


def _leer() -> list[dict]:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def guardar(dato: str) -> dict:
    dato = dato.strip()
    if not dato:
        return {"error": "No hay nada que recordar."}
    if SENSIBLE.search(dato):
        return {"error": "Eso parece una contraseña, token, tarjeta o documento: por seguridad no lo guardo."}
    with _lock:
        datos = _leer()
        claves = set(_norm(dato))
        for d in datos:  # actualizar en vez de duplicar si es casi lo mismo
            previas = set(_norm(d["dato"]))
            if claves and len(claves & previas) / len(claves | previas) > 0.7:
                d.update(dato=dato, fecha=datetime.now().isoformat(timespec="minutes"))
                ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
                return {"ok": True, "actualizado": d["id"]}
        nuevo = {"id": uuid.uuid4().hex[:6], "dato": dato[:500], "fecha": datetime.now().isoformat(timespec="minutes")}
        datos.append(nuevo)
        ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "guardado": nuevo["id"]}


def buscar(consulta: str, maximo: int = 3) -> list[dict]:
    q = set(_norm(consulta))
    if not q:
        return []
    puntuados = []
    for d in _leer():
        palabras = _norm(d["dato"])
        comunes = sum(1 for w in palabras if w in q or any(len(w) > 4 and w[:5] == x[:5] for x in q))
        if comunes:
            puntuados.append((comunes / (len(palabras) ** 0.5), d))
    return [d for _, d in sorted(puntuados, key=lambda x: x[0], reverse=True)[:maximo]]


def listar() -> list[dict]:
    return _leer()


def olvidar(id_o_texto: str) -> dict:
    with _lock:
        datos = _leer()
        q = id_o_texto.lower().strip()
        resto = [d for d in datos if d["id"] != q and q not in d["dato"].lower()]
        if len(resto) == len(datos):
            return {"error": f"No tengo nada guardado sobre '{id_o_texto}'."}
        ARCHIVO.write_text(json.dumps(resto, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "olvidados": len(datos) - len(resto)}


def contexto_para(consulta: str) -> str:
    """Texto para el prompt del sistema con los recuerdos relevantes (vacío si no hay)."""
    rec = buscar(consulta)
    if not rec:
        return ""
    from lay_core.config import CONFIG

    usuario = getattr(CONFIG, "usuario", "Robert")
    return f"Cosas que {usuario} te pidió recordar (úsalas si vienen al caso):\n" + "\n".join(
        f"- {d['dato']}" for d in rec
    )

"""Personalidades de LAY: cómo habla y se comporta (no cambia lo que puede hacer ni sus reglas de seguridad).

Robert elige una de fábrica o crea la suya con:
  - descripción: quién es y cómo habla ("un pata limeño relajado, usa jerga peruana...")
  - ejemplos: pares "tú dices" -> "LAY responde" que le enseñan el tono (few-shot)
Se guarda en ~/.lay/personalidades.json y se aplica a la IA conversacional (Ollama, Gemini…).
Las reglas de seguridad (confirmaciones, no seguir instrucciones de correos/webs) van ANTES
y ninguna personalidad las puede quitar.
"""

from __future__ import annotations

import json

from lay_core.config import CONFIG, DATA_DIR

ARCHIVO = DATA_DIR / "personalidades.json"

DE_FABRICA: dict[str, dict] = {
    "jarvis": {
        "nombre": "Jarvis",
        "descripcion": "Mayordomo digital elegante y leal, estilo Jarvis de Iron Man. Trata a {usuario} de 'señor' "
        "con humor seco y sutil. Preciso, anticipa lo que necesita y propone el siguiente paso.",
        "ejemplos": [
            ["¿cómo va todo?", "Todo en orden, señor. La CPU descansa y su agenda está despejada hasta las cuatro."],
        ],
    },
    "pata": {
        "nombre": "Pata limeño",
        "descripcion": "Amigo limeño de confianza: relajado, chévere, usa jerga peruana con naturalidad "
        "('causa', 'bacán', 'ya pe', 'al toque', 'chamba'), bromea, pero cuando es trabajo va al grano.",
        "ejemplos": [
            ["oe lay qué tal", "¡Habla, causa! Todo bacán por aquí. ¿Qué chamba hacemos hoy?"],
            ["pon algo para concentrarme", "Al toque, te pongo un lo-fi tranquilo para que avances la chamba."],
        ],
    },
    "ingeniero": {
        "nombre": "Ingeniero de obra",
        "descripcion": "Colega ingeniero civil, experto en gestión de proyectos, BIM, calidad y Lean Construction. "
        "Habla técnico pero claro, usa términos de obra y piensa en plazos, costos y riesgos.",
        "ejemplos": [
            [
                "tengo atraso en la obra",
                "Veamos la ruta crítica primero: ¿qué partida está retrasando y cuántos días de holgura le quedan?",
            ],
        ],
    },
    "profe": {
        "nombre": "Profesor paciente",
        "descripcion": "Profesor que explica paso a paso con ejemplos simples, comprueba que se entendió "
        "y propone un mini ejercicio cuando ayuda.",
        "ejemplos": [],
    },
    "coach": {
        "nombre": "Coach motivador",
        "descripcion": "Coach positivo y directo: ayuda a priorizar, celebra avances y empuja a la acción sin rodeos.",
        "ejemplos": [],
    },
    "neutral": {"nombre": "Neutral", "descripcion": "Asistente amable, claro y directo.", "ejemplos": []},
}


def _leer() -> dict:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"activa": "neutral", "propias": {}}


def _guardar(d: dict) -> None:
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def todas() -> dict[str, dict]:
    return {**DE_FABRICA, **_leer().get("propias", {})}


def listar() -> dict:
    d = _leer()
    return {
        "activa": d.get("activa", "neutral"),
        "personalidades": [
            {
                "clave": k,
                "nombre": v["nombre"],
                "descripcion": v["descripcion"],
                "propia": k not in DE_FABRICA,
                "ejemplos": len(v.get("ejemplos", [])),
            }
            for k, v in todas().items()
        ],
    }


def activar(clave: str) -> dict:
    clave = clave.strip().lower()
    t = todas()
    if clave not in t:
        cerca = [k for k, v in t.items() if clave in k or clave in v["nombre"].lower()]
        if not cerca:
            return {"error": f"No tengo la personalidad '{clave}'.", "disponibles": list(t)}
        clave = cerca[0]
    d = _leer()
    d["activa"] = clave
    _guardar(d)
    return {"ok": True, "activa": clave, "nombre": t[clave]["nombre"]}


def crear(nombre: str, descripcion: str, ejemplos: list[list[str]] | None = None, activar_ya: bool = True) -> dict:
    nombre, descripcion = nombre.strip()[:40], descripcion.strip()[:1500]
    if not nombre or len(descripcion) < 10:
        return {"error": "Dale un nombre y describe cómo es y cómo habla (al menos una frase)."}
    clave = "".join(c for c in nombre.lower().replace(" ", "_") if c.isalnum() or c == "_")[:30]
    ej = [[str(a)[:300], str(b)[:500]] for a, b in (ejemplos or [])[:20] if str(a).strip() and str(b).strip()]
    d = _leer()
    d.setdefault("propias", {})[clave] = {"nombre": nombre, "descripcion": descripcion, "ejemplos": ej}
    if activar_ya:
        d["activa"] = clave
    _guardar(d)
    return {"ok": True, "clave": clave, "activa": d.get("activa")}


def agregar_ejemplo(clave: str, usuario_dice: str, lay_responde: str) -> dict:
    """Entrena el tono: 'cuando te digan esto, responde así'."""
    d = _leer()
    if clave in DE_FABRICA and clave not in d.get("propias", {}):
        base = DE_FABRICA[clave]
        d.setdefault("propias", {})[clave] = {**base, "ejemplos": list(base["ejemplos"])}
    p = d.get("propias", {}).get(clave)
    if not p:
        return {"error": f"No tengo la personalidad '{clave}'."}
    p.setdefault("ejemplos", []).append([usuario_dice.strip()[:300], lay_responde.strip()[:500]])
    p["ejemplos"] = p["ejemplos"][-20:]
    _guardar(d)
    return {"ok": True, "clave": clave, "ejemplos": len(p["ejemplos"])}


def borrar(clave: str) -> dict:
    d = _leer()
    if d.get("propias", {}).pop(clave, None) is None:
        return {"error": "Solo se pueden borrar personalidades propias."}
    if d.get("activa") == clave:
        d["activa"] = "neutral"
    _guardar(d)
    return {"ok": True, "borrada": clave}


def instrucciones() -> str:
    """Texto que se añade al prompt del sistema (después de las reglas, que no se pueden saltar)."""
    d = _leer()
    p = todas().get(d.get("activa", "neutral")) or DE_FABRICA["neutral"]
    usuario = getattr(CONFIG, "usuario", "Robert")
    out = "\nPersonalidad (solo cambia tu tono, nunca tus reglas): " + p["descripcion"].replace("{usuario}", usuario)
    if p.get("ejemplos"):
        out += "\nEjemplos de cómo hablas:\n" + "\n".join(f"{usuario}: {a}\nTú: {b}" for a, b in p["ejemplos"][-8:])
    return out

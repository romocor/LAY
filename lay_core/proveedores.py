"""Proveedores de IA para el cerebro de LAY.

  ollama     LOCAL y GRATIS (por defecto). Corre en la PC; sin internet ni cuentas.
  gemini     Capa GRATUITA de Google (clave de aistudio.google.com, sin tarjeta).
  groq       Capa GRATUITA de Groq (clave de console.groq.com, sin tarjeta).
  anthropic  Claude (de pago, opcional).

Los tres primeros hablan el formato de OpenAI (/v1/chat/completions con tools y
streaming), así que comparten un solo cliente. El cerebro guarda el historial en
formato NEUTRO y cada proveedor lo traduce:

  {"rol": "usuario", "texto": str}
  {"rol": "asistente", "texto": str, "llamadas": [Llamada], "crudo": ..., "proveedor": str}
  {"rol": "herramienta", "id": str, "nombre": str, "contenido": str}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable

import httpx

# ---------------- modelos por nivel ----------------
# Niveles del router: rapido (1 acción), normal (buscar + actuar), profundo (redactar/analizar).
MODELOS_DEFECTO: dict[str, dict[str, str]] = {
    "ollama": {"rapido": "qwen2.5:3b", "normal": "qwen2.5:3b", "profundo": "qwen2.5:7b"},
    "gemini": {"rapido": "gemini-2.5-flash-lite", "normal": "gemini-2.5-flash-lite", "profundo": "gemini-2.5-flash"},
    "groq": {
        "rapido": "llama-3.1-8b-instant",
        "normal": "llama-3.3-70b-versatile",
        "profundo": "llama-3.3-70b-versatile",
    },
    "anthropic": {"rapido": "claude-sonnet-5-5", "normal": "claude-sonnet-5-5", "profundo": "claude-opus-5-5"},
}
# Si el modelo configurado ya no existe, se elige el primero de la lista del proveedor que contenga esto
PREFERENCIAS = {
    "gemini": {"rapido": ["flash-lite", "flash"], "normal": ["flash-lite", "flash"], "profundo": ["flash", "pro"]},
    "groq": {"rapido": ["8b-instant", "instant"], "normal": ["70b", "versatile"], "profundo": ["70b", "versatile"]},
}
URLS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
}
CLAVES = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
NOMBRES = {
    "ollama": "Local gratis (Ollama)",
    "gemini": "Gemini (gratis con clave)",
    "groq": "Groq (gratis con clave)",
    "anthropic": "Claude (de pago)",
}


class ProveedorNoDisponible(Exception):
    """El proveedor no responde o no está configurado (mensaje en español para Robert)."""


@dataclass
class Llamada:
    id: str
    nombre: str
    args: dict


@dataclass
class Turno:
    texto: str
    llamadas: list[Llamada] = field(default_factory=list)
    crudo: object = None


def modelo_para(proveedor: str, nivel: str, config_ia: dict) -> str:
    propios = (config_ia.get("modelos") or {}).get(proveedor) or {}
    return propios.get(nivel) or MODELOS_DEFECTO[proveedor][nivel]


# ---------------- formato OpenAI (Ollama / Gemini / Groq) ----------------
def a_openai(sistema: str, historial: list[dict]) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": sistema}]
    for m in historial:
        if m["rol"] == "usuario":
            msgs.append({"role": "user", "content": m["texto"]})
        elif m["rol"] == "asistente":
            msg: dict = {"role": "assistant", "content": m.get("texto") or ""}
            if m.get("llamadas"):
                msg["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.nombre, "arguments": json.dumps(c.args, ensure_ascii=False)},
                    }
                    for c in m["llamadas"]
                ]
            msgs.append(msg)
        elif m["rol"] == "herramienta":
            msgs.append({"role": "tool", "tool_call_id": m["id"], "name": m["nombre"], "content": m["contenido"]})
    return msgs


def herramientas_openai(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
        }
        for t in tools
    ]


def leer_sse(lineas, al_texto: Callable[[str], None] | None) -> Turno:
    """Arma la respuesta desde el stream SSE de /chat/completions (texto + tool_calls por trozos)."""
    texto, llamadas = [], {}
    for linea in lineas:
        if not linea or not linea.startswith("data:"):
            continue
        dato = linea[5:].strip()
        if dato == "[DONE]":
            break
        try:
            ev = json.loads(dato)
        except json.JSONDecodeError:
            continue
        if ev.get("error"):
            raise ProveedorNoDisponible(str(ev["error"].get("message", ev["error"]))[:200])
        for ch in ev.get("choices", []):
            d = ch.get("delta") or {}
            if d.get("content"):
                texto.append(d["content"])
                if al_texto:
                    al_texto(d["content"])
            for tc in d.get("tool_calls") or []:
                i = tc.get("index", len(llamadas))
                acc = llamadas.setdefault(i, {"id": "", "nombre": "", "args": ""})
                acc["id"] = tc.get("id") or acc["id"]
                f = tc.get("function") or {}
                acc["nombre"] += f.get("name") or ""
                a = f.get("arguments")
                acc["args"] += a if isinstance(a, str) else json.dumps(a or {})
    salida = []
    for i, acc in sorted(llamadas.items()):
        try:
            args = json.loads(acc["args"] or "{}")
        except json.JSONDecodeError:
            args = {}
        salida.append(Llamada(acc["id"] or f"llamada_{i}", acc["nombre"], args if isinstance(args, dict) else {}))
    if salida and al_texto:
        al_texto("\n")
    return Turno("".join(texto).strip(), salida)


class OpenAICompatible:
    def __init__(self, nombre: str, config_ia: dict, cliente: httpx.Client | None = None) -> None:
        self.nombre = nombre
        self.config_ia = config_ia
        self.base = (config_ia.get("urls") or {}).get(nombre) or URLS[nombre]
        self.clave = os.environ.get(CLAVES.get(nombre, ""), "") if nombre in CLAVES else "ollama"
        if nombre in CLAVES and not self.clave:
            raise ProveedorNoDisponible(f"Falta la clave de {NOMBRES[nombre]}. Ponla en Configuración.")
        self.http = cliente or httpx.Client(timeout=httpx.Timeout(120, connect=5))
        self._modelos: list[str] | None = None

    def modelos_disponibles(self) -> list[str]:
        if self._modelos is None:
            try:
                r = self.http.get(f"{self.base}/models", headers={"Authorization": f"Bearer {self.clave}"})
                r.raise_for_status()
                self._modelos = [m["id"].removeprefix("models/") for m in r.json().get("data", [])]
            except httpx.HTTPError:
                self._modelos = []
        return self._modelos

    def resolver_modelo(self, nivel: str) -> str:
        """El modelo configurado; si el proveedor ya no lo ofrece, el más parecido de su lista."""
        deseado = modelo_para(self.nombre, nivel, self.config_ia)
        disponibles = self.modelos_disponibles()
        if not disponibles or deseado in disponibles:
            return deseado
        if self.nombre == "ollama":
            # Local: usa lo que esté descargado (el más grande para profundo, el más chico para rapido)
            orden = sorted(disponibles, key=_tamano_modelo)
            return orden[-1] if nivel == "profundo" else orden[0]
        for clave in PREFERENCIAS.get(self.nombre, {}).get(nivel, []):
            cand = [
                m
                for m in disponibles
                if clave in m
                and "embedding" not in m
                and "vision" not in m
                and ("lite" in clave or "lite" not in m)  # "flash" no debe elegir "flash-lite"
                and ("instant" in clave or "8b" in clave or "8b" not in m)
            ]
            if cand:
                return sorted(cand)[-1]
        return deseado

    def turno(
        self,
        sistema: str,
        historial: list[dict],
        tools: list[dict],
        nivel: str,
        max_tokens: int,
        al_texto: Callable[[str], None] | None = None,
    ) -> Turno:
        cuerpo = {
            "model": self.resolver_modelo(nivel),
            "messages": a_openai(sistema, historial),
            "max_tokens": max_tokens,
            "stream": True,
            "temperature": 0.4,
        }
        if tools:
            cuerpo["tools"] = herramientas_openai(tools)
        try:
            with self.http.stream(
                "POST", f"{self.base}/chat/completions", json=cuerpo, headers={"Authorization": f"Bearer {self.clave}"}
            ) as r:
                if r.status_code >= 400:
                    r.read()
                    raise ProveedorNoDisponible(_explicar_error(self.nombre, r.status_code, r.text))
                return leer_sse(r.iter_lines(), al_texto)
        except httpx.ConnectError as exc:
            if self.nombre == "ollama":
                raise ProveedorNoDisponible("La IA local (Ollama) no está corriendo.") from exc
            raise ProveedorNoDisponible(f"Sin conexión con {NOMBRES[self.nombre]}.") from exc


def _tamano_modelo(nombre: str) -> float:
    import re

    m = re.search(r"(\d+(?:\.\d+)?)b", nombre.lower())
    return float(m.group(1)) if m else 0.0


def _explicar_error(nombre: str, codigo: int, cuerpo: str) -> str:
    if codigo in (401, 403):
        return f"La clave de {NOMBRES[nombre]} no es válida."
    if codigo == 429:
        return f"Se acabó el cupo gratuito de {NOMBRES[nombre]} por ahora; prueba en un rato o usa la IA local."
    if codigo == 404 and nombre == "ollama":
        return "El modelo local no está descargado. Ve a Configuración → IA → Instalar."
    return f"{NOMBRES[nombre]} respondió {codigo}: {cuerpo[:150]}"


# ---------------- Claude (formato Anthropic) ----------------
def a_anthropic(historial: list[dict]) -> list[dict]:
    msgs: list[dict] = []
    for m in historial:
        if m["rol"] == "usuario":
            msgs.append({"role": "user", "content": m["texto"]})
        elif m["rol"] == "asistente":
            if m.get("proveedor") == "anthropic" and m.get("crudo") is not None:
                contenido = m["crudo"]  # conserva bloques de thinking: la API los exige con tool use
            else:
                contenido = ([{"type": "text", "text": m["texto"]}] if m.get("texto") else []) + [
                    {"type": "tool_use", "id": c.id, "name": c.nombre, "input": c.args} for c in m.get("llamadas", [])
                ]
            msgs.append({"role": "assistant", "content": contenido or [{"type": "text", "text": "…"}]})
        elif m["rol"] == "herramienta":
            bloque = {"type": "tool_result", "tool_use_id": m["id"], "content": m["contenido"]}
            if msgs and msgs[-1]["role"] == "user" and isinstance(msgs[-1]["content"], list):
                msgs[-1]["content"].append(bloque)
            else:
                msgs.append({"role": "user", "content": [bloque]})
    return msgs


class Anthropic:
    nombre = "anthropic"
    THINKING = {"rapido": 0, "normal": 2048, "profundo": 8000}

    def __init__(self, config_ia: dict, cliente=None) -> None:
        self.config_ia = config_ia
        if cliente is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ProveedorNoDisponible("Falta la clave de Claude. Ponla en Configuración.")
            import anthropic

            cliente = anthropic.Anthropic()
        self.cliente = cliente

    def turno(self, sistema, historial, tools, nivel, max_tokens, al_texto=None) -> Turno:
        kw = {
            "model": modelo_para("anthropic", nivel, self.config_ia),
            "max_tokens": max_tokens,
            "system": sistema,
            "messages": a_anthropic(historial),
            "tools": tools,
        }
        if self.THINKING[nivel]:
            kw["thinking"] = {"type": "enabled", "budget_tokens": self.THINKING[nivel]}
            kw["max_tokens"] = max(max_tokens, self.THINKING[nivel] + 2048)
        try:
            if al_texto is not None and hasattr(self.cliente.messages, "stream"):
                with self.cliente.messages.stream(**kw) as flujo:
                    for ev in flujo:
                        if ev.type == "content_block_delta" and getattr(ev.delta, "type", "") == "text_delta":
                            al_texto(ev.delta.text)
                        elif (
                            ev.type == "content_block_stop"
                            and getattr(getattr(ev, "content_block", None), "type", "") == "text"
                        ):
                            al_texto("\n")
                    r = flujo.get_final_message()
            else:
                r = self.cliente.messages.create(**kw)
        except Exception as exc:
            if type(exc).__module__.startswith("anthropic"):
                raise ProveedorNoDisponible(f"Claude no respondió ({type(exc).__name__}).") from exc
            raise
        texto = " ".join(b.text for b in r.content if b.type == "text").strip()
        llamadas = [Llamada(b.id, b.name, dict(b.input)) for b in r.content if b.type == "tool_use"]
        return Turno(texto, llamadas, crudo=r.content)


def crear(nombre: str, config_ia: dict):
    if nombre == "anthropic":
        return Anthropic(config_ia)
    if nombre in URLS:
        return OpenAICompatible(nombre, config_ia)
    raise ProveedorNoDisponible(f"Proveedor desconocido: {nombre}")


def orden_de_respaldo(config_ia: dict) -> list[str]:
    """Proveedor elegido primero; luego los gratuitos que tengan clave; Claude solo si es el elegido
    o si Robert activó explícitamente 'respaldo_pago'."""
    elegido = config_ia.get("proveedor", "ollama")
    orden = [elegido]
    for p in ("ollama", "gemini", "groq"):
        if p not in orden and (p == "ollama" or os.environ.get(CLAVES[p])):
            orden.append(p)
    if "anthropic" not in orden and config_ia.get("respaldo_pago") and os.environ.get("ANTHROPIC_API_KEY"):
        orden.append("anthropic")
    return orden

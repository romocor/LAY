"""Router de modelos: tareas fáciles -> Sonnet (rápido), difíciles -> Opus (profundo).

Esfuerzo distribuido en 3 niveles:
  rapido   Sonnet, sin thinking, 1k tokens     -> "abre Spotify", "¿cuánta RAM?"
  normal   Sonnet, thinking 2k, 4k tokens       -> buscar + abrir, resumir 5 correos
  profundo Opus,   thinking 8k, 16k tokens      -> planificar, redactar, analizar, multi-paso

Escalado automático: si Sonnet supera N iteraciones de herramientas o falla,
la misma conversación se reintenta con Opus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lay_core.config import CONFIG

DIFICIL = re.compile(
    r"\b(analiz|planific|plan de|compar|estrategi|redact|resum[ei]\w* (todos|varios|la semana)|"
    r"prioriz|organiza(me)? (la|mi) semana|investig|c[oó]digo|programa|depura|arquitectura|por qu[eé]|"
    r"explica|decide|recomienda|propuesta|presupuesto|cronograma|(haz|hazme|prepara|genera|elabora)(me)? (un |el |una )?(informe|reporte|resumen))",
    re.I,
)
MEDIO = re.compile(
    r"\b(busca|encuentra|resume|correos?|blackboard|pendientes|agenda|y (luego|despu[eé]s)|varios)\b", re.I
)


@dataclass(frozen=True)
class Perfil:
    nivel: str
    modelo: str
    max_tokens: int
    thinking: int  # 0 = sin thinking
    max_iter: int

    def params(self) -> dict:
        p = {"model": self.modelo, "max_tokens": self.max_tokens}
        if self.thinking:
            p["thinking"] = {"type": "enabled", "budget_tokens": self.thinking}
        return p


RAPIDO = Perfil("rapido", CONFIG.modelo_facil, 1024, 0, 4)
NORMAL = Perfil("normal", CONFIG.modelo_facil, 4096, 2048, 8)
PROFUNDO = Perfil("profundo", CONFIG.modelo_dificil, 16000, 8000, 16)


def elegir(texto: str) -> Perfil:
    t = texto.strip()
    if t.lower().startswith(("piensa bien", "a fondo", "modo opus")) or DIFICIL.search(t) or len(t) > 220:
        return PROFUNDO
    if MEDIO.search(t) or len(t) > 90 or t.count(",") >= 2:
        return NORMAL
    return RAPIDO


def escalar(p: Perfil) -> Perfil | None:
    return {"rapido": NORMAL, "normal": PROFUNDO}.get(p.nivel)

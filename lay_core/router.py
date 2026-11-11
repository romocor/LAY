"""Router de esfuerzo: decide CUÁNTO pensar; el proveedor decide CON QUÉ modelo.

  rapido    1 acción ("abre Spotify", "¿cuánta RAM?")       -> modelo chico, sin thinking
  normal    buscar + actuar, resúmenes cortos                 -> modelo chico/medio
  profundo  redactar, analizar, planificar, multi-paso        -> modelo grande (+ thinking en Claude)

Modelos por proveedor en lay_core/proveedores.py (MODELOS_DEFECTO) o en lay.json -> ia.modelos.
Escalado automático: si un nivel agota sus pasos, la conversación se reintenta en el siguiente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DIFICIL = re.compile(
    r"\b(analiz|planific|plan de|compar|estrategi|redact|res[uú]m[eií]\w* (todos|varios|la semana)|"
    r"prioriz|organiza(me)? (la|mi) semana|investig|c[oó]digo|programa|depura|arquitectura|por qu[eé]|"
    r"explica|decide|recomienda|propuesta|presupuesto|cronograma|res[uú]m\w* (mis |los |el )?correos?|"
    r"resp[oó]nde(le)? (a|al)|cont[eé]sta(le)? (a|al)|(haz|hazme|prepara|genera|elabora)(me)? (un |el |una )?(informe|reporte|resumen))",
    re.I,
)
MEDIO = re.compile(
    r"\b(busca|encuentra|resume|correos?|blackboard|pendientes|agenda|y (luego|despu[eé]s)|varios)\b", re.I
)


@dataclass(frozen=True)
class Perfil:
    nivel: str
    max_tokens: int
    max_iter: int


RAPIDO = Perfil("rapido", 1024, 4)
NORMAL = Perfil("normal", 2048, 8)
PROFUNDO = Perfil("profundo", 4096, 14)


def elegir(texto: str) -> Perfil:
    t = texto.strip()
    if (
        t.lower().startswith(("piensa bien", "a fondo", "modo opus", "modo profundo"))
        or DIFICIL.search(t)
        or len(t) > 220
    ):
        return PROFUNDO
    if MEDIO.search(t) or len(t) > 90 or t.count(",") >= 2:
        return NORMAL
    return RAPIDO


def escalar(p: Perfil) -> Perfil | None:
    return {"rapido": NORMAL, "normal": PROFUNDO}.get(p.nivel)


# ---------------- herramientas por tema (para modelos locales chicos) ----------------
BASE = {"abrir", "archivos_abrir_por_nombre", "app_abrir", "hud_decir"}
GRUPOS: dict[str, tuple[re.Pattern, set[str]]] = {
    "sistema": (
        re.compile(r"ram|cpu|disco|bater|memoria|proceso|rendimiento|lento|estado (del|de la) (pc|compu)", re.I),
        {"sistema_estado", "sistema_procesos"},
    ),
    "ventanas": (
        re.compile(
            r"ventana|monitor|pantalla|pon\b|ponlo|mueve|mu[eé]velo|workspace|modo \w+|maximiz|"
            r"izquierda|derecha|arriba|abajo|enfoca|cierra",
            re.I,
        ),
        {
            "monitores_listar",
            "ventanas_listar",
            "ventana_mover",
            "ventana_enfocar",
            "ventana_cerrar",
            "workspace_aplicar",
        },
    ),
    "archivos": (
        re.compile(r"busca|encuentra|archivo|carpeta|documento|descarg|pdf|excel|word|plano|reciente", re.I),
        {"archivos_buscar", "archivos_listar", "archivos_recientes"},
    ),
    "teclado": (
        re.compile(r"escrib|tecl|atajo|captura|copia|pega|guarda|dicta", re.I),
        {"teclado_escribir", "teclado_atajo", "pantalla_capturar"},
    ),
    "manos": (
        re.compile(r"c[aá]mara|gesto|mis manos|las manos|holo|tony|escane|explorador", re.I),
        {"camara", "manos_activar", "gesto_entrenar", "gestos_listar", "gesto_borrar", "carpeta_abrir"},
    ),
    "overlay": (
        re.compile(r"foto|imagen|im[aá]genes|galer|mu[eé]strame", re.I),
        {"overlay_mostrar_imagenes", "overlay_colocar", "hud_panel"},
    ),
    "correo": (
        re.compile(r"correo|mail|bandeja|respond|resp[oó]nd|contest|env[ií]a|outlook|gmail|mensaje|borrador", re.I),
        {
            "correo_resumen",
            "gmail_buscar",
            "gmail_leer",
            "gmail_borrador",
            "gmail_responder_borrador",
            "gmail_enviar",
            "gmail_enviar_borrador",
            "gmail_archivar",
            "outlook_no_leidos",
            "outlook_leer",
            "outlook_responder_borrador",
            "outlook_enviar",
            "outlook_enviar_borrador",
            "hud_panel",
        },
    ),
    "navegador": (
        re.compile(
            r"naveg|brave|chrome|google|edge|p[aá]gina|web|sitio|youtube|pesta[ñn]a|enlace|link|"
            r"haz clic|clic en|formulario|inicia sesi[oó]n|\.com|\.pe|\.org",
            re.I,
        ),
        {
            "navegador_abrir",
            "navegador_leer",
            "navegador_elementos",
            "navegador_click",
            "navegador_escribir",
            "navegador_escribir_y_enviar",
            "navegador_buscar_en_sitio",
            "navegador_pestanas",
            "navegador_ir_pestana",
            "navegador_cerrar_pestana",
            "navegador_mover",
        },
    ),
    "windows_ui": (
        re.compile(
            r"bot[oó]n|men[uú]|pulsa|presiona|ventana de|en (la app|el programa)|configuraci[oó]n de|"
            r"ajuste|wifi|bluetooth|pantalla|sonido|actualiza|modo oscuro|fondo|instalad|abre (el|la) app",
            re.I,
        ),
        {"ui_elementos", "ui_click", "ui_escribir", "ui_leer_texto", "ajustes_abrir", "app_abrir"},
    ),
    "multimedia": (
        re.compile(
            r"volumen|sube|baja|silenci|m[uú]sica|canci[oó]n|pausa|siguiente|anterior|brillo|"
            r"apaga|reinicia|suspend",
            re.I,
        ),
        {"volumen", "multimedia", "brillo", "energia"},
    ),
    "informacion": (
        re.compile(
            r"qui[eé]n|qu[eé] es|cu[aá]nto|cu[aá]l|noticia|precio|d[oó]lar|clima|tiempo|llover|"
            r"temperatura|wikipedia|investiga|busca en internet|informaci[oó]n",
            re.I,
        ),
        {"web_buscar", "web_leer", "wikipedia", "clima"},
    ),
    "recordatorios": (
        re.compile(
            r"recu[eé]rda|recordatorio|alarma|av[ií]same|temporizador|timer|despi[eé]rta|"
            r"olvida|qu[eé] sabes de|memoria",
            re.I,
        ),
        {
            "recordatorio_crear",
            "temporizador",
            "recordatorios_listar",
            "recordatorio_borrar",
            "memoria_guardar",
            "memoria_buscar",
            "memoria_olvidar",
        },
    ),
    "universidad": (
        re.compile(r"blackboard|entrega|tarea|examen|curso|pendiente|agenda|calendario|universidad|clase", re.I),
        {"blackboard_pendientes", "outlook_agenda", "hud_panel"},
    ),
}


def temas(texto: str) -> set[str]:
    return {g for g, (patron, _) in GRUPOS.items() if patron.search(texto)}


def filtrar(tools: list[dict], grupos: set[str]) -> list[dict]:
    """Solo las herramientas de los temas detectados (+ básicas). Sin tema: sistema + ventanas + archivos."""
    if not grupos:
        grupos = {"sistema", "ventanas", "archivos"}
    nombres = set(BASE)
    for g in grupos:
        nombres |= GRUPOS[g][1]
    return [t for t in tools if t["name"] in nombres]

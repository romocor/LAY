"""LAY Núcleo: la IA propia de LAY, hecha desde cero (sin modelos de terceros).

  entender(texto)  -> Comprension(intencion, confianza, datos)   (clasificador propio + extracción)
  Nucleo           -> proveedor para el cerebro: convierte la intención en llamadas a herramientas y
                      redacta la respuesta con el resultado. Instantáneo, offline, en cualquier PC.

Modo híbrido (por defecto): las ÓRDENES las ejecuta el núcleo (garantizado, sin depender de que un
modelo de lenguaje "decida" usar la herramienta); la charla abierta va al modelo de lenguaje elegido.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from lay_core.nucleo import modelo as _m
from lay_core.nucleo.modelo import normalizar

_cache: dict = {}
UMBRAL = 0.55  # confianza mínima para que el núcleo actúe solo
NUMEROS = {
    "cero": 0,
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "quince": 15,
    "veinte": 20,
    "veinticinco": 25,
    "treinta": 30,
    "cuarenta": 40,
    "cuarenta y cinco": 45,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
    "cien": 100,
    "media": 30,
}
SITIOS = {
    "youtube": "youtube.com",
    "gmail": "mail.google.com",
    "correo": "mail.google.com",
    "facebook": "facebook.com",
    "github": "github.com",
    "blackboard": "pucp.blackboard.com",
    "linkedin": "linkedin.com",
    "netflix": "netflix.com",
    "whatsapp": "web.whatsapp.com",
    "chatgpt": "chatgpt.com",
    "drive": "drive.google.com",
    "google drive": "drive.google.com",
    "instagram": "instagram.com",
    "twitter": "x.com",
    "x": "x.com",
    "amazon": "amazon.com",
    "mercado libre": "mercadolibre.com.pe",
    "pucp": "pucp.edu.pe",
    "maps": "maps.google.com",
    "google maps": "maps.google.com",
    "wikipedia": "es.wikipedia.org",
    "google": "google.com",
    "outlook": "outlook.office.com",
}
CARPETAS = {
    "descargas": "~/Downloads",
    "documentos": "~/Documents",
    "escritorio": "~/Desktop",
    "imagenes": "~/Pictures",
    "fotos": "~/Pictures",
    "musica": "~/Music",
    "videos": "~/Videos",
    "capturas": "~/Pictures/Screenshots",
}


@dataclass
class Comprension:
    intencion: str
    confianza: float
    datos: dict = field(default_factory=dict)
    segunda: str = ""


def cargar_modelo() -> _m.Modelo:
    if "m" not in _cache:
        _cache["m"] = _m.Modelo.cargar()
        _al_cargar()
    return _cache["m"]


def recargar_modelo() -> None:
    _cache.pop("m", None)


def _al_cargar() -> None:
    """Tras actualizar LAY, el modelo personal queda viejo: se rehace con las frases aprendidas."""
    from lay_core.nucleo import aprendizaje

    if aprendizaje.ejemplos():
        try:
            import numpy as np

            d = np.load(aprendizaje.CARPETA / "modelo_nucleo.npz", allow_pickle=False)
            vigente = "huella" in d.files and str(d["huella"]) == aprendizaje.huella_datos()
        except Exception:  # noqa: BLE001
            vigente = False
        if not vigente:
            aprendizaje.reentrenar_en_fondo()


# ---------------- extracción de datos ----------------
def numero(t: str) -> int | None:
    m = re.search(r"\b(\d{1,3})\b", t)
    if m:
        return int(m.group(1))
    for palabra, n in sorted(NUMEROS.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{palabra}\b", t):
            return n
    return None


def _resto(t: str, verbos: str) -> str:
    """Lo que viene después del verbo: 'busca en google precio del dólar' -> 'precio del dólar'."""
    m = re.search(rf"\b(?:{verbos})\b\s*(.*)", t)
    r = m.group(1) if m else t
    r = re.sub(
        r"^(en (google|internet|la web|mi navegador|el navegador|brave|chrome|youtube)|informacion (de|sobre)|"
        r"el programa|la app|la aplicacion|el archivo|el documento|la carpeta( de)?|mis?|el|la|los|las|un|una)\s+",
        "",
        r,
    )
    r = re.sub(r"^(en (google|internet|la web|mi navegador|el navegador|brave|chrome)|y busca)\s+", "", r)
    r = re.sub(
        r"\b(por favor|porfa|ahora|ya|rapido|en el navegador|en brave|en chrome|en el explorador|en mi pc)\b", "", r
    )
    return re.sub(r"\s+", " ", r).strip(" ,.")


VERBOS_MUSICA = (
    r"busca(me)?|pon(me|te|le|la|lo|melo)?|reproduce(me)?|reproducir|reproduci|toca(me)?|dale play a|escuchemos|"
    r"quiero (escuchar|oir|ver)|me gustaria (escuchar|oir)|mete|coloca(me)?|abre|entra a|ve a|quiero"
)


def limpiar_consulta(t: str) -> str:
    """'pon nadie sabe en spotify por favor' -> 'nadie sabe'. Quita verbos, plataforma y relleno, en
    cualquier orden, para que Spotify/YouTube reciban SOLO la canción o el artista."""
    q = f" {t} "
    q = re.sub(r"\s(en|por|de|desde)\s+(spotify|youtube)\b", " ", q)  # "... en spotify"
    q = re.sub(r"\s(spotify|youtube)\s", " ", q)
    q = re.sub(rf"^\s*(lay\s+)?({VERBOS_MUSICA})\b", " ", q)
    q = re.sub(rf"^\s*({VERBOS_MUSICA})\b", " ", q)  # "abre youtube y pon..." ya vino cortado
    q = re.sub(r"\s+y\s+(ponla|ponlo|reproducela|reproducelo|dale play)\s*$", " ", q)
    q = re.sub(
        r"^\s*(algo de|musica de|la musica de|canciones de|la cancion|el tema|la rola|el video de|un video de|"
        r"la de|el de|una cancion de|un tema de|el disco|el album|la playlist( de)?|mi playlist( de)?)\s+",
        " ",
        q,
    )
    q = re.sub(r"\s+(ahora|ya|porfa|por favor|pe|pues|de una|please)\s*$", " ", q)
    return re.sub(r"\s+", " ", q).strip()


def extraer(intencion: str, original: str) -> dict:
    t = normalizar(original)
    d: dict = {}
    if intencion == "abrir_app":
        d["app"] = _resto(t, "abre|abrir|abreme|ejecuta|inicia|lanza|pon|usar|necesito|prende|arranca|abrire")
    elif intencion == "abrir_carpeta":
        d["carpeta"] = _resto(t, "carpeta de|carpeta|mis|a mis|ve a|entra a|llevame a|al|en|abre")
    elif intencion in ("abrir_archivo", "buscar_archivo"):
        d["consulta"] = _resto(t, "abre|abreme|ver|muestrame|busca y abre|busca|encuentra|localiza|donde esta|tengo")
    elif intencion == "camara":
        apagar = re.search(r"\b(apag|desactiv|quit|cierr|paus|deja|ya no|fuera)", t)
        d["accion"] = "apagar" if apagar else "encender"
    elif intencion == "entrenar_gesto":
        cortes = list(re.finditer(r"\b(?:para|que|gesto)\s+", t))  # lo que va tras el ÚLTIMO "para/que/gesto"
        orden = t[cortes[-1].end() :] if cortes else ""
        d["orden"] = re.sub(r"^(se|lay|me)\s+", "", orden).strip()
    elif intencion == "mostrar_imagenes":
        m = re.search(r"\b(?:de|del|de la)\s+(.+)$", t)
        d["consulta"] = (m.group(1) if m else "").replace("la obra de ", "").strip()
    elif intencion == "buscar_web":
        d["consulta"] = _resto(t, "busca|buscame|googlea|investiga|busca en google|abre google y busca")
        d["navegador"] = next((n for n in ("brave", "chrome", "edge") if n in t), None)
    elif intencion == "pregunta_info":
        d["consulta"] = original.strip(" ?¿!¡")
    elif intencion == "abrir_web":
        sitio = _resto(t, "abre|entra a|entrar a|ve a|llevame a|pon|la pagina de")
        d["navegador"] = next((n for n in ("brave", "chrome", "edge") if n in t), None)
        clave = next((k for k in sorted(SITIOS, key=len, reverse=True) if re.search(rf"\b{k}\b", sitio)), None)
        d["url"] = SITIOS[clave] if clave else sitio
    elif intencion == "youtube":
        d["consulta"] = limpiar_consulta(t)
    elif intencion == "clima":
        m = re.search(r"\b(?:en|de)\s+([a-z ]+)$", t)
        d["ciudad"] = m.group(1).strip() if m and m.group(1).strip() not in ("hoy", "la manana", "manana") else None
    elif intencion == "volumen":
        n = numero(t)
        if re.search(r"quita el silencio|desmutea|activa el (sonido|audio)", t):
            d.update(accion="activar")
        elif re.search(r"silencia|mutea|silencio", t):
            d.update(accion="silenciar")
        elif re.search(r"cuanto", t):
            d.update(accion="consultar")
        elif n is not None and re.search(r"\b(al|en|a)\s+\w+|por ciento", t):
            d.update(accion="fijar", nivel=n)
        else:
            d.update(accion="bajar" if re.search(r"baja|menos|bajale", t) else "subir", nivel=n or 10)
    elif intencion == "musica":
        d["accion"] = (
            "siguiente"
            if re.search(r"siguiente|salta|adelanta", t)
            else "anterior"
            if re.search(r"anterior|regresa|atras", t)
            else "pausa"
        )
    elif intencion == "reproducir":
        d["plataforma"] = "youtube" if re.search(r"youtube|video", t) else "spotify"
        if re.search(r"\bplaylist|lista de reproduccion\b", t):
            d["tipo"] = "playlist"
        elif re.search(r"\b(album|disco)\b", t):
            d["tipo"] = "album"
        d["consulta"] = limpiar_consulta(t)
    elif intencion == "personalidad":
        q = re.sub(r"^.*?\b(personalidad( a)?|habla como|modo|que seas|forma de hablar a|se)\s+", "", t).strip()
        d["nombre"] = re.sub(r"^(el|la|un|una)\s+", "", q).replace("limeno", "").strip() or q
    elif intencion == "consultar_libros":
        if re.search(r"\b(sobre|acerca de|respecto a)\s+", t):  # "qué dice la norma SOBRE escaleras"
            d["pregunta"] = re.split(r"\b(?:sobre|acerca de|respecto a)\s+", t, maxsplit=1)[1].strip()
        else:
            d["pregunta"] = (
                re.sub(
                    r"^(de|del|sobre)\s+",
                    "",
                    re.sub(r"^.*?\b(de|documentos|libros|apuntes|reglamento|norma)\s+", "", t, count=1).strip(),
                )
                or t
            )
    elif intencion == "clic":
        d["objetivo"] = re.sub(
            r"^.*?\b(clic en|click en|clic a|pulsa|presiona( el boton)?|aprieta|selecciona|dale a|toca el boton)\s+",
            "",
            t,
        ).strip()
    elif intencion == "buscar_en_app":
        m = re.search(r"busca(?:me)?\s+(.+?)\s+en\s+(.+)$", t) or re.search(r"encuentra\s+(.+?)\s+en\s+(.+)$", t)
        if m:
            d["consulta"], d["app"] = m.group(1).strip(), m.group(2).strip()
        else:
            m = re.search(r"(?:en|dentro de|abre)\s+(.+?)\s+(?:y\s+)?busca\s+(.+)$", t)
            d["app"], d["consulta"] = (m.group(1).strip(), m.group(2).strip()) if m else ("", "")
        d["app"] = re.sub(r"^(el|la|mi|mis)\s+", "", d["app"])
    elif intencion == "brillo":
        n = numero(t)
        if n is not None and re.search(r"\b(al|en|a)\b", t):
            d["nivel"] = n
        else:
            d["cambio"] = -20 if re.search(r"baja|menos|muy brillante", t) else 20
    elif intencion == "ajustes":
        d["seccion"] = _resto(
            t, "configuracion del|configuracion de|ajustes del|ajustes de|configurar el|activa el|configuracion"
        )
    elif intencion == "workspace":
        d["nombre"] = _resto(t, "modo|espacio de|entorno de|workspace")
    elif intencion == "mover_ventana":
        m = re.search(
            r"(?:pon|mueve|manda|lleva|pasa)\s+(?:la ventana de\s+)?(?:el|la)?\s*(.+?)\s+(?:en|a|al)\s+(.+)$", t
        )
        if m:
            d["titulo"] = m.group(1).strip()
            dest = m.group(2)
            n = numero(dest)
            d["direccion"] = (
                "arriba"
                if "arriba" in dest
                else "derecha"
                if "derech" in dest
                else "izquierda"
                if "izquierd" in dest
                else "abajo"
                if "abajo" in dest
                else None
            )
            d["monitor"] = n if n and n <= 6 else (1 if "laptop" in dest else None)
    elif intencion == "energia":
        d["accion"] = (
            "cancelar"
            if "cancela" in t
            else "reiniciar"
            if "reinici" in t
            else "suspender"
            if "suspen" in t
            else "apagar"
        )
    elif intencion == "recordatorio":
        cuando = re.search(
            r"(en (?:\d+|una?|dos|media|cinco|diez|quince|veinte|treinta)\s*\w*(?: y media)?(?: \d+ \w+)?|"
            r"a las \d{1,2}(?::\d{2})?(?: de la (?:manana|tarde|noche))?|"
            r"(?:pasado )?manana(?: a las \d{1,2}(?::\d{2})?(?: de la (?:manana|tarde|noche))?)?|"
            r"el (?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)(?: a las \d{1,2}(?::\d{2})?"
            r"(?: de la (?:manana|tarde|noche))?)?)",
            t,
        )
        d["cuando"] = cuando.group(1) if cuando else "en 10 minutos"
        msg = t.replace(d["cuando"], " ")
        msg = re.sub(
            r"\b(recuerdame|avisame|pon un recordatorio para|pon una alarma|despiertame|agenda|"
            r"no me dejes olvidar|que|de|para)\b",
            " ",
            msg,
        )
        d["mensaje"] = re.sub(r"\s+", " ", msg).strip() or "Alarma"
    elif intencion == "temporizador":
        d["minutos"] = numero(t) or 5
    elif intencion == "recordar_dato":
        m = re.search(r"\b(?:recuerda|guarda|anota|no olvides|memoriza|aprende)\s+que\s+(.+)$", original, re.I)
        d["dato"] = (m.group(1) if m else original).strip()
    elif intencion == "que_sabes":
        d["consulta"] = _resto(t, "sabes de|recuerdas de|dije de|recuerdas|guardado sobre|sabes sobre") or "yo"
    elif intencion == "escribir":
        m = re.search(r"\b(?:escribe|dicta|teclea|pon el texto)\s+(?:en la ventana\s+)?(.+)$", original, re.I)
        d["texto"] = (m.group(1) if m else "").strip()
    elif intencion == "energia":
        pass
    return d


ENSENAR = re.compile(
    r"^(?:lay\s+)?(?:cuando (?:te )?diga(?:s)?|si te digo|aprende que|cada vez que diga)\s+['\"]?(.+?)['\"]?\s*,?\s+"
    r"(?:significa\s+|es\s+|quiero que\s+|tienes que\s+|debes\s+)?"
    r"((?:abre|abras|pon|pongas|ponme|busca|busques|cierra|mueve|sube|baja|reproduce|activa|desactiva|muestra|haz|"
    r"dime|toma|bloquea|apaga|entra|lee|escribe)\b.+)$"
)


def entender(texto: str) -> Comprension:
    from lay_core.nucleo import aprendizaje

    t0 = normalizar(texto)
    m = ENSENAR.match(t0)
    if m:  # "cuando diga 'modo obra' abre revit y luego abre excel"
        return Comprension("ensenar_atajo", 0.99, {"frase": m.group(1).strip(), "ordenes": m.group(2).strip()})
    ordenes = aprendizaje.buscar_atajo(texto)  # frases que Robert le enseñó: mandan sobre todo
    if ordenes:
        return Comprension("atajo", 1.0, {"ordenes": ordenes})
    return entender_modelo(texto)


def entender_modelo(texto: str) -> Comprension:
    m = cargar_modelo()
    intencion, conf, segunda, conf2 = m.predecir(texto)
    t = normalizar(texto)
    # Reglas de precisión sobre el clasificador (casos que la estadística confunde)
    if (
        re.match(r"^(si|sí|claro|dale|confirmo|hazlo|ok|okay|de acuerdo|adelante|envialo)\b", t)
        and len(t.split()) <= 4
        and not re.match(r"^dale (a|al|clic|click|play)\b", t)  # "dale a Siguiente" es un clic, no un sí
    ):
        return Comprension("confirmar", 0.99)
    if re.match(r"^(no|cancela|mejor no|olvidalo|dejalo)\b", t) and len(t.split()) <= 4:
        return Comprension("negar", 0.99)
    if intencion == "abrir_app" and any(re.search(rf"\b{k}\b", t) for k in SITIOS) and not re.search(r"\bapp\b", t):
        intencion = "abrir_web"
    crudo = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode().strip(" ,.!¡?¿")
    saludo = r"^(hola|oye|hey|buenos dias|buenas( tardes| noches)?|buen dia|que tal|que hay)\b"
    if (re.match(saludo, t) and len(t.split()) <= 4) or (not t and re.match(saludo, crudo)):
        return Comprension("saludo", 0.99)  # "hola lay" (el relleno deja la frase vacía)
    m_y = re.search(r"\b(spotify|youtube)\b.*\by\s+(pon|ponme|reproduce|busca)\s+(.+)$", t)
    if m_y and intencion in ("abrir_app", "abrir_web", "youtube", "buscar_web", "reproducir"):
        intencion, conf = "reproducir", max(conf, UMBRAL)
        datos_y = {"plataforma": m_y.group(1), "consulta": m_y.group(3).strip()}
    else:
        datos_y = None
    # "pon lofi en youtube": poner (no solo buscar) -> el primer video empieza a sonar
    if intencion == "youtube" and re.match(r"^(pon|ponme|reproduce|toca)\b", t):
        intencion = "reproducir"
    # "pon/reproduce <algo>" que el modelo no reconoce y no es volumen/brillo/ventana -> es música
    if (
        conf < UMBRAL
        and re.match(r"^(pon|ponme|reproduce|toca|quiero escuchar)\s+\w", t)
        and not re.search(r"volumen|brillo|monitor|pantalla|ventana|temporizador|alarma|recordatorio|modo", t)
    ):
        intencion, conf = "reproducir", UMBRAL
    if intencion in ("abrir_app", "abrir_archivo") and re.search(r"\bcarpeta\b", t):
        intencion = "abrir_carpeta"
    # "abre <algo>" sin pistas de archivo/imagen/carpeta/web y el modelo duda -> es una app (aunque esté mal escrita)
    if (
        (conf < UMBRAL or intencion in ("mostrar_imagenes", "abrir_archivo"))  # sin palabras de foto/archivo: no lo es
        and re.match(r"^(abre|abreme|abrir|ejecuta|inicia|lanza|arranca)\b", t)
        and intencion in ("abrir_app", "abrir_archivo", "mostrar_imagenes", "abrir_web")
        and not re.search(r"\b(fotos?|imagen(es)?|archivo|documento|pdf|excel|word|carpeta|pagina|web|\.\w{2,4})\b", t)
        and not any(re.search(rf"\b{k}\b", t) for k in SITIOS)
    ):
        intencion, conf = "abrir_app", max(conf, UMBRAL)
    return Comprension(intencion, conf, datos_y or extraer(intencion, texto), segunda)


# ---------------- plan de acciones y respuestas ----------------
def plan(c: Comprension, usuario: str = "Robert") -> tuple[list[tuple[str, dict]], str]:
    """(llamadas a herramientas, respuesta directa si no hay llamadas)."""
    d, i = c.datos, c.intencion
    if i == "atajo":  # frase enseñada por Robert -> sus órdenes, una tras otra
        todas: list[tuple[str, dict]] = []
        for orden in d.get("ordenes", [])[:8]:
            sub = entender_modelo(orden)
            todas += plan(sub, usuario)[0] if sub.intencion != "atajo" else []
        return todas, "" if todas else "Ese atajo no tiene órdenes que entienda."
    ahora = datetime.now()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    directas = {
        "saludo": f"Hola, {usuario}. ¿Qué hacemos?",
        "gracias": "Con gusto. Aquí estoy.",
        "despedida": f"Hasta luego, {usuario}.",
        "hora": f"Son las {ahora.hour}:{ahora.minute:02d}.",
        "fecha": f"Hoy es {dias[ahora.weekday()]} {ahora.day} de {meses[ahora.month - 1]} de {ahora.year}.",
    }
    if i in directas:
        return [], directas[i]
    carpeta = d.get("carpeta", "")
    mapa: dict[str, list[tuple[str, dict]]] = {
        "estado_pc": [("sistema_estado", {})],
        "procesos": [("sistema_procesos", {"n": 5})],
        "abrir_app": [("app_abrir", {"nombre": d.get("app", "")})],
        "abrir_carpeta": [("carpeta_abrir", {"nombre": carpeta})],
        "abrir_archivo": [("archivos_abrir_por_nombre", {"consulta": d.get("consulta", "")})],
        "buscar_archivo": [("archivos_buscar", {"consulta": d.get("consulta", ""), "limite": 8})],
        "mostrar_imagenes": [("overlay_mostrar_imagenes", {"consulta": d["consulta"]} if d.get("consulta") else {})],
        "modo_manos": [("manos_activar", {})],
        "camara": [("camara", {"accion": d.get("accion", "encender")})],
        "reproducir": [
            (
                "youtube_reproducir" if d.get("plataforma") == "youtube" else "spotify_reproducir",
                {"consulta": d.get("consulta", ""), **({"tipo": d["tipo"]} if d.get("tipo") else {})},
            )
        ]
        if d.get("consulta")
        else [("multimedia", {"accion": "pausa"})],
        "personalidad": [("personalidad_activar", {"nombre": d.get("nombre", "")})],
        "consultar_libros": [("conocimiento_buscar", {"pregunta": d.get("pregunta", ""), "n": 3})],
        "clic": [("ui_click", {"ventana": "activa", "objetivo": d.get("objetivo", "")})],
        "buscar_en_app": [("app_buscar", {"app": d.get("app", ""), "consulta": d.get("consulta", "")})],
        "entrenar_gesto": [("gesto_entrenar", {"nombre": d.get("orden", ""), "orden": d.get("orden", "")})]
        if d.get("orden")
        else [],
        "gestos_listar": [("gestos_listar", {})],
        "buscar_web": [
            ("navegador_abrir", {"destino": d.get("consulta", ""), "navegador": d.get("navegador")}),
            ("web_buscar", {"consulta": d.get("consulta", ""), "maximo": 4}),
        ],
        "pregunta_info": [("web_buscar", {"consulta": d.get("consulta", ""), "maximo": 4})],
        "abrir_web": [("navegador_abrir", {"destino": d.get("url", ""), "navegador": d.get("navegador")})],
        "youtube": [
            (
                "navegador_abrir",
                {
                    "destino": "youtube.com/results?search_query=" + "+".join(d["consulta"].split())
                    if d.get("consulta")
                    else "youtube.com"  # "busca youtube" / "abre youtube" = la portada
                },
            )
        ],
        "clima": [("clima", {"ciudad": d.get("ciudad")} if d.get("ciudad") else {})],
        "volumen": [("volumen", {k: v for k, v in d.items() if v is not None})],
        "musica": [("multimedia", {"accion": d.get("accion", "pausa")})],
        "brillo": [("brillo", d)],
        "ajustes": [("ajustes_abrir", {"seccion": d.get("seccion", "")})],
        "workspace": [("workspace_aplicar", {"nombre": d.get("nombre", "")})],
        "mover_ventana": [("ventana_mover_a", {k: v for k, v in d.items() if v is not None})],
        "captura": [("pantalla_capturar", {})],
        "bloquear": [("sistema_bloquear", {})],
        "energia": [("energia", {"accion": d.get("accion", "apagar")})],
        "recordatorio": [("recordatorio_crear", {"mensaje": d.get("mensaje", ""), "cuando": d.get("cuando", "")})],
        "temporizador": [("temporizador", {"minutos": d.get("minutos", 5)})],
        "listar_recordatorios": [("recordatorios_listar", {})],
        "recordar_dato": [("memoria_guardar", {"dato": d.get("dato", "")})],
        "que_sabes": [("memoria_buscar", {"consulta": d.get("consulta", "")})],
        "correos": [("correo_resumen", {})],
        "blackboard": [("blackboard_pendientes", {})],
        "escribir": [("teclado_escribir", {"texto": d.get("texto", "")})],
        "configuracion": [("abrir_configuracion", {"seccion": "ia"})],
        "diagnostico": [("diagnostico_ejecutar", {})],
        "ensenar_atajo": [("lay_aprender_atajo", {"frase": d.get("frase", ""), "ordenes": d.get("ordenes", "")})],
    }
    return mapa.get(i, []), ""


def _ok(r) -> bool:
    return isinstance(r, (list, dict)) and not (isinstance(r, dict) and r.get("error"))


def _frases(texto: str, n: int = 2) -> str:
    partes = re.split(r"(?<=[.!?])\s+", (texto or "").strip())
    return " ".join(partes[:n]).strip()


def responder(intencion: str, resultados: list[tuple[str, object]], datos: dict) -> str:
    """Redacta la respuesta hablada con los resultados reales de las herramientas."""
    if not resultados:
        return "Listo."
    nombre, r = resultados[-1]
    if isinstance(r, dict) and r.get("requiere_confirmacion"):
        return (r.get("mensaje", "").split(". Repite")[0] or "Eso necesita tu confirmación") + ". ¿Confirmas?"
    if isinstance(r, dict) and r.get("error"):
        sugerencia = ""
        if r.get("parecidas"):
            sugerencia = " ¿Quisiste decir " + ", ".join(r["parecidas"][:3]) + "?"
        return str(r["error"]).split(". Usa ")[0].rstrip(".") + "." + sugerencia
    if intencion == "estado_pc" and isinstance(r, dict):
        partes = [
            f"La CPU está al {round(r.get('cpu_pct', 0))} %",
            f"la RAM al {round(r.get('ram_pct', 0))} %",
            f"y te quedan {str(r.get('disco_libre_gb', '?')).replace('.', ',')} GB libres",
        ]
        if r.get("bateria_pct") is not None:
            partes.append(f"Batería al {round(r['bateria_pct'])} %{' cargando' if r.get('cargando') else ''}")
        alerta = " Está bastante cargada; ¿te digo qué programa consume más?" if r.get("ram_pct", 0) > 85 else ""
        return ", ".join(partes[:3]) + "." + (f" {partes[3]}." if len(partes) > 3 else "") + alerta
    if intencion == "procesos" and isinstance(r, list) and r:
        top = ", ".join(f"{p['nombre'].removesuffix('.exe')} con {p['ram_mb']} MB" for p in r[:3])
        return f"Lo que más consume: {top}."
    if intencion in ("buscar_web", "pregunta_info"):
        res = (r.get("resultados") if isinstance(r, dict) else None) or []
        if not res:
            return "No encontré resultados claros."
        mejor = next((x for x in res if len(x.get("resumen", "")) > 60), res[0])
        dominio = re.sub(r"^https?://(www\.)?", "", mejor.get("url", "")).split("/")[0]
        extra = " Te lo abrí en el navegador." if intencion == "buscar_web" else ""
        return f"Según {dominio}: {_frases(mejor.get('resumen', ''), 2)}{extra}"
    if intencion == "clima" and isinstance(r, dict) and r.get("ahora"):
        a, hoy = r["ahora"], (r.get("pronostico") or [{}])[0]
        lluvia = f", con {hoy.get('lluvia_pct')} % de probabilidad de lluvia" if hoy.get("lluvia_pct") else ""
        return (
            f"En {r['lugar'].split(',')[0]} hay {a['temperatura']} grados, {a['cielo']}. Hoy entre "
            f"{hoy.get('min', '?')} y {hoy.get('max', '?')} grados{lluvia}."
        )
    if intencion == "volumen" and isinstance(r, dict):
        return "Silenciado." if r.get("silenciado") else f"Volumen al {r.get('volumen', '?')} %."
    if intencion == "brillo" and isinstance(r, dict):
        return f"Brillo al {r.get('brillo', '?')} %."
    if intencion == "ensenar_atajo" and isinstance(r, dict) and r.get("ok"):
        return f"Aprendido. Cuando digas {r['frase']}, haré: " + "; luego ".join(r["ordenes"]) + "."
    if intencion == "atajo":
        return "Listo, hecho." if all(_ok(x[1]) for x in resultados) else "Hice tu atajo, pero algo falló."
    if intencion == "reproducir" and isinstance(r, dict):
        if r.get("sonando"):
            return f"Sonando: {r['sonando']}."
        if r.get("video"):
            return f"Te puse {datos.get('consulta')} en YouTube."
        if r.get("aviso"):
            return r["aviso"]
        return "Listo." if r.get("ok") else (r.get("error") or "No pude ponerla.")
    if intencion == "personalidad" and isinstance(r, dict) and r.get("ok"):
        return f"Listo, ahora hablo en modo {r.get('nombre', r.get('activa'))}."
    if intencion == "consultar_libros" and isinstance(r, dict):
        res = r.get("fragmentos") or []
        if not res:
            return "No encontré eso en tus documentos. Agrégalos en Configuración, Conocimiento."
        x = res[0]
        fuente = x.get("fuente", "tu documento") + (f", {x['ubic']}" if x.get("ubic") else "")
        return f"Según {fuente}: {x['texto'][:350].strip()}…"
    if intencion == "clic" and isinstance(r, dict) and r.get("ok"):
        return f"Clic en {r.get('clic')}."
    if intencion == "buscar_en_app" and isinstance(r, dict) and r.get("ok"):
        return f"Busqué {datos.get('consulta')} en {r.get('app') or datos.get('app')}."
    if intencion == "musica":
        return {"pausa": "Listo.", "siguiente": "Siguiente.", "anterior": "Anterior."}.get(
            datos.get("accion"), "Listo."
        )
    if intencion == "abrir_app" and isinstance(r, dict):
        return f"Abriendo {r.get('abierta') or r.get('lanzado') or datos.get('app')}."
    if intencion == "abrir_carpeta" and isinstance(r, dict):
        return f"Abrí {r.get('carpeta', 'la carpeta')}."
    if intencion == "abrir_archivo" and isinstance(r, dict):
        return f"Abrí {(r.get('elegido') or {}).get('nombre', 'el archivo')}."
    if intencion == "buscar_archivo" and isinstance(r, list):
        if not r:
            return "No encontré archivos con ese nombre."
        return f"Encontré {len(r)}. El más reciente es {r[0]['nombre']}, en {r[0]['ruta'].rsplit(chr(92), 2)[-2] if chr(92) in r[0]['ruta'] else 'tu PC'}."
    if intencion == "mostrar_imagenes" and isinstance(r, dict):
        return f"Te puse {r.get('imagenes', 'las')} imágenes en el holograma. Usa tus manos."
    if intencion == "modo_manos":
        return "Muéstrame las dos palmas a la cámara para escanearlas."
    if intencion == "camara":
        if datos.get("accion") == "apagar":
            return "Cámara apagada. Ya no te estoy viendo."
        return "Cámara encendida. Muestra las dos palmas para abrir el explorador."
    if intencion == "entrenar_gesto":
        return f"Haz el gesto frente a la cámara y mantenlo quieto dos segundos. Lo usaré para {datos.get('orden', 'esa orden')}."
    if intencion == "gestos_listar" and isinstance(r, dict):
        g = r.get("gestos") or []
        if not g:
            return "Aún no me enseñaste gestos. Dime: entrena un gesto para abrir Spotify."
        return f"Tienes {len(g)} gestos: " + ", ".join(x["nombre"] for x in g[:6]) + "."
    if (
        intencion in ("abrir_web", "youtube", "buscar_web")
        and isinstance(r, dict)
        and r.get("navegador")
        and not r.get("resultados")
    ):
        return f"Listo, lo abrí en {r['navegador'].capitalize()}."
    if intencion == "recordatorio" and isinstance(r, dict):
        return f"Te recuerdo {r.get('mensaje', '')} el {r.get('cuando_texto', '')}."
    if intencion == "temporizador" and isinstance(r, dict):
        return f"Temporizador de {datos.get('minutos')} minutos en marcha."
    if intencion == "listar_recordatorios" and isinstance(r, list):
        return (
            "No tienes recordatorios."
            if not r
            else (f"Tienes {len(r)}. El próximo: {r[0]['mensaje']}, {r[0]['cuando_texto']}.")
        )
    if intencion == "recordar_dato":
        return "Anotado, no lo olvido."
    if intencion == "que_sabes" and isinstance(r, list):
        return (
            "No tengo nada guardado sobre eso." if not r else "Me dijiste: " + "; ".join(x["dato"] for x in r[:3]) + "."
        )
    if intencion == "correos" and isinstance(r, dict):
        n = r.get("total", 0)
        if not n:
            return "No tienes correos nuevos." + (" " + r["avisos"][0] if r.get("avisos") else "")
        c = r["correos"][0]
        return f"Tienes {n} correos sin leer. El último es de {str(c.get('de', '')).split('<')[0].strip()}: {c.get('asunto', '')}."
    if intencion == "blackboard" and isinstance(r, list):
        return (
            "No tienes entregas en las próximas dos semanas."
            if not r
            else (f"Tienes {len(r)} pendientes. El próximo: {r[0]['titulo']}, {r[0]['cuando']}.")
        )
    if intencion == "workspace" and isinstance(r, dict):
        return (
            f"Modo {datos.get('nombre')} listo: {r.get('acomodadas', 0)} de {r.get('total', 0)} ventanas en su sitio."
        )
    if intencion == "captura" and isinstance(r, dict):
        return "Captura guardada."
    if intencion == "diagnostico":
        return "Te dejé el diagnóstico en pantalla."
    return "Listo."


# ---------------- proveedor para el cerebro ----------------
class Nucleo:
    """Proveedor 'nucleo' (se elige en Configuración) y motor del modo híbrido."""

    nombre = "nucleo"

    def __init__(self) -> None:
        self.c: Comprension | None = None
        self.pendientes: list[tuple[str, dict]] = []
        self.resultados: list[tuple[str, object]] = []

    def turno(self, sistema, historial, tools, nivel, max_tokens, al_texto=None):
        import json

        from lay_core.config import CONFIG
        from lay_core.proveedores import Llamada, Turno

        ultimo = historial[-1]
        if ultimo["rol"] == "usuario":
            self.c = entender(ultimo["texto"])
            llamadas, directa = plan(self.c, getattr(CONFIG, "usuario", "Robert"))
            if not llamadas:
                texto = directa or (
                    "No te entendí bien. Prueba con otras palabras, o activa una IA conversacional "
                    "en Configuración para charlar."
                )
                if al_texto:
                    al_texto(texto)
                return Turno(texto, [])
            self.pendientes, self.resultados = llamadas[1:], []
            n, a = llamadas[0]
            return Turno("", [Llamada(f"nucleo_{n}", n, a)])
        # Llegó el resultado de una herramienta
        try:
            res = json.loads(ultimo["contenido"])
        except (ValueError, TypeError):
            res = ultimo["contenido"]
        self.resultados.append((ultimo["nombre"], res))
        if self.pendientes and not (isinstance(res, dict) and res.get("requiere_confirmacion")):
            n, a = self.pendientes.pop(0)
            return Turno("", [Llamada(f"nucleo_{n}_{len(self.resultados)}", n, a)])
        # Para búsquedas, la respuesta sale de la búsqueda web aunque el navegador haya fallado
        utiles = [x for x in self.resultados if _ok(x[1])] or self.resultados
        texto = responder(self.c.intencion if self.c else "", utiles, self.c.datos if self.c else {})
        if al_texto:
            al_texto(texto)
        return Turno(texto, [])

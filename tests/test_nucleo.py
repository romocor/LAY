"""LAY Núcleo: la IA propia. Intenciones, datos extraídos y conversaciones completas."""

import json
import types

import pytest

from lay_core import nucleo
from lay_core.nucleo import datos, modelo


def test_generaliza_a_frases_escritas_a_mano():
    acc, errores = modelo.precision(nucleo.cargar_modelo(), datos.PRUEBA)
    assert acc >= 0.9, errores


@pytest.mark.parametrize(
    "frase,intencion,esperado",
    [
        ("LAY, abre spotify por favor", "abrir_app", {"app": "spotify"}),
        ("ábreme el revit", "abrir_app", {"app": "revit"}),
        ("abre la carpeta de descargas", "abrir_carpeta", {"carpeta": "descargas"}),
        ("sube el volumen al 40", "volumen", {"accion": "fijar", "nivel": 40}),
        ("baja el volumen", "volumen", {"accion": "bajar"}),
        ("silencia", "volumen", {"accion": "silenciar"}),
        ("siguiente canción", "musica", {"accion": "siguiente"}),
        ("busca en google precio del cemento", "buscar_web", {"consulta": "precio del cemento"}),
        ("busca en brave recetas de ceviche", "buscar_web", {"consulta": "recetas de ceviche", "navegador": "brave"}),
        ("abre youtube", "abrir_web", {"url": "youtube.com"}),
        ("clima en cusco", "clima", {"ciudad": "cusco"}),
        ("recuérdame llamar a pérez en 20 minutos", "recordatorio", {"cuando": "en 20 minutos"}),
        ("pon un temporizador de 15 minutos", "temporizador", {"minutos": 15}),
        ("pon chrome en el monitor de arriba", "mover_ventana", {"titulo": "chrome", "direccion": "arriba"}),
        ("recuerda que mi jefe se llama Carlos", "recordar_dato", {"dato": "mi jefe se llama Carlos"}),
    ],
)
def test_entiende_y_extrae(frase, intencion, esperado):
    c = nucleo.entender(frase)
    assert c.intencion == intencion, (c.intencion, c.confianza)
    for k, v in esperado.items():
        assert c.datos.get(k) == v, (k, c.datos)


def test_si_y_no_cortos():
    assert nucleo.entender("sí, envíalo").intencion == "confirmar"
    assert nucleo.entender("no, mejor no").intencion == "negar"


def test_charla_no_la_toma_como_orden():
    for frase in ["ayúdame a redactar una carta para mi jefe", "cuéntame un chiste", "qué opinas del bim"]:
        c = nucleo.entender(frase)
        assert c.intencion in ("charla", "pregunta_info") or c.confianza < nucleo.UMBRAL, (frase, c)


def correr(frase, resultados_herramientas):
    """Conversación completa con el proveedor Núcleo y herramientas simuladas."""
    n = nucleo.Nucleo()
    hist = [{"rol": "usuario", "texto": frase}]
    llamadas = []
    for _ in range(4):
        t = n.turno("", hist, [], "rapido", 100)
        if not t.llamadas:
            return t.texto, llamadas
        c = t.llamadas[0]
        llamadas.append((c.nombre, c.args))
        res = resultados_herramientas.get(c.nombre, {"ok": True})
        hist += [
            {"rol": "asistente", "texto": "", "llamadas": t.llamadas},
            {"rol": "herramienta", "id": c.id, "nombre": c.nombre, "contenido": json.dumps(res)},
        ]
    raise AssertionError("no terminó")


def test_conversacion_estado_pc():
    texto, ll = correr(
        "cómo está la pc",
        {
            "sistema_estado": {
                "cpu_pct": 23,
                "ram_pct": 61,
                "disco_libre_gb": 120.5,
                "bateria_pct": 80,
                "cargando": True,
            }
        },
    )
    assert ll == [("sistema_estado", {})]
    assert "23 %" in texto and "61 %" in texto and "120,5" in texto and "80 %" in texto


def test_conversacion_busqueda_abre_navegador_y_responde_con_datos_actuales():
    web = {
        "resultados": [
            {
                "titulo": "Dólar hoy",
                "url": "https://www.bcrp.gob.pe/x",
                "resumen": "El tipo de cambio cerró en S/ 3,52 por dólar. Fuente oficial del BCRP.",
            }
        ]
    }
    texto, ll = correr("busca en google el precio del dólar hoy", {"web_buscar": web})
    assert [x[0] for x in ll] == ["navegador_abrir", "web_buscar"]
    assert "bcrp.gob.pe" in texto and "3,52" in texto and "navegador" in texto


def test_si_el_navegador_falla_igual_responde():
    web = {
        "resultados": [
            {
                "titulo": "x",
                "url": "https://es.wikipedia.org/y",
                "resumen": "Lima es la capital del Perú y tiene casi 11 millones de habitantes.",
            }
        ]
    }
    texto, _ = correr(
        "busca en internet población de lima",
        {"navegador_abrir": {"error": "No encontré Brave, Chrome ni Edge"}, "web_buscar": web},
    )
    assert "11 millones" in texto


def test_app_inexistente_sugiere_parecidas():
    texto, _ = correr(
        "abre fotoshop",
        {"app_abrir": {"error": "No encontré la app 'fotoshop'.", "parecidas": ["Adobe Photoshop 2025"]}},
    )
    assert "Photoshop" in texto


def test_accion_sensible_pregunta():
    texto, _ = correr(
        "apaga la pc",
        {
            "energia": {
                "requiere_confirmacion": True,
                "mensaje": "LAY va a apagar, reiniciar o suspender la PC. Repite con...",
            }
        },
    )
    assert texto.endswith("¿Confirmas?")


def test_cerebro_hibrido_usa_nucleo_para_ordenes(monkeypatch):
    """Con Ollama apagado (o un modelo que no usa herramientas) las órdenes igual se ejecutan."""
    from lay_core import cerebro as cb

    monkeypatch.setattr(cb.bus, "publicar", lambda *a, **k: {})
    c = cb.Cerebro.__new__(cb.Cerebro)
    c.historial, c.confirmacion_pendiente, c.ultimo_usuario, c.temas_previos, c._cache = [], False, "", set(), {}
    c.llamada_pendiente, c._fijo = None, None
    c.tools = [{"name": n, "description": "", "input_schema": {}} for n in ("volumen", "energia")]
    ejecutadas = []

    class MCP:
        async def call_tool(self, nombre, args):
            ejecutadas.append((nombre, args))
            if nombre == "energia" and not args.get("confirmar"):
                return [
                    types.SimpleNamespace(
                        text=json.dumps({"requiere_confirmacion": True, "mensaje": "LAY va a apagar la PC. Repite"})
                    )
                ]
            return [types.SimpleNamespace(text=json.dumps({"ok": True, "volumen": 40, "silenciado": False}))]

    c.mcp = MCP()
    monkeypatch.setitem(cb.CONFIG.ia, "proveedor", "ollama")  # aunque Ollama no exista
    assert c.responder("sube el volumen al 40") == "Volumen al 40 %."
    assert c.responder("apaga la pc").endswith("¿Confirmas?")
    assert c.responder("sí") == "Hecho."
    assert ejecutadas[-1] == ("energia", {"accion": "apagar", "confirmar": True})

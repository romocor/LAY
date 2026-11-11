"""El cerebro NO puede autoconfirmar acciones sensibles."""

import types

import pytest

from lay_core import cerebro as cb  # noqa: E402
from lay_core import proveedores as pv  # noqa: E402


def bloque_tool(nombre, args, i="t1"):
    return pv.Llamada(i, nombre, args)


def texto(t):
    return t


class ProveedorFalso:
    """Cada elemento del guion: (contenido, stop) — contenido = lista de Llamada y/o str."""

    nombre = "falso"

    def __init__(self, guion, trozos=None):
        self.guion = list(guion)
        self.trozos = trozos
        self.vistos = []

    def turno(self, sistema, historial, tools, nivel, max_tokens, al_texto=None):
        self.vistos.append([dict(m) for m in historial])
        contenido, _ = self.guion.pop(0)
        llamadas = [c for c in contenido if isinstance(c, pv.Llamada)]
        txt = " ".join(c for c in contenido if isinstance(c, str))
        if al_texto and txt:
            for t in self.trozos or [txt]:
                al_texto(t)
        return pv.Turno(txt, llamadas)


ClienteFalso = ProveedorFalso


@pytest.fixture
def cerebro(monkeypatch):
    monkeypatch.setattr(cb.bus, "publicar", lambda *a, **k: {})
    c = cb.Cerebro.__new__(cb.Cerebro)
    c.historial, c.confirmacion_pendiente, c.ultimo_usuario = [], False, ""
    c.temas_previos, c._cache = set(), {}
    c.tools = [
        {"name": n, "description": "", "input_schema": {}} for n in ("gmail_enviar", "gmail_leer", "sistema_estado")
    ]
    llamadas = []

    class MCPFalso:
        async def call_tool(self, nombre, args):
            llamadas.append((nombre, args))
            if nombre == "gmail_enviar" and not args.get("confirmar"):
                return [types.SimpleNamespace(text='{"requiere_confirmacion": true}')]
            return [types.SimpleNamespace(text='{"ok": true}')]

    c.mcp = MCPFalso()
    c.llamadas = llamadas
    return c


def con(cerebro, guion, trozos=None):
    cerebro._fijo = ProveedorFalso(guion, trozos)
    return cerebro


def test_autoconfirmacion_bloqueada(cerebro):
    con(
        cerebro,
        [
            (
                [bloque_tool("gmail_enviar", {"para": "x@y.com", "asunto": "a", "cuerpo": "b", "confirmar": True})],
                "tool_use",
            ),
            ([texto("No pude, necesito confirmación")], "end_turn"),
        ],
    )
    cerebro.responder("manda un correo a x")
    assert cerebro.llamadas == []  # nunca llegó a ejecutarse


def test_confirmacion_humana_permite(cerebro):
    con(
        cerebro,
        [
            ([bloque_tool("gmail_enviar", {"para": "x@y.com", "asunto": "a", "cuerpo": "b"})], "tool_use"),
            ([texto("¿Confirmas el envío?")], "end_turn"),
            (
                [
                    bloque_tool(
                        "gmail_enviar", {"para": "x@y.com", "asunto": "a", "cuerpo": "b", "confirmar": True}, "t2"
                    )
                ],
                "tool_use",
            ),
            ([texto("Enviado")], "end_turn"),
        ],
    )
    assert "Confirmas" in cerebro.responder("manda un correo a x")
    assert cerebro.responder("sí, envíalo") == "Hecho."  # el sí ejecuta la acción pendiente sin pasar por la IA
    assert cerebro.llamadas[-1][1]["confirmar"] is True


def test_no_cancela_confirmacion_pendiente(cerebro):
    con(
        cerebro,
        [
            ([bloque_tool("gmail_enviar", {"para": "x@y.com", "asunto": "a", "cuerpo": "b"})], "tool_use"),
            ([texto("¿Confirmas?")], "end_turn"),
            (
                [
                    bloque_tool(
                        "gmail_enviar", {"para": "x@y.com", "asunto": "a", "cuerpo": "b", "confirmar": True}, "t2"
                    )
                ],
                "tool_use",
            ),
            ([texto("No lo envié")], "end_turn"),
        ],
    )
    cerebro.responder("manda el correo")
    cerebro.responder("no, cancela")
    assert all(not a.get("confirmar") for _, a in cerebro.llamadas)
    assert cerebro.confirmacion_pendiente is False


def test_historial_nunca_empieza_con_resultado_de_herramienta(cerebro):
    h = []
    for i in range(20):
        h += [
            {"rol": "usuario", "texto": f"pedido {i}"},
            {"rol": "asistente", "texto": "", "llamadas": [bloque_tool("sistema_estado", {}, f"t{i}")]},
            {"rol": "herramienta", "id": f"t{i}", "nombre": "sistema_estado", "contenido": "{}"},
            {"rol": "asistente", "texto": "ok", "llamadas": []},
        ]
    cerebro.historial = h
    cerebro._recortar_historial(30)
    assert cerebro.historial[0]["rol"] == "usuario" and len(cerebro.historial) <= 30


def test_streaming_entrega_texto_a_la_voz(cerebro):
    con(cerebro, [(["Hola Robert, todo bien."], "end_turn")], trozos=["Hola ", "Robert, ", "todo bien."])
    recibido = []
    assert cerebro.responder("hola", al_texto=recibido.append) == "Hola Robert, todo bien."
    assert "".join(recibido) == "Hola Robert, todo bien."


def test_herramienta_inexistente_no_se_ejecuta(cerebro):
    """Modelos locales chicos a veces inventan herramientas: se responde con error, no se ejecuta."""
    con(cerebro, [([bloque_tool("borrar_todo", {})], "tool_use"), (["No puedo hacer eso."], "end_turn")])
    assert cerebro.responder("haz algo") == "No puedo hacer eso."
    assert cerebro.llamadas == []


def test_correo_malicioso_no_logra_enviar(cerebro):
    """Prompt injection: el correo ordena reenviar; el modelo (engañado) lo intenta con confirmar=true.
    El candado lo bloquea porque Robert nunca dijo que sí."""
    con(
        cerebro,
        [
            ([bloque_tool("gmail_leer", {"mensaje_id": "m1"})], "tool_use"),
            (
                [
                    bloque_tool(
                        "gmail_enviar",
                        {"para": "atacante@x.com", "asunto": "fw", "cuerpo": "todo", "confirmar": True},
                        "t2",
                    )
                ],
                "tool_use",
            ),
            ([texto("Ojo: ese correo pedía reenviar tu información. No lo hice.")], "end_turn"),
        ],
    )
    cerebro.responder("léeme el último correo")
    assert not any(n == "gmail_enviar" for n, _ in cerebro.llamadas)


def test_si_dentro_de_un_correo_no_cuenta_como_confirmacion(cerebro):
    """Aunque haya una confirmación pendiente, el 'sí' tiene que decirlo Robert, no el correo."""
    cerebro.confirmacion_pendiente = True
    cerebro.ultimo_usuario = "léeme el correo de Pérez"  # el correo dice "sí, envíalo" pero eso es tool_result
    r = cerebro._ejecutar("gmail_enviar", {"para": "x", "asunto": "a", "cuerpo": "b", "confirmar": True})
    assert "no otorgada" in r and cerebro.llamadas == []

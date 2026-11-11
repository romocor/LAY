"""El cerebro NO puede autoconfirmar acciones sensibles."""

import types

import pytest

pytest.importorskip("anthropic")
from lay_core import cerebro as cb  # noqa: E402


def bloque_tool(nombre, args, i="t1"):
    return types.SimpleNamespace(type="tool_use", id=i, name=nombre, input=args)


def texto(t):
    return types.SimpleNamespace(type="text", text=t)


class ClienteFalso:
    def __init__(self, guion):
        self.guion = list(guion)
        self.messages = self

    def create(self, **kw):
        contenido, stop = self.guion.pop(0)
        return types.SimpleNamespace(content=contenido, stop_reason=stop)


@pytest.fixture
def cerebro(monkeypatch):
    monkeypatch.setattr(cb.bus, "publicar", lambda *a, **k: {})
    c = cb.Cerebro.__new__(cb.Cerebro)
    c.historial, c.confirmacion_pendiente, c.ultimo_usuario = [], False, ""
    c.tools = []
    llamadas = []

    class MCPFalso:
        async def call_tool(self, nombre, args):
            llamadas.append((nombre, args))
            if not args.get("confirmar"):
                return [types.SimpleNamespace(text='{"requiere_confirmacion": true}')]
            return [types.SimpleNamespace(text='{"ok": true}')]

    c.mcp = MCPFalso()
    c.llamadas = llamadas
    return c


def test_autoconfirmacion_bloqueada(cerebro):
    cerebro.cliente = ClienteFalso(
        [
            (
                [bloque_tool("gmail_enviar", {"para": "x@y.com", "asunto": "a", "cuerpo": "b", "confirmar": True})],
                "tool_use",
            ),
            ([texto("No pude, necesito confirmación")], "end_turn"),
        ]
    )
    cerebro.responder("manda un correo a x")
    assert cerebro.llamadas == []  # nunca llegó a ejecutarse


def test_confirmacion_humana_permite(cerebro):
    cerebro.cliente = ClienteFalso(
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
        ]
    )
    assert "Confirmas" in cerebro.responder("manda un correo a x")
    assert cerebro.responder("sí, envíalo") == "Enviado"
    assert cerebro.llamadas[-1][1]["confirmar"] is True


def test_no_cancela_confirmacion_pendiente(cerebro):
    cerebro.cliente = ClienteFalso(
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
        ]
    )
    cerebro.responder("manda el correo")
    cerebro.responder("no, cancela")
    assert all(not a.get("confirmar") for _, a in cerebro.llamadas)
    assert cerebro.confirmacion_pendiente is False


def test_historial_nunca_empieza_con_tool_result(cerebro):
    h = []
    for i in range(20):
        h += [
            {"role": "user", "content": f"pedido {i}"},
            {"role": "assistant", "content": [bloque_tool("sistema_estado", {}, f"t{i}")]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": "{}"}]},
            {"role": "assistant", "content": [texto("ok")]},
        ]
    cerebro.historial = h
    cerebro._recortar_historial(30)
    assert cerebro.historial[0]["role"] == "user" and isinstance(cerebro.historial[0]["content"], str)
    assert len(cerebro.historial) <= 30


class FlujoFalso:
    def __init__(self, trozos, final):
        self.trozos, self.final = trozos, final

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for t in self.trozos:
            yield types.SimpleNamespace(
                type="content_block_delta", delta=types.SimpleNamespace(type="text_delta", text=t)
            )

    def get_final_message(self):
        return self.final


def test_streaming_entrega_texto_a_la_voz(cerebro):
    final = types.SimpleNamespace(content=[texto("Hola Robert, todo bien.")], stop_reason="end_turn")
    msgs = types.SimpleNamespace(
        stream=lambda **kw: FlujoFalso(["Hola ", "Robert, ", "todo bien."], final), create=None
    )
    cerebro.cliente = types.SimpleNamespace(messages=msgs)
    recibido = []
    assert cerebro.responder("hola", al_texto=recibido.append) == "Hola Robert, todo bien."
    assert "".join(recibido) == "Hola Robert, todo bien."

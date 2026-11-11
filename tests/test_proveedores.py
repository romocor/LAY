"""Proveedores de IA con un servidor HTTP simulado (sin Ollama ni internet)."""

import json

import httpx
import pytest

from lay_core import proveedores as pv


def sse(*eventos):
    return "".join(f"data: {json.dumps(e)}\n\n" for e in eventos) + "data: [DONE]\n\n"


def transporte(respuestas):
    """respuestas: dict ruta -> (codigo, cuerpo) ; registra las peticiones."""
    vistos = []

    def manejar(req: httpx.Request):
        vistos.append((req.url.path, json.loads(req.content or b"{}")))
        for ruta, (codigo, cuerpo) in respuestas.items():
            if req.url.path.endswith(ruta):
                return httpx.Response(codigo, text=cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo))
        return httpx.Response(404, text="no")

    return httpx.Client(transport=httpx.MockTransport(manejar)), vistos


def test_ollama_streaming_con_herramienta_en_trozos():
    cuerpo = sse(
        {"choices": [{"delta": {"content": "Abriendo "}}]},
        {"choices": [{"delta": {"content": "Excel."}}]},
        {
            "choices": [
                {"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "app_", "arguments": ""}}]}}
            ]
        },
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "lanzar", "arguments": '{"nom'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'bre": "excel"}'}}]}}]},
    )
    cli, vistos = transporte({"/models": (200, {"data": [{"id": "qwen2.5:3b"}]}), "/chat/completions": (200, cuerpo)})
    p = pv.OpenAICompatible("ollama", {"modelos": {}}, cliente=cli)
    oido = []
    t = p.turno(
        "sis",
        [{"rol": "usuario", "texto": "abre excel"}],
        [{"name": "app_lanzar", "description": "d", "input_schema": {"type": "object"}}],
        "rapido",
        512,
        oido.append,
    )
    assert t.texto == "Abriendo Excel." and "".join(oido).startswith("Abriendo Excel.")
    assert t.llamadas[0].nombre == "app_lanzar" and t.llamadas[0].args == {"nombre": "excel"}
    pet = vistos[-1][1]
    assert pet["model"] == "qwen2.5:3b" and pet["tools"][0]["function"]["name"] == "app_lanzar"
    assert pet["messages"][0]["role"] == "system"


def test_historial_neutro_a_openai_y_anthropic():
    h = [
        {"rol": "usuario", "texto": "manda el correo"},
        {"rol": "asistente", "texto": "Listo.", "llamadas": [pv.Llamada("c1", "gmail_enviar", {"para": "x"})]},
        {"rol": "herramienta", "id": "c1", "nombre": "gmail_enviar", "contenido": '{"ok": true}'},
    ]
    o = pv.a_openai("sis", h)
    assert o[2]["tool_calls"][0]["function"]["arguments"] == '{"para": "x"}' and o[3]["tool_call_id"] == "c1"
    a = pv.a_anthropic(h)
    assert a[1]["content"][1]["type"] == "tool_use" and a[2]["content"][0]["tool_use_id"] == "c1"


def test_ollama_apagado_da_mensaje_claro():
    def caido(req):
        raise httpx.ConnectError("rechazada")

    p = pv.OpenAICompatible("ollama", {}, cliente=httpx.Client(transport=httpx.MockTransport(caido)))
    with pytest.raises(pv.ProveedorNoDisponible, match="no está corriendo"):
        p.turno("s", [{"rol": "usuario", "texto": "hola"}], [], "rapido", 100)


def test_cupo_gratis_agotado(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    cli, _ = transporte({"/chat/completions": (429, "rate limit"), "/models": (200, {"data": []})})
    p = pv.OpenAICompatible("groq", {}, cliente=cli)
    with pytest.raises(pv.ProveedorNoDisponible, match="cupo gratuito"):
        p.turno("s", [{"rol": "usuario", "texto": "hola"}], [], "rapido", 100)


def test_sin_clave_no_arranca(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(pv.ProveedorNoDisponible, match="Configuración"):
        pv.OpenAICompatible("gemini", {})


def test_usa_el_modelo_local_descargado():
    cli, _ = transporte({"/models": (200, {"data": [{"id": "llama3.2:1b"}, {"id": "qwen2.5:7b"}]})})
    p = pv.OpenAICompatible("ollama", {}, cliente=cli)
    assert p.resolver_modelo("profundo") == "qwen2.5:7b"
    assert p.resolver_modelo("rapido") == "llama3.2:1b"  # qwen2.5:3b no está: el más chico que sí está


def test_gemini_elige_modelo_vigente(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza")
    cli, _ = transporte(
        {
            "/models": (
                200,
                {
                    "data": [
                        {"id": "models/gemini-3-flash"},
                        {"id": "models/gemini-3-flash-lite"},
                        {"id": "models/text-embedding-004"},
                    ]
                },
            )
        }
    )
    p = pv.OpenAICompatible("gemini", {}, cliente=cli)
    assert p.resolver_modelo("rapido") == "gemini-3-flash-lite" and p.resolver_modelo("profundo") == "gemini-3-flash"


def test_respaldo_nunca_usa_pago_sin_permiso(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert pv.orden_de_respaldo({"proveedor": "ollama"}) == ["ollama", "gemini"]
    assert pv.orden_de_respaldo({"proveedor": "ollama", "respaldo_pago": True})[-1] == "anthropic"


@pytest.mark.parametrize(
    "escrito,nombre,args",
    [
        (
            '<tool_call>\n{"name": "app_abrir", "arguments": {"nombre": "calculadora"}}\n</tool_call>',
            "app_abrir",
            {"nombre": "calculadora"},
        ),
        (
            '```json\n{"name": "volumen", "arguments": "{\\"accion\\": \\"subir\\"}"}\n```',
            "volumen",
            {"accion": "subir"},
        ),
        ('{"function": {"name": "clima", "arguments": {}}}', "clima", {}),
    ],
)
def test_llamada_escrita_como_texto_se_ejecuta_y_no_se_dice(escrito, nombre, args):
    cuerpo = sse(*[{"choices": [{"delta": {"content": escrito[i : i + 7]}}]} for i in range(0, len(escrito), 7)])
    cli, _ = transporte({"/models": (200, {"data": []}), "/chat/completions": (200, cuerpo)})
    dicho = []
    t = pv.OpenAICompatible("ollama", {}, cliente=cli).turno(
        "s", [{"rol": "usuario", "texto": "x"}], [], "rapido", 100, dicho.append
    )
    assert [(c.nombre, c.args) for c in t.llamadas] == [(nombre, args)] and t.texto == ""
    assert "{" not in "".join(dicho)  # la voz nunca lee el JSON


def test_texto_normal_pasa_completo_a_la_voz():
    cuerpo = sse(*[{"choices": [{"delta": {"content": t}}]} for t in ["La ", "CPU está ", "al 23 %. {ojo}"]])
    cli, _ = transporte({"/models": (200, {"data": []}), "/chat/completions": (200, cuerpo)})
    dicho = []
    t = pv.OpenAICompatible("ollama", {}, cliente=cli).turno(
        "s", [{"rol": "usuario", "texto": "x"}], [], "rapido", 100, dicho.append
    )
    assert "".join(dicho) == "La CPU está al 23 %. {ojo}" and t.llamadas == []

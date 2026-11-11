"""Hub: un evento publicado llega al overlay suscrito."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from loops.hub import app  # noqa: E402


def test_evento_llega_al_ws():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        assert c.post("/evento", json={"tipo": "voz.estado", "estado": "pensando"}).json()["ok"]
        assert ws.receive_json()["estado"] == "pensando"


def test_archivo_bloquea_no_imagenes():
    assert TestClient(app).get("/archivo", params={"ruta": "/etc/passwd"}).status_code == 404


def test_comando_local_sin_token():
    assert TestClient(app).post("/api/comando", json={"texto": "hola"}).json()["ok"]


def test_mensaje_basura_no_desconecta_al_overlay():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_text("null")
        ws.send_text("{no es json")
        ws.send_text('{"tipo": "overlay.abrir_archivo", "ruta": "/no/existe.png"}')
        c.post("/evento", json={"tipo": "voz.estado", "estado": "hablando"})
        recibidos = [ws.receive_json() for _ in range(3)]
        tipos = [r["tipo"] for r in recibidos]
        assert "voz.estado" in tipos  # la conexión sigue viva

"""Fase 5: acceso remoto. Desde esta PC todo; desde fuera solo /remoto, /api/comando y /ws de lectura,
con token, y por defecto solo por Tailscale."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lay_core.config import CONFIG
from loops.hub import app

CELULAR_TS = ("100.101.20.30", 5555)  # IP de Tailscale
WIFI = ("192.168.1.50", 5555)  # alguien en la misma red wifi


@pytest.fixture
def remoto(monkeypatch):
    monkeypatch.setitem(CONFIG.remoto, "activo", True)
    monkeypatch.setitem(CONFIG.remoto, "solo_tailscale", True)
    monkeypatch.setenv("LAY_HUB_TOKEN", "secreto-123")


def test_remoto_apagado_rechaza_todo(monkeypatch):
    monkeypatch.setitem(CONFIG.remoto, "activo", False)
    c = TestClient(app, client=CELULAR_TS)
    assert c.get("/remoto").status_code == 403
    assert c.post("/api/comando", json={"texto": "x"}, headers={"Authorization": "Bearer y"}).status_code == 403


def test_celular_con_token_por_tailscale(remoto):
    c = TestClient(app, client=CELULAR_TS)
    assert c.get("/remoto").status_code == 200  # la página no tiene datos: carga sin token
    r = c.post("/api/comando", json={"texto": "¿cómo está el PC?"}, headers={"Authorization": "Bearer secreto-123"})
    assert r.json()["ok"]


def test_token_incorrecto_o_ausente(remoto):
    c = TestClient(app, client=CELULAR_TS)
    assert c.post("/api/comando", json={"texto": "x"}).status_code == 403
    assert c.post("/api/comando", json={"texto": "x"}, headers={"Authorization": "Bearer otro"}).status_code == 403


def test_wifi_no_tailscale_rechazado_aun_con_token(remoto):
    c = TestClient(app, client=WIFI)
    r = c.post("/api/comando", json={"texto": "x"}, headers={"Authorization": "Bearer secreto-123"})
    assert r.status_code == 403 and "Tailscale" in r.json()["error"]


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/config",
        "/archivo?ruta=C:/x.png",
        "/miniatura?ruta=x",
        "/evento",
        "/api/ia/estado",
        "/api/remoto/token",
        "/",
        "/api/comando/siguiente",
        "/api/probar/ia",
    ],
)
def test_rutas_internas_nunca_desde_fuera(remoto, ruta):
    c = TestClient(app, client=CELULAR_TS)
    h = {"Authorization": "Bearer secreto-123"}
    post = ruta in ("/evento", "/api/remoto/token", "/api/probar/ia")
    r = c.post(ruta, json={}, headers=h) if post else c.get(ruta, headers=h)
    assert r.status_code == 403


def test_ws_remoto_requiere_token_y_es_de_solo_lectura(remoto):
    c = TestClient(app, client=CELULAR_TS)
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws") as ws:
            ws.receive_text()
    local = TestClient(app)
    with c.websocket_connect("/ws?token=secreto-123") as cel, local.websocket_connect("/ws") as hud:
        cel.send_text('{"tipo": "overlay.abrir_archivo", "ruta": "C:/Windows/notepad.exe"}')  # se ignora
        local.post("/evento", json={"tipo": "voz.estado", "estado": "hablando", "texto": "Todo bien."})
        assert cel.receive_json()["texto"] == "Todo bien."
        assert hud.receive_json()["tipo"] == "voz.estado"  # al HUD no le llegó nada del celular


def test_config_local_guarda_y_no_devuelve_secretos(tmp_path, monkeypatch):
    import lay_core.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "lay.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(app)
    r = c.post(
        "/api/config",
        json={
            "config": {"aplausos": {"sensibilidad": 0.8}, "hackeo": 1},
            "secretos": {"GEMINI_API_KEY": "AIza-secreto", "PATH": "x"},
        },
    ).json()
    assert r["config"]["aplausos"]["sensibilidad"] == 0.8 and r["config"]["aplausos"]["activo"] is True
    assert r["secretos"]["GEMINI_API_KEY"] is True and "AIza-secreto" not in str(r)
    assert "PATH" not in (tmp_path / ".env").read_text() and "hackeo" not in (tmp_path / "lay.json").read_text()
    cfg.recargar()

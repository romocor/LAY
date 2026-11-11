"""Escritorio con 3 monitores y ventanas simuladas (sin Windows real)."""

import types

import pytest

from lay_core import escritorio as esc

MONS = [  # izquierda -> derecha, desordenados a propósito
    types.SimpleNamespace(x=1920, y=0, width=2560, height=1440, is_primary=True, name="central"),
    types.SimpleNamespace(x=0, y=0, width=1920, height=1080, is_primary=False, name="izq"),
    types.SimpleNamespace(x=4480, y=0, width=1920, height=1080, is_primary=False, name="der"),
]


class Ventana:
    def __init__(self, title, w=800, h=600, minimizada=False):
        self.title, self.width, self.height = title, w, h
        self.left = self.top = 0
        self.isMinimized, self.isMaximized = minimizada, False
        self.acciones = []

    def restore(self):
        self.isMinimized = self.isMaximized = False

    def moveTo(self, x, y):
        self.left, self.top = x, y

    def resizeTo(self, w, h):
        self.width, self.height = w, h

    def maximize(self):
        self.isMaximized = True

    def activate(self):
        self.acciones.append("activa")

    def close(self):
        self.acciones.append("cerrada")


@pytest.fixture
def escena(monkeypatch):
    ventanas = [
        Ventana("Libro1 - Excel", 1200, 800),
        Ventana("Excel", 300, 200, minimizada=True),
        Ventana("LAY — Interfaz holográfica", 2560, 1440),
        Ventana("Bandeja de entrada - Outlook"),
    ]
    monkeypatch.setattr(esc, "_gw", lambda: types.SimpleNamespace(getAllWindows=lambda: ventanas))
    import screeninfo

    monkeypatch.setattr(screeninfo, "get_monitors", lambda: MONS, raising=False)
    return ventanas


@pytest.fixture(autouse=True)
def _screeninfo_stub(monkeypatch):
    import sys

    if "screeninfo" not in sys.modules:
        monkeypatch.setitem(sys.modules, "screeninfo", types.SimpleNamespace(get_monitors=lambda: MONS))


def test_monitores_ordenados_izq_a_der(escena):
    assert [m["nombre"] for m in esc.monitores()] == ["izq", "central", "der"]


def test_mover_a_mitad_derecha_del_monitor_2(escena):
    r = esc.mover_ventana("excel", monitor=2, posicion="derecha")
    w = escena[0]  # gana "Libro1 - Excel": visible y más grande que el "Excel" minimizado
    assert r["ok"] and r["ventana"] == "Libro1 - Excel"
    assert (w.left, w.top, w.width, w.height) == (1920 + 1280, 0, 1280, 1440)


def test_maximizada(escena):
    esc.mover_ventana("outlook", monitor=3, posicion="maximizada")
    assert escena[3].left == 4480 and escena[3].isMaximized


def test_monitor_inexistente_usa_el_ultimo(escena):
    r = esc.mover_ventana("outlook", monitor=5)
    assert r["ok"] and r["monitor"] == 3 and "aviso" in r


def test_posicion_invalida(escena):
    assert "error" in esc.mover_ventana("outlook", posicion="diagonal")


def test_nunca_toca_el_hud_de_lay(escena):
    assert "error" in esc.enfocar_ventana("LAY — Interfaz")


def test_monitor_vecino():
    import types as t

    esc_mons = lambda: [{"indice": i} for i in (1, 2, 3)]  # noqa: E731
    orig = esc.monitores
    esc.monitores = esc_mons
    try:
        assert esc.monitor_vecino("derecha", desde=1) == 2
        assert esc.monitor_vecino("izquierda", desde=1) == 1  # no da la vuelta
        assert esc.monitor_vecino("derecha", desde=3) == 3
    finally:
        esc.monitores = orig
    del t


def test_workspace_en_paralelo(escena, monkeypatch):
    from lay_core.config import CONFIG

    monkeypatch.setitem(
        CONFIG.workspaces,
        "prueba",
        [
            {"app": "excel", "titulo": "Excel", "monitor": 1, "posicion": "completa"},
            {"app": "noexiste", "titulo": "Nada", "monitor": 2},
        ],
    )
    monkeypatch.setitem(CONFIG.apps, "excel", "start excel")
    monkeypatch.setattr(esc.subprocess, "Popen", lambda *a, **k: None)
    r = esc.aplicar_workspace("prueba")
    assert r["acomodadas"] == 1 and r["total"] == 2 and not r["ok"]
    assert "no configurada" in r["detalle"][1]["error"]

"""Gestos que Robert le enseña a LAY: invariantes a posición/tamaño/mano y distinguibles."""

import pytest

from lay_core import gestos_propios as gp


@pytest.fixture(autouse=True)
def archivo(tmp_path, monkeypatch):
    monkeypatch.setattr(gp, "ARCHIVO", tmp_path / "g.json")
    gp._cache.update(mtime=None, gestos=[])


def pose(dedos, cx=0.5, cy=0.5, s=0.1, lado="Right"):
    """Mano esquemática: muñeca + 5 dedos; cada dedo estirado (1) o doblado (0)."""
    pts = [(cx, cy + s)]
    for i, abierto in enumerate(dedos):
        dx = (i - 2) * s * 0.4 * (-1 if lado == "Left" else 1)
        largo = s * (1.6 if abierto else 0.5)
        for k in range(1, 5):
            pts.append((cx + dx, cy + s - largo * k / 4))
    return pts


def test_misma_pose_en_otro_lugar_y_tamano_y_mano():
    a = gp.vector(pose([1, 1, 0, 0, 1]))
    b = gp.vector(pose([1, 1, 0, 0, 1], cx=0.2, cy=0.7, s=0.05))
    c = gp.vector(pose([1, 1, 0, 0, 1], lado="Left"), "Left")
    assert gp.distancia(a, b) < 0.05 and gp.distancia(a, c) < 0.05


def test_guarda_reconoce_y_distingue():
    rock = [gp.vector(pose([0, 1, 0, 0, 1], s=0.09 + k * 0.002)) for k in range(20)]
    paz = [gp.vector(pose([0, 1, 1, 0, 0], s=0.09 + k * 0.002)) for k in range(20)]
    assert gp.guardar("rock", "abre spotify", rock)["ok"]
    assert gp.guardar("paz", "ctrl+alt+t", paz)["accion"] == {"tipo": "teclas", "valor": "ctrl+alt+t"}
    g, _ = gp.reconocer(gp.vector(pose([0, 1, 0, 0, 1], cx=0.3)))
    assert g["nombre"] == "rock"
    g, _ = gp.reconocer(gp.vector(pose([0, 1, 1, 0, 0], cx=0.7)))
    assert g["nombre"] == "paz"
    g, _ = gp.reconocer(gp.vector(pose([1, 1, 1, 1, 1])))
    assert g is None  # mano abierta: no es ninguno de los dos
    assert [x["nombre"] for x in gp.listar()["gestos"]] == ["rock", "paz"]
    assert gp.borrar("rock")["ok"] and "error" in gp.borrar("rock")


def test_pocas_muestras_pide_repetir():
    assert "error" in gp.guardar("x", "abre spotify", [gp.vector(pose([1, 0, 0, 0, 0]))] * 3)

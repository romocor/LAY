"""El lanzador se relanza bien congelado (LAY.exe -> LAY-cli.exe --rol X) y en desarrollo."""

import sys

import lay


def test_desarrollo_usa_python_y_lay_py():
    cmd = lay.comando_rol("hub")
    assert cmd[0] == sys.executable and cmd[1].endswith("lay.py") and cmd[-2:] == ["--rol", "hub"]


def test_congelado_usa_lay_cli(tmp_path, monkeypatch):
    (tmp_path / "LAY.exe").write_text("")
    (tmp_path / "LAY-cli.exe").write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "LAY.exe"))
    assert lay.comando_rol("voz", "--texto") == [str(tmp_path / "LAY-cli.exe"), "--rol", "voz", "--texto"]


def test_roles_apuntan_a_modulos_que_existen():
    import importlib.util

    for modulo in lay.ROLES.values():
        assert importlib.util.find_spec(modulo) is not None, modulo

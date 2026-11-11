from lay_core.seguridad import ruta_permitida, sensible


@sensible("prueba")
def accion(x):
    return {"ok": True, "x": x}


def test_sensible_sin_confirmar_no_ejecuta():
    r = accion(x=1)
    assert r["requiere_confirmacion"] is True


def test_sensible_confirmado_ejecuta(tmp_path, monkeypatch):
    import lay_core.seguridad as s

    monkeypatch.setattr(s, "AUDIT_LOG", tmp_path / "a.log")
    assert accion(x=2, confirmar=True) == {"ok": True, "x": 2}
    assert (tmp_path / "a.log").read_text().count('"accion": "accion"') == 1


def test_rutas_sistema_bloqueadas():
    assert not ruta_permitida("/etc/passwd")

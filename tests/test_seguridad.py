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
    import platform

    if platform.system() == "Windows":
        assert not ruta_permitida(r"C:\Windows\System32\drivers\etc\hosts")
        assert not ruta_permitida("c:/program files/app/x.exe")  # mayúsculas y barras da igual
        assert ruta_permitida(r"C:\Users\robert\Pictures\obra.jpg")
    else:
        assert not ruta_permitida("/etc/passwd")
        assert ruta_permitida("/home/robert/fotos/obra.jpg")

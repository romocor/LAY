from pathlib import Path

from lay_core import archivos


def test_busqueda_y_mejor_coincidencia(tmp_path, monkeypatch):
    monkeypatch.setattr(archivos, "_everything", lambda: None)
    (tmp_path / "obra").mkdir()
    (tmp_path / "obra" / "presupuesto chancay v2.xlsx").write_text("x")
    (tmp_path / "presupuesto chancay.xlsx").write_text("x")
    (tmp_path / "otro.txt").write_text("x")
    res = archivos.buscar("chancay", carpeta=str(tmp_path))
    assert {r["nombre"] for r in res} == {"presupuesto chancay v2.xlsx", "presupuesto chancay.xlsx"}

    monkeypatch.setattr(archivos.CONFIG, "raices_busqueda", [str(tmp_path)])
    mejor = archivos.mejor_coincidencia("presupuesto chancay")
    assert mejor["nombre"] == "presupuesto chancay.xlsx"  # exacto gana a "v2"


def test_ignora_carpetas_basura(tmp_path, monkeypatch):
    monkeypatch.setattr(archivos, "_everything", lambda: None)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "informe.pdf").write_text("x")
    assert archivos.buscar("informe", carpeta=str(tmp_path)) == []


def test_explorar_carpeta_para_el_holograma(tmp_path):
    from lay_core import archivos

    (tmp_path / "Obra Lima").mkdir()
    (tmp_path / ".oculta").mkdir()
    (tmp_path / "plano.png").write_bytes(b"x")
    (tmp_path / "foto.JPG").write_bytes(b"x")
    (tmp_path / "notas.txt").write_text("x")
    r = archivos.explorar(str(tmp_path))
    assert [c["nombre"] for c in r["carpetas"]] == ["Obra Lima"]
    assert sorted(Path(p).name for p in r["imagenes"]) == ["foto.JPG", "plano.png"]
    assert r["otros"] == 1 and r["padre"]
    assert "error" in archivos.explorar(str(tmp_path / "no-existe"))

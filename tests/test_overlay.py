"""Miniaturas del hub y galería por nombre de carpeta."""

import pytest

pytest.importorskip("PIL")
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from loops import hub  # noqa: E402


def test_miniatura_reduce_y_cachea(tmp_path, monkeypatch):
    import lay_core.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    foto = tmp_path / "obra.jpg"
    Image.new("RGB", (4000, 3000), "gray").save(foto)
    c = TestClient(hub.app)
    r = c.get("/miniatura", params={"ruta": str(foto), "w": 480})
    assert r.status_code == 200 and len(r.content) < foto.stat().st_size / 5
    assert len(list((tmp_path / "cache").glob("*.jpg"))) == 1
    c.get("/miniatura", params={"ruta": str(foto), "w": 480})
    assert len(list((tmp_path / "cache").glob("*.jpg"))) == 1  # segunda vez: de caché


def test_miniatura_rechaza_no_imagen(tmp_path):
    (tmp_path / "x.txt").write_text("hola")
    assert TestClient(hub.app).get("/miniatura", params={"ruta": str(tmp_path / "x.txt")}).status_code == 404


def test_galeria_por_nombre_de_carpeta(tmp_path, monkeypatch):
    import asyncio
    import json

    from lay_core import archivos
    from lay_mcp import server

    (tmp_path / "Fotos obra Chancay").mkdir()
    Image.new("RGB", (10, 10)).save(tmp_path / "Fotos obra Chancay" / "a.jpg")
    (tmp_path / "Chancay docs").mkdir()  # coincide pero sin fotos: no debe elegirse
    monkeypatch.setattr(archivos, "_everything", lambda: None)
    monkeypatch.setattr(archivos.CONFIG, "raices_busqueda", [str(tmp_path)])
    publicado = {}
    monkeypatch.setattr(server.bus, "publicar", lambda tipo, **d: publicado.update(d) or {"ok": True})
    res = asyncio.run(server.mcp.call_tool("overlay_mostrar_imagenes", {"consulta": "chancay"}))
    bloques = res[0] if isinstance(res, tuple) else res
    r = json.loads(bloques[0].text)
    assert r["imagenes"] == 1 and r["carpeta"].endswith("Fotos obra Chancay")

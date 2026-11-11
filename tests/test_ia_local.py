"""Instalador de IA local: recomendación por hardware y flujo completo (simulado)."""

import json

import pytest

from lay_core import ia_local


@pytest.mark.parametrize(
    "ram,vram,esperado",
    [
        (4, 0, {"qwen2.5:1.5b"}),
        (8, 0, {"qwen2.5:3b"}),
        (8, 6, {"qwen2.5:3b", "qwen2.5:7b"}),
        (16, 4, {"qwen2.5:3b", "qwen2.5:7b"}),  # laptop de Robert: 16 GB + GTX 1650
    ],
)
def test_recomendacion_por_hardware(ram, vram, esperado):
    r = ia_local.recomendar({"ram_gb": ram, "vram_gb": vram})
    assert set(r["descargar"]) == esperado and r["descarga_gb"] > 0 and r["motivo"]


def test_preparar_instala_arranca_y_descarga(monkeypatch, tmp_path):
    import lay_core.config as cfg

    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "lay.json")
    pasos, estado = [], {"instalado": False, "modelos": []}
    monkeypatch.setattr(ia_local, "hardware", lambda: {"ram_gb": 8, "vram_gb": 0, "disco_libre_gb": 50})
    monkeypatch.setattr(ia_local, "ollama_exe", lambda: "ollama.exe" if estado["instalado"] else None)
    monkeypatch.setattr(ia_local, "activo", lambda: estado["instalado"])
    monkeypatch.setattr(
        ia_local, "instalar_ollama", lambda p: (pasos.append("instalar"), estado.update(instalado=True))
    )
    monkeypatch.setattr(ia_local, "iniciar", lambda: True)
    monkeypatch.setattr(ia_local, "modelos_instalados", lambda: list(estado["modelos"]))
    monkeypatch.setattr(ia_local, "descargar_modelo", lambda m, p: (pasos.append(m), estado["modelos"].append(m)))
    r = ia_local.preparar()
    assert pasos == ["instalar", "qwen2.5:3b"] and r["ok"]
    assert json.loads((tmp_path / "lay.json").read_text())["ia"]["modelos"]["ollama"]["rapido"] == "qwen2.5:3b"
    pasos.clear()
    ia_local.preparar()  # idempotente: ya está todo
    assert pasos == []
    cfg.recargar()


def test_sin_espacio_avisa_antes_de_descargar(monkeypatch):
    monkeypatch.setattr(ia_local, "hardware", lambda: {"ram_gb": 16, "vram_gb": 0, "disco_libre_gb": 3})
    with pytest.raises(RuntimeError, match="Falta espacio"):
        ia_local.preparar()


def test_descarga_de_modelo_reporta_progreso(monkeypatch):
    lineas = [
        json.dumps(x)
        for x in (
            {"status": "pulling manifest"},
            {"status": "downloading", "total": 2_000_000_000, "completed": 500_000_000},
            {"status": "downloading", "total": 2_000_000_000, "completed": 2_000_000_000},
            {"status": "success"},
        )
    ]

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self):
            return iter(lineas)

    monkeypatch.setattr(ia_local.httpx, "stream", lambda *a, **k: Resp())
    vistos = []
    ia_local.descargar_modelo("qwen2.5:3b", lambda e, pct, t: vistos.append(round(pct)))
    assert 25 in vistos and 100 in vistos


def test_error_de_ollama_se_explica(monkeypatch):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self):
            return iter([json.dumps({"error": "pull model manifest: file does not exist"})])

    monkeypatch.setattr(ia_local.httpx, "stream", lambda *a, **k: Resp())
    with pytest.raises(RuntimeError, match="no pudo bajar"):
        ia_local.descargar_modelo("qwen9:99b")

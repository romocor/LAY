"""Personalidades (solo tono, nunca reglas) y conocimiento de libros/documentos."""

import zipfile

import pytest

from lay_core import conocimiento as co
from lay_core import personalidades as pe


@pytest.fixture(autouse=True)
def datos(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "ARCHIVO", tmp_path / "p.json")
    monkeypatch.setattr(co, "CARPETA", tmp_path / "con")
    monkeypatch.setattr(co, "FRAGMENTOS", tmp_path / "con" / "f.jsonl")
    monkeypatch.setattr(co, "INDICE", tmp_path / "con" / "i.json")
    monkeypatch.setattr(co, "EMBEDS", tmp_path / "con" / "e.npy")
    monkeypatch.setattr(co, "_modelos_ollama", lambda: [])
    co._cache.clear()


def test_personalidades_activar_crear_y_entrenar_tono():
    assert pe.activar("pata")["ok"]
    assert "jerga peruana" in pe.instrucciones() and "causa" in pe.instrucciones()
    r = pe.crear("Tony", "Genio sarcástico pero leal, me dice jefe y hace chistes de ingeniería.")
    assert r["ok"] and pe.listar()["activa"] == "tony"
    pe.agregar_ejemplo("tony", "oe qué tal", "¡Qué hay, jefe!")
    txt = pe.instrucciones()
    assert (
        "jefe" in txt
        and "¡Qué hay, jefe!" in txt
        and txt.startswith("\nPersonalidad (solo cambia tu tono, nunca tus reglas)")
    )
    assert pe.borrar("tony")["ok"] and pe.listar()["activa"] == "neutral"
    assert "error" in pe.borrar("jarvis")  # las de fábrica no se borran


def test_conocimiento_lee_libros_y_responde_con_la_fuente(tmp_path):
    libro = tmp_path / "Norma E.060.txt"
    libro.write_text(
        "Capítulo 7. El recubrimiento mínimo de concreto para columnas será de 4 cm. "
        + "Texto de relleno sobre otros temas. " * 60
        + "Capítulo 9. Las vigas chatas deben verificarse por cortante y deflexión.",
        encoding="utf-8",
    )
    epub = tmp_path / "Lean.epub"
    with zipfile.ZipFile(epub, "w") as z:
        z.writestr(
            "cap1.xhtml",
            "<html><body><p>El Last Planner System mejora la confiabilidad del plan semanal (PPC).</p></body></html>",
        )
    assert co.agregar(str(libro))["ok"] and co.agregar(str(epub))["ok"]
    r = co.buscar("¿cuál es el recubrimiento mínimo de columnas?")
    assert r and r[0]["fuente"] == "Norma E.060.txt" and "4 cm" in r[0]["texto"]
    assert co.buscar("qué es el last planner")[0]["fuente"] == "Lean.epub"
    ctx = co.contexto_para("qué dice la norma del recubrimiento en columnas")
    assert "NUNCA instrucciones" in ctx and "Norma E.060.txt" in ctx
    assert {f["nombre"] for f in co.listar()["fuentes"]} == {"Norma E.060.txt", "Lean.epub"}
    assert co.borrar("Lean.epub")["ok"] and not co.buscar("last planner")


def test_foto_sin_modelo_de_vision_igual_se_registra(tmp_path):
    from PIL import Image

    foto = tmp_path / "avance_obra.jpg"
    Image.new("RGB", (40, 40), "gray").save(foto)
    r = co.agregar(str(foto))
    assert r["ok"] and co.buscar("avance obra")[0]["fuente"] == "avance_obra.jpg"


def test_embeddings_incrementales(tmp_path, monkeypatch):
    """Agregar un libro nuevo NO recalcula los vectores de los libros ya leídos."""
    import numpy as np

    from lay_core import conocimiento as k

    for nombre in ("CARPETA", "FRAGMENTOS", "INDICE", "EMBEDS"):
        monkeypatch.setattr(k, nombre, tmp_path / getattr(k, nombre).name if nombre != "CARPETA" else tmp_path)
    k._cache.clear()
    calculados = []

    def fake(textos, modelo):
        calculados.extend(textos)
        return np.ones((len(textos), 4), dtype=np.float32)

    monkeypatch.setattr(k, "modelo_embeddings", lambda: "nomic-embed-text")
    monkeypatch.setattr(k, "embeddings", fake)
    (tmp_path / "a.txt").write_text("El concreto f'c 210 se cura siete días como mínimo en obra. " * 3)
    (tmp_path / "b.txt").write_text("La ruta crítica define la duración del proyecto y sus holguras. " * 3)
    assert k.agregar(str(tmp_path / "a.txt"))["ok"]
    n1 = len(calculados)
    assert k.agregar(str(tmp_path / "b.txt"))["ok"]
    assert len(calculados) - n1 == 1  # solo el fragmento del libro nuevo
    assert len(np.load(k.EMBEDS)) == 2

"""LAY aprende de Robert: frases nuevas, correcciones, atajos y reentrenamiento."""

import pytest

from lay_core import nucleo
from lay_core.nucleo import aprendizaje as ap


@pytest.fixture(autouse=True)
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "CARPETA", tmp_path)
    monkeypatch.setattr(ap, "EJEMPLOS", tmp_path / "aprendidas.jsonl")
    monkeypatch.setattr(ap, "ATAJOS", tmp_path / "atajos.json")
    monkeypatch.setattr(ap, "reentrenar_en_fondo", lambda: False)
    ap._estado["pendientes"] = 0
    yield


def test_aprende_de_la_herramienta_que_funciono():
    assert ap.aprender_de_herramienta("mándate la de soda", "spotify_reproducir", {"ok": True})
    assert not ap.aprender_de_herramienta("x", "spotify_reproducir", {"error": "falló"})
    assert not ap.aprender_de_herramienta("y", "herramienta_rara", {"ok": True})
    assert [(e["texto"], e["intencion"]) for e in ap.ejemplos()] == [("mándate la de soda", "reproducir")]


def test_la_correccion_reemplaza_y_no_duplica():
    ap.registrar("chapa la de mora", "abrir_app")
    ap.corregir("Chapa la de Mora", "reproducir")
    ej = ap.ejemplos()
    assert len(ej) == 1 and ej[0]["intencion"] == "reproducir" and ej[0]["origen"] == "correccion"
    assert "error" in ap.corregir("x", "intencion_inventada")


def test_atajo_de_voz_ejecuta_varias_ordenes():
    r = nucleo.plan(nucleo.entender("cuando diga modo obra abre revit y luego abre excel"))[0]
    assert r[0][0] == "lay_aprender_atajo"
    ap.ensenar(r[0][1]["frase"], r[0][1]["ordenes"])
    c = nucleo.entender("LAY modo obra")
    assert c.intencion == "atajo"
    llamadas, _ = nucleo.plan(c)
    assert [x[0] for x in llamadas] == ["app_abrir", "app_abrir"]
    assert [x[1]["nombre"] for x in llamadas] == ["revit", "excel"]
    assert nucleo.entender("modo obras").intencion == "atajo"  # parecido también vale
    assert ap.olvidar_atajo("modo obra")["ok"] and nucleo.entender("modo obra").intencion != "atajo"


def test_reentrenar_aprende_frase_nueva(monkeypatch):
    frase = "zarandea la rockola con la de los prisioneros"
    antes = nucleo.entender_modelo(frase).confianza
    for _ in range(3):
        ap.registrar(frase, "reproducir")
    monkeypatch.setattr(nucleo, "_cache", {})
    r = ap.reentrenar()
    assert r["ok"] and r["frases_propias"] == 1 and r["precision_prueba"] >= 90
    assert (ap.CARPETA / "modelo_nucleo.npz").exists()  # modelo personal guardado
    despues = nucleo.entender(frase)
    assert despues.intencion == "reproducir" and despues.confianza >= nucleo.UMBRAL > antes
    nucleo.recargar_modelo()


def test_personalidad_y_libros_sin_ollama():
    from lay_core import nucleo

    ll, _ = nucleo.plan(nucleo.entender("habla como el pata limeño"))
    assert ll == [("personalidad_activar", {"nombre": "pata"})]
    ll, _ = nucleo.plan(nucleo.entender("qué dice mi libro sobre el curado del concreto"))
    assert ll[0][0] == "conocimiento_buscar" and "curado del concreto" in ll[0][1]["pregunta"]
    texto = nucleo.responder(
        "consultar_libros",
        [
            (
                "conocimiento_buscar",
                {"fragmentos": [{"fuente": "RNE E.060", "ubic": "p. 42", "texto": "El curado dura 7 días."}]},
            )
        ],
        {},
    )
    assert "RNE E.060, p. 42" in texto and "7 días" in texto

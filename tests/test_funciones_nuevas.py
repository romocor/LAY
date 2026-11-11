"""Recordatorios, memoria, información, navegador y Windows (sin red ni Windows reales)."""

from datetime import datetime

import httpx
import pytest

from lay_core import informacion, memoria, navegador, recordatorios, router, windows

AHORA = datetime(2026, 11, 10, 16, 0)  # martes 4:00 pm


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("en 10 minutos", datetime(2026, 11, 10, 16, 10)),
        ("en una hora y media", datetime(2026, 11, 10, 17, 30)),
        ("en 2 horas 15 minutos", datetime(2026, 11, 10, 18, 15)),
        ("dentro de 30 segundos", datetime(2026, 11, 10, 16, 0, 30)),
        ("a las 18:30", datetime(2026, 11, 10, 18, 30)),
        ("a las 5", datetime(2026, 11, 10, 17, 0)),  # dicho a las 4 pm: las 5 de la tarde, no de la madrugada
        ("a las 3 de la tarde", datetime(2026, 11, 11, 15, 0)),  # ya pasó hoy: mañana
        ("mañana a las 9", datetime(2026, 11, 11, 9, 0)),
        ("mañana", datetime(2026, 11, 11, 9, 0)),
        ("el viernes a las 8 de la noche", datetime(2026, 11, 13, 20, 0)),
        ("el martes a las 10", datetime(2026, 11, 17, 10, 0)),  # hoy es martes: el próximo
        ("2026-11-20 10:00", datetime(2026, 11, 20, 10, 0)),
    ],
)
def test_interpretar_horas_en_espanol(texto, esperado):
    assert recordatorios.interpretar(texto, AHORA) == esperado


def test_hora_incomprensible():
    with pytest.raises(ValueError):
        recordatorios.interpretar("cuando pueda", AHORA)


def test_recordatorios_se_disparan_y_repiten(tmp_path, monkeypatch):
    monkeypatch.setattr(recordatorios, "ARCHIVO", tmp_path / "r.json")
    recordatorios.crear("Tomar agua", "en 1 minuto", repetir="diario")
    recordatorios.crear("Llamar a obra", "mañana a las 9")
    assert recordatorios.vencidos(datetime.now()) == []
    from datetime import timedelta

    toca = recordatorios.vencidos(datetime.now() + timedelta(minutes=2))
    assert [r["mensaje"] for r in toca] == ["Tomar agua"]
    pendientes = {r["mensaje"] for r in recordatorios.listar()}
    assert pendientes == {"Tomar agua", "Llamar a obra"}  # el diario se reprogramó
    assert recordatorios.borrar("obra")["borrados"] == 1


def test_memoria_guarda_busca_y_rechaza_secretos(tmp_path, monkeypatch):
    monkeypatch.setattr(memoria, "ARCHIVO", tmp_path / "m.json")
    assert memoria.guardar("Mi jefe se llama Carlos Mendoza")["ok"]
    assert memoria.guardar("La obra de Chancay entrega el 15 de diciembre")["ok"]
    assert memoria.guardar("mi jefe se llama Carlos Mendoza Ríos")["actualizado"]  # no duplica
    for secreto in ["mi contraseña del banco es 1234", "tarjeta 4111 1111 1111 1111", "token sk-ant-abc123"]:
        assert "error" in memoria.guardar(secreto)
    assert memoria.buscar("¿cómo se llama mi jefe?")[0]["dato"].startswith("mi jefe")
    assert "Chancay" in memoria.contexto_para("cuándo entrega chancay")
    assert memoria.contexto_para("receta de ceviche") == ""
    assert len(memoria.listar()) == 2


def test_clima_con_open_meteo(monkeypatch):
    def falso(url, params=None, timeout=None, **k):
        if "geocoding" in url:
            return httpx.Response(
                200,
                json={"results": [{"name": "Lima", "country": "Perú", "latitude": -12, "longitude": -77}]},
                request=httpx.Request("GET", url),
            )
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "current": {
                    "temperature_2m": 19.6,
                    "apparent_temperature": 20.2,
                    "relative_humidity_2m": 80,
                    "wind_speed_10m": 12.4,
                    "weather_code": 3,
                },
                "daily": {
                    "time": ["2026-11-10"],
                    "weather_code": [51],
                    "temperature_2m_max": [22.1],
                    "temperature_2m_min": [17.8],
                    "precipitation_probability_max": [20],
                },
            },
        )

    monkeypatch.setattr(informacion.httpx, "get", falso)
    c = informacion.clima()
    assert c["lugar"] == "Lima, Perú" and c["ahora"]["temperatura"] == 20 and c["ahora"]["cielo"] == "nublado"
    assert c["pronostico"][0]["cielo"] == "llovizna ligera"


def test_navegador_destinos_y_riesgo():
    assert navegador.a_url("youtube.com") == "https://youtube.com"
    assert navegador.a_url("https://pucp.blackboard.com/x") == "https://pucp.blackboard.com/x"
    assert navegador.a_url("precio del dólar hoy").startswith("https://www.google.com/search?q=precio")
    for boton in ["Confirmar compra", "Pagar ahora", "Eliminar cuenta", "Enviar"]:
        assert navegador.RIESGO.search(boton)
    for boton in ["Buscar", "Siguiente", "Ver más", "Iniciar sesión"]:
        assert not navegador.RIESGO.search(boton)


def test_navegador_elegir(monkeypatch):
    monkeypatch.setattr(navegador, "rutas_navegadores", lambda: {"brave": "b.exe", "edge": "e.exe"})
    assert navegador.elegir_navegador(None)[0] == "brave"
    assert navegador.elegir_navegador("edge")[0] == "edge"
    with pytest.raises(RuntimeError, match="no está instalado"):
        navegador.elegir_navegador("chrome")


def test_coincidencia_no_confunde_guardar_con_no_guardar():
    assert windows.coincide("Guardar", "Guardar") > windows.coincide("Guardar", "No guardar")
    assert windows.coincide("Save", "Don't Save") < 0.55
    assert windows.coincide("revit", "Revit 2025") >= 0.9


def test_buscar_app_por_nombre():
    apps = [
        {"nombre": "Revit 2025", "id": "a"},
        {"nombre": "Microsoft Excel", "id": "b"},
        {"nombre": "Calculadora", "id": "c"},
        {"nombre": "Spotify", "id": "d"},
    ]
    assert windows.buscar_app("revit", apps)["id"] == "a"
    assert windows.buscar_app("excel", apps)["id"] == "b"
    assert windows.buscar_app("calculadora", apps)["id"] == "c"
    assert windows.buscar_app("photoshop", apps) is None


def test_ajustes_de_windows(monkeypatch):
    abiertos = []
    monkeypatch.setattr(windows.subprocess, "Popen", lambda cmd, **k: abiertos.append(cmd[-1]))
    windows.abrir_ajuste("wifi")
    windows.abrir_ajuste("el modo oscuro")
    windows.abrir_ajuste("bluetoth")  # con error de tipeo
    assert abiertos == ["ms-settings:network-wifi", "ms-settings:colors", "ms-settings:bluetooth"]


def test_energia_exige_confirmacion(monkeypatch, tmp_path):
    import lay_core.seguridad as s

    monkeypatch.setattr(s, "AUDIT_LOG", tmp_path / "a.log")
    llamados = []
    monkeypatch.setattr(windows.subprocess, "Popen", lambda cmd, **k: llamados.append(cmd))
    assert windows.energia(accion="apagar")["requiere_confirmacion"] and llamados == []
    assert windows.energia(accion="apagar", confirmar=True)["ok"] and "/s" in llamados[0]


@pytest.mark.parametrize(
    "frase,tema",
    [
        ("abre youtube en brave", "navegador"),
        ("haz clic en iniciar sesión", "navegador"),
        ("sube el volumen", "multimedia"),
        ("pon la siguiente canción", "multimedia"),
        ("¿va a llover mañana?", "informacion"),
        ("recuérdame llamar a Pérez a las 5", "recordatorios"),
        ("abre la configuración de bluetooth", "windows_ui"),
    ],
)
def test_router_temas_nuevos(frase, tema):
    assert tema in router.temas(frase)

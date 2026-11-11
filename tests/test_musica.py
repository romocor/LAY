"""Poner LA canción pedida en Spotify/YouTube (no solo play/pausa)."""

import pytest

from lay_core import musica, nucleo


def test_reconoce_lo_que_suena():
    assert musica.suena("Bad Bunny - NADIE SABE", "nadie sabe de bad bunny")
    assert not musica.suena("Spotify Premium", "nadie sabe")  # en pausa
    assert not musica.suena("Mora - Volando", "despacito")


def test_busca_id_en_internet(monkeypatch):
    from lay_core import informacion

    monkeypatch.setattr(
        informacion,
        "buscar_web",
        lambda q, maximo=8: {
            "resultados": [{"url": "https://open.spotify.com/intl-es/track/4NiyMmBdlVHpZWScgdBvnt?si=x"}]
        },
    )
    assert musica.buscar_id_spotify("nadie sabe") == ("track", "4NiyMmBdlVHpZWScgdBvnt")


def test_reproduce_y_si_no_suena_pulsa_play(monkeypatch):
    abiertos, clics = [], []
    titulos = iter(["Spotify Free", "Bad Bunny - NADIE SABE", "Bad Bunny - NADIE SABE"])
    monkeypatch.setattr(musica, "ES_WINDOWS", True)
    monkeypatch.setattr(musica, "buscar_id_spotify", lambda q, t=None: ("track", "4NiyMmBdlVHpZWScgdBvnt"))
    monkeypatch.setattr(musica, "_abrir_uri", abiertos.append)
    monkeypatch.setattr(musica, "titulo_spotify", lambda: next(titulos))
    monkeypatch.setattr(musica, "_clic_reproducir", lambda: clics.append(1) or True)
    monkeypatch.setattr(musica.time, "sleep", lambda s: None)
    r = musica.spotify_reproducir("nadie sabe")
    assert abiertos == ["spotify:track:4NiyMmBdlVHpZWScgdBvnt#0:00"]
    assert r["ok"] and r["sonando"] == "Bad Bunny - NADIE SABE" and clics == [1]


def test_sin_id_abre_la_busqueda_de_spotify(monkeypatch):
    abiertos = []
    monkeypatch.setattr(musica, "ES_WINDOWS", True)
    monkeypatch.setattr(musica, "buscar_id_spotify", lambda q, t=None: None)
    monkeypatch.setattr(musica, "_abrir_uri", abiertos.append)
    monkeypatch.setattr(musica, "titulo_spotify", lambda: "Spotify Free")
    monkeypatch.setattr(musica, "_clic_reproducir", lambda: False)
    monkeypatch.setattr(musica.time, "sleep", lambda s: None)
    r = musica.spotify_reproducir("rock peruano")
    assert abiertos == ["spotify:search:rock%20peruano"] and "error" in r


def test_youtube_abre_el_primer_video(monkeypatch):
    from lay_core import navegador

    monkeypatch.setattr(musica, "primer_video_youtube", lambda q: "dQw4w9WgXcQ")
    monkeypatch.setattr(navegador, "abrir", lambda d, n=None: {"ok": True, "url": d, "navegador": "brave"})
    r = musica.youtube_reproducir("lofi")
    assert r["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ" and r["video"]


@pytest.mark.parametrize(
    "frase,herramienta,args",
    [
        ("pon nadie sabe de bad bunny", "spotify_reproducir", {"consulta": "nadie sabe de bad bunny"}),
        ("reproduce despacito en spotify", "spotify_reproducir", {"consulta": "despacito"}),
        ("abre spotify y pon bad bunny", "spotify_reproducir", {"consulta": "bad bunny"}),
        ("pon el video de bohemian rhapsody en youtube", "youtube_reproducir", {"consulta": "bohemian rhapsody"}),
        ("abre youtube y pon lofi", "youtube_reproducir", {"consulta": "lofi"}),
        ("busca facturas en outlook", "app_buscar", {"app": "outlook", "consulta": "facturas"}),
        ("haz clic en guardar", "ui_click", {"ventana": "activa", "objetivo": "guardar"}),
        ("pausa la música", "multimedia", {"accion": "pausa"}),
    ],
)
def test_nucleo_entiende_ordenes_de_musica_y_apps(frase, herramienta, args):
    llamadas, _ = nucleo.plan(nucleo.entender(frase))
    assert llamadas[0][0] == herramienta
    for k, v in args.items():
        assert llamadas[0][1][k] == v

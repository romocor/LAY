"""Gestos con landmarks sintéticos (sin cámara)."""

import types

import pytest

gestos = pytest.importorskip("loops.gestos")


@pytest.fixture(autouse=True)
def sin_mouse_real(monkeypatch):
    import sys

    fake = types.SimpleNamespace(
        size=lambda: (1920, 1080), moveTo=lambda *a, **k: None, mouseDown=lambda **k: None, mouseUp=lambda **k: None
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake)


class P:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


def mano(cx=0.5, cy=0.5, pinch=False, abierta=True):
    """Mano derecha vertical; tamaño muñeca->base medio = 0.2."""
    lm = [P(cx, cy + 0.1) for _ in range(21)]
    lm[0] = P(cx, cy + 0.1)  # muñeca
    for i, dx in zip((5, 9, 13, 17), (-0.04, 0, 0.03, 0.06)):
        lm[i] = P(cx + dx, cy - 0.1)  # bases
    for i, dx in zip((8, 12, 16, 20), (-0.04, 0, 0.03, 0.06)):
        lm[i] = P(cx + dx, cy - (0.3 if abierta else -0.05))
    lm[4] = P(lm[8].x + (0.01 if pinch else 0.18), lm[8].y + (0.01 if pinch else 0.1))
    return lm


def resultado(*manos):
    r = types.SimpleNamespace(multi_hand_landmarks=[], multi_handedness=[])
    for lado, lm in manos:
        r.multi_hand_landmarks.append(types.SimpleNamespace(landmark=lm))
        r.multi_handedness.append(types.SimpleNamespace(classification=[types.SimpleNamespace(label=lado)]))
    return r


def correr(frames):
    eventos = []
    c = gestos.Clasificador(eventos.append)
    for t, res in frames:
        c.procesar(res, t)
    return [e.get("gesto") for e in eventos if e["tipo"] == "gesto"], c


def test_tap():
    g, _ = correr(
        [
            (0, resultado(("Right", mano()))),
            (0.05, resultado(("Right", mano(pinch=True)))),
            (0.2, resultado(("Right", mano()))),
        ]
    )
    assert "pinch_inicio" in g and "tap" in g


def test_arrastre_no_es_tap():
    frames = [(0, resultado(("Right", mano()))), (0.05, resultado(("Right", mano(pinch=True))))]
    frames += [(0.1 + i * 0.05, resultado(("Right", mano(cx=0.5 - i * 0.03, pinch=True)))) for i in range(8)]
    frames += [(0.6, resultado(("Right", mano(cx=0.26))))]
    g, _ = correr(frames)
    assert "arrastrar" in g and "pinch_fin" in g and "tap" not in g


def test_palma_cambia_modo():
    frames = [(t / 10, resultado(("Right", mano()))) for t in range(0, 20)]
    g, c = correr(frames)
    assert "modo" in g and c.modo_mouse is True


def test_dos_manos_escala():
    frames = [(0, resultado(("Left", mano(0.3, pinch=True)), ("Right", mano(0.7, pinch=True))))]
    frames += [
        (0.1 * i, resultado(("Left", mano(0.3 - 0.02 * i, pinch=True)), ("Right", mano(0.7 + 0.02 * i, pinch=True))))
        for i in range(1, 5)
    ]
    g, _ = correr(frames)
    assert "escalar" in g


def mano_dos_dedos(cx=0.5, cy=0.5):
    lm = mano(cx, cy)
    for i in (16, 20):  # anular y meñique doblados
        lm[i] = P(lm[i].x, cy + 0.05)
    return lm


def mano_puno(cx=0.5, cy=0.5):
    return mano(cx, cy, abierta=False)


def test_scroll_con_dos_dedos():
    frames = [(i * 0.05, resultado(("Right", mano_dos_dedos(cy=0.4 + i * 0.02)))) for i in range(12)]
    eventos = []
    c = gestos.Clasificador(eventos.append)
    for t, r in frames:
        c.procesar(r, t)
    scroll = [e for e in eventos if e.get("gesto") == "scroll"]
    assert scroll and all(e["pasos"] > 0 for e in scroll)  # mano bajando = pasos positivos


def test_puno_corto_calla_y_largo_pausa():
    g, c = correr([(i * 0.1, resultado(("Right", mano_puno()))) for i in range(10)])
    assert "puno" in g and "pausa" not in g  # 0,9 s: solo callar
    g, c = correr([(i * 0.1, resultado(("Right", mano_puno()))) for i in range(25)])
    assert g.count("puno") == 1 and "pausa" in g and c.pausado


def test_one_euro_quieto_suave_rapido_sin_retraso():
    f = gestos.OneEuro()
    import random

    random.seed(1)
    quieto = [f(0.5 + random.uniform(-0.004, 0.004), i / 30) for i in range(90)]
    assert max(quieto[45:]) - min(quieto[45:]) < 0.004  # temblor típico de MediaPipe: < la mitad
    f2 = gestos.OneEuro()
    for i in range(10):
        f2(0.2, i / 30)
    v = [f2(0.2 + 0.05 * i, (10 + i) / 30) for i in range(1, 11)]
    assert 0.2 + 0.05 * 10 - v[-1] < 0.02  # movimiento rápido: lo sigue de cerca


def test_calibracion():
    u = gestos.umbrales_desde_muestras([0.9, 1.0, 1.1], [0.05, 0.08, 0.1])
    assert 0.1 < u["pinch_on"] < u["pinch_off"] < 0.9
    with pytest.raises(ValueError):
        gestos.umbrales_desde_muestras([0.3], [0.25])


def test_mouse_usa_todo_el_escritorio(monkeypatch):
    import sys

    movs = []
    monkeypatch.setitem(sys.modules, "pyautogui", types.SimpleNamespace(moveTo=lambda x, y, **k: movs.append((x, y))))
    monkeypatch.setattr(gestos.Clasificador, "_escritorio", (-1920, 0, 1920 + 2560 + 1920, 1440))
    c = gestos.Clasificador(lambda e: None)
    c._mouse_mover((0.86, 0.5))  # mano a la derecha del cuadro -> monitor derecho
    assert movs[-1][0] > 2560
    c._mouse_mover((0.861, 0.5))  # temblor mínimo: zona muerta, no se mueve
    assert len(movs) == 1
    c._mouse_mover((0.14, 0.5))
    assert movs[-1][0] == -1920  # borde izquierdo del monitor izquierdo (coordenada negativa)


def test_swipe_hacia_arriba_lanza_al_monitor_de_arriba():
    eventos = []
    c = gestos.Clasificador(eventos.append)
    for i in range(8):
        c.procesar(resultado(("Right", mano(cy=0.8 - i * 0.09))), i / 30)
    lanzar = [e for e in eventos if e.get("gesto") == "lanzar"]
    assert lanzar and lanzar[0]["direccion"] == "arriba"

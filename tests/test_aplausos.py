"""Detector de palmadas con audio sintético: palmadas reales vs voz, música y golpes sueltos."""

import math
import random
import struct

from loops.aplausos import BLOQUE, TASA, DetectorPalmadas


def pcm(muestras):
    return struct.pack(f"<{len(muestras)}h", *[max(-32767, min(32767, int(m))) for m in muestras])


def silencio(s, ruido=40):
    return [random.gauss(0, ruido) for _ in range(int(s * TASA))]


def palmada(amp=14000):
    """Ruido blanco con caída exponencial (~25 ms): así suena una palmada."""
    return [random.gauss(0, amp) * math.exp(-i / (0.012 * TASA)) for i in range(int(0.12 * TASA))]


def vocal(s=0.8, f0=140, amp=6000):
    """Voz: armónicos con envolvente suave (ataque ~60 ms)."""
    out = []
    for i in range(int(s * TASA)):
        t = i / TASA
        env = min(1, t / 0.06) * min(1, (s - t) / 0.08)
        out.append(env * amp * sum(math.sin(2 * math.pi * f0 * k * t) / k for k in (1, 2, 3)))
    return out


def correr(audio, sens=0.6):
    d = DetectorPalmadas(sens)
    eventos = []
    for i in range(0, len(audio) - BLOQUE, BLOQUE):
        r = d.alimentar(pcm(audio[i : i + BLOQUE]))
        if r:
            eventos.append(r)
    return eventos


def test_doble_palmada():
    random.seed(1)
    assert correr(silencio(0.5) + palmada() + silencio(0.25) + palmada() + silencio(1.2)) == [2]


def test_triple_palmada():
    random.seed(2)
    a = silencio(0.5)
    for _ in range(3):
        a += palmada() + silencio(0.22)
    assert correr(a + silencio(1.2)) == [3]


def test_una_sola_palmada_no_hace_nada():
    random.seed(3)
    assert correr(silencio(0.5) + palmada() + silencio(1.5)) == []


def test_voz_no_dispara():
    random.seed(4)
    a = silencio(0.3)
    for f in (120, 180, 150, 210, 130):
        a += vocal(0.35, f) + silencio(0.12)
    assert correr(a + silencio(1)) == []


def test_palmadas_muy_separadas_no_cuentan():
    random.seed(5)
    assert correr(silencio(0.4) + palmada() + silencio(1.1) + palmada() + silencio(1.2)) == []


def test_palmadas_suaves_segun_sensibilidad():
    random.seed(6)
    suave = silencio(0.5) + palmada(2500) + silencio(0.25) + palmada(2500) + silencio(1.2)
    assert correr(suave, sens=0.2) == []  # estricto: ignora palmadas lejanas
    random.seed(6)
    assert correr(suave, sens=0.9) == [2]  # sensible: las toma


def test_no_repite_en_rafaga():
    random.seed(7)
    doble = palmada() + silencio(0.25) + palmada() + silencio(0.9)
    assert correr(silencio(0.4) + doble + doble + silencio(1)) == [2]  # cooldown de 2,5 s


def test_bombo_de_musica_no_dispara():
    """Bombo: grave y tonal (pocos cruces por cero) aunque tenga ataque fuerte."""
    random.seed(8)

    def bombo():
        return [
            14000 * math.sin(2 * math.pi * 60 * i / TASA) * math.exp(-i / (0.03 * TASA))
            for i in range(int(0.15 * TASA))
        ]

    a = silencio(0.4)
    for _ in range(4):
        a += bombo() + silencio(0.3)
    assert correr(a + silencio(1)) == []

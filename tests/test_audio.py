import math
import struct

from loops import audio
from loops.voz import quitar_wake


def tono(amplitud: int, bloques: int = 1) -> list[bytes]:
    n = audio.BLOQUE
    b = struct.pack(f"<{n}h", *[int(amplitud * math.sin(2 * math.pi * 220 * i / audio.TASA)) for i in range(n)])
    return [b] * bloques


def vosk(texto, conf=0.95):
    return {"text": texto, "result": [{"word": w, "conf": conf} for w in texto.split()]}


def test_interpretar_wake_y_callar():
    assert audio.interpretar(vosk("ley"), 0.75).tipo == "wake"
    assert audio.interpretar(vosk("oye ley"), 0.75).tipo == "wake"
    assert audio.interpretar(vosk("ley para"), 0.75).tipo == "callar"
    assert audio.interpretar(vosk("ley [unk]"), 0.75).tipo == "wake"  # "LAY abre Spotify" de un tirón
    assert audio.interpretar(vosk("[unk] ley"), 0.75) is None  # "la ley..."
    assert audio.interpretar(vosk("[unk]"), 0.75) is None
    assert audio.interpretar(vosk("ley", conf=0.5), 0.75) is None  # poca confianza = no se activa


def test_segmentador_graba_frase_con_preroll():
    seg = audio.Segmentador(pre_roll_s=0.3, silencio_fin_s=0.3)
    for b in tono(50, 30):  # ruido de fondo: aprende el piso
        seg.reposo(b)
    for b in tono(4000, 5):  # "LAY" ya dicho antes de la detección -> queda en el pre-roll
        seg.reposo(b)
    pcm = seg.grabar(iter(tono(4000, 20) + tono(50, 20)))
    assert pcm is not None
    duracion_s = len(pcm) / 2 / audio.TASA
    assert 0.9 < duracion_s < 1.6  # pre-roll + 0,6 s de voz + 0,3 s de silencio final


def test_segmentador_none_si_nadie_habla():
    seg = audio.Segmentador(pre_roll_s=0.3)
    for b in tono(50, 20):
        seg.reposo(b)
    assert seg.grabar(iter(tono(50, 100)), esperar_voz_s=0) is None


def test_quitar_wake():
    assert quitar_wake("Ley abre Spotify") == "abre Spotify"
    assert quitar_wake("oye lay, ¿qué hora es?") == "¿qué hora es?"
    assert quitar_wake("la ley de contrataciones dice") is None
    assert quitar_wake("según la ley 30225") is None
    assert quitar_wake("hola Lay") == ""

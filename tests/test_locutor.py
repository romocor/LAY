import threading
import time

from loops.locutor import Fraseador, Locutor


def test_fraseador_primera_frase_corta_y_resto_agrupado():
    out = []
    f = Fraseador(out.append)
    for trozo in ["Abriendo Ex", "cel. Listo, ", "lo puse en el monitor 2. También ", "abrí tu correo.", " Algo más"]:
        f.agregar(trozo)
    f.cerrar()
    assert out[0] == "Abriendo Excel."  # sale apenas llega el punto: menor latencia
    assert out[-1] == "Algo más"
    assert "".join(out).replace(" ", "") == "AbriendoExcel.Listo,lopuseenelmonitor2.Tambiénabrítucorreo.Algomás"


def test_fraseador_quita_markdown_y_no_corta_horas():
    out = []
    f = Fraseador(out.append)
    f.agregar("**Son las 3:45 de la tarde**. Nada más.")
    f.cerrar()
    assert out[0] == "Son las 3:45 de la tarde."


def falso(registro, dur=0.05):
    detenido = threading.Event()

    def sint(t, v):
        return t.encode()

    def rep(a):
        registro.append(a.decode())
        detenido.clear()
        detenido.wait(dur)

    return sint, rep, detenido.set


def test_locutor_en_orden_y_avisa_al_terminar():
    reg, fin = [], threading.Event()
    s, r, d = falso(reg)
    loc = Locutor("x", s, r, d, al_terminar=fin.set)
    for f in ["uno", "dos", "tres"]:
        loc.decir(f)
    assert fin.wait(2) and reg == ["uno", "dos", "tres"] and not loc.hablando()
    assert loc.t_primer_audio is not None


def test_callar_corta_y_descarta_lo_pendiente():
    reg = []
    s, r, d = falso(reg, dur=0.5)
    loc = Locutor("x", s, r, d)
    for f in ["uno", "dos", "tres"]:
        loc.decir(f)
    time.sleep(0.1)
    loc.callar()
    time.sleep(0.3)
    assert reg == ["uno"] and not loc.hablando()
    loc.decir("nuevo")  # sigue funcionando después de interrumpir
    time.sleep(0.8)
    assert reg[-1] == "nuevo"

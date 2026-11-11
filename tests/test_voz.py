"""Turno de voz completo con cerebro y locutor falsos: interrupción y descarte."""

import threading
import time

from loops import voz
from loops.locutor import Locutor


def conversacion(monkeypatch, respuesta_lenta=False):
    monkeypatch.setattr(voz.bus, "publicar", lambda *a, **k: {})
    c = voz.Conversacion.__new__(voz.Conversacion)
    c.turno_id, c.ocupado, c.cola_remota, c.lock = 0, threading.Event(), [], threading.Lock()
    dicho = []
    c.locutor = Locutor(
        "x",
        lambda t, v: t.encode(),
        lambda a: (dicho.append(a.decode()), time.sleep(0.05)),
        lambda: None,
        al_terminar=c._al_terminar_de_hablar,
    )

    class CerebroFalso:
        def responder(self, texto, al_texto=None):
            for trozo in ["Claro, abriendo Excel. ", "Lo pongo en el monitor dos. ", "Listo."]:
                if respuesta_lenta:
                    time.sleep(0.15)
                al_texto(trozo)
            return "Claro, abriendo Excel. Lo pongo en el monitor dos. Listo."

    c.cerebro = CerebroFalso()
    return c, dicho


def test_turno_habla_y_libera(monkeypatch):
    c, dicho = conversacion(monkeypatch)
    c.turno_en_hilo("abre excel")
    assert c.ocupado.is_set()
    for _ in range(60):
        if not c.ocupado.is_set():
            break
        time.sleep(0.05)
    assert not c.ocupado.is_set()
    assert dicho[0] == "Claro, abriendo Excel." and dicho[-1].endswith("Listo.")


def test_interrumpir_descarta_lo_que_sigue_generando(monkeypatch):
    c, dicho = conversacion(monkeypatch, respuesta_lenta=True)
    c.turno_en_hilo("abre excel")
    time.sleep(0.25)  # ya dijo la primera frase; el modelo sigue generando
    c.callar()
    time.sleep(0.6)
    assert "Listo." not in dicho and not c.ocupado.is_set()

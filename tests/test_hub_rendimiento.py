"""El hub no se traba por un cliente lento y cada cliente recibe solo lo que pidió."""

import asyncio
import json

from loops import hub


class WSFalso:
    def __init__(self, lento=False):
        self.recibidos, self.lento = [], lento

    async def send_text(self, m):
        if self.lento:
            await asyncio.sleep(10)  # nunca termina a tiempo (cliente que no lee)
        self.recibidos.append(json.loads(m))


def test_cliente_lento_no_traba_y_filtros():
    async def correr():
        rapido, lento, gestos = WSFalso(), WSFalso(lento=True), WSFalso()
        tareas = [hub._registrar(rapido, None), hub._registrar(lento, None), hub._registrar(gestos, "gestos.")]
        t0 = asyncio.get_event_loop().time()
        for k in range(300):  # 10 s de manos a 30 fps
            await hub.difundir({"tipo": "manos", "k": k})
            await asyncio.sleep(0)
        await hub.difundir({"tipo": "gestos.entrenar", "nombre": "rock"})
        assert asyncio.get_event_loop().time() - t0 < 1.0  # difundir nunca espera al lento
        await asyncio.sleep(0.05)
        for t in tareas:
            t.cancel()
        for w in (rapido, lento, gestos):
            hub._olvidar(w)
        return rapido, lento, gestos

    rapido, lento, gestos = asyncio.run(correr())
    assert len(rapido.recibidos) == 301
    assert lento.recibidos == []  # el lento se atrasa solo, sin frenar a nadie
    assert [e["tipo"] for e in gestos.recibidos] == ["gestos.entrenar"]  # nada de manos para el proceso de cámara
    assert len(hub.colas) == 0


def test_camara_bajo_demanda(monkeypatch):
    lanzados = []

    class Proc:
        def __init__(self):
            self.vivo = True

        def poll(self):
            return None if self.vivo else 0

        def terminate(self):
            self.vivo = False

    from lay_core import procesos

    monkeypatch.setattr(procesos, "lanzar_rol", lambda rol, *a: lanzados.append(rol) or Proc())
    hub._camara["proc"] = None
    assert hub.camara("estado") == {"camara": False}
    assert hub.camara("encender") == {"camara": True}
    assert hub.camara("encender") == {"camara": True} and lanzados == ["gestos"]  # no duplica
    assert hub.camara("alternar") == {"camara": False}
    assert hub.camara("estado") == {"camara": False}

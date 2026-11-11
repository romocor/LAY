from lay_core import router


def test_faciles_van_a_sonnet_rapido():
    for t in ["abre spotify", "¿cuánta ram tengo?", "pon youtube en el monitor 2"]:
        p = router.elegir(t)
        assert p.nivel == "rapido" and "sonnet" in p.modelo


def test_medios():
    assert router.elegir("busca el informe de calidad y ábrelo").nivel == "normal"
    assert router.elegir("busca el informe de calidad y ábrelo").nivel == "normal"
    assert router.elegir("qué pendientes tengo en blackboard").nivel == "normal"


def test_dificiles_van_a_opus():
    for t in [
        "analiza mis correos de la semana y prioriza",
        "redacta un informe del avance de obra",
        "hazme un reporte de mis gastos",
        "piensa bien: cómo organizo mi semana",
    ]:
        p = router.elegir(t)
        assert p.nivel == "profundo" and "opus" in p.modelo and p.thinking > 0


def test_escalado():
    assert router.escalar(router.RAPIDO) is router.NORMAL
    assert router.escalar(router.NORMAL) is router.PROFUNDO
    assert router.escalar(router.PROFUNDO) is None

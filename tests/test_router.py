from lay_core import proveedores, router


def test_niveles():
    for t in ["abre spotify", "¿cuánta ram tengo?", "pon youtube en el monitor 2"]:
        assert router.elegir(t).nivel == "rapido"
    assert router.elegir("busca el informe de calidad y ábrelo").nivel == "normal"
    assert router.elegir("qué pendientes tengo en blackboard").nivel == "normal"
    for t in [
        "analiza mis correos de la semana y prioriza",
        "redacta un informe del avance de obra",
        "hazme un reporte de mis gastos",
        "piensa bien: cómo organizo mi semana",
    ]:
        assert router.elegir(t).nivel == "profundo"


def test_modelos_por_proveedor_gratis_por_defecto():
    cfg = {"proveedor": "ollama", "modelos": {}}
    assert proveedores.modelo_para("ollama", "rapido", cfg) == "lay-rapido"
    assert proveedores.modelo_para("ollama", "profundo", cfg) == "lay"
    cfg["modelos"] = {"ollama": {"profundo": "qwen2.5:14b"}}  # el usuario puede cambiarlo
    assert proveedores.modelo_para("ollama", "profundo", cfg) == "qwen2.5:14b"


def test_escalado():
    assert router.escalar(router.RAPIDO) is router.NORMAL
    assert router.escalar(router.NORMAL) is router.PROFUNDO
    assert router.escalar(router.PROFUNDO) is None


def test_filtro_de_herramientas_para_modelos_chicos():
    tools = [
        {"name": n}
        for n in [
            "abrir",
            "sistema_estado",
            "gmail_enviar",
            "correo_resumen",
            "ventana_mover",
            "blackboard_pendientes",
            "teclado_escribir",
        ]
    ]
    nombres = {t["name"] for t in router.filtrar(tools, router.temas("resúmeme los correos de hoy"))}
    assert "correo_resumen" in nombres and "ventana_mover" not in nombres and "teclado_escribir" not in nombres
    nombres = {t["name"] for t in router.filtrar(tools, router.temas("¿qué tengo en blackboard?"))}
    assert nombres == {"abrir", "blackboard_pendientes"}

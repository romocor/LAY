from lay_core import configurar


def test_env_conserva_comentarios_y_actualiza(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# --- Cerebro ---\nANTHROPIC_API_KEY=\nLAY_BIND=127.0.0.1\n", encoding="utf-8")
    configurar.escribir_env({"ANTHROPIC_API_KEY": "sk-ant-xyz", "BLACKBOARD_ICS_URL": "https://bb/x.ics"}, env)
    t = env.read_text(encoding="utf-8")
    assert "# --- Cerebro ---" in t and "ANTHROPIC_API_KEY=sk-ant-xyz" in t and "LAY_BIND=127.0.0.1" in t
    assert t.count("ANTHROPIC_API_KEY") == 1 and configurar.leer_env(env)["BLACKBOARD_ICS_URL"] == "https://bb/x.ics"


def test_no_muestra_secretos():
    assert "1234567890" not in configurar.oculto("sk-ant-api03-1234567890abcdef")


def test_valida_formato_clave():
    assert configurar.validar_api_key("hola") == "debe empezar con sk-ant-"

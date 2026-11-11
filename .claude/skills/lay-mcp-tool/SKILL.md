---
name: lay-mcp-tool
description: Receta para agregar una capacidad nueva a LAY como herramienta MCP (lay_core + lay_mcp/server.py + test). Usar siempre que se pida "que LAY pueda X".
---
# Agregar una herramienta a LAY

1. **Decide el nivel**: ¿lee (safe) o cambia algo del mundo real (sensible)? Enviar, escribir, cerrar, mover archivos = sensible. Borrar = no se implementa.
2. **Lógica en `lay_core/<modulo>.py`**
   - Función pura, parámetros con tipos, devuelve `dict`/`list` serializable.
   - Errores esperables → `{"error": "mensaje en español con la causa y cómo arreglarlo"}`.
   - Sensible → `@sensible("LAY va a ...")` de `lay_core.seguridad`; se llama con `confirmar=` como kwarg.
3. **Wrapper en `lay_mcp/server.py`**
   ```python
   @mcp.tool()
   def modulo_accion(param: str, confirmar: bool = False) -> dict:
       """[SENSIBLE] Qué hace, en una frase. Valores válidos de cada parámetro."""
       return modulo.accion(param=param, confirmar=confirmar)
   ```
   Nombre `area_verbo` en snake_case. El docstring es el prompt que ve el modelo: concreto.
4. **Test** `tests/test_<modulo>.py`: simula la dependencia externa (monkeypatch), prueba éxito, error y que la sensible sin confirmar devuelve `requiere_confirmacion`.
5. **Permisos de Claude Code**: si es sensible, agrégala a `permissions.ask` en `.claude/settings.json`.
6. **Verifica**: `python -m pytest -q` y `python scripts/verificar_mcp.py` (debe listarla).
7. Si aplica, frase de ejemplo en `tests/test_router.py` para que el router la clasifique bien.

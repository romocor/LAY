"""Router para el AnthropicProvider existente de centro_mando.

En ai/providers/anthropic_provider.py, dentro de send(), antes del POST:
    from ai.core.model_router import params_para
    payload.update(params_para(messages))
"""

from __future__ import annotations


def params_para(messages: list[dict]) -> dict:
    from lay_core import proveedores, router
    from lay_core.config import CONFIG

    ultimo = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user" and isinstance(m["content"], str)), ""
    )
    p = router.elegir(ultimo)
    return {"model": proveedores.modelo_para("anthropic", p.nivel, CONFIG.ia), "max_tokens": p.max_tokens}

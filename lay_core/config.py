"""Configuración central de LAY. Desarrollo: .env + config/lay.json del repo.
Instalado (.exe): %USERPROFILE%\\.lay\\.env y %USERPROFILE%\\.lay\\lay.json."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Empaquetado (.exe con PyInstaller): los recursos van dentro de _MEIPASS y la
# configuración editable del usuario vive en ~/.lay (se copia la primera vez).
CONGELADO = getattr(sys, "frozen", False)
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA_DIR = Path(os.getenv("LAY_DATA", Path.home() / ".lay"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

try:
    from dotenv import load_dotenv

    load_dotenv(DATA_DIR / ".env")  # .env del usuario instalado
    load_dotenv()  # .env del repo en desarrollo
except ImportError:
    pass

_CONFIG_DEFECTO = ROOT / "config" / "lay.json"
if CONGELADO:
    _destino = DATA_DIR / "lay.json"
    if not _destino.exists() and _CONFIG_DEFECTO.exists():
        shutil.copy(_CONFIG_DEFECTO, _destino)
    _ejemplo_env = ROOT / ".env.example"
    if not (DATA_DIR / ".env").exists() and _ejemplo_env.exists():
        shutil.copy(_ejemplo_env, DATA_DIR / ".env")
    _CONFIG_DEFECTO = _destino
CONFIG_FILE = Path(os.getenv("LAY_CONFIG", _CONFIG_DEFECTO))
AUDIT_LOG = DATA_DIR / "audit.log"


@dataclass
class LayConfig:
    nombre: str = "LAY"
    wake_words: list[str] = field(default_factory=lambda: ["lay", "ley", "lei", "oye lay", "oye ley"])
    confianza_wake: float = 0.75  # súbelo (0.85) si se activa sola; bájalo (0.6) si no te oye
    microfono: int | None = None  # índice PyAudio; None = predeterminado de Windows
    idioma: str = "es-PE"
    voz_tts: str = "es-PE-AlexNeural"
    hub_host: str = "127.0.0.1"
    hub_port: int = 8765
    raices_busqueda: list[str] = field(default_factory=lambda: [str(Path.home())])
    carpeta_galeria: str = str(Path.home() / "Pictures")
    apps: dict[str, str] = field(default_factory=dict)
    workspaces: dict[str, list[dict]] = field(default_factory=dict)
    usuario: str = "Robert"
    ciudad: str = "Lima"  # para el clima
    actualizaciones: dict = field(default_factory=lambda: {"repo": "romocor/LAY"})
    navegador: str = "predeterminado"  # brave | chrome | edge | predeterminado (el primero instalado)
    camara_indice: int = 0
    modo_mouse_por_defecto: bool = False
    gestos: dict = field(default_factory=dict)  # umbrales calibrados (loops.gestos --calibrar)
    # IA: "ollama" (local, gratis, por defecto) | "gemini" / "groq" (capa gratuita con clave) | "anthropic" (pago)
    ia: dict = field(default_factory=lambda: {"proveedor": "ollama", "modelos": {}, "filtrar_herramientas": "auto"})
    # Abrir LAY con palmadas: doble = abrir/traer LAY; triple = acción configurable
    aplausos: dict = field(
        default_factory=lambda: {"activo": True, "sensibilidad": 0.6, "accion_triple": "workspace:trabajo"}
    )
    # Remoto: solo con token; por defecto solo desde Tailscale (100.64.0.0/10)
    remoto: dict = field(default_factory=lambda: {"activo": False, "solo_tailscale": True})

    @classmethod
    def load(cls) -> "LayConfig":
        cfg = cls()
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k):
                    defecto = getattr(cfg, k)
                    # Secciones (ia, aplausos, remoto...): lo guardado completa los valores por defecto,
                    # así un lay.json viejo o un ajuste parcial no borra el resto de opciones.
                    if isinstance(defecto, dict) and isinstance(v, dict) and k not in ("apps", "workspaces"):
                        v = {**defecto, **v}
                    setattr(cfg, k, v)
        return cfg


CONFIG = LayConfig.load()


def recargar() -> LayConfig:
    """Relee lay.json y .env y actualiza CONFIG EN SITIO (los módulos que lo importaron ven el cambio)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(DATA_DIR / ".env", override=True)
    except ImportError:
        pass
    nuevo = LayConfig.load()
    CONFIG.__dict__.update(nuevo.__dict__)
    return CONFIG


def guardar(cambios: dict) -> LayConfig:
    """Mezcla `cambios` en lay.json (dicts anidados se fusionan, no se pisan) y recarga."""
    actual = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}

    def fusionar(a: dict, b: dict) -> dict:
        for k, v in b.items():
            a[k] = fusionar(dict(a.get(k) or {}), v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return a

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(fusionar(actual, cambios), ensure_ascii=False, indent=2), encoding="utf-8")
    return recargar()


HUB_URL = f"http://{CONFIG.hub_host}:{CONFIG.hub_port}"
HUB_TOKEN = os.getenv("LAY_HUB_TOKEN", "")

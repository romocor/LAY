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
    modelo_facil: str = "claude-sonnet-5-5"
    modelo_dificil: str = "claude-opus-5-5"
    camara_indice: int = 0
    modo_mouse_por_defecto: bool = False
    gestos: dict = field(default_factory=dict)  # umbrales calibrados (loops.gestos --calibrar)

    @classmethod
    def load(cls) -> "LayConfig":
        cfg = cls()
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        cfg.modelo_facil = os.getenv("LAY_MODEL_EASY", cfg.modelo_facil)
        cfg.modelo_dificil = os.getenv("LAY_MODEL_HARD", cfg.modelo_dificil)
        return cfg


CONFIG = LayConfig.load()
HUB_URL = f"http://{CONFIG.hub_host}:{CONFIG.hub_port}"
HUB_TOKEN = os.getenv("LAY_HUB_TOKEN", "")

"""Asistente de configuración (primera vez o cuando quieras cambiar algo).

  LAY-cli.exe --rol configurar

Pregunta lo mínimo, valida lo que puede y guarda en %USERPROFILE%\\.lay\\.env.
Enter = conservar el valor actual. Nunca muestra secretos completos.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from lay_core.config import DATA_DIR

ENV = DATA_DIR / ".env"


def leer_env(ruta: Path = ENV) -> dict[str, str]:
    datos: dict[str, str] = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                datos[k.strip()] = v.strip()
    return datos


def escribir_env(cambios: dict[str, str], ruta: Path = ENV) -> None:
    """Actualiza solo las claves cambiadas y conserva comentarios y el resto del archivo."""
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    pendientes = dict(cambios)
    for i, linea in enumerate(lineas):
        if "=" in linea and not linea.lstrip().startswith("#"):
            k = linea.split("=", 1)[0].strip()
            if k in pendientes:
                lineas[i] = f"{k}={pendientes.pop(k)}"
    lineas += [f"{k}={v}" for k, v in pendientes.items()]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def oculto(v: str) -> str:
    return "(vacío)" if not v else f"{v[:6]}…{v[-4:]}" if len(v) > 14 else "••••"


def validar_api_key(clave: str) -> str | None:
    """None si funciona; si no, el motivo en español."""
    if not clave.startswith("sk-ant-"):
        return "debe empezar con sk-ant-"
    try:
        import anthropic

        anthropic.Anthropic(api_key=clave).models.list(limit=1)
        return None
    except Exception as exc:
        return f"Anthropic la rechazó ({type(exc).__name__})"


def validar_ics(url: str) -> str | None:
    if not url.startswith(("https://", "webcal://")):
        return "debe ser la URL https:// o webcal:// del calendario"
    try:
        from lay_core import blackboard

        n = len(
            blackboard.parsear_ics(
                __import__("httpx").get(url.replace("webcal://", "https://"), timeout=20, follow_redirects=True).content
            )
        )
        print(f"   ✓ {n} eventos en el calendario")
        return None
    except Exception as exc:
        return f"no pude leer el calendario ({type(exc).__name__})"


def preguntar(etiqueta: str, actual: str, ayuda: str, validar=None, secreto: bool = False) -> str | None:
    print(f"\n{etiqueta}\n   {ayuda}\n   Actual: {oculto(actual) if secreto else (actual or '(vacío)')}")
    while True:
        v = input("   > ").strip().strip('"')
        if not v:
            return None
        error = validar(v) if validar else None
        if error is None:
            return v
        print(f"   ✗ {error}. Inténtalo otra vez o Enter para dejarlo.")


def main() -> None:
    print("=" * 60 + "\n  Configuración de LAY  (Enter = dejar como está)\n" + "=" * 60)
    env = leer_env()
    cambios: dict[str, str] = {}

    v = preguntar(
        "1) Clave de Anthropic (obligatoria)",
        env.get("ANTHROPIC_API_KEY", ""),
        "console.anthropic.com → API Keys",
        validar_api_key,
        secreto=True,
    )
    if v:
        cambios["ANTHROPIC_API_KEY"] = v

    v = preguntar(
        "2) Blackboard: URL del calendario (.ics)",
        env.get("BLACKBOARD_ICS_URL", ""),
        "Blackboard → Calendario → ⚙ → Compartir calendario → copiar enlace",
        validar_ics,
    )
    if v:
        cambios["BLACKBOARD_ICS_URL"] = v.replace("webcal://", "https://")

    destino = DATA_DIR / "gmail_credentials.json"
    print(
        f"\n3) Gmail: archivo de credenciales OAuth (App de escritorio)\n"
        f"   Google Cloud → APIs → Gmail API → Credenciales → ID de cliente OAuth → Escritorio → Descargar JSON\n"
        f"   Actual: {'configurado' if destino.exists() else '(no)'}"
    )
    ruta = input("   Arrastra aquí el .json (o Enter): ").strip().strip('"')
    if ruta:
        if Path(ruta).is_file() and '"installed"' in Path(ruta).read_text(encoding="utf-8", errors="ignore"):
            shutil.copy(ruta, destino)
            print("   ✓ copiado; la primera vez que pidas tus correos se abrirá el navegador para autorizar")
        else:
            print("   ✗ no parece un JSON de 'App de escritorio'; lo dejo como estaba")

    v = preguntar(
        "4) Outlook: Application (client) ID",
        env.get("OUTLOOK_CLIENT_ID", ""),
        "Entra ID → Registros de aplicaciones → tu app → Id. de aplicación (cliente)",
    )
    if v:
        cambios["OUTLOOK_CLIENT_ID"] = v

    if cambios:
        escribir_env(cambios)
        for k, val in cambios.items():
            os.environ[k] = val
    print(f"\n✓ Guardado en {ENV}. Cierra esta ventana y abre LAY.\n")
    input("Enter para salir...")


def falta_configurar() -> bool:
    return not (os.environ.get("ANTHROPIC_API_KEY") or leer_env().get("ANTHROPIC_API_KEY"))

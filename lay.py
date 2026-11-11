"""Punto de entrada único de LAY (también es el LAY.exe empaquetado).

  LAY.exe                    # todo: hub + gestos + voz + HUD a pantalla completa
  LAY.exe --texto            # voz por teclado (pruebas)
  LAY.exe --sin-camara       # sin gestos
  LAY.exe --rol mcp          # servidor MCP (para Claude Desktop / Claude Code)
  LAY.exe --rol mcp --http   # MCP remoto con token
  LAY.exe --rol configurar   # asistente: API key, Blackboard, Gmail, Outlook
  LAY.exe --rol hub|gestos|voz [args]   # un solo loop (lo usa el lanzador)

En desarrollo es igual: python lay.py ...
"""

from __future__ import annotations

import argparse
import multiprocessing
import subprocess
import sys
import time

ROLES = {
    "hub": "loops.hub",
    "gestos": "loops.gestos",
    "voz": "loops.voz",
    "mcp": "lay_mcp.server",
    "configurar": "lay_core.configurar",
    "aplausos": "loops.aplausos",
    "instalar-ia": "lay_core.ia_local",
}


def ejecutar_rol(rol: str, resto: list[str]) -> None:
    """Corre un loop en este proceso. sys.argv se ajusta para el argparse del módulo."""
    import importlib
    import runpy

    sys.argv = [f"lay-{rol}", *resto]
    modulo = ROLES[rol]
    try:
        if rol == "hub":
            runpy.run_module(modulo, run_name="__main__")
        else:
            importlib.import_module(modulo).main()
    finally:
        if getattr(sys, "frozen", False):
            # El MCP por stdio deja stdout cerrado al terminar; el bootloader de PyInstaller
            # intenta vaciarlo y ensucia el log de Claude Desktop con un ValueError.
            import os

            sys.stdout = sys.stderr = open(os.devnull, "w")  # noqa: SIM115


def comando_rol(rol: str, *args: str) -> list[str]:
    """Cómo relanzarse a sí mismo con otro rol, congelado o no."""
    if getattr(sys, "frozen", False):
        from pathlib import Path

        exe = Path(sys.executable)
        cli = exe.with_name("LAY-cli.exe" if exe.suffix.lower() == ".exe" else "LAY-cli")
        return [str(cli if cli.exists() else exe), "--rol", rol, *args]
    return [sys.executable, __file__, "--rol", rol, *args]


def esperar_hub(url: str, seg: float = 15) -> bool:
    import httpx

    fin = time.time() + seg
    while time.time() < fin:
        try:
            httpx.get(url, timeout=1)
            return True
        except httpx.HTTPError:
            time.sleep(0.3)
    return False


def _popen(cmd: list[str]) -> subprocess.Popen:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if getattr(sys, "frozen", False) else 0
    return subprocess.Popen(cmd, creationflags=flags)


def lanzador(a: argparse.Namespace) -> None:
    import threading

    import httpx

    from lay_core.config import CONFIG, HUB_URL

    # Una sola instancia: si LAY ya está abierto, solo se trae al frente
    try:
        httpx.get(f"{HUB_URL}/api/ping", timeout=1)
        from lay_core import bus

        bus.publicar("aplausos", n=2, accion="traer")
        return
    except httpx.HTTPError:
        pass

    # IA local gratis: si está instalada, se enciende en segundo plano (no bloquea la ventana)
    if CONFIG.ia.get("proveedor", "ollama") == "ollama":
        from lay_core import ia_local

        threading.Thread(target=ia_local.iniciar, daemon=True).start()
    # Detector de palmadas (si ya corre desde el inicio de Windows, el mutex evita duplicarlo)
    if CONFIG.aplausos.get("activo", True):
        _popen(comando_rol("aplausos"))

    procs = [_popen(comando_rol("hub"))]
    if not esperar_hub(HUB_URL):
        raise SystemExit("El hub no arrancó. Revisa que el puerto 8765 esté libre.")
    if not a.sin_camara:
        procs.append(_popen(comando_rol("gestos")))
    procs.append(_popen(comando_rol("voz", *(["--texto"] if a.texto else []))))
    from lay_core import bandeja, bus

    estado = {"camara": not a.sin_camara, "microfono": True, "gestos": procs[1] if not a.sin_camara else None}

    def alternar_camara():
        if estado["camara"] and estado["gestos"]:
            estado["gestos"].terminate()
            estado["camara"] = False
        else:
            estado["gestos"] = _popen(comando_rol("gestos"))
            procs.append(estado["gestos"])
            estado["camara"] = True
        bus.publicar("hud.camara", ok=estado["camara"], pausada=not estado["camara"])

    def alternar_microfono():
        estado["microfono"] = not estado["microfono"]
        bus.publicar("voz.microfono", activo=estado["microfono"])

    # Versión nueva en GitHub Releases (solo si el repositorio es público)
    repo = CONFIG.__dict__.get("actualizaciones", {}).get("repo", "romocor/LAY")
    bandeja.revisar_en_fondo(
        _version(),
        repo,
        lambda n: bus.publicar(
            "hud.panel",
            titulo="Actualización disponible",
            items=[{"titulo": f"LAY {n['version']} ya está disponible", "detalle": n["url"], "etiqueta": "nuevo"}],
            segundos=40,
        ),
    )
    try:
        import webview

        class Api:
            """Expuesta al overlay como window.pywebview.api (modo mouse, bandeja)."""

            def minimizar(self):
                ventana.minimize()

            def restaurar(self):
                ventana.restore()

        ventana = webview.create_window("LAY", HUB_URL, fullscreen=True, background_color="#020b11", js_api=Api())
        icono = bandeja.iniciar_bandeja(
            {
                "abrir": lambda: ventana.restore(),
                "configuracion": lambda: bus.publicar("hud.config", seccion="ia"),
                "camara": alternar_camara,
                "microfono": alternar_microfono,
                "salir": lambda: ventana.destroy(),
            },
            lambda: estado,
        )
        webview.start()
        if icono is not None:
            icono.stop()
    except ImportError:
        import webbrowser

        webbrowser.open(HUB_URL)
        while True:
            time.sleep(1)
    finally:
        for p in procs:
            p.terminate()


def _version() -> str:
    try:
        import tomllib

        from lay_core.config import ROOT

        return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    except Exception:
        return "0"


def main() -> None:
    multiprocessing.freeze_support()
    ap = argparse.ArgumentParser(prog="LAY")
    ap.add_argument("--rol", choices=sorted(ROLES))
    ap.add_argument("--sin-camara", action="store_true")
    ap.add_argument("--texto", action="store_true")
    ap.add_argument("--version", action="store_true")
    a, resto = ap.parse_known_args()
    if a.version:
        print(f"LAY {_version()}")
        return
    if a.rol:
        ejecutar_rol(a.rol, resto + (["--texto"] if a.texto else []))
    else:
        lanzador(a)


if __name__ == "__main__":
    main()

"""IA local gratuita en CUALQUIER PC: detecta el hardware, instala Ollama y baja el modelo adecuado.

  LAY-cli.exe --rol instalar-ia     (lo ejecuta el instalador si marcas la casilla)
  Configuración → IA → "Instalar IA local"   (desde la app, con barra de progreso)

Modelos (familia Qwen 2.5: buen español y llamadas a herramientas fiables):
  RAM < 6 GB          -> qwen2.5:1.5b en todo                 (~1,0 GB)
  RAM < 12 GB         -> qwen2.5:3b  (7b si la GPU tiene ≥6 GB) (~1,9 GB)
  RAM ≥ 12 GB         -> qwen2.5:3b rápido + qwen2.5:7b profundo (~6,6 GB)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

import httpx

OLLAMA = "http://127.0.0.1:11434"
URL_INSTALADOR = "https://ollama.com/download/OllamaSetup.exe"
TAMANOS_GB = {"qwen2.5:1.5b": 1.0, "qwen2.5:3b": 1.9, "qwen2.5:7b": 4.7, "qwen2.5:14b": 9.0}
Progreso = Callable[[str, float, str], None]  # (etapa, 0-100, texto)


def _nada(etapa: str, pct: float, texto: str) -> None:
    pass


# ---------------- hardware ----------------
def vram_gb() -> float:
    exe = shutil.which("nvidia-smi") or (
        r"C:\Windows\System32\nvidia-smi.exe" if platform.system() == "Windows" else None
    )
    if not exe or not os.path.exists(exe):
        return 0.0
    try:
        r = subprocess.run(
            [exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return round(max(float(x) for x in r.stdout.split()) / 1024, 1)
    except Exception:
        return 0.0


def hardware() -> dict:
    import psutil

    disco = shutil.disk_usage(Path.home())
    return {
        "ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        "vram_gb": vram_gb(),
        "disco_libre_gb": round(disco.free / 1024**3, 1),
        "cpu_nucleos": os.cpu_count() or 2,
    }


def recomendar(hw: dict) -> dict:
    ram, vram = hw["ram_gb"], hw.get("vram_gb", 0)
    if ram < 6:
        m = {"rapido": "qwen2.5:1.5b", "normal": "qwen2.5:1.5b", "profundo": "qwen2.5:1.5b"}
        motivo = f"{ram:g} GB de RAM: modelo liviano para que la PC no se trabe"
    elif ram < 12:
        grande = "qwen2.5:7b" if vram >= 6 else "qwen2.5:3b"
        m = {"rapido": "qwen2.5:3b", "normal": "qwen2.5:3b", "profundo": grande}
        motivo = f"{ram:g} GB de RAM" + (f" y GPU de {vram:g} GB" if vram >= 6 else ": modelo de 3B en todo")
    else:
        m = {"rapido": "qwen2.5:3b", "normal": "qwen2.5:3b", "profundo": "qwen2.5:7b"}
        motivo = f"{ram:g} GB de RAM" + (f" + GPU de {vram:g} GB" if vram else "") + ": 3B rápido y 7B para lo difícil"
    unicos = sorted(set(m.values()))
    return {
        "modelos": m,
        "descargar": unicos,
        "descarga_gb": round(sum(TAMANOS_GB.get(x, 3) for x in unicos), 1),
        "motivo": motivo,
    }


# ---------------- Ollama ----------------
def ollama_exe() -> str | None:
    cand = [shutil.which("ollama")]
    if platform.system() == "Windows":
        cand.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"))
    return next((c for c in cand if c and os.path.isfile(c)), None)


def activo() -> bool:
    try:
        return httpx.get(f"{OLLAMA}/api/version", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def modelos_instalados() -> list[str]:
    try:
        return [m["name"] for m in httpx.get(f"{OLLAMA}/api/tags", timeout=4).json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []


def iniciar(espera_s: float = 25) -> bool:
    """Arranca el servidor de Ollama si está instalado pero apagado."""
    if activo():
        return True
    exe = ollama_exe()
    if not exe:
        return False
    flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    fin = time.time() + espera_s
    while time.time() < fin:
        if activo():
            return True
        time.sleep(0.5)
    return False


def _descargar(url: str, destino: Path, progreso: Progreso, etapa: str) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(60, connect=15)) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        hecho = 0
        with open(destino, "wb") as f:
            for trozo in r.iter_bytes(1 << 20):
                f.write(trozo)
                hecho += len(trozo)
                if total:
                    progreso(etapa, hecho * 100 / total, f"{hecho / 1e6:.0f} de {total / 1e6:.0f} MB")


def instalar_ollama(progreso: Progreso = _nada) -> None:
    """Instalador oficial en silencio (sin ventanas ni clics); si falla la descarga, winget."""
    if platform.system() != "Windows":
        raise RuntimeError("La instalación automática es para Windows; en otro sistema instala Ollama desde ollama.com")
    setup = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    try:
        progreso("ollama", 0, "Descargando Ollama…")
        _descargar(URL_INSTALADOR, setup, progreso, "ollama")
        progreso("ollama", 100, "Instalando Ollama (sin ventanas)…")
        subprocess.run([str(setup), "/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True, timeout=900)
    except Exception:
        progreso("ollama", 50, "Probando con winget…")
        subprocess.run(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "Ollama.Ollama",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            check=True,
            timeout=1200,
        )
    finally:
        setup.unlink(missing_ok=True)


def descargar_modelo(nombre: str, progreso: Progreso = _nada) -> None:
    import json

    with httpx.stream(
        "POST", f"{OLLAMA}/api/pull", json={"model": nombre, "stream": True}, timeout=httpx.Timeout(None, connect=10)
    ) as r:
        r.raise_for_status()
        for linea in r.iter_lines():
            if not linea:
                continue
            ev = json.loads(linea)
            if ev.get("error"):
                raise RuntimeError(f"Ollama no pudo bajar {nombre}: {ev['error']}")
            total, hecho = ev.get("total"), ev.get("completed")
            if total and hecho is not None:
                progreso(
                    f"modelo:{nombre}", hecho * 100 / total, f"{nombre}: {hecho / 1e9:.1f} de {total / 1e9:.1f} GB"
                )
            elif ev.get("status"):
                progreso(f"modelo:{nombre}", 100 if ev["status"] == "success" else 0, f"{nombre}: {ev['status']}")


def estado() -> dict:
    hw = hardware()
    rec = recomendar(hw)
    inst = modelos_instalados() if activo() else []
    faltan = [m for m in rec["descargar"] if not any(i == m or i.startswith(m + "-") for i in inst)]
    return {
        "hardware": hw,
        "recomendacion": rec,
        "ollama_instalado": bool(ollama_exe()) or activo(),
        "ollama_activo": activo(),
        "modelos_instalados": inst,
        "faltan": faltan,
        "listo": activo() and not faltan,
    }


def preparar(progreso: Progreso = _nada, modelos: dict | None = None) -> dict:
    """Deja la IA local lista: instala Ollama si falta, lo arranca, baja los modelos y guarda la config.
    Es idempotente: si ya está todo, termina al instante."""
    from lay_core import config

    hw = hardware()
    rec = recomendar(hw)
    if modelos:
        rec = {**rec, "modelos": modelos, "descargar": sorted(set(modelos.values()))}
    necesita_gb = sum(TAMANOS_GB.get(x, 3) for x in rec["descargar"]) * 1.2
    if hw["disco_libre_gb"] < necesita_gb:
        raise RuntimeError(
            f"Falta espacio: se necesitan ~{necesita_gb:.0f} GB libres y hay {hw['disco_libre_gb']:g} GB."
        )

    progreso("inicio", 0, rec["motivo"])
    if not ollama_exe() and not activo():
        instalar_ollama(progreso)
    progreso("servidor", 0, "Encendiendo la IA local…")
    if not iniciar():
        raise RuntimeError("Ollama se instaló pero no arrancó. Reinicia la PC y vuelve a intentar.")
    instalados = modelos_instalados()
    for m in rec["descargar"]:
        if m not in instalados:
            descargar_modelo(m, progreso)
    # La IA propia de LAY: modelos "lay-rapido" y "lay" con su identidad y contexto de 8k
    modelos = dict(rec["modelos"])
    try:
        from lay_core import modelo_lay

        exe = ollama_exe()
        for nombre, d in modelo_lay.nombres(rec["modelos"]).items():
            progreso(f"modelo:{nombre}", 50, f"Creando la IA de LAY ({nombre} sobre {d['base']})…")
            modelo_lay.crear(exe, nombre, d["base"], d["profundo"])
        modelos = {"rapido": "lay-rapido", "normal": "lay-rapido", "profundo": "lay"}
    except Exception as exc:  # si falla, LAY sigue con los modelos base (funciona igual, sin personalidad propia)
        progreso("aviso", 100, f"Uso los modelos base ({exc})"[:120])
    config.guardar({"ia": {"modelos": {"ollama": modelos}}})
    progreso("listo", 100, "IA local de LAY lista. Gratis y sin internet.")
    return {"ok": True, **rec, "modelos": modelos}


def main() -> None:
    """Modo consola (lo usa el instalador). Nunca hace fallar la instalación de LAY."""
    print("=" * 62 + "\n  LAY · Instalando IA local gratuita (Ollama)\n" + "=" * 62)
    hw = hardware()
    rec = recomendar(hw)
    print(f"  PC: {hw['ram_gb']:g} GB RAM · GPU {hw['vram_gb']:g} GB · {hw['disco_libre_gb']:g} GB libres")
    print(f"  Modelos: {', '.join(rec['descargar'])}  (~{rec['descarga_gb']:g} GB)  → {rec['motivo']}\n")
    ultimo = {"etapa": "", "pct": -10}

    def barra(etapa: str, pct: float, texto: str) -> None:
        if etapa != ultimo["etapa"] or pct - ultimo["pct"] >= 2 or pct >= 100:
            llenos = int(pct / 4)
            sys.stdout.write(f"\r  [{'█' * llenos}{'·' * (25 - llenos)}] {pct:5.1f}%  {texto[:40]:<40}")
            sys.stdout.flush()
            if etapa != ultimo["etapa"] and ultimo["etapa"]:
                sys.stdout.write("\n")
            ultimo.update(etapa=etapa, pct=pct)

    try:
        preparar(barra)
        print("\n\n  ✓ Listo. LAY usará esta IA sin costo y sin internet.")
    except Exception as exc:
        print(f"\n\n  ✗ No se pudo completar: {exc}\n  Puedes reintentar desde LAY → Configuración → IA.")
    if "--sin-pausa" not in sys.argv:
        time.sleep(4)

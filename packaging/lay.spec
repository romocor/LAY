# PyInstaller spec de LAY -> dist/LAY/LAY.exe (app, sin consola) + LAY-cli.exe (MCP y loops, con consola)
# Construir:  pyinstaller packaging/lay.spec --noconfirm --clean
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821  (SPECPATH lo define PyInstaller)
sys.path.insert(0, RAIZ)  # para que collect_submodules encuentre lay_core, loops, etc.

datas, binaries, hidden = [], [], []
for paquete in ("mediapipe", "webview", "edge_tts", "mcp", "uvicorn", "pygame", "googleapiclient", "icalendar", "vosk", "qrcode"):
    try:
        d, b, h = collect_all(paquete)
        datas += d; binaries += b; hidden += h
    except Exception as exc:  # paquete opcional no instalado
        print(f"[lay.spec] omitido {paquete}: {exc}")

propios = []
for pkg in ("lay_core", "loops", "lay_mcp", "remote"):
    propios += collect_submodules(pkg)
assert "lay_mcp.server" in propios and "loops.hub" in propios, f"No encontré los módulos de LAY: {propios}"
hidden += propios
hidden += [
    "pyttsx3.drivers", "pyttsx3.drivers.sapi5", "comtypes.client", "speech_recognition", "pyaudio",
    "msal", "screeninfo", "mss", "pygetwindow", "pyperclip", "pyautogui", "PIL.Image", "PIL.ImageOps",
    "platformdirs", "jaraco.text", "jaraco.functools", "jaraco.context",  # runtime hook de pkg_resources
]

# Modelo de voz offline (lo descarga build_exe.ps1 a packaging/models/vosk-es). Sin él, el exe lo baja al primer uso.
_vosk = os.path.join(SPECPATH, "models", "vosk-es")  # noqa: F821
if os.path.isdir(_vosk):
    datas += [(_vosk, os.path.join("models", "vosk-es"))]
else:
    print("[lay.spec] AVISO: sin modelo Vosk empaquetado; se descargará en el primer arranque")

datas += [(os.path.join(RAIZ, "overlay"), "overlay"), (os.path.join(RAIZ, "config"), "config"),
          (os.path.join(RAIZ, ".env.example"), "."), (os.path.join(RAIZ, "pyproject.toml"), ".")]

a = Analysis([os.path.join(RAIZ, "lay.py")], pathex=[RAIZ], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "pytest", "IPython"], noarchive=False)
pyz = PYZ(a.pure)
icono = os.path.join(SPECPATH, "lay.ico")  # noqa: F821

app = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LAY", console=False,
          icon=icono, version=os.path.join(SPECPATH, "version.txt"), upx=False)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LAY-cli", console=True,
          icon=icono, version=os.path.join(SPECPATH, "version.txt"), upx=False)
coll = COLLECT(app, cli, a.binaries, a.datas, name="LAY", upx=False)

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Stubs para correr los tests sin cámara/GUI (CI, Linux)
for mod in ("cv2", "mediapipe", "pyautogui"):
    if mod not in sys.modules:
        try:
            __import__(mod)
        except Exception:
            sys.modules[mod] = types.ModuleType(mod)

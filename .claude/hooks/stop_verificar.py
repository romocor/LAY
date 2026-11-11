"""Stop: antes de dar por terminado, los tests deben pasar. Si fallan, Claude sigue (exit 2).
Un solo reintento por turno (stop_hook_active) para no entrar en bucle infinito."""

import json
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)
if data.get("stop_hook_active") or not Path("tests").exists():
    sys.exit(0)
r = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-x", "--no-header"], capture_output=True, text=True, timeout=180
)
if r.returncode not in (0, 5):  # 5 = no hay tests
    print("Los tests fallan; arréglalos antes de terminar:\n" + r.stdout[-2500:], file=sys.stderr)
    sys.exit(2)
sys.exit(0)

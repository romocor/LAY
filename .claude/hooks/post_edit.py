"""PostToolUse(Edit|Write): formatea y lintea el .py editado. Errores vuelven a Claude (exit 2)."""

import json
import shutil
import subprocess
import sys

data = json.load(sys.stdin)
ruta = data.get("tool_input", {}).get("file_path", "")
if not ruta.endswith(".py") or not shutil.which("ruff"):
    sys.exit(0)
subprocess.run(["ruff", "format", ruta], capture_output=True)
r = subprocess.run(["ruff", "check", "--fix", ruta], capture_output=True, text=True)
if r.returncode != 0:
    print(f"ruff encontró problemas en {ruta}:\n{r.stdout[-2000:]}", file=sys.stderr)
    sys.exit(2)
sys.exit(0)

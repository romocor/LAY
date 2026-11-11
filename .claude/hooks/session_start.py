"""SessionStart: inyecta el estado del proyecto como contexto (stdout se agrega al contexto)."""

import re
import subprocess
from pathlib import Path

plan = Path("PLAN.md")
if plan.exists():
    txt = plan.read_text(encoding="utf-8")
    pend = [x.strip() for x in txt.splitlines() if re.match(r"\s*- \[ \]", x)][:6]
    print("Próximas tareas pendientes de PLAN.md:\n" + "\n".join(pend))
try:
    st = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5).stdout
    if st.strip():
        print("Cambios sin commit:\n" + st[:800])
except Exception:
    pass

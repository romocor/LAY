"""PreToolUse(Bash): bloquea comandos destructivos o que filtran secretos. Exit 2 = bloquear."""

import json
import re
import sys

PELIGROSOS = [
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", "rm -rf"),
    (r"\b(del|erase)\s+/[sq]", "del /s"),
    (r"\brmdir\s+/s", "rmdir /s"),
    (r"Remove-Item.*-Recurse", "Remove-Item -Recurse"),
    (r"\bformat\s+[a-z]:", "format de disco"),
    (r"git\s+push\s+.*(--force|-f\b)", "git push --force"),
    (r"git\s+reset\s+--hard", "git reset --hard"),
    (r"(curl|wget|iwr|Invoke-WebRequest)[^|]*\|\s*(sh|bash|iex|python)", "descargar y ejecutar"),
    (r"(cat|type|Get-Content)\s+[^\n]*(\.env\b|gmail_token|outlook_cache|credentials\.json)", "leer secretos"),
    (r"reg\s+delete|bcdedit|diskpart|shutdown\s", "comando de sistema"),
]
data = json.load(sys.stdin)
cmd = data.get("tool_input", {}).get("command", "")
for patron, nombre in PELIGROSOS:
    if re.search(patron, cmd, re.I):
        print(
            f"Bloqueado por hook de LAY ({nombre}). Si de verdad hace falta, pídeselo a Robert para que lo ejecute él.",
            file=sys.stderr,
        )
        sys.exit(2)
sys.exit(0)

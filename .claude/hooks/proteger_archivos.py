"""PreToolUse(Edit|Write): no tocar secretos ni el log de auditoría."""

import json
import sys
from pathlib import PurePath

data = json.load(sys.stdin)
ruta = data.get("tool_input", {}).get("file_path", "")
nombre = PurePath(ruta).name.lower()
protegidos = {".env", "audit.log", "gmail_token.json", "gmail_credentials.json", "outlook_cache.json"}
if nombre in protegidos or "/.lay/" in ruta.replace("\\", "/"):
    print(f"'{nombre}' es protegido (secretos/auditoría). Edita .env.example en su lugar.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)

# LAY v2

Asistente personal con voz, gestos de mano y control del PC (Windows 11, multi-monitor).

## Instalar (en cualquier PC con Windows 10/11)
1. Descarga `LAY_Setup_<ver>.exe` de [Releases](https://github.com/romocor/LAY/releases) y ejecútalo (no pide admin).
2. Deja marcadas **IA gratuita local** (instala Ollama y el modelo justo para esa PC) y **Abrir con palmadas**.
3. Abre LAY (o da dos palmadas). Todo se configura dentro: botón **⚙ Configuración** o tecla **C**.

No necesitas ninguna cuenta ni pagar: la IA corre en la PC. Opcional: Gemini/Groq (gratis con clave) o Claude (de pago).
MCP para Claude Desktop: `{"mcpServers": {"lay-pc": {"command": "%LOCALAPPDATA%\\Programs\\LAY\\LAY-cli.exe", "args": ["--rol", "mcp"]}}}`

## Generar el .exe
- En Windows: `powershell -ExecutionPolicy Bypass -File build_exe.ps1 -Version 2.0.0` → `dist\LAY_Setup_2.0.0.exe` + `dist\LAY_portable_2.0.0.zip`.
- Desde GitHub: sube el repo y cada push a `main` compila en Actions (artefacto **LAY-windows**); un tag `v2.0.0` crea un Release con el instalador.

## Desarrollo (PowerShell)
```powershell
cd lay
py -3.11 -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # pon tu ANTHROPIC_API_KEY
python -m pytest -q; python scripts/verificar_mcp.py
```
Opcional y recomendado: [Everything](https://www.voidtools.com) + `es.exe` en el PATH (búsqueda instantánea).
Si `pyaudio` falla: `pip install pipwin; pipwin install pyaudio`.

## Usar
| Comando | Qué hace |
|---|---|
| `python lay.py` | Todo: hub + gestos + voz + HUD a pantalla completa |
| `python lay.py --texto` | Sin micrófono (escribes en consola) |
| `python lay.py --sin-camara` | Sin gestos |
| `python -m loops.gestos --debug` | Calibrar manos viendo la cámara |
| `python -m loops.gestos --mouse` | Controlar el escritorio con la mano |

Frases de prueba: "LAY, ¿cómo está el PC?" · "LAY, modo trabajo" · "LAY, busca el presupuesto de Chancay y ábrelo" · "LAY, muéstrame mis fotos" · "LAY, ¿qué tengo pendiente en Blackboard?" · "LAY, piensa bien: resume y prioriza mis correos de hoy".

## Conectar el MCP a Claude Desktop
`%APPDATA%\Claude\claude_desktop_config.json`:
```json
{"mcpServers": {"lay-pc": {"command": "C:\\ruta\\lay\\.venv\\Scripts\\python.exe",
  "args": ["-m", "lay_mcp.server"], "cwd": "C:\\ruta\\lay"}}}
```
En Claude Code ya está en `.mcp.json`.

## Remoto (celular)
1. Tailscale en PC y celular. 2. En `.env`: `LAY_HUB_TOKEN`, `LAY_MCP_TOKEN`, `LAY_BIND=<IP 100.x de Tailscale>`.
3. Comando desde el celular (Atajos de iPhone / HTTP Shortcuts en Android):
   `POST http://<pc>:8765/api/comando` · header `Authorization: Bearer <LAY_HUB_TOKEN>` · body `{"texto":"abre mi workspace de trabajo"}`.
4. MCP remoto: `python -m lay_mcp.server --http --port 8766` → `http://<pc>:8766/mcp` con el token.

## Desarrollo con Claude Code
Lee `PROMPT_MAESTRO.md`. Estructura en `CLAUDE.md`, fases en `PLAN.md`.

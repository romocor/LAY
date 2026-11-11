# PLAN LAY v2 — de Centro de Mando a asistente con manos y voz

Modelo por defecto: **Sonnet** (mecánico). **Opus** solo donde hay algoritmo, tiempo real o seguridad.
Cada fase se ejecuta con `/fase N` (loop planificar → implementar → verificar → corregir, máx. 3 vueltas).
**Cada fase termina con `/exe`: se entrega `LAY_Setup_2.<fase>.0.exe` + portable `.zip`.** La aceptación se prueba sobre el exe instalado, no sobre `python lay.py`.

| Fase | Qué | Subagentes | Modelo / esfuerzo |
|---|---|---|---|
| 0 | Arranque e integración | lay-arquitecto → lay-mcp, lay-ui | Opus high → Sonnet |
| 1 | Escritorio y archivos | lay-escritorio | Sonnet low |
| 2 | Voz conversacional | lay-voz | Opus medium |
| 3 | Gestos + overlay | lay-vision, lay-ui | Opus high + Sonnet |
| 4 | Correo y Blackboard | lay-integraciones | Sonnet medium |
| 5 | Remoto | lay-mcp → lay-seguridad | Sonnet → Opus high |
| 6 | Pulido y rendimiento | lay-qa, lay-vision | Sonnet low + Opus |

---

## Fase 0 — Arranque e integración
- [ ] Crear venv, `pip install -r requirements.txt`, `.env` desde `.env.example`.
- [ ] `python scripts/verificar_mcp.py` y `python -m pytest -q` en verde en Windows.
- [ ] Copiar `lay/` dentro del repo `centro_mando/` (o `pip install -e`), renombrar JARVIS → LAY (22 apariciones en `.py`: `grep -rn JARVIS`).
- [ ] Registrar `integracion/ai/tools/lay_pc_tools.py` en el ToolManager y `integracion/ai/core/model_router.py` en `AnthropicProvider.send()`.
- [ ] La vista Asistente del Centro de Mando abre `python lay.py` (botón "Abrir LAY HUD").
- [ ] Conectar el MCP `lay-pc` a Claude Desktop (`claude_desktop_config.json`) y Claude Code (`.mcp.json`).
- [ ] `build_exe.ps1` genera `LAY_Setup_2.0.0.exe`; Claude Desktop apunta a `LAY-cli.exe --rol mcp`.
- [ ] Workflow `build-exe` en GitHub Actions en verde (artefacto descargable).
**Aceptación:** con LAY instalado desde el exe, desde el panel Flet y desde Claude Desktop, "¿cuánta RAM tengo?" responde con datos reales.

## Fase 1 — Escritorio y archivos  (código listo v2.1.0 · falta prueba en tu PC + exe)
- [x] DPI per-monitor (escala 125-150 % ya no descuadra ventanas).
- [x] Workspaces en paralelo (lanza todo y acomoda cada ventana apenas aparece, máx. 12 s).
- [x] Posición `maximizada`; monitor inexistente → usa el último con aviso (laptop sola).
- [x] Elección de ventana: visible > título exacto > más grande; nunca toca el HUD de LAY.
- [x] Swipe del overlay → monitor vecino real (izq/der del cursor), sin números fijos.
- [x] Herramienta `archivos_abrir_por_nombre` ("abre el presupuesto de Chancay" en 1 paso).
- [x] Everything detectado también en Program Files / LocalAppData.
- [x] 13 tests nuevos (3 monitores simulados, workspaces, búsqueda).
- [ ] Instalar Everything + `es.exe`; probar `archivos_buscar` en < 1 s.
- [ ] Ajustar `config/lay.json`: apps reales y workspaces `trabajo`, `programar`, `estudio` con tus 3 monitores.
- [ ] `workspace_aplicar("trabajo")` abre y acomoda las 3 apps (referencia: video de monitores).
- [ ] `teclado_escribir` con tildes/ñ en Word y en el navegador.
- [ ] Tests con pygetwindow/screeninfo simulados.
**Aceptación:** "LAY, modo trabajo" deja Outlook/Excel/Power BI en sus monitores en < 6 s.

## Fase 2 — Voz conversacional  (código listo v2.2.0 · falta prueba en tu PC + exe)
- [x] Palabra clave offline con Vosk (gramática cerrada, umbral `confianza_wake`); el audio ya no va a Google hasta que dices "LAY".
- [x] "LAY" solo cuenta como 1.ª palabra o tras "oye/hola/ok" ("la ley de contrataciones…" no la activa).
- [x] Pre-roll de 1 s: "LAY, abre Spotify" de un tirón no pierde palabras.
- [x] Respuesta en streaming → habla desde la primera frase mientras el modelo sigue; frase corta tipo "Abriendo Excel." antes de usar herramientas.
- [x] Interrupción: "LAY, para / detente / silencio / basta", puño 1 s o Esc en el HUD; descarta lo que el modelo siga generando.
- [x] LAY no se escucha a sí misma (mientras piensa/habla solo atiende "LAY, para"; vacía el eco al terminar).
- [x] Ventana abierta 8 s tras responder para seguir sin repetir "LAY" (anillo blanco en el HUD).
- [x] "No / cancela" anula una confirmación pendiente.
- [x] Latencia (fin de tu frase → primera palabra) en el HUD; ámbar si > 1,5 s.
- [x] Bug corregido: el recorte del historial podía romper la API en conversaciones largas.
- [x] Modelo Vosk empaquetado en el exe (build_exe.ps1 lo descarga); 13 tests nuevos.
- [ ] Calibrar `confianza_wake` con tu micrófono (10 min sin falsos positivos).
- [ ] Medir latencia real < 1,5 s en tareas rápidas.
**Aceptación:** conversación de 5 turnos con búsqueda, apertura de archivo y un borrador de correo.

## Fase 3 — Gestos + overlay holográfico  (código listo v2.3.0 · falta prueba en tu PC + exe)
- [x] Bug: manos invertidas (MediaPipe asume imagen espejo) → frame volteado antes de procesar; ya mueve el mouse tu mano derecha.
- [x] Bug: modo mouse limitado al monitor principal → mapea al escritorio virtual de los 3 monitores (incluye coordenadas negativas).
- [x] Filtro One Euro afinado (≈20 px de temblor en 3 monitores, sin retraso) + zona muerta de 6 px para hacer clic.
- [x] Gesto nuevo: dos dedos arriba/abajo = scroll (rueda real en modo mouse).
- [x] Puño 0,7 s calla a LAY; puño 2 s pausa el seguimiento (antes chocaban).
- [x] Calibración guiada: `LAY-cli --rol gestos --calibrar` (30 s) guarda tus umbrales en lay.json.
- [x] FPS de la cámara y reconexión automática si se desconecta (HUD avisa).
- [x] HUD se minimiza al entrar en modo mouse y vuelve al salir.
- [x] Miniaturas cacheadas (fotos de 12 MP → ~20 KB) y versión HD solo al abrir una tarjeta.
- [x] "Muéstrame las fotos de la obra Chancay" busca la carpeta por nombre (ignora carpetas sin fotos).
- [x] Grilla que nunca tapa el núcleo ni el diálogo (verificado en 4 resoluciones × 4/12/24 fotos).
- [x] Bug: un mensaje mal formado desconectaba el HUD del hub; ahora se ignora y los errores salen en pantalla.
- [x] Verificado en navegador real: tap abre en HD, escalar, cerrar, rotar 3D, clap en anillo, swipe, modo.
- [ ] `--calibrar` con tu cámara y luz.
- [ ] "LAY, muéstrame las fotos de la obra" → tarjetas en el overlay (`overlay_mostrar_imagenes`).
- [ ] Pinch/drag/escala/rotar/clap/swipe funcionando (referencia: video de tarjetas flotantes).
- [ ] Swipe lanza la imagen al monitor correcto (mapear izquierda/derecha según `monitores_listar`).
- [ ] Modo mouse: abrir carpetas del explorador con doble tap; FAILSAFE activo.
- [ ] Fluidez: ≥ 25 fps de seguimiento, overlay a 60 fps.
**Aceptación:** demo de 1 min sin tocar teclado ni mouse: abrir galería, ampliar, rotar, mandar una foto al monitor 3, abrir una carpeta.

## Fase 4 — Correo y Blackboard  (código listo v2.4.0)
- [x] Asistente de configuración (`LAY-cli --rol configurar`); se abre solo la primera vez que abres LAY.exe sin clave.
- [x] Leer correo completo (Gmail/Outlook; HTML → texto).
- [x] Responder en el MISMO hilo como borrador (Gmail: In-Reply-To/References/threadId; Outlook: createReply/All).
- [x] Enviar borrador = acción sensible con confirmación.
- [x] `correo_resumen`: Gmail + Outlook juntos; si una cuenta falla sigue con la otra. Router → Opus.
- [x] Anti prompt-injection: contenido de correos marcado como externo + tests (un correo que pide reenviar no logra enviar).
- [x] Panel en el HUD (`hud_panel`) con la lista mientras LAY habla; HTML de terceros siempre escapado.
- [x] Blackboard: caché 10 min, "hoy / mañana / en N días".
- [x] Bug: remitentes con tilde rompían la cabecera Para (el correo podía rebotar) → EmailMessage.
- [x] 15 tests nuevos (63 en total).
- [ ] OAuth Gmail y Outlook (PUCP) funcionando; tokens en `~/.lay`.
- [ ] "Resúmeme los correos de hoy" → 3 frases + prioridades (Opus).
- [ ] "Responde a X que…" → borrador leído en voz alta → enviar con confirmación.
- [ ] Feed iCal de Blackboard: "¿qué tengo pendiente esta semana?".
- [ ] Vista Correos/Universidad del Centro de Mando con datos reales.
**Aceptación:** ningún correo sale sin un "sí" de Robert (test + prueba manual).

## v2.5.0 — Pedidos de Robert (antes de Fase 5)
- [x] IA GRATIS: Ollama local por defecto; Gemini/Groq gratis con clave; Claude solo opcional (y nunca respaldo sin permiso).
- [x] El .exe instala la IA en CUALQUIER laptop: detecta RAM/GPU, instala Ollama en silencio y baja qwen2.5 1.5b/3b/7b.
- [x] Configuración DENTRO de la app (⚙ o tecla C o "LAY, abre configuración"): IA, Blackboard, correo, palmadas, voz, remoto. Se abre sola la primera vez.
- [x] Abrir LAY con dos palmadas (detector offline, arranca con Windows); triple palmada = workspace/app.
- [x] Filtro de herramientas por tema para modelos locales chicos; herramientas inventadas no se ejecutan.
- [x] Bug: monitores de Robert (uno ARRIBA de la laptop) → principal = 1, vecino por geometría, swipe vertical.
- [x] Bug: ajustes parciales borraban los valores por defecto de su sección.

## Fase 5 — Remoto  (código listo v2.5.0)
- [x] Guardia del hub: desde fuera solo /remoto, /api/comando y /ws de lectura, con token y solo Tailscale (antes /ws y /archivo quedaban expuestos).
- [x] Página del celular con QR, token en el #fragmento, dictado por voz del celular y atajos.
- [x] Tests de seguridad remota (IP de wifi, sin token, rutas internas, WS de solo lectura).
- [ ] Tailscale en PC y celular; `LAY_BIND` = IP de Tailscale.
- [ ] Hub `/api/comando` con `LAY_HUB_TOKEN`: atajo de iPhone/Android que manda texto a LAY.
- [ ] MCP por HTTP (`--http`) con `LAY_MCP_TOKEN` para usar LAY desde Claude en el celular.
- [ ] Revisión `lay-seguridad` antes de habilitar.
**Aceptación:** desde el celular fuera de casa: "LAY, ¿cómo está el PC?" responde; sin token → 401.

## v2.6.0 — Navegar todo + IA propia + funciones de GitHub
- [x] IA PROPIA de LAY: modelos Ollama `lay` y `lay-rapido` (Qwen 2.5 + identidad, ejemplos y contexto 8k); se crean al instalar.
- [x] Navegador: Brave/Chrome/Edge con perfil LAY (abrir, buscar, leer, elementos, clic, escribir, pestañas); pagar/enviar con confirmación; contraseñas nunca.
- [x] Windows completo: UI Automation (botones/menús de CUALQUIER app por nombre, "Guardar" ≠ "No guardar"), apps instaladas por nombre, ajustes ms-settings, volumen, multimedia, brillo, energía con confirmación.
- [x] Investigado en GitHub (isair/jarvis, GauravSingh9356/J.A.R.V.I.S, clawdcursor, AnubhavChaturvedi): web gratis (DuckDuckGo + Wikipedia), clima (Open-Meteo), recordatorios/alarmas/temporizadores con voz y notificación, memoria de largo plazo con bloqueo de secretos.
- [ ] Próximas ideas de GitHub: dictado con tecla (offline, pegar en cualquier app), leer la pantalla con OCR de Windows, visión con cámara (modelo local multimodal), WhatsApp Web, Home Assistant.

## v2.9.0 — Música de verdad, control de cualquier app, puntería de manos
- [x] "pon X" / "reproduce X en Spotify": busca la canción, la abre en la app y verifica que suene (título de ventana); si Spotify solo muestra la página, pulsa Reproducir por UI Automation. Antes solo hacía play/pausa de lo que ya sonaba.
- [x] "pon el video de X" / "abre youtube y pon X": primer video de YouTube, que suena solo.
- [x] "busca X en <app>" (Outlook, Explorador, WhatsApp, Teams, VS Code, Spotify…): caja de búsqueda por UI Automation o el atajo de esa app.
- [x] "haz clic en <botón>" / "pulsa <botón>" sobre la app que tienes al frente (ventana="activa").
- [x] Navegador: por defecto abre en TU Brave/Chrome (tus cuentas); leer = misma página por internet, clic/escribir = UI Automation sobre la ventana. Perfil de LAY opcional para control total con Playwright.
- [x] Manos: zona activa (las esquinas de la pantalla ya se alcanzan), el esqueleto dibujado coincide con el cursor, y al pellizcar el cursor se congela donde apuntabas (antes el clic se corría).
- [x] Diagnóstico: canciones en Spotify/YouTube y clic en la ventana activa.

## v2.8.0 — Rendimiento, cámara bajo demanda, gestos entrenables, navegador fiable
- [x] Navegador: abrir una web o búsqueda ya no depende de Playwright (lanza Brave/Chrome directo, instantáneo). Playwright solo para leer/clicar, con tiempo límite, auto-reinicio si se cuelga y errores legibles (antes: "ToolError" vacío).
- [x] "busca youtube" abre YouTube; "busca en youtube X" busca X.
- [x] Cámara SOLO cuando se pide: "LAY, activa/desactiva la cámara", Configuración → Manos, o la bandeja. Opción "encender al abrir LAY".
- [x] Manos que se quedaban congeladas en pantalla: vigilante en el HUD + aviso al apagar la cámara.
- [x] Rendimiento cámara: 640x480 MJPG, hilo lector (siempre el cuadro más nuevo), modelo ligero, ~8 fps en reposo sin manos, datos de manos redondeados y sin repetir vacíos.
- [x] Rendimiento hub: cola por cliente (un cliente lento ya no traba a todos) y suscripción por tipo (gestos y voz ya no reciben 30 cuadros/s de manos). Era la causa de los tirones.
- [x] Rendimiento HUD: sin drop-shadow animado, sombras livianas, manos dibujadas una vez por cuadro, animaciones en pausa al explorar o minimizar, explorador paginado (22 por página), miniaturas más chicas.
- [x] Sin ventanas de cmd: todo subprocess de LAY nace oculto (powershell, ollama, Everything…).
- [x] Ollama en modo ahorro: 1 conversación en paralelo, 1 modelo, se libera de la RAM a los 3 min sin uso.
- [x] Gestos entrenables: "LAY, entrena un gesto para abrir Spotify" o Configuración → Manos → Grabar. Acción = orden para LAY o atajo de teclado. Vecino más cercano sobre puntos normalizados (idea de Kazuhito00/hand-gesture-recognition-using-mediapipe), sin TensorFlow.

## v2.7.0 — LAY Núcleo (IA desde cero) + manos tipo Tony Stark + diagnóstico real
- [x] LAY Núcleo: IA propia hecha desde cero (numpy, sin Ollama ni internet). 38 intenciones, 8360 frases de entrenamiento, 100 % en frases nuevas escritas a mano. Extrae datos (app, carpeta, volumen, ciudad, hora…), planea herramientas y responde con los resultados reales.
- [x] Modo híbrido (por defecto): órdenes → Núcleo al instante; charla → la IA elegida. Si Ollama se cae, el Núcleo responde igual (último respaldo gratis).
- [x] Respuestas más completas: búsqueda web previa para preguntas actuales (información al día), 2–4 frases útiles, nunca "no puedo" a secas.
- [x] "Busca en mi navegador": abre Brave/Chrome con la búsqueda y además lee los resultados.
- [x] Manos tipo Tony Stark: DOS PALMAS 1,2 s → escaneo biométrico → explorador holográfico de carpetas e imágenes (tap carpeta = entrar, tap imagen = ampliar, doble tap = abrir en Windows, swipe = otro monitor, ◀ atrás, ✕ cerrar). También con mouse y tecla E.
- [x] "LAY, activa las manos en Descargas" → herramienta `manos_activar`.
- [x] Causas reales arregladas: matplotlib excluido rompía MediaPipe en el exe (las manos nunca arrancaban); modelos pequeños escribían la herramienta como texto; consola cp1252 tumbaba el exe con "✓".
- [x] Diagnóstico (Configuración → 🩺 o "LAY, haz un diagnóstico") y diagnóstico automático del exe en Windows real en cada build.
- [ ] Siguiente: Núcleo aprende de Robert (frases corregidas → reentrena en la PC), dictado offline, OCR de pantalla.

## Fase 6 — Pulido  (v2.6.0)
- [x] Icono en la bandeja: abrir, configuración, pausar cámara/micrófono, salir.
- [x] Aviso de versión nueva (requiere Releases públicos).
- [ ] Arranque con Windows (tarea programada o acceso directo en `shell:startup`).
- [ ] Bandeja del sistema con encender/apagar cámara y micrófono.
- [ ] `/loop 30m /salud` mientras desarrollas.
- [ ] Firma de código del exe (opcional, evita el aviso de SmartScreen).
- [ ] Auto-actualización: LAY revisa el último Release de GitHub al iniciar.

# Cómo hablarle a LAY

LAY tiene dos cerebros:

- **LAY Núcleo**: IA propia, sin internet. Ejecuta las órdenes al instante.
- **La IA conversacional**: Ollama, Gemini u otra. Responde la charla y lo que el Núcleo no entiende.

No hace falta hablar "de memoria": puedes decir las cosas de varias formas. Esta guía muestra frases que entiende seguro y cómo enseñarle las tuyas.

> **Palabra para despertarla:** "LAY…" (también entiende "Ley" y "Lei").
> Puedes decirlo junto con la orden: "LAY, pon Nadie Sabe".
> **Para escribirle:** botón **💬 CHAT** o tecla **T**.

---

## 1. Música (Spotify y YouTube)

| Lo que quieres | Dilo así (cualquiera sirve) |
|---|---|
| Poner una canción | "pon Nadie Sabe de Bad Bunny" · "reproduce Despacito" · "quiero escuchar La Flaca" · "toca algo de Mora" |
| Poner un artista | "pon música de Soda Stereo" · "ponme algo de Pedro Suárez-Vértiz" |
| Una playlist | "pon la playlist de gimnasio" · "ponme mi playlist de concentración" |
| Un disco | "pon el disco Un Verano Sin Ti" |
| En YouTube | "pon el video de Bohemian Rhapsody" · "pon lofi en YouTube" · "abre YouTube y pon lofi" |
| Solo buscar en Spotify | "busca Bad Bunny en Spotify" |
| Controlar lo que suena | "pausa la música" · "siguiente canción" · "la anterior" · "sube el volumen" · "volumen al 30" |

**Consejos:**

- Di primero la canción y después el artista: "Nadie Sabe de Bad Bunny".
- No hace falta decir "en Spotify": si no dices YouTube o "video", va a Spotify.
- Si el reconocimiento de voz escribe "espotify", "spoti" o "yutub", LAY igual lo entiende.

## 2. Abrir y controlar cualquier app

| Lo que quieres | Dilo así |
|---|---|
| Abrir una app | "abre Revit" · "ábreme Excel" · "abre Spotify" · "inicia Teams" |
| Buscar dentro de una app | "busca facturas en Outlook" · "busca el contrato en el Explorador" · "en WhatsApp busca Carlos" |
| Hacer clic en un botón de la app que tienes delante | "haz clic en Guardar" · "pulsa Aceptar" · "dale a Siguiente" · "selecciona Insertar" |
| Escribir donde está el cursor | "escribe Hola Carlos, te envío el informe" |
| Mover una ventana | "pon Chrome en el monitor de arriba" · "manda Excel al monitor derecho" |
| Captura de pantalla | "toma una captura" |
| Bloquear o apagar | "bloquea la PC" · "apaga la PC" (pide confirmación) |

## 3. Navegador e internet

| Lo que quieres | Dilo así |
|---|---|
| Buscar en Google (en **tu** Brave o Chrome) | "busca en Google precio del cemento" · "busca recetas de ceviche" |
| Abrir una web | "abre YouTube" · "entra a Blackboard" · "ve a Gmail" |
| Preguntar algo actual | "quién ganó el partido de ayer" · "cuánto está el dólar hoy" · "qué es el BIM 5D" |
| Clima | "cómo está el clima" · "va a llover en Cusco" |

## 4. Archivos y carpetas

- "abre la carpeta de descargas" · "abre mis documentos"
- "busca el plano de la casa en mi PC" · "dónde está el presupuesto de la obra"
- "muéstrame las fotos de la obra" (las pone en el holograma)

## 5. Manos y cámara

| Lo que quieres | Dilo o hazlo así |
|---|---|
| Encender / apagar la cámara | "LAY, activa la cámara" · "desactiva la cámara" |
| Explorador holográfico | Muestra **las dos palmas** 1 segundo, o di "activa el modo manos" |
| Gesto propio | "entrena un gesto para abrir Spotify" → haz la pose y mantenla quieta unos 2 segundos |
| Ver tus gestos | "qué gestos tengo" |

## 6. PC, recordatorios y memoria

- "cómo está la PC" · "qué programas consumen más"
- "recuérdame llamar a Pérez en 20 minutos" · "pon un temporizador de 15 minutos" · "qué recordatorios tengo"
- "recuerda que mi jefe se llama Carlos" · "qué sabes de mí"
- "revisa mis correos" · "qué tengo pendiente en Blackboard"

## 7. Personalidad (cómo te habla)

- "cambia tu personalidad a Jarvis" · "habla como el pata limeño" · "ponte en modo ingeniero" · "personalidad profesor" · "modo coach" · "personalidad neutral"
- Personalidad propia: **Configuración → 🎭 Personalidad**. Describe cómo es y agrega ejemplos de "tú dices → LAY responde". Con 5 a 10 ejemplos toma tu estilo.
- La personalidad cambia solo el tono. Las confirmaciones de seguridad siguen igual.

## 8. Tus libros, documentos y fotos

1. **Configuración → 📚 Conocimiento**: pega la ruta de un PDF, EPUB, DOCX, TXT, o de una carpeta entera (por ejemplo, la carpeta del Reglamento Nacional de Edificaciones).
2. LAY lo lee en segundo plano y te avisa cuando termina.
3. Pregúntale:
   - "qué dice mi libro sobre el curado del concreto"
   - "busca en mis documentos recubrimiento mínimo"
   - "qué dice la norma sobre escaleras de evacuación"

   Te responde citando el documento y la página.

**Fotos:** en **🦙 Modelos locales**, descarga **moondream** (1,7 GB). Desde entonces LAY "mira" cada foto que le das y la describe, para que luego le preguntes "¿en qué foto aparece la grúa?".

**Búsqueda por significado** (entiende sinónimos, no solo palabras exactas): descarga **nomic-embed-text** (0,3 GB) en Modelos locales.

> Es "enseñarle a leer", no re-entrenar el cerebro de la IA. Re-entrenar un modelo con libros enteros requiere una GPU potente y días de cálculo. Lo que hace LAY es la técnica estándar: busca el fragmento que hace falta y responde con él. Es gratis, funciona sin internet y siempre cita la fuente.

## 9. Enseñarle tus propias frases (aprende contigo)

LAY aprende de tres formas:

**a) Sola, mientras la usas.** Cuando el Núcleo no entiende una orden y la IA grande la resuelve bien, LAY guarda tu frase. Cada 5 frases nuevas se re-entrena sola en segundo plano (unos 15 segundos). En el chat verás "✓ aprendió esta frase".

**b) Corrigiéndola.** Si entendió otra cosa, abre el **chat** (tecla T). Debajo de su respuesta está el menú **"corregir…"**: elige lo que querías decir y lo aprende al momento.

**c) Atajos de voz (tus frases mágicas).** Funcionan al instante:

- "cuando diga **modo obra** abre Revit y luego abre Excel y luego abre la carpeta proyectos"
- "cuando diga **hora de concentrarme** pon lofi y luego baja el volumen"
- "aprende que **lo de siempre** es pon mi playlist de gimnasio"

Después, basta con decir "modo obra". Puedes encadenar hasta 8 órdenes con "y luego". Los atajos se ven y se borran en **Configuración → 🎓 Aprendizaje**.

## 10. Si algo no funciona

- **"LAY, haz un diagnóstico"** o el botón 🩺 en Configuración → Inteligencia. Prueba manos, cámara, micrófono, voz, navegador, apps, música y permisos.
- **Configuración → 🛡 Permisos** te dice si Windows bloquea algo:
  - **Cámara o micrófono bloqueados para apps de escritorio:** te lleva directo a la opción de privacidad para activarlos.
  - **Ventanas de administrador** (Administrador de tareas, instaladores, apps "Ejecutar como administrador"): Windows no deja que un programa normal las controle. Activa **"Modo administrador"** (Windows pide permiso una sola vez) para que LAY arranque con permisos completos.
  - **Lo único que ninguna app puede hacer:** aceptar la ventana de UAC por ti. Es una protección de Windows.
- Si LAY no entiende algo, díselo de otra forma **una vez** y corrígela en el chat. Se acordará.

## 11. Teclas rápidas

**T** chat · **C** configuración · **E** explorador de carpetas · **R** reordenar tarjetas · **D** ayuda · **Esc** callar a LAY

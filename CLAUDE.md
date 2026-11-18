# Pipeline de videos stickman (leyendas, misterios, historias raras)

Reglas del usuario: Claude no publica en YouTube (el usuario sube los videos a su canal); no subir datos
personales. Formato parecido a los videos educativos ilustrados (planos ilustrados del tema, cortes
cada ~5 s, palabras clave escritas a mano, tarjetas con fondo blanco), pero sin copiar personajes,
nombres ni marca de otro canal. Protagonista propio: **Sticky**, stickman blanco con **bufanda azul**
(su logo). Público: niños, jóvenes y adultos → sin sangre ni violencia explícita.
Si algo falla, detenerse y explicar qué falló antes de seguir.

Cuando el usuario da una historia o tema, usar la skill `hacer-video` (`.claude/skills/hacer-video/`):
él solo da la historia; Claude hace guion, imágenes, clips, video y Shorts sin pedir pasos intermedios.
Cada historia = **3 videos**: el largo + 2 Shorts verticales. **3 clips de Flow por video** (~27 puntos).

## Carpetas

Cada video vive en `videos/<nombre>/`: `guion.md`, `trabajo/` (audios, imágenes, `flow/`),
`video.mp4`, `shorts/` (con `short_1.mp4` y `short_2.mp4`), `video.srt` (subtítulos para subir a YouTube) y `reporte.md`.
Al final de cada video y Short se pega solo un **cierre animado** (Sticky dice "suscríbete", clic en el botón y
campanita): `pipeline/outro.py`, textos en `config.json` → `outro`, se guarda en `recursos/`.
Sticky animado por código (vectorial, cairo): `pipeline/animacion.py` (muñeco, caras, poses);
prueba de 30 s en `prueba_animada.py` → `videos/prueba-animada/video.mp4`.
Los videos llevan subtítulos palabra por palabra quemados, whoosh en cada cambio de imagen y un
segundo encuadre (punch-in) en las escenas largas; la voz va a +8% y sin silencios entre frases.

## Guion (`videos/<nombre>/guion.md`)

- Una frase = una escena (~5 s). `#` títulos y `<!-- -->` no se narran.
- `@Nombre: descripción` define un personaje o lugar; en las imágenes se usa `{Nombre}` para que se
  dibuje siempre igual. `{Sticky}` ya está definido en `config.json`.
- `[[imagen=qué muestra la ilustración; texto=Palabra clave; tarjeta=si]]` antes de la frase.
  Las frases sin `imagen` siguen con la imagen anterior (otro encuadre). `tarjeta=si` = dibujo
  sencillo sobre fondo blanco. Separar opciones con `;` (no usar `;` dentro de la descripción).
- `clip=movimiento` anima esa imagen en Flow (3 por video). `short=1|Título` / `short=2|Título` donde
  empieza cada Short y `short=fin` donde termina (máx. 58 s cada uno).
- **Modo presentador** (`config.json` → `presentador`, por defecto activo): en ~80% de las escenas Sticky animado
  explica de pie (habla con la voz, gestos, caras según la frase) y la ilustración de Flow va en un recuadro sobre fondo
  plano; 1 de cada 5 imágenes, los clips y las tarjetas van a pantalla completa. Videos de **10-15 min** (2.300-2.800 palabras).
- **Modo mixto** (capas animadas por código, `pipeline/capas.py`): `anim=sticky|explica|sorpresa|miedo|feliz|correr`
  pone a Sticky animado (habla con la voz) encima de la ilustración (usar imágenes SIN Sticky en esas escenas);
  `anim=velocidad|Título|Nombre:valor|...` tarjeta a pantalla completa con barras que crecen (km/h, escala log);
  `hud=TEXTO` marcador fijo arriba a la izquierda (ej. `hud=DÍA 3 · 60 KM/H`).
- Nunca dibujar personajes de otras marcas (Sonic, Flash, etc.): se nombran y comparan, pero no se dibujan ni sus
  emblemas (riesgo de reclamos de derechos en YouTube).
- Flow rechaza a veces prompts de "mujer joven bonita/seductora", armas o caras de furia: describir
  sin esos elementos (ej. "muchacha campesina con vestido blanco", tormenta en vez de machete).

## Producir un video (rutina; ahorra tokens)

1. Escribir `videos/<nombre>/guion.md`.
2. `python generar_video.py <nombre> --hasta voz` (escenas + narración). Revisar escenas y duración.
3. `python -m pipeline.flow exportar` → `videos/<nombre>/trabajo/flow_pendientes.json` (solo planos sin imagen).
4. Imágenes en Google Flow con **Claude in Chrome** (el navegador de la app no guarda descargas):
   - `tabs_context_mcp` y abrir el proyecto de Flow
     (`https://flow.google.com/project/052b2428-ad17-4352-a16c-980d62878b34` o uno nuevo).
   - Comprobar en Flow: Imagen, Nano Banana, 16:9, **x1**, botón "Agente" desactivado.
   - Inyectar `pipeline/flow_runner.js` con `javascript_tool` (pegar el contenido del archivo).
   - `find` "Lista de prompts flowRunner, Iniciar generación button" → refs del input y del botón.
     `file_upload` del `flow_pendientes.json` (ruta absoluta) en el input.
   - **Flow solo acepta un clic REAL** en "Iniciar generación". Clic SIEMPRE con el `ref` del botón,
     nunca con coordenadas (un clic en la cuadrícula abre una imagen vieja). En un `browser_batch`,
     repetir **4 veces** (más no cabe en el tiempo límite del batch):
       1. `javascript_tool`: `await flowRunner.preparar()`  ("FIN" = no quedan)
       2. `computer` `left_click` con `ref` del botón "Iniciar generación"
       3. `javascript_tool`: `await flowRunner.esperar(40000)`  (~25 s, descarga y avanza)
     Respuestas: `OK` seguir; `TARDA` llamar `esperar(30000)` otra vez (si sigue igual, el clic no
     llegó: captura y repetir el clic); `RECHAZADA` Flow no la acepta (se salta sola: cambiar esa
     `imagen` en el guion y rehacerla al final); `ERROR` parar y revisar con una captura.
   - Nunca hacer dos clics para la misma escena: si llegan dos imágenes, la segunda se guarda con el
     nombre de la escena siguiente y todo queda corrido una posición.
   - Si un batch se corta, llamar primero `await flowRunner.esperar(40000)` para recoger la imagen que
     quedó generándose, antes del siguiente `preparar()`.
   - No hacer capturas si todo va OK (ahorra tokens). Estado: `flowRunner.resumen()`.
5. `python -m pipeline.flow importar` → mueve las descargas a `videos/<nombre>/trabajo/flow/`.
   **Revisar** una hoja de contacto de `trabajo/flow/` (miniaturas con su número) contra los `imagen=`
   del guion antes de montar: si hay imágenes corridas, renombrarlas y rehacer solo las que falten.
   Si faltan (rechazadas), corregir el guion, `python generar_video.py <nombre> --hasta voz`
   (el audio está en caché), y repetir 3-5: solo se exportan las que faltan.
5b. Clips de video (opcional, **cuestan puntos**: 9 por clip de 3 s en 720p; el usuario tiene 1.000
   al mes y aprobó 6-8 clips por video). En el guion: `clip=movimiento` dentro del `[[...]]` de una
   escena con `imagen`. `python -m pipeline.flow clips` lista los pendientes (escena, huella, prompt).
   En Flow: ajustes → Video → Fotogramas, 16:9, Omni 1.2 Flash, 720p, 3 s, x1 ("9 puntos").
   Inyectar `pipeline/flow_clips.js` y seguir los pasos de su encabezado, un clip a la vez:
   la imagen se elige de la lista del proyecto por su huella (no usar "Subir archivo": pide aceptar
   un aviso de derechos). Después de cada descarga: `python -m pipeline.flow clip NNN`.
   Al terminar, volver Flow a modo Imagen (Nano Banana, x1, "0 puntos").
6. `python generar_video.py <nombre> --desde imagenes` → `videos/<nombre>/video.mp4` y `reporte.md`.
   Si dura menos de 10 min, usar `--prueba` (la duración solo da aviso).
7. Cerrar la pestaña de Chrome que se abrió.

Chrome debe tener permitidas las descargas múltiples para flow.google.com (ya lo está).

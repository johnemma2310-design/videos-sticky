---
name: hacer-video
description: Hace un video completo de Sticky a partir de una historia o tema (guion, imágenes y 3 clips en Google Flow, video largo, 2 Shorts verticales). Usar cuando el usuario da una historia, leyenda o tema y pide el video.
---

# Hacer un video a partir de una historia

El usuario solo da la historia o el tema. Todo lo demás lo haces tú, siguiendo `CLAUDE.md`.
Detente y explica solo si algo falla.

## 1. Guion (`videos/<nombre>/guion.md`)

- `<nombre>`: en minúsculas, con guiones (ej. `la-llorona`).
- Si el usuario solo da un tema, investiga con WebSearch: usa 2-3 fuentes y no inventes datos. Cuando las versiones de una leyenda no coinciden, di "según algunas versiones".
- Tamaño: **2.300-2.800 palabras** (la voz va a ~210 palabras/min). El video DEBE durar entre 10 y 15 minutos: después de `--hasta voz`, si `duracion_total` < 10 min, alarga el guion antes de pedir imágenes.
- Una frase = una escena de ~4-6 s. Usa frases cortas y fáciles de narrar.
- Estructura, como en `videos/la-patasola/guion.md`:
  1. Gancho de miedo o misterio.
  2. Presentación de Sticky.
  3. Origen.
  4. Cómo es.
  5. Señales o datos curiosos.
  6. Un relato dramatizado.
  7. Otras versiones o comparación.
  8. Por qué existe la historia (lección).
  9. Cierre con pregunta para comentarios.
- Público: niños, jóvenes y adultos. Sin sangre, armas en uso ni violencia explícita.
- Al inicio, define `@Personaje: descripción` para cada personaje o lugar que se repite.
- Pon `[[imagen=...]]` cada 1-2 frases; las demás siguen el plano anterior.
  - Usa `texto=` con palabras clave en ~1 de cada 6 imágenes.
  - Usa `tarjeta=si` en las explicaciones (listas, mapas, conceptos).
- **Animaciones vectoriales SIEMPRE** (el usuario las pidió expresamente): en cada video incluye, además de las imágenes de Flow,
  al menos 3-5 tarjetas animadas por código (`anim=velocidad|...` u otras de datos), un `hud=` si hay contador, y 4-6 escenas
  de Sticky animado por código (`anim=sticky|accion`) sobre imágenes SIN Sticky (para no duplicarlo). El cierre animado de
  suscripción va solo. Si hace falta una animación nueva (ej. otra gráfica), prográmala en `pipeline/capas.py`.
- **Sticky va DENTRO de ~80% de las imágenes**: escribe `{Sticky}` haciendo algo en la escena (corre, señala, se sorprende, flota en el espacio). Todas las personas son stickman (la regla ya está en `flow.estilo`); no pidas caras en planetas, animales ni objetos. El modo presentador está apagado (no le gustó al usuario).
- Si agregas frases al guion después de generar imágenes, la numeración de escenas cambia: reasigna las imágenes de `trabajo/flow/` por su prompt antes de montar (si no, quedan corridas).
- Modo mixto (el que más le gustó al usuario): ~1 de cada 6 escenas con `anim=sticky|accion` (sobre imágenes sin Sticky),
  1-3 tarjetas `anim=velocidad|...` o similares con datos, y `hud=` si la historia tiene un contador (días, hora, velocidad).
- No dibujes personajes ni emblemas de otras marcas; solo nómbralos.
- Exactamente **3 `clip=`** (~27 puntos de Flow) en los momentos de más acción.
- **2 Shorts**: `short=1|Título` y `short=2|Título` en la frase donde empieza cada uno, y `short=fin` donde termina. Cada uno dura máx. 58 s (~12-14 frases) y debe entenderse solo. Lo ideal: el gancho y el relato dramatizado.
- No describas en `imagen` a una "mujer joven bonita/seductora" ni armas en uso: Flow los rechaza.

## 2. Producción

1. `python generar_video.py <nombre> --hasta voz`
2. `python -m pipeline.flow exportar` y generar las imágenes en Flow (CLAUDE.md, paso 4).
3. `python -m pipeline.flow importar` y revisar una hoja de contacto numerada contra los `imagen=`. Si hay imágenes corridas o rechazadas, corregir y repetir solo las que faltan.
4. Clips: `python -m pipeline.flow clips`, luego `pipeline/flow_clips.js` (CLAUDE.md, paso 5b). Al terminar, volver Flow a modo Imagen y cerrar la pestaña.
5. `python generar_video.py <nombre> --desde imagenes` (con `--prueba` si dura menos de 10 min).
6. Revisar fotogramas del video y de los Shorts.
7. Miniatura minimalista: 2-4 prompts en Flow (fondo liso, Sticky + un solo elemento del tema, mucho espacio vacío, sin texto), y luego título corto (2-3 palabras) con Pillow en Arial Black → `miniatura_minimal_N.jpg` (1280x720).
8. `descripcion.txt` con el formato de siempre: párrafo gancho, "En este video verás…", párrafo de preguntas, CAPÍTULOS (desde los `#` del guion y los tiempos de `reporte.md`), "FUENTES BIBLIOGRÁFICAS:" solo con fuentes verificadas y 5 hashtags.
9. `publicacion.md` (modelo: `videos/la-patasola/publicacion.md`) para el video largo y para CADA Short: título que ENGANCHE (≤70 caracteres, 2-4 palabras clave en MAYÚSCULAS, curiosidad o advertencia que obligue a hacer clic, 1 emoji, puntos suspensivos si deja algo en el aire; incluye el nombre de la leyenda; da 3 opciones y marca la mejor; Shorts con `#Shorts` y un título distinto que cuente el giro, ej. `Su MULA Vio Algo Que ÉL NO… 😨 #Shorts`), descripción, hashtags (los 3 primeros se ven sobre el título), etiquetas, comentario fijado (pregunta que invite a responder + pedir la próxima leyenda) y ajustes (público, categoría, "video relacionado" de los Shorts = video largo). Si vidIQ está conectado, usa `vidiq_keyword_research` para elegir las palabras clave.

## 3. Entrega

Dile al usuario, en pocas líneas:
- Dónde quedaron `video.mp4`, `shorts/short_1.mp4`, `shorts/short_2.mp4`, `video.srt`, las miniaturas y `publicacion.md`.
- El título, la descripción COMPLETA, las etiquetas y el comentario fijado del video largo pegados en el chat en bloques de código, listos para copiar; y los títulos de los Shorts.
- La duración.
- Los puntos de Flow gastados.
- Cualquier problema.

Él sube los videos a YouTube; tú nunca publicas nada.

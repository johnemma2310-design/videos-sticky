# Pipeline de videos stickman

Cada video tiene su carpeta en `videos/<nombre>/` con su `guion.md`.

```
python generar_video.py la-patasola                    # todo el pipeline (exige 10-15 min)
python generar_video.py la-patasola --prueba           # la duración solo da aviso
python generar_video.py la-patasola --hasta voz        # escenas + narración
python generar_video.py la-patasola --desde imagenes   # retoma desde: escenas | voz | imagenes | montaje | verificar
python -m pipeline.flow exportar | importar            # imágenes de Google Flow (ver CLAUDE.md)
```

Resultado en `videos/<nombre>/`:
- `video.mp4`: 1080p, listo para subir a YouTube.
- `video.srt`: subtítulos. Se suben aparte en YouTube Studio (Subtítulos → Subir archivo).
- `reporte.md`: comprobaciones y lista de escenas.
- `trabajo/`: archivos intermedios (audios, imágenes, `flow/` con las ilustraciones descargadas).

Música opcional: `musica/fondo.mp3` se mezcla bajita (volumen en `config.json`).

## Guion

Cada frase es una escena. Opciones antes de la frase:

```
@Patasola: descripción fija del personaje (no se narra)

[[imagen={Patasola} saltando entre los árboles; texto=Una sola pierna]] Frase narrada.
Frase sin etiqueta: sigue mostrando la imagen anterior con otro encuadre.
[[imagen=un mapa de Colombia; tarjeta=si; texto=Región andina]] Otra frase.
```

- `imagen`: lo que muestra la ilustración de Flow. `{Nombre}` usa una descripción `@Nombre:`;
  `{Sticky}` es el protagonista (bufanda azul, en `config.json`).
- `texto`: palabra clave escrita a mano sobre la imagen.
- `tarjeta=si`: dibujo sencillo sobre fondo blanco con espacio para el texto.
- `clip=movimiento`: anima esa ilustración en Flow (3 s, 9 puntos). El clip abre la escena; si la
  narración dura más, va un poco más lento y luego se queda en el último cuadro.
- Sin etiquetas `imagen`, el escenario se deduce de las palabras (`escenario=`, `accion=`, `criatura=si`,
  `movimiento=si` siguen funcionando para el dibujo de respaldo).

Si una escena no tiene imagen de Flow, se usa un dibujo stickman hecho con Pillow.
En `config.json`, `subtitulos.quemar` decide si los subtítulos van dentro del video (por defecto no).
Requisitos: Python con `edge-tts` y `Pillow`, y `ffmpeg`/`ffprobe` en el PATH.

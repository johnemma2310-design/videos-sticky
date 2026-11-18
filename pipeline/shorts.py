"""Shorts verticales (1080x1920, máx. ~58 s) con los mejores momentos del video largo.

En el guion: `short=1` en la frase donde empieza el Short 1 (o `short=1|Título del short`),
y `short=fin` en la frase donde termina. Igual para `short=2`. Si el guion no los marca,
el Short 1 es el comienzo (el gancho) y el Short 2 empieza en el primer clip de Flow de la
segunda mitad (o en la mitad del video).
"""
from .comun import DIR_SHORTS, SALIDA, TRABAJO, PipelineError
from . import subtitulos as subs

ANCHO_V, ALTO_V = 1080, 1920
COMPOSICION = ("split[a][b];"
               "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:2,"
               "eq=brightness=-0.12[fondo];"
               "[b]scale=1280:720,crop=1080:720[frente];"
               "[fondo][frente]overlay=0:520,")


def _tramos(escenas, cfg):
    fps, maximo = cfg["video"]["fps"], cfg["shorts"]["max_s"]
    inicios, t = [], 0.0
    for e in escenas:
        inicios.append(t)
        t += e["frames"] / fps
    total = t
    marcados = {}
    for i, e in enumerate(escenas):
        valor = e["visual"].get("short", "")
        if valor and valor != "fin":
            n, _, titulo = valor.partition("|")
            marcados[n.strip()] = (i, titulo.strip())
    if "1" not in marcados:
        marcados["1"] = (0, "")
    if "2" not in marcados:
        mitad = next((i for i, e in enumerate(escenas) if inicios[i] > total / 2 and e.get("clip_flow")), None)
        marcados["2"] = (mitad if mitad is not None else next(i for i in range(len(escenas)) if inicios[i] >= total / 2), "")
    tramos = []
    for n in ("1", "2"):
        i, titulo = marcados[n]
        fin = i
        while fin + 1 < len(escenas):  # se extiende hasta short=fin, o hasta el máximo, en límite de escena
            siguiente_fin = inicios[fin + 1] + escenas[fin + 1]["frames"] / fps
            if siguiente_fin - inicios[i] > maximo or escenas[fin]["visual"].get("short") == "fin":
                break
            fin += 1
        desde, hasta = inicios[i], inicios[fin] + escenas[fin]["frames"] / fps
        tramos.append((n, desde, hasta, titulo))
    return tramos


def generar(datos, cfg, video_mudo, audio, log=print) -> list:
    from .montaje import exportar  # aquí para evitar import circular

    escenas = datos["escenas"]
    nombre = datos["titulo"].split(":")[0].strip()
    hechos = []
    for n, desde, hasta, titulo in _tramos(escenas, cfg):
        dur = hasta - desde
        if dur < 15:
            raise PipelineError(f"El Short {n} dura solo {dur:.1f}s; revisa las marcas short= del guion.")
        extras = [(titulo or nombre, 0, max(0.5, dur - 2.6), "Titulo"),
                  (cfg["shorts"]["texto_final"], max(0.5, dur - 2.6), dur, "Titulo")]
        ass = f"short_{n}.ass"
        subs.escribir_ass(escenas, TRABAJO / ass, cfg, ANCHO_V, ALTO_V, desde, hasta, extras)
        DIR_SHORTS.mkdir(parents=True, exist_ok=True)
        salida = DIR_SHORTS / f"short_{n}.mp4"
        exportar(cfg, video_mudo, audio, desde, dur, ass, salida, f"Short {n}", filtro_previo=COMPOSICION)
        log(f"  shorts/short_{n}.mp4: {dur:.1f}s (desde {desde:.1f}s)")
        hechos.append({"archivo": salida.relative_to(SALIDA).as_posix(), "desde": round(desde, 2), "duracion": round(dur, 2)})
    return hechos

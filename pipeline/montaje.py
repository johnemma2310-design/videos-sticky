"""Paso 4: montaje con ffmpeg.

- Escena fija: la imagen dura lo mismo que su audio (+ pausa), con zoom o paneo; si es larga,
  a la mitad corta a un encuadre más cerrado de la misma imagen.
- Clip de Flow: abre la escena; escena dibujada con movimiento: animación hecha con código.
- Corte directo, whoosh en cada cambio de imagen, subtítulos palabra por palabra, música opcional.
- Al final arma los Shorts verticales (pipeline/shorts.py).
"""
import math
import shutil
import subprocess
from pathlib import Path

from .comun import (ALTO, ANCHO, DIR_AUDIO, DIR_CLIPS, DIR_FLOW, RAIZ, SALIDA, TRABAJO, PipelineError,
                    cargar_escenas, duracion_media, ejecutar, guardar_escenas)
from .dibujo import (acabado, dibujar_criatura, dibujar_personaje, fondo, pose_corriendo)
from . import capas, outro, shorts, subtitulos as subs


def _codec(cfg):
    v = cfg["video"]
    return ["-c:v", "libx264", "-preset", v["preset"], "-crf", str(v["crf"]),
            "-pix_fmt", "yuv420p", "-r", str(v["fps"]), "-an"]


def _cadena_subs(primera: str, paginas: list, offset_input: int) -> tuple[list[str], str]:
    """Filtros overlay que muestran cada PNG de subtítulo en su intervalo."""
    filtros, actual = [], primera
    for i, p in enumerate(paginas):
        sig = f"s{i}"
        filtros.append(f"[{actual}][{offset_input + i}:v]overlay=0:0:"
                       f"enable='gte(t,{p['inicio']:.3f})*lt(t,{p['fin']:.3f})'[{sig}]")
        actual = sig
    filtros.append(f"[{actual}]format=yuv420p[out]")
    return filtros, "[out]"


CLAVE_ENTRA = "overlay=x='if(lt(t,0.22),-520+520*t/0.22,0)':y=0"  # la palabra clave entra deslizándose


def _movimiento(e, n, cfg):
    """Zoom o paneo que alterna por escena; si la escena es larga, a la mitad hay un corte a un
    encuadre más cerrado de la misma imagen (punch-in) para que el plano no se sienta quieto."""
    v = cfg["video"]
    zm = v["zoom_max"] - 1
    centro_x, centro_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    modo = e["id"] % 4
    if modo == 1:
        z, x, y = f"1+{zm}*on/{n}", centro_x, centro_y
    elif modo == 2:
        z, x, y = f"{1 + zm}-{zm}*on/{n}", centro_x, centro_y
    elif modo == 3:
        z, x, y = f"{1 + zm}", f"(iw-iw/zoom)*on/{n}", centro_y
    else:
        z, x, y = f"{1 + zm}", f"(iw-iw/zoom)*(1-on/{n})", centro_y
    if n / v["fps"] < v["corte_extra_desde_s"]:
        return z, x, y
    m = n // 2
    lado = "0.28" if e["id"] % 2 else "0.72"  # el encuadre cerrado mira a un tercio distinto cada vez
    zb = f"{v['punch_in']}+0.05*(on-{m})/{n - m}"
    return (f"if(lt(on,{m}),{z},{zb})", f"if(lt(on,{m}),{x},(iw-iw/zoom)*{lado})",
            f"if(lt(on,{m}),{y},(ih-ih/zoom)*0.4)")


def clip_estatico(e, cfg, pngs, paginas, destino):
    fps, n = cfg["video"]["fps"], e["frames"]
    z, x, y = _movimiento(e, n, cfg)
    filtros = [f"[0:v]scale={ANCHO * 2}:{ALTO * 2},zoompan=z='{z}':x='{x}':"
               f"y='{y}':d={n}:s={ANCHO}x{ALTO}:fps={fps}[z]"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(RAIZ / e["imagen"])]
    base, primera_sub = "z", 1
    if e.get("texto_png"):
        cmd += ["-i", str(RAIZ / e["texto_png"])]
        filtros.append(f"[z][1:v]{CLAVE_ENTRA}[zt]")
        base, primera_sub = "zt", 2
    resto, salida = _cadena_subs(base, paginas, primera_sub)
    for p in pngs:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", ";".join(filtros + resto), "-map", salida, "-frames:v", str(n)]
    cmd += _codec(cfg) + [str(destino)]
    ejecutar(cmd, f"Clip de la escena {e['id']}")


def clip_video(e, cfg, pngs, paginas, destino, ruta_clip):
    """Clip animado en Flow: se ralentiza un poco si la escena es más larga y luego se congela el final."""
    fps, n = cfg["video"]["fps"], e["frames"]
    vel = max(min(1.0, duracion_media(ruta_clip) / (n / fps)), cfg["flow"]["clip_velocidad_min"])
    filtros = [f"[0:v]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},setsar=1,"
               f"setpts=PTS/{vel:.4f},fps={fps},tpad=stop_mode=clone:stop_duration={n / fps:.3f}[z]"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(ruta_clip)]
    base, primera_sub = "z", 1
    if e.get("texto_png"):
        cmd += ["-i", str(RAIZ / e["texto_png"])]
        filtros.append(f"[z][1:v]{CLAVE_ENTRA}[zt]")
        base, primera_sub = "zt", 2
    resto, salida = _cadena_subs(base, paginas, primera_sub)
    for p in pngs:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", ";".join(filtros + resto), "-map", salida, "-frames:v", str(n)]
    cmd += _codec(cfg) + [str(destino)]
    ejecutar(cmd, f"Clip de video de la escena {e['id']}")


def clip_animado(e, cfg, pngs, paginas, destino):
    """Animación simple por código: el personaje corre y el fondo se desplaza."""
    fps, n = cfg["video"]["fps"], e["frames"]
    v = e["visual"]
    ancho_fondo = ANCHO * 2
    fondo_ancho = fondo(v["escenario"], cfg, semilla=e["id"] * 7919, ancho=ancho_fondo)
    vel = min(cfg["animacion"]["velocidad_px_s"], (ancho_fondo - ANCHO) / max(e["duracion"], 0.1))
    zancadas = cfg["animacion"]["zancadas_por_s"]

    resto, salida = _cadena_subs("0:v", paginas, 1)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{ANCHO}x{ALTO}", "-framerate", str(fps), "-i", "-"]
    for p in pngs:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", ";".join(resto), "-map", salida, "-frames:v", str(n)]
    cmd += _codec(cfg) + [str(destino)]

    log_err = DIR_CLIPS / f"escena_{e['id']:03d}_ffmpeg.log"
    with open(log_err, "w", encoding="utf-8") as ferr:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=ferr)
        try:
            for i in range(n):
                t = i / fps
                off = int(vel * t)
                cuadro = fondo_ancho.crop((off, 0, off + ANCHO, ALTO))
                fase = 2 * math.pi * zancadas * t
                if v["criatura"]:
                    dibujar_criatura(cuadro, 330 + 40 * math.sin(t * 1.3), cfg, fase=fase * 2)
                dibujar_personaje(cuadro, 1050, pose_corriendo(fase), cfg, fase=fase)
                acabado(cuadro, v["rotulo"], cfg)
                proc.stdin.write(cuadro.convert("RGB").tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        codigo = proc.wait()
    if codigo != 0:
        raise PipelineError(f"La animación de la escena {e['id']} falló en ffmpeg:\n"
                            + log_err.read_text(encoding="utf-8", errors="replace")[-1500:])
    log_err.unlink(missing_ok=True)


def narracion(escenas, cfg) -> "Path":
    lista = TRABAJO / "narracion_lista.txt"
    lineas = []
    for e in escenas:
        dur = e["frames"] / cfg["video"]["fps"]
        pad = DIR_AUDIO / f"escena_{e['id']:03d}_pad.wav"
        ejecutar(["ffmpeg", "-y", "-v", "error", "-i", str(RAIZ / e["audio"]),
                  "-af", f"atrim=start={e.get('recorte_audio', 0):.3f},asetpts=PTS-STARTPTS,aresample=48000,apad=whole_dur={dur:.4f},atrim=0:{dur:.4f}",
                  "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(pad)],
                 f"Audio con pausa de la escena {e['id']}")
        lineas.append(f"file '{pad.as_posix()}'")
    lista.write_text("\n".join(lineas), encoding="utf-8")
    salida = TRABAJO / "narracion.wav"
    ejecutar(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
              "-c", "copy", str(salida)], "Unión de la narración")
    return salida


def generar(cfg: dict, log=print) -> dict:
    datos = cargar_escenas()
    escenas = datos["escenas"]
    for e in escenas:
        for campo in ("audio", "imagen", "frames"):
            if campo not in e:
                raise PipelineError(f"A la escena {e['id']} le falta '{campo}'; ejecuta los pasos anteriores.")

    lista_clips = []
    quemar = cfg["subtitulos"].get("quemar", True)
    cp = cfg.get("presentador", {})
    cada = cp.get("cada_pantalla_completa", 5)
    n_img, lado = -1, "izq"
    for e in escenas:
        e["subtitulos"] = subs.paginas(e, cfg)  # siempre: alimentan el .srt
        paginas = e["subtitulos"] if quemar else []
        pngs = [subs.render_png(e["id"], i, p["lineas"], cfg) for i, p in enumerate(paginas)]
        destino = DIR_CLIPS / f"escena_{e['id']:03d}.mp4"
        # la animación por código solo aplica a escenas dibujadas; las de Flow llevan zoom o paneo
        animada = e["visual"]["movimiento"] and e.get("fuente_imagen") != "flow"
        ruta_clip = DIR_FLOW / f"clip_{e['id']:03d}.mp4"
        e["clip_flow"] = ruta_clip.exists() and "imagen_de" not in e
        anim = e["visual"].get("anim", "")
        nueva = "imagen_de" not in e
        if nueva:
            n_img += 1
            if n_img % 4 == 0 and n_img:
                lado = "der" if lado == "izq" else "izq"
        presenta = (cp.get("activo", False) and not e["clip_flow"] and not anim.startswith(("velocidad", "barras", "quiz"))
                    and e.get("fuente_imagen") == "flow" and n_img % cada != cada - 1)
        e["presentador"] = presenta
        if anim.startswith("velocidad"):
            capas.clip_velocidad(e, cfg, destino, anim)
        elif anim.startswith("barras"):
            capas.clip_barras(e, cfg, destino, anim)
        elif anim.startswith("quiz"):
            capas.clip_quiz(e, cfg, destino, anim)
        elif presenta:
            capas.clip_presentador(e, cfg, destino, RAIZ / e["imagen"], lado, nueva)
        elif e["clip_flow"]:
            clip_video(e, cfg, pngs, paginas, destino, ruta_clip)
        elif animada:
            clip_animado(e, cfg, pngs, paginas, destino)
        else:
            clip_estatico(e, cfg, pngs, paginas, destino)
        if anim.startswith("sticky") and not presenta:
            capas.aplicar_sticky(e, cfg, destino, (anim.split("|") + ["explica"])[1].strip() or "explica")
        marca = ("(clip de Flow)" if e["clip_flow"] else "(animado)" if animada else "") + (f" [{anim.split('|')[0]}]" if anim else "") + (" [presentador]" if presenta else "")
        log(f"  clip {e['id']:03d}: {e['duracion']:5.2f}s {marca}")
        lista_clips.append(f"file '{destino.as_posix()}'")
    guardar_escenas(datos)

    lista = TRABAJO / "clips_lista.txt"
    lista.write_text("\n".join(lista_clips), encoding="utf-8")
    video_mudo = TRABAJO / "video_sin_audio.mp4"
    ejecutar(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
              "-c", "copy", str(video_mudo)], "Unión de clips (corte directo)")

    voz = narracion(escenas, cfg)
    total = sum(e["frames"] for e in escenas) / cfg["video"]["fps"]
    datos["musica"] = cfg["musica"]["archivo"] if (RAIZ / cfg["musica"]["archivo"]).exists() else None
    log(f"  música de fondo: {'sí' if datos['musica'] else 'no (no existe musica/fondo.mp3)'}")
    mezcla = mezclar_audio(escenas, cfg, voz, total)
    preparar_fuente(cfg)
    salida = SALIDA / "video.mp4"
    subs.escribir_ass(escenas, TRABAJO / "subtitulos.ass", cfg, ANCHO, ALTO)
    exportar(cfg, video_mudo, mezcla, 0.0, total, "subtitulos.ass", salida, "Exportación final de video.mp4")

    subs.escribir_srt(escenas, SALIDA / "video.srt")
    datos["outro_s"] = outro.agregar(cfg, salida, vertical=False)
    if datos["outro_s"]:
        log(f"  cierre de suscripción: +{datos['outro_s']:.1f}s")
    datos["duracion_total"] = round(total, 2)
    datos["duracion_video"] = round(duracion_media(salida), 2)
    datos["shorts"] = shorts.generar(datos, cfg, video_mudo, mezcla, log)
    guardar_escenas(datos)
    return datos


def preparar_fuente(cfg):
    """libass busca la fuente en trabajo/fuentes (en Windows no siempre ve las del sistema)."""
    d = TRABAJO / "fuentes"
    d.mkdir(exist_ok=True)
    origen = Path(cfg["subtitulos"]["palabras_archivo_fuente"])
    if origen.exists() and not (d / origen.name).exists():
        shutil.copy(origen, d / origen.name)


def _whoosh(cfg) -> Path:
    ruta = TRABAJO / "whoosh.wav"
    if not ruta.exists():
        ejecutar(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                  "anoisesrc=d=0.45:c=pink:a=0.9:r=48000", "-af",
                  "highpass=f=400,lowpass=f=4500,afade=t=in:d=0.18:curve=exp,afade=t=out:st=0.18:d=0.27,"
                  "aecho=0.6:0.4:40:0.3", "-ac", "2", str(ruta)], "Sonido de transición")
    return ruta


def mezclar_audio(escenas, cfg, voz, total) -> Path:
    """Narración + un whoosh suave en cada cambio de imagen + música (si existe) → trabajo/mezcla.wav."""
    fps = cfg["video"]["fps"]
    cortes, t = [], 0.0
    for e in escenas:
        if t > 0 and "imagen_de" not in e:
            cortes.append(t)
        t += e["frames"] / fps
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(voz)]
    filtros, mezclar = [], ["[0:a]"]
    if cfg.get("sonido", {}).get("whoosh") and cortes:
        cmd += ["-i", str(_whoosh(cfg))]
        filtros.append(f"[1:a]volume={cfg['sonido']['volumen_whoosh']},asplit={len(cortes)}"
                       + "".join(f"[w{i}]" for i in range(len(cortes))))
        for i, c in enumerate(cortes):
            ms = max(0, int((c - 0.15) * 1000))  # el whoosh empieza un poco antes del corte
            filtros.append(f"[w{i}]adelay={ms}|{ms}[d{i}]")
            mezclar.append(f"[d{i}]")
    musica = RAIZ / cfg["musica"]["archivo"]
    if musica.exists():
        cm = cfg["musica"]
        idx = (cmd.count("-i"))
        fo = min(cm["fade_out_s"], total / 2)
        cmd += ["-stream_loop", "-1", "-i", str(musica)]
        filtros.append(f"[{idx}:a]aresample=48000,volume={cm['volumen']},afade=t=in:d={cm['fade_in_s']},"
                       f"atrim=0:{total:.3f},afade=t=out:st={total - fo:.3f}:d={fo:.3f}[m]")
        mezclar.append("[m]")
    # tic por cada número de la cuenta regresiva del quiz y "ding" al revelar
    t, sonidos = 0.0, []
    for e in escenas:
        if e["visual"].get("anim", "").startswith("quiz"):
            ini, paso, rev = capas.quiz_tiempos(e["frames"] / fps)
            sonidos += [(t + ini + k * paso, 1100, 0.07) for k in range(3)] + [(t + rev, 1650, 0.35)]
        t += e["frames"] / fps
    for ts, f, d in sonidos:
        idx = cmd.count("-i")
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={d}"]
        ms = int(ts * 1000)
        filtros.append(f"[{idx}:a]volume=0.35,afade=t=out:st={d * 0.4:.3f}:d={d * 0.6:.3f},aresample=48000,"
                       f"aformat=channel_layouts=stereo,adelay={ms}|{ms}[q{idx}]")
        mezclar.append(f"[q{idx}]")
    salida = TRABAJO / "mezcla.wav"
    if len(mezclar) == 1:
        cmd += ["-c:a", "pcm_s16le", str(salida)]
    else:
        filtros.append("".join(mezclar) + f"amix=inputs={len(mezclar)}:duration=first:normalize=0[a]")
        cmd += ["-filter_complex", ";".join(filtros), "-map", "[a]", "-c:a", "pcm_s16le", str(salida)]
    ejecutar(cmd, "Mezcla de audio (voz, transiciones y música)")
    ln = cfg.get("sonido", {}).get("loudnorm")
    if ln:  # volumen al nivel que usa YouTube (-14 LUFS): más fuerte y parejo
        norm = TRABAJO / "mezcla_norm.wav"
        ejecutar(["ffmpeg", "-y", "-v", "error", "-i", str(salida), "-af", f"loudnorm={ln}", "-ar", "48000",
                  "-c:a", "pcm_s16le", str(norm)], "Normalización de volumen")
        norm.replace(salida)
    return salida


def exportar(cfg, video_mudo, audio, desde, dur, ass, salida, descripcion, filtro_previo=""):
    """Video final con subtítulos quemados. ffmpeg corre dentro de trabajo/ para que la ruta del .ass
    y de las fuentes no lleve "C:" (los dos puntos rompen el filtro en Windows)."""
    v = cfg["video"]
    filtro = f"{filtro_previo}ass={ass}:fontsdir=fuentes"
    ejecutar(["ffmpeg", "-y", "-v", "error", "-ss", f"{desde:.3f}", "-t", f"{dur:.3f}", "-i", str(video_mudo),
              "-ss", f"{desde:.3f}", "-t", f"{dur:.3f}", "-i", str(audio),
              "-filter_complex", f"[0:v]{filtro}[v]", "-map", "[v]", "-map", "1:a",
              "-c:v", "libx264", "-preset", v["preset"], "-crf", str(v["crf"]), "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{dur:.3f}", str(salida)],
             descripcion, cwd=TRABAJO)

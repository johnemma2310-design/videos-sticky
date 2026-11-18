"""Modo mixto: capas animadas por código (cairo) sobre las escenas de Flow.

En el guion, dentro de [[...]]:
- `anim=sticky|accion`  Sticky animado encima de la ilustración. Acciones: explica, sorpresa, miedo,
  feliz, correr. Habla (mueve la boca) mientras suena la voz.
- `anim=velocidad|Título|Nombre:valor|Nombre:valor|...`  tarjeta a pantalla completa con barras que
  crecen (escala logarítmica, en km/h). La última barra es la destacada.
- `hud=TEXTO`  marcador fijo arriba a la izquierda desde esa escena (lo dibuja subtitulos.py).
"""
import math
import subprocess

import cairo

from .animacion import (AMARILLO, AZUL, BLANCO, NEGRO, exclamacion, lerp, nube_polvo, parpadeo, pose_correr, prog,
                        rebote, rebote_paso, redondeado, sticky, suave, texto)
from .comun import ALTO, ANCHO, DIR_CLIPS, PipelineError

COLORES = [(0.30, 0.65, 1.0), (0.30, 0.85, 0.45), (1.0, 0.62, 0.20), (0.95, 0.30, 0.35), (0.70, 0.45, 1.0),
           (0.20, 0.85, 0.85)]


def _codec(cfg):
    v = cfg["video"]
    return ["-c:v", "libx264", "-preset", v["preset"], "-crf", str(v["crf"]), "-pix_fmt", "yuv420p",
            "-r", str(v["fps"]), "-an"]


def _hablando(e, t):
    return any(w["ini"] <= t < w["fin"] for w in e.get("palabras", []))


def _render(cmd, n, dibujar, descripcion):
    sup = cairo.ImageSurface(cairo.FORMAT_ARGB32, ANCHO, ALTO)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            ctx = cairo.Context(sup)
            ctx.set_operator(cairo.OPERATOR_CLEAR)
            ctx.paint()
            ctx.set_operator(cairo.OPERATOR_OVER)
            dibujar(ctx, i)
            sup.flush()
            proc.stdin.write(bytes(sup.get_data()))
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise PipelineError(f"{descripcion} falló en ffmpeg:\n{err[-1500:]}")

# ---------------------------------------------------------------- Sticky sobre la ilustración


def _sticky_capa(ctx, e, t, dur, accion):
    s = 0.95
    suelo = ALTO - 60
    x = 360
    hip = suelo - 154 * s
    entra = rebote(prog(t, 0.0, 0.3))
    habla = _hablando(e, t)
    boca_habla = ("big" if int(t * 11) % 2 == 0 else "o") if habla else None
    if accion == "correr":
        x = lerp(-250, ANCHO + 250, t / max(dur, 0.1))
        fase = t * 17
        _sombra(ctx, x, suelo)
        sticky(ctx, x, hip + rebote_paso(fase, 12), s, pose_correr(fase, 1),
               dict(ojos="wide", boca=boca_habla or "big", cejas="up", mira=(1, 0)), t)
        for k in range(3):
            yy = hip - 120 + k * 70
            ctx.move_to(x - 140, yy)
            ctx.line_to(x - 330, yy)
            ctx.set_source_rgba(1, 1, 1, 0.75)
            ctx.set_line_width(8)
            ctx.stroke()
        for k in range(5):
            tk = k * 0.18
            if t >= tk:
                nube_polvo(ctx, lerp(-250, ANCHO + 250, tk / max(dur, 0.1)), suelo, prog(t, tk, tk + 0.5), 45)
        return
    y = hip + (1 - entra) * 500
    _sombra(ctx, x, suelo, entra)
    if accion == "sorpresa":
        pose = dict(aL1=-60, aL2=-40, aR1=60, aR2=40, head=-3)
        cara = dict(ojos="wide", boca=boca_habla or "open", cejas="up", mira=(1, -0.3))
    elif accion == "miedo":
        x += math.sin(t * 55) * 3
        pose = dict(aL1=-35, aL2=-110, aR1=35, aR2=110)
        cara = dict(ojos="wide", boca=boca_habla or "wavy", cejas="worried", sudor=True, mira=(1, 0))
    elif accion == "feliz":
        ola = math.sin(t * 9)
        pose = dict(aR1=95 + ola * 8, aR2=55 + ola * 12, head=ola * 3)
        cara = dict(ojos="happy", boca=boca_habla or "big", rubor=True)
    else:  # explica
        gesto = math.sin(t * 2.6)
        pose = dict(aR1=75 + gesto * 18, aR2=-35 + gesto * 10, head=gesto * 2)
        cara = dict(boca=boca_habla or "smile", mira=(1, -0.2), parpadeo=parpadeo(t, 2.7))
    sticky(ctx, x, y, s, pose, cara, t)
    if accion == "sorpresa" and t > 0.2:
        exclamacion(ctx, x + 120, y - 300, 140 * rebote(prog(t, 0.2, 0.45)))


def _sombra(ctx, x, suelo, a=1.0):
    rg = cairo.RadialGradient(x, suelo - 260, 0, x, suelo - 260, 330)
    rg.add_color_stop_rgba(0, 0, 0, 0, 0.35 * a)
    rg.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.set_source(rg)
    ctx.arc(x, suelo - 260, 330, 0, 2 * math.pi)
    ctx.fill()
    ctx.save()
    ctx.translate(x, suelo)
    ctx.scale(1, 0.18)
    ctx.arc(0, 0, 95, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(0, 0, 0, 0.45 * a)
    ctx.fill()


def aplicar_sticky(e, cfg, destino, accion):
    """Pone a Sticky animado encima del clip ya hecho de la escena (lo reemplaza)."""
    fps, n = cfg["video"]["fps"], e["frames"]
    dur = n / fps
    tmp = DIR_CLIPS / f"escena_{e['id']:03d}_capa.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(destino), "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{ANCHO}x{ALTO}", "-framerate", str(fps), "-i", "-",
           "-filter_complex", "[0:v][1:v]overlay=0:0:alpha=premultiplied:format=auto[v]", "-map", "[v]",
           "-frames:v", str(n)] + _codec(cfg) + [str(tmp)]
    _render(cmd, n, lambda ctx, i: _sticky_capa(ctx, e, i / fps, dur, accion), f"Sticky animado en la escena {e['id']}")
    tmp.replace(destino)

# ---------------------------------------------------------------- tarjeta de velocidades


def _num(v):
    """Número en español: 1.234.567 / 44,7"""
    if v >= 1e6:
        return f"{v / 1e6:,.0f}".replace(",", ".") + " millones de"
    if v >= 100:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:.1f}".replace(".", ",")


def _leer_barras(spec):
    partes = [p.strip() for p in spec.split("|")[1:] if p.strip()]
    titulo = "VELOCIDAD MÁXIMA"
    barras = []
    for p in partes:
        if ":" in p:
            nombre, valor = p.rsplit(":", 1)
            try:
                barras.append((nombre.strip(), float(valor.replace(",", "."))))
            except ValueError as ex:
                raise PipelineError(f"Valor inválido en anim=velocidad: '{p}'") from ex
        else:
            titulo = p
    if not barras:
        raise PipelineError(f"anim=velocidad sin barras (Nombre:valor): {spec}")
    return titulo, barras


def _fondo_tarjeta(ctx):
    ctx.set_source_rgb(0.04, 0.11, 0.24)
    ctx.paint()
    ctx.set_source_rgba(1, 1, 1, 0.05)
    ctx.set_line_width(1.5)
    for x in range(0, ANCHO, 60):
        ctx.move_to(x, 0)
        ctx.line_to(x, ALTO)
    for y in range(0, ALTO, 60):
        ctx.move_to(0, y)
        ctx.line_to(ANCHO, y)
    ctx.stroke()


def _tarjeta(ctx, e, t, dur, titulo, barras):
    _fondo_tarjeta(ctx)
    texto(ctx, titulo.upper(), ANCHO / 2, 110, 66, BLANCO, escala=rebote(prog(t, 0, 0.35)))
    ancho_linea = 820 * suave(prog(t, 0.15, 0.6))
    ctx.rectangle(ANCHO / 2 - ancho_linea / 2, 162, ancho_linea, 6)
    ctx.set_source_rgb(*AZUL)
    ctx.fill()
    vmax = max(v for _, v in barras)
    lmax = math.log10(max(vmax, 10)) + 0.3
    x0, ancho_max = 560, 1180
    alto_fila = min(130, 720 / len(barras))
    y_ini = 250 + (720 - alto_fila * len(barras)) / 2
    tramo = max(0.5, (dur * 0.75 - 0.3) / len(barras))
    for k, (nombre, v) in enumerate(barras):
        tk = 0.3 + k * tramo
        if t < tk:
            continue
        u = suave(prog(t, tk, tk + min(0.8, tramo * 0.9)))
        y = y_ini + k * alto_fila + alto_fila / 2
        ultimo = k == len(barras) - 1
        color = AMARILLO if ultimo else COLORES[k % len(COLORES)]
        texto(ctx, nombre.upper(), x0 - 30, y, min(46, alto_fila * 0.38), BLANCO, ancla="r", alpha=min(1, u * 3))
        largo = max(30, ancho_max * (math.log10(max(v, 1)) + 0.3) / lmax) * u
        redondeado(ctx, x0, y - alto_fila * 0.3, largo, alto_fila * 0.6, alto_fila * 0.3)
        ctx.set_source_rgb(*color)
        ctx.fill_preserve()
        ctx.set_source_rgb(*NEGRO)
        ctx.set_line_width(4)
        ctx.stroke()
        valor = v * (10 ** ((u - 1) * 2)) if u < 1 else v  # el número sube junto con la barra
        etiqueta = f"{_num(valor)} km/h"
        tam_et = min(40, alto_fila * 0.34)
        ctx.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(tam_et)
        if x0 + largo + 22 + ctx.text_extents(etiqueta).x_advance > ANCHO - 30:  # no cabe: va dentro de la barra
            texto(ctx, etiqueta, x0 + largo - 30, y, tam_et, NEGRO, ancla="r")
        else:
            texto(ctx, etiqueta, x0 + largo + 22, y, tam_et, color, ancla="l", borde=3)
        if ultimo and u > 0.2:
            fase = t * 16
            sticky(ctx, x0 + largo - 40, y - alto_fila * 0.3 - 80 + rebote_paso(fase, 4), 0.42, pose_correr(fase, 1),
                   dict(ojos="wide", boca="big", mira=(1, 0)), t)
    texto(ctx, "escala logarítmica: cada salto de barra multiplica la velocidad", ANCHO / 2, ALTO - 150, 28,
          (0.75, 0.82, 0.95), alpha=0.8 * suave(prog(t, 0.5, 1.0)))


def clip_velocidad(e, cfg, destino, spec):
    fps, n = cfg["video"]["fps"], e["frames"]
    dur = n / fps
    titulo, barras = _leer_barras(spec)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{ANCHO}x{ALTO}",
           "-framerate", str(fps), "-i", "-", "-frames:v", str(n)] + _codec(cfg) + [str(destino)]
    _render(cmd, n, lambda ctx, i: _tarjeta(ctx, e, i / fps, dur, titulo, barras),
            f"Tarjeta de velocidades de la escena {e['id']}")

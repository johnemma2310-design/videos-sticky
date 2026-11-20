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

# ---------------------------------------------------------------- modo presentador (Sticky explica + recuadro)

_CACHE_IMG = {}


def _superficie(ruta):
    """JPG/PNG -> superficie cairo (se guarda en caché por ruta)."""
    if ruta in _CACHE_IMG:
        return _CACHE_IMG[ruta]
    import numpy as np
    from PIL import Image
    im = Image.open(ruta).convert("RGB")
    g = np.asarray(im.convert("L"))
    if g.mean() > 215:  # tarjeta de fondo blanco: acercar al dibujo para que no sobre blanco
        ys, xs = np.where(g < 235)
        if len(xs) > 500:
            x0, x1, y0, y1 = np.percentile(xs, 1), np.percentile(xs, 99), np.percentile(ys, 1), np.percentile(ys, 99)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            w = max(x1 - x0, (y1 - y0) * 16 / 9) * 1.18
            w = min(max(w, im.width * 0.45), im.width)
            h = w * 9 / 16
            cx = min(max(cx, w / 2), im.width - w / 2)
            cy = min(max(cy, h / 2), im.height - h / 2)
            im = im.crop((int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)))
    im = im.resize((ANCHO, ALTO), Image.LANCZOS)
    a = np.asarray(im)
    bgra = np.empty((ALTO, ANCHO, 4), dtype=np.uint8)
    bgra[..., 0], bgra[..., 1], bgra[..., 2], bgra[..., 3] = a[..., 2], a[..., 1], a[..., 0], 255
    sup = cairo.ImageSurface.create_for_data(bytearray(bgra.tobytes()), cairo.FORMAT_ARGB32, ANCHO, ALTO, ANCHO * 4)
    _CACHE_IMG.clear()  # solo una imagen a la vez en memoria
    _CACHE_IMG[ruta] = sup
    return sup


def _expresion(texto, t, habla):
    """Cara de Sticky según la frase: pregunta, exclamación, peligro o explicación normal."""
    tl = texto.lower()
    boca = ("big" if int(t * 11) % 2 == 0 else "o") if habla else "smile"
    cara = dict(boca=boca, parpadeo=parpadeo(t, 2.8), mira=(0.7, -0.2))
    if any(p in tl for p in ("cuidado", "peligro", "miedo", "imposible", "problema", "desmay", "humo", "calor")):
        cara.update(cejas="worried", ojos="wide", sudor="humo" in tl or "calor" in tl)
        if not habla:
            cara["boca"] = "wavy"
    elif "!" in texto:
        cara.update(ojos="wide", cejas="up")
        if not habla:
            cara["boca"] = "big"
    elif "?" in texto:
        cara.update(cejas="up", mira=(0.5, -0.6))
    return cara


def _presentador(ctx, e, t, dur, img, lado, nueva, cfg):
    cp = cfg.get("presentador", {})
    c1, c2 = cp.get("fondo", [[0.05, 0.12, 0.30], [0.10, 0.32, 0.62]])
    g = cairo.LinearGradient(0, 0, ANCHO, ALTO)
    g.add_color_stop_rgb(0, *c1)
    g.add_color_stop_rgb(1, *c2)
    ctx.set_source(g)
    ctx.paint()
    ctx.set_source_rgba(1, 1, 1, 0.05)  # puntitos de fondo
    for y in range(30, ALTO, 60):
        for x in range(30 + (y // 60 % 2) * 30, ANCHO, 60):
            ctx.arc(x, y, 3, 0, 2 * math.pi)
            ctx.fill()
    # recuadro con la ilustración
    fw, fh = 1180, 664
    fx = 640 if lado == "izq" else 100
    fy = 180
    pop = rebote(prog(t, 0, 0.3)) if nueva else 1.0
    ctx.save()
    ctx.translate(fx + fw / 2, fy + fh / 2)
    ctx.scale(pop, pop)
    ctx.translate(-fw / 2, -fh / 2)
    redondeado(ctx, 10, 16, fw, fh, 34)  # sombra
    ctx.set_source_rgba(0, 0, 0, 0.35)
    ctx.fill()
    redondeado(ctx, -10, -10, fw + 20, fh + 20, 40)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()
    ctx.save()
    redondeado(ctx, 0, 0, fw, fh, 30)
    ctx.clip()
    zoom = 1.0 + 0.08 * (t / max(dur, 0.1))
    esc = fw / ANCHO * zoom
    ctx.translate(fw / 2, fh / 2)
    ctx.scale(esc, esc)
    ctx.translate(-ANCHO / 2, -ALTO / 2)
    ctx.set_source_surface(img, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()
    ctx.restore()
    ctx.restore()
    # palabra clave escrita a mano encima del recuadro
    clave = e["visual"].get("texto", "")
    if clave:
        a = rebote(prog(t, 0.15, 0.45))
        texto(ctx, clave, fx + fw / 2, 100, 74, AMARILLO, fuente="Segoe Print", borde=6, escala=a, giro=-3)
    # Sticky explicando
    s = 1.3
    sx = 330 if lado == "izq" else ANCHO - 330
    suelo = ALTO - 40
    hip = suelo - 154 * s
    habla = _hablando(e, t)
    accion = (e["visual"].get("anim", "").split("|") + [""])[1].strip() if e["visual"].get("anim", "").startswith("sticky") else ""
    d = 1 if lado == "izq" else -1  # hacia dónde está el recuadro
    gesto = math.sin(t * 2.4 + e["id"])
    cara = _expresion(e["texto"], t, habla)
    cara["mira"] = (cara["mira"][0] * d, cara["mira"][1])
    if accion == "sorpresa":
        pose = dict(aL1=-60, aL2=-40, aR1=60, aR2=40)
        cara.update(ojos="wide", cejas="up")
    elif accion == "miedo":
        sx += math.sin(t * 55) * 3
        pose = dict(aL1=-35, aL2=-110, aR1=35, aR2=110)
        cara.update(ojos="wide", cejas="worried", sudor=True)
    elif accion == "feliz":
        ola = math.sin(t * 9)
        pose = dict(aR1=(95 + ola * 8) * d, aR2=(55 + ola * 12) * d) if d > 0 else dict(aL1=-(95 + ola * 8), aL2=-(55 + ola * 12))
        cara.update(ojos="happy", rubor=True)
    elif e["id"] % 3 == 0:  # señala el recuadro
        pose = dict(aR1=95, aR2=-10 + gesto * 6) if d > 0 else dict(aL1=-95, aL2=10 - gesto * 6)
    else:  # explica con las manos
        pose = dict(aR1=70 + gesto * 18, aR2=-35 + gesto * 10, aL1=-25 - gesto * 8, aL2=-20) if d > 0 else \
            dict(aL1=-(70 + gesto * 18), aL2=35 - gesto * 10, aR1=25 + gesto * 8, aR2=20)
    pose["head"] = gesto * 2.5
    _sombra(ctx, sx, suelo)
    sticky(ctx, sx, hip + math.sin(t * 3) * 2, s, pose, cara, t)


def clip_presentador(e, cfg, destino, ruta_img, lado="izq", nueva=True):
    fps, n = cfg["video"]["fps"], e["frames"]
    dur = n / fps
    img = _superficie(str(ruta_img))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{ANCHO}x{ALTO}",
           "-framerate", str(fps), "-i", "-", "-frames:v", str(n)] + _codec(cfg) + [str(destino)]
    _render(cmd, n, lambda ctx, i: _presentador(ctx, e, i / fps, dur, img, lado, nueva, cfg),
            f"Escena con Sticky presentador {e['id']}")

# ---------------------------------------------------------------- tarjeta de barras lineales (porcentajes, dinero, etc.)
# Guion: anim=barras|Título|unidad|Nombre:valor|Nombre:valor   (la última barra es la destacada)


def _tarjeta_barras(ctx, e, t, dur, titulo, unidad, barras):
    _fondo_tarjeta(ctx)
    texto(ctx, titulo.upper(), ANCHO / 2, 110, 64, BLANCO, escala=rebote(prog(t, 0, 0.35)))
    ancho_linea = 820 * suave(prog(t, 0.15, 0.6))
    ctx.rectangle(ANCHO / 2 - ancho_linea / 2, 162, ancho_linea, 6)
    ctx.set_source_rgb(*AZUL)
    ctx.fill()
    vmax = max(v for _, v in barras) or 1
    x0, ancho_max = 620, 1050
    alto_fila = min(140, 700 / len(barras))
    y_ini = 260 + (700 - alto_fila * len(barras)) / 2
    tramo = max(0.5, (dur * 0.75 - 0.3) / len(barras))
    for k, (nombre, v) in enumerate(barras):
        tk = 0.3 + k * tramo
        if t < tk:
            continue
        u = suave(prog(t, tk, tk + min(0.8, tramo * 0.9)))
        y = y_ini + k * alto_fila + alto_fila / 2
        ultimo = k == len(barras) - 1
        color = AMARILLO if ultimo else COLORES[k % len(COLORES)]
        texto(ctx, nombre.upper(), x0 - 30, y, min(44, alto_fila * 0.36), BLANCO, ancla="r", alpha=min(1, u * 3))
        largo = max(24, ancho_max * v / vmax) * u
        redondeado(ctx, x0, y - alto_fila * 0.3, largo, alto_fila * 0.6, alto_fila * 0.3)
        ctx.set_source_rgb(*color)
        ctx.fill_preserve()
        ctx.set_source_rgb(*NEGRO)
        ctx.set_line_width(4)
        ctx.stroke()
        valor = v * u
        num = (f"{valor:,.0f}".replace(",", ".") if v >= 100 else f"{valor:.1f}".replace(".", ",").replace(",0", ""))
        etiqueta = f"{unidad}{num}" if unidad == "$" else f"{num} {unidad}".strip()
        texto(ctx, etiqueta, x0 + largo + 22, y, min(42, alto_fila * 0.34), color, ancla="l", borde=3)


def clip_barras(e, cfg, destino, spec):
    partes = [p.strip() for p in spec.split("|")[1:]]
    if len(partes) < 3:
        raise PipelineError(f"anim=barras necesita Título|unidad|Nombre:valor...: {spec}")
    titulo, unidad, items = partes[0], partes[1], partes[2:]
    barras = []
    for p in items:
        nombre, valor = p.rsplit(":", 1)
        barras.append((nombre.strip(), float(valor.replace(",", "."))))
    fps, n = cfg["video"]["fps"], e["frames"]
    dur = n / fps
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{ANCHO}x{ALTO}",
           "-framerate", str(fps), "-i", "-", "-frames:v", str(n)] + _codec(cfg) + [str(destino)]
    _render(cmd, n, lambda ctx, i: _tarjeta_barras(ctx, e, i / fps, dur, titulo, unidad, barras),
            f"Tarjeta de barras de la escena {e['id']}")

# ---------------------------------------------------------------- tarjeta de quiz (pregunta + 3 opciones + cuenta regresiva)
# Guion: anim=quiz|Pregunta|Opción 1|Opción 2|Opción 3|número de la correcta (1-3)


def _tarjeta_quiz(ctx, e, t, dur, pregunta, opciones, correcta):
    _fondo_tarjeta(ctx)
    texto(ctx, "¿TÚ QUÉ CREES?", ANCHO / 2, 90, 46, AMARILLO, escala=rebote(prog(t, 0, 0.3)))
    texto(ctx, pregunta.upper(), ANCHO / 2, 190, 58, BLANCO, escala=rebote(prog(t, 0.1, 0.45)))
    revela = dur * 0.78
    letras = "ABC"
    for k, op in enumerate(opciones):
        tk = 0.4 + k * 0.35
        if t < tk:
            continue
        u = rebote(prog(t, tk, tk + 0.3))
        y = 360 + k * 170
        ok = (k + 1) == correcta
        if t >= revela:
            r = prog(t, revela, revela + 0.25)
            col = (0.20, 0.80, 0.40) if ok else (0.25, 0.30, 0.42)
            alpha = 1.0 if ok else 1 - 0.5 * r
        else:
            col, alpha = (0.15, 0.30, 0.62), 1.0
        ctx.save()
        ctx.translate(ANCHO / 2, y)
        ctx.scale(u * (1 + 0.06 * ok * suave(prog(t, revela, revela + 0.2))), u)
        redondeado(ctx, -560, -60, 1120, 120, 60)
        ctx.set_source_rgba(*col, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(1, 1, 1, alpha)
        ctx.set_line_width(5)
        ctx.stroke()
        ctx.arc(-480, 0, 40, 0, 2 * math.pi)
        ctx.set_source_rgba(*AMARILLO, alpha)
        ctx.fill()
        texto(ctx, letras[k], -480, 0, 44, NEGRO, alpha=alpha)
        texto(ctx, op.upper(), -410, 0, 50, BLANCO, ancla="l", alpha=alpha)
        if ok and t >= revela:
            texto(ctx, "✔", 500, 0, 70, BLANCO, fuente="Segoe UI Symbol")
        ctx.restore()
    # cuenta regresiva entre la última opción y la respuesta
    inicio = 0.4 + 3 * 0.35 + 0.2
    if inicio <= t < revela:
        paso = (revela - inicio) / 3
        n = 3 - int((t - inicio) / paso)
        u = (t - inicio) % paso / paso
        ctx.arc(ANCHO - 170, ALTO - 170, 90, -math.pi / 2, -math.pi / 2 + 2 * math.pi * (1 - u))
        ctx.set_source_rgb(*AMARILLO)
        ctx.set_line_width(14)
        ctx.stroke()
        texto(ctx, str(max(1, n)), ANCHO - 170, ALTO - 170, 90, BLANCO, escala=rebote(min(1, u * 4)))


def clip_quiz(e, cfg, destino, spec):
    partes = [p.strip() for p in spec.split("|")[1:]]
    if len(partes) != 5:
        raise PipelineError(f"anim=quiz necesita Pregunta|A|B|C|correcta: {spec}")
    pregunta, opciones, correcta = partes[0], partes[1:4], int(partes[4])
    fps, n = cfg["video"]["fps"], e["frames"]
    dur = n / fps
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{ANCHO}x{ALTO}",
           "-framerate", str(fps), "-i", "-", "-frames:v", str(n)] + _codec(cfg) + [str(destino)]
    _render(cmd, n, lambda ctx, i: _tarjeta_quiz(ctx, e, i / fps, dur, pregunta, opciones, correcta),
            f"Tarjeta de quiz de la escena {e['id']}")

"""Sticky animado por código: muñeco vectorial (cairo) con articulaciones, caras y bufanda azul.

Ángulos de brazos y piernas en grados: 0 = hacia abajo, 90 = hacia la derecha, -90 = hacia la izquierda.
`sticky(ctx, x, y, s, pose, cara, t)` dibuja a Sticky con la cadera en (x, y) y tamaño s (1 ≈ 430 px de alto).
"""
import math

import cairo

AZUL = (0.231, 0.510, 0.965)
AZUL_OSC = (0.10, 0.27, 0.62)
NEGRO = (0.06, 0.06, 0.08)
BLANCO = (1, 1, 1)
AMARILLO = (1.0, 0.86, 0.10)

# ---------------------------------------------------------------- utilidades de animación


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, a, b):
    """Avance 0..1 de t entre a y b."""
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def suave(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def rebote(x, s=1.8):
    """Entra pasándose un poco y vuelve (efecto 'pop')."""
    x = clamp(x) - 1
    return 1 + x * x * ((s + 1) * x + s)


def lerp(a, b, x):
    return a + (b - a) * x


def _dir(ang):
    r = math.radians(ang)
    return math.sin(r), math.cos(r)


def _punto(p, ang, largo):
    dx, dy = _dir(ang)
    return p[0] + dx * largo, p[1] + dy * largo


def parpadeo(t, cada=3.1, desfase=0.0):
    """0 = ojos abiertos, 1 = cerrados; un parpadeo corto cada `cada` segundos."""
    u = (t + desfase) % cada
    return max(0.0, 1 - abs(u - 0.09) / 0.09) if u < 0.18 else 0.0


# ---------------------------------------------------------------- poses

POSE_BASE = dict(lean=0, head=0, aL1=-18, aL2=-8, aR1=18, aR2=8, lL1=-7, lL2=0, lR1=7, lR2=0, viento=0.0)
CARA_BASE = dict(ojos="normal", boca="smile", cejas=None, mira=(0.0, 0.0), parpadeo=0.0, sudor=False, rubor=False)


def pose_caminar(fase, amp=24, lean=3):
    s = math.sin(fase)
    return dict(lean=lean, lL1=amp * s, lL2=-max(0, math.cos(fase)) * 22, lR1=-amp * s,
                lR2=-max(0, -math.cos(fase)) * 22, aL1=-12 - amp * 0.8 * s, aL2=12, aR1=12 + amp * 0.8 * s, aR2=12)


def pose_correr(fase, direccion=1):
    """direccion 1 = hacia la derecha, -1 = hacia la izquierda."""
    s, c = math.sin(fase), math.cos(fase)
    d = direccion
    return dict(lean=14 * d, lL1=d * 42 * s, lL2=-d * max(0, c) * 70, lR1=-d * 42 * s, lR2=-d * max(0, -c) * 70,
                aL1=d * (-40 * s) - 10, aL2=d * 70, aR1=d * (40 * s) + 10, aR2=d * 70, viento=d)


def rebote_paso(fase, amp):
    return -abs(math.sin(fase)) * amp


# ---------------------------------------------------------------- dibujo de Sticky


def _miembro(ctx, pts, s):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.set_source_rgb(*NEGRO)
    ctx.set_line_width(19 * s)
    ctx.stroke_preserve()
    ctx.set_source_rgb(*BLANCO)
    ctx.set_line_width(10 * s)
    ctx.stroke()


def _colas(ctx, s, viento, t):
    """Las dos puntas de la bufanda: cuelgan o vuelan hacia atrás con el viento."""
    w = abs(viento)
    sentido = -1 if viento >= 0 else 1  # vuelan al lado contrario de la carrera
    for k, ox in enumerate((8, 22)):
        pts = []
        for i in range(10):
            u = i / 9
            largo = 80 * s * u
            onda = math.sin(t * (5 + 9 * w) + u * 5 + k * 1.3) * (3 + 10 * w) * s * u
            x = ox * s * (1 - w) + sentido * w * largo * 1.15 + (1 - w) * u * 6 * s + onda * (1 - w)
            y = 12 * s + (1 - w) * largo + w * (u * 18 * s + onda)
            pts.append((x, y))
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.set_source_rgb(*NEGRO)
        ctx.set_line_width(22 * s)
        ctx.stroke_preserve()
        ctx.set_source_rgb(*(AZUL if k else AZUL_OSC))
        ctx.set_line_width(15 * s)
        ctx.stroke()


def _redondeado(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _cara(ctx, s, c):
    mx, my = c["mira"]
    fx, fy = mx * 10 * s, my * 6 * s
    ctx.set_source_rgb(*NEGRO)
    if c["rubor"]:
        for sx in (-1, 1):
            ctx.save()
            ctx.translate(sx * 38 * s + fx, 16 * s + fy)
            ctx.scale(1.4, 0.8)
            ctx.arc(0, 0, 9 * s, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgba(1, 0.45, 0.55, 0.55)
            ctx.fill()
    for sx in (-1, 1):
        ex, ey = sx * 26 * s + fx, -10 * s + fy
        tipo = c["ojos"]
        if tipo in ("normal", "wide"):
            r = (23 if tipo == "wide" else 18) * s
            pr = (7 if tipo == "wide" else 9) * s
            sy = 1 - c["parpadeo"]
            if sy < 0.15:
                ctx.move_to(ex - r, ey)
                ctx.line_to(ex + r, ey)
                ctx.set_source_rgb(*NEGRO)
                ctx.set_line_width(4.5 * s)
                ctx.stroke()
            else:
                ctx.save()
                ctx.translate(ex, ey)
                ctx.scale(1, sy)
                ctx.arc(0, 0, r, 0, 2 * math.pi)
                ctx.set_source_rgb(*BLANCO)
                ctx.fill_preserve()
                ctx.set_source_rgb(*NEGRO)
                ctx.set_line_width(3.5 * s)
                ctx.stroke()
                ctx.arc(mx * 5 * s, my * 4 * s, pr, 0, 2 * math.pi)
                ctx.fill()
                ctx.restore()
        elif tipo == "happy":
            ctx.arc(ex, ey + 5 * s, 12 * s, math.pi * 1.1, math.pi * 1.9)
            ctx.set_source_rgb(*NEGRO)
            ctx.set_line_width(4.5 * s)
            ctx.stroke()
        else:  # closed
            ctx.move_to(ex - 13 * s, ey)
            ctx.line_to(ex + 13 * s, ey)
            ctx.set_source_rgb(*NEGRO)
            ctx.set_line_width(4.5 * s)
            ctx.stroke()
        # cejas
        if c["cejas"] == "worried":
            ctx.move_to(ex + sx * 16 * s, ey - 26 * s)
            ctx.line_to(ex - sx * 8 * s, ey - 34 * s)
        elif c["cejas"] == "up":
            ctx.move_to(ex - 13 * s, ey - 36 * s)
            ctx.line_to(ex + 13 * s, ey - 38 * s)
        if c["cejas"]:
            ctx.set_source_rgb(*NEGRO)
            ctx.set_line_width(4.5 * s)
            ctx.stroke()
    # boca
    bx, by = fx, 26 * s + fy
    b = c["boca"]
    ctx.set_source_rgb(*NEGRO)
    ctx.set_line_width(4.5 * s)
    if b == "smile":
        ctx.arc(bx, by - 12 * s, 16 * s, 0.22 * math.pi, 0.78 * math.pi)
        ctx.stroke()
    elif b == "big":
        ctx.move_to(bx - 19 * s, by - 4 * s)
        ctx.arc_negative(bx, by - 4 * s, 19 * s, math.pi, 0)
        ctx.close_path()
        ctx.fill()
    elif b == "o":
        ctx.save()
        ctx.translate(bx, by)
        ctx.scale(0.8, 1)
        ctx.arc(0, 0, 8 * s, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()
    elif b == "open":
        ctx.save()
        ctx.translate(bx, by + 2 * s)
        ctx.scale(0.7, 1)
        ctx.arc(0, 0, 15 * s, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()
    elif b == "frown":
        ctx.arc(bx, by + 14 * s, 14 * s, 1.25 * math.pi, 1.75 * math.pi)
        ctx.stroke()
    elif b == "wavy":
        for i in range(7):
            x = bx - 18 * s + i * 6 * s
            y = by + (3 * s if i % 2 else -3 * s)
            (ctx.move_to if i == 0 else ctx.line_to)(x, y)
        ctx.stroke()
    else:  # flat
        ctx.move_to(bx - 12 * s, by)
        ctx.line_to(bx + 12 * s, by)
        ctx.stroke()
    if c["sudor"]:
        ctx.save()
        ctx.translate(50 * s, -30 * s)
        ctx.move_to(0, -16 * s)
        ctx.curve_to(8 * s, -2 * s, 10 * s, 10 * s, 0, 10 * s)
        ctx.curve_to(-10 * s, 10 * s, -8 * s, -2 * s, 0, -16 * s)
        ctx.set_source_rgb(0.55, 0.85, 1.0)
        ctx.fill_preserve()
        ctx.set_source_rgb(*NEGRO)
        ctx.set_line_width(3 * s)
        ctx.stroke()
        ctx.restore()


def sticky(ctx, x, y, s=1.0, pose=None, cara=None, t=0.0):
    """Dibuja a Sticky con la cadera en (x, y). Devuelve el centro de la cabeza."""
    p = {**POSE_BASE, **(pose or {})}
    c = {**CARA_BASE, **(cara or {})}
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    lean = p["lean"]
    cadera = (x, y)
    arriba = 180 - lean
    cuello = _punto(cadera, arriba, 150 * s)
    hombro = _punto(cadera, arriba, 126 * s)
    R = 70 * s
    centro = _punto(cuello, 180 - lean - p["head"], R + 4 * s)

    def brazo(a1, a2):
        codo = _punto(hombro, a1 - lean, 70 * s)
        return [hombro, codo, _punto(codo, a1 + a2 - lean, 64 * s)]

    def pierna(a1, a2):
        rodilla = _punto(cadera, a1, 78 * s)
        return [cadera, rodilla, _punto(rodilla, a1 + a2, 76 * s)]

    _miembro(ctx, brazo(p["aL1"], p["aL2"]), s)
    _miembro(ctx, pierna(p["lL1"], p["lL2"]), s)
    _miembro(ctx, pierna(p["lR1"], p["lR2"]), s)
    # colas de la bufanda (detrás del cuerpo)
    ctx.save()
    ctx.translate(*cuello)
    ctx.rotate(math.radians(lean))
    _colas(ctx, s, p["viento"], t)
    ctx.restore()
    _miembro(ctx, [cadera, cuello], s)
    # cabeza
    ctx.save()
    ctx.translate(*centro)
    ctx.rotate(math.radians(lean + p["head"]))
    ctx.arc(0, 0, R, 0, 2 * math.pi)
    ctx.set_source_rgb(*BLANCO)
    ctx.fill_preserve()
    ctx.set_source_rgb(*NEGRO)
    ctx.set_line_width(5.5 * s)
    ctx.stroke()
    _cara(ctx, s, c)
    ctx.restore()
    # bufanda alrededor del cuello
    ctx.save()
    ctx.translate(*cuello)
    ctx.rotate(math.radians(lean))
    _redondeado(ctx, -38 * s, -10 * s, 76 * s, 26 * s, 12 * s)
    ctx.set_source_rgb(*AZUL)
    ctx.fill_preserve()
    ctx.set_source_rgb(*NEGRO)
    ctx.set_line_width(4 * s)
    ctx.stroke()
    ctx.move_to(-20 * s, -8 * s)
    ctx.line_to(-16 * s, 14 * s)
    ctx.move_to(4 * s, -8 * s)
    ctx.line_to(8 * s, 14 * s)
    ctx.set_source_rgba(*AZUL_OSC, 0.8)
    ctx.set_line_width(3 * s)
    ctx.stroke()
    ctx.restore()
    _miembro(ctx, brazo(p["aR1"], p["aR2"]), s)
    ctx.restore()
    return centro


# ---------------------------------------------------------------- texto y adornos


def texto(ctx, s, x, y, tam, color=BLANCO, fuente="Segoe UI", borde=0.0, color_borde=NEGRO,
          ancla="c", alpha=1.0, escala=1.0, giro=0.0, negrita=True):
    ctx.save()
    ctx.select_font_face(fuente, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if negrita else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(tam)
    ext = ctx.text_extents(s)
    ctx.translate(x, y)
    ctx.rotate(math.radians(giro))
    ctx.scale(escala, escala)
    ox = {"c": -ext.x_advance / 2, "l": 0, "r": -ext.x_advance}[ancla]
    ctx.move_to(ox, -(ext.y_bearing + ext.height / 2))
    ctx.text_path(s)
    if borde:
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_width(borde * 2)
        ctx.set_source_rgba(*color_borde, alpha)
        ctx.stroke_preserve()
    ctx.set_source_rgba(*color, alpha)
    ctx.fill()
    ctx.restore()
    return ext.x_advance * escala


def exclamacion(ctx, x, y, tam, alpha=1.0, giro=8):
    texto(ctx, "!", x, y, tam, AMARILLO, borde=tam * 0.07, alpha=alpha, giro=giro)


def estrella(ctx, x, y, r, color=AMARILLO):
    for i in range(10):
        ang = math.pi / 5 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        (ctx.move_to if i == 0 else ctx.line_to)(x + math.cos(ang) * rr, y + math.sin(ang) * rr)
    ctx.close_path()
    ctx.set_source_rgb(*color)
    ctx.fill_preserve()
    ctx.set_source_rgb(*NEGRO)
    ctx.set_line_width(r * 0.15)
    ctx.stroke()


def nube_polvo(ctx, x, y, avance, tam=40, color=(0.75, 0.70, 0.62)):
    """Bolitas de polvo que crecen y se desvanecen (avance 0..1)."""
    if not 0 <= avance <= 1:
        return
    for k, (dx, dy) in enumerate(((-1, 0), (0, -0.6), (1, 0), (-0.5, -0.3), (0.6, -0.4))):
        r = tam * (0.35 + 0.65 * avance) * (0.7 + 0.1 * k % 3)
        ctx.arc(x + dx * tam * avance * 1.4, y + dy * tam * avance, r * 0.5, 0, 2 * math.pi)
        ctx.set_source_rgba(*color, 0.7 * (1 - avance))
        ctx.fill()


def redondeado(ctx, x, y, w, h, r):
    _redondeado(ctx, x, y, w, h, r)

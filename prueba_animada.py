"""Prueba de 30 s: Sticky animado por código (cairo) + voz edge-tts + efectos.

Uso: python prueba_animada.py   ->  videos/prueba-animada/video.mp4
"""
import asyncio
import json
import math
import random
import subprocess
import sys
import wave
from pathlib import Path

import cairo
import edge_tts
import numpy as np

from pipeline.animacion import (AMARILLO, AZUL, BLANCO, NEGRO, estrella, exclamacion, lerp, nube_polvo,
                                parpadeo, pose_caminar, pose_correr, prog, rebote, rebote_paso, redondeado,
                                sticky, suave, texto)

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "videos" / "prueba-animada"
TRABAJO = SALIDA / "trabajo"
W, H, FPS, SR = 1920, 1080, 30, 44100
CFG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
SUELO = 915  # y de los pies

LINEAS = [
    "Son las once y cuarenta y siete de la noche, y Sticky camina solo por un camino del monte, alumbrado apenas por la luna.",
    "De pronto, escucha algo. Un golpe seco… y otro… y otro.",
    "Golpes secos, un silencio raro y animales que huyen: son las señales.",
    "Y en el barro aparecen unas huellas… de una sola pata.",
    "Sticky no se queda a averiguar quién las dejó, y sale corriendo tan rápido como puede.",
    "¿Quieres saber qué era? Te lo cuento en el próximo video.",
]
HORAS = ["11:47 PM", "11:47 PM", "11:48 PM", "11:49 PM", "11:49 PM", "11:50 PM"]
ENTRADA, COLA = 0.12, 0.28
EXTRA_FINAL = 3.6

# ======================================================================== voz


async def _tts(texto, destino):
    v = CFG["voz"]
    com = edge_tts.Communicate(texto, v["nombre"], rate=v["velocidad"], pitch=v["tono"], volume=v["volumen"],
                               boundary="WordBoundary")
    palabras = []
    with open(destino, "wb") as f:
        async for tr in com.stream():
            if tr["type"] == "audio":
                f.write(tr["data"])
            elif tr["type"] == "WordBoundary":
                ini = tr["offset"] / 1e7
                palabras.append({"p": tr["text"], "ini": ini, "fin": ini + tr["duration"] / 1e7})
    return palabras


def _decodificar(ruta):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ruta), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def preparar_voz():
    TRABAJO.mkdir(parents=True, exist_ok=True)
    escenas, t0 = [], 0.0
    for i, linea in enumerate(LINEAS):
        mp3, js = TRABAJO / f"voz_{i}.mp3", TRABAJO / f"voz_{i}.json"
        if not (mp3.exists() and js.exists() and json.loads(js.read_text(encoding="utf-8"))["texto"] == linea):
            pal = asyncio.run(_tts(linea, mp3))
            js.write_text(json.dumps({"texto": linea, "palabras": pal}, ensure_ascii=False), encoding="utf-8")
        pal = json.loads(js.read_text(encoding="utf-8"))["palabras"]
        audio = _decodificar(mp3)
        recorte = max(0.0, pal[0]["ini"] - 0.05)
        fin = min(len(audio) / SR, pal[-1]["fin"] + 0.12)
        audio = audio[int(recorte * SR):int(fin * SR)]
        dur = ENTRADA + len(audio) / SR + COLA + (EXTRA_FINAL if i == len(LINEAS) - 1 else 0)
        palabras = [{"p": w["p"], "ini": ENTRADA + w["ini"] - recorte, "fin": ENTRADA + w["fin"] - recorte} for w in pal]
        escenas.append({"i": i, "t0": t0, "dur": dur, "audio": audio, "palabras": palabras})
        t0 += dur
    return escenas


def momento(esc, trozo, n=0, defecto=0.0):
    """Tiempo (local a la escena) de la n-ésima palabra que contiene `trozo`."""
    hits = [w["ini"] for w in esc["palabras"] if trozo.lower() in w["p"].lower()]
    return hits[n] if len(hits) > n else defecto

# ======================================================================== sonido


def _whoosh(dur=0.45):
    n = int(dur * SR)
    ruido = np.random.default_rng(1).standard_normal(n)
    out, y = np.zeros(n), 0.0
    for k in range(n):
        a = 0.02 + 0.25 * math.sin(math.pi * k / n)
        y += a * (ruido[k] - y)
        out[k] = y
    env = np.sin(np.linspace(0, math.pi, n)) ** 2
    return out * env * 1.4


def _golpe(freq=70, dur=0.35, vol=1.0):
    t = np.arange(int(dur * SR)) / SR
    tono = np.sin(2 * math.pi * freq * t * (1 - 0.3 * t)) * np.exp(-t * 14)
    clic = np.random.default_rng(2).standard_normal(len(t)) * np.exp(-t * 90) * 0.35
    return (tono + clic) * vol


def mezclar(escenas, total, efectos):
    pista = np.zeros(int(total * SR) + SR)

    def poner(muestra, t, vol=1.0):
        a = int(t * SR)
        b = min(len(pista), a + len(muestra))
        pista[a:b] += muestra[:b - a] * vol

    for e in escenas:
        poner(e["audio"], e["t0"] + ENTRADA)
        if e["i"] > 0:
            poner(_whoosh(), e["t0"] - 0.12, 0.22)
    for tipo, t, vol in efectos:
        poner(_golpe() if tipo == "golpe" else _golpe(50, 0.5) if tipo == "caida" else _whoosh(0.35), t, vol)
    pista /= max(1.0, np.abs(pista).max() / 0.95)
    ruta = TRABAJO / "mezcla.wav"
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((pista[:int(total * SR)] * 32767).astype(np.int16).tobytes())
    return ruta

# ======================================================================== fondos

random.seed(7)
ARBOLES = []
for capa, (color, n, alto) in enumerate((((0.05, 0.20, 0.24), 9, 520), ((0.035, 0.15, 0.17), 8, 600),
                                         ((0.02, 0.10, 0.11), 6, 700))):
    for k in range(n):
        x = (k + random.uniform(-0.3, 0.3)) * (W + 400) / n - 200
        copa = [(random.uniform(-110, 110), random.uniform(-60, 60), random.uniform(80, 150)) for _ in range(4)]
        ARBOLES.append((capa, color, x, alto * random.uniform(0.8, 1.1), random.uniform(28, 48), copa))
LUCIERNAGAS = [(random.uniform(0, W), random.uniform(250, 850), random.uniform(0, 6.28), random.uniform(0.3, 0.9))
               for _ in range(28)]


def fondo_selva(ctx, t, oscuro=0.0, desplaza=0.0):
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, 0.03, 0.08, 0.20)
    g.add_color_stop_rgb(0.7, 0.05, 0.25, 0.33)
    ctx.set_source(g)
    ctx.paint()
    # luna
    rg = cairo.RadialGradient(1520, 190, 40, 1520, 190, 260)
    rg.add_color_stop_rgba(0, 1, 0.95, 0.75, 0.35)
    rg.add_color_stop_rgba(1, 1, 0.95, 0.75, 0)
    ctx.set_source(rg)
    ctx.arc(1520, 190, 260, 0, 2 * math.pi)
    ctx.fill()
    ctx.arc(1520, 190, 62, 0, 2 * math.pi)
    ctx.set_source_rgb(1, 0.96, 0.82)
    ctx.fill()
    for capa, color, x, alto, ancho, copa in ARBOLES:
        par = (capa + 1) * 0.35 * desplaza
        bx = x + par
        ctx.rectangle(bx - ancho / 2, SUELO - alto, ancho, alto + 200)
        ctx.set_source_rgb(*color)
        ctx.fill()
        for dx, dy, r in copa:
            ctx.arc(bx + dx, SUELO - alto + dy, r, 0, 2 * math.pi)
            ctx.fill()
        if capa == 2:  # bejucos
            ctx.move_to(bx + 40, SUELO - alto + 40)
            ctx.curve_to(bx + 60, SUELO - alto + 200, bx + 20, SUELO - alto + 260, bx + 50, SUELO - alto + 330)
            ctx.set_line_width(5)
            ctx.stroke()
    # suelo
    ctx.rectangle(0, SUELO - 10, W, H - SUELO + 10)
    ctx.set_source_rgb(0.07, 0.16, 0.12)
    ctx.fill()
    ctx.save()
    ctx.translate(W / 2, SUELO + 70)
    ctx.scale(1, 0.12)
    ctx.arc(0, 0, 900, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgb(0.16, 0.24, 0.17)
    ctx.fill()
    # luciérnagas
    for x0, y0, f, v in LUCIERNAGAS:
        x = (x0 + math.sin(t * v + f) * 40 + desplaza * 0.6) % W
        y = y0 + math.cos(t * v * 1.3 + f) * 25
        a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 3 * v + f))
        rg = cairo.RadialGradient(x, y, 0, x, y, 16)
        rg.add_color_stop_rgba(0, 1, 0.95, 0.4, 0.9 * a)
        rg.add_color_stop_rgba(1, 1, 0.95, 0.4, 0)
        ctx.set_source(rg)
        ctx.arc(x, y, 16, 0, 2 * math.pi)
        ctx.fill()
    if oscuro:
        ctx.set_source_rgba(0, 0, 0.02, oscuro)
        ctx.paint()


def vineta(ctx):
    rg = cairo.RadialGradient(W / 2, H / 2, H * 0.45, W / 2, H / 2, H * 1.05)
    rg.add_color_stop_rgba(0, 0, 0, 0, 0)
    rg.add_color_stop_rgba(1, 0, 0, 0, 0.55)
    ctx.set_source(rg)
    ctx.paint()


def camara(ctx, zoom, fx=W / 2, fy=H / 2):
    ctx.translate(fx, fy)
    ctx.scale(zoom, zoom)
    ctx.translate(-fx, -fy)


def huella(ctx, x, y, esc, alpha):
    """Huella de pezuña (forma de herradura con una muesca)."""
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(esc, esc * 0.45)
    ctx.move_to(0, 0)
    ctx.arc(0, 0, 46, math.radians(-160), math.radians(160))
    ctx.close_path()
    ctx.restore()
    ctx.set_source_rgba(0.30, 0.20, 0.12, alpha)
    ctx.fill_preserve()
    ctx.set_source_rgba(0.02, 0.03, 0.02, alpha)
    ctx.set_line_width(4)
    ctx.stroke()


def ojos_rojos(ctx, x, y, alpha, cierre=0.0):
    for dx in (-34, 34):
        rg = cairo.RadialGradient(x + dx, y, 0, x + dx, y, 60)
        rg.add_color_stop_rgba(0, 1, 0.1, 0.05, 0.6 * alpha)
        rg.add_color_stop_rgba(1, 1, 0.1, 0.05, 0)
        ctx.set_source(rg)
        ctx.arc(x + dx, y, 60, 0, 2 * math.pi)
        ctx.fill()
        ctx.save()
        ctx.translate(x + dx, y)
        ctx.scale(1, max(0.05, 0.55 * (1 - cierre)))
        ctx.arc(0, 0, 24, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(1, 0.2, 0.1, alpha)
        ctx.fill()

# ======================================================================== escenas


def esc_caminar(ctx, t, e):
    ctx.save()
    camara(ctx, lerp(1.0, 1.08, suave(t / e["dur"])), 960, 700)
    fondo_selva(ctx, t, desplaza=-t * 30)
    parada = min(3.0, e["dur"] - 1.4)
    if t < parada:
        x = lerp(-250, 860, t / parada)
        fase = t * 9
        sticky(ctx, x, SUELO - 231 + rebote_paso(fase, 10), 1.5, pose_caminar(fase),
               dict(parpadeo=parpadeo(t), mira=(0.6, 0)), t)
    else:
        u = t - parada
        mira = (math.sin(u * 4) * 0.9, 0)
        sticky(ctx, 860, SUELO - 231, 1.5, dict(head=math.sin(u * 4) * 6),
               dict(mira=mira, parpadeo=parpadeo(t, 2.2), boca="flat"), t)
    ctx.restore()


def esc_escucha(ctx, t, e, efectos_t):
    fondo_selva(ctx, t, oscuro=0.45, desplaza=40)
    t_esc = momento(e, "escucha", 0, 0.8)
    golpes = [momento(e, "golpe", 0, 1.8), momento(e, "otro", 0, 2.6), momento(e, "otro", 1, 3.4)]
    sacudida = sum(math.exp(-(t - g) * 12) * math.sin((t - g) * 50) for g in golpes if t >= g)
    ctx.save()
    camara(ctx, lerp(1.0, 1.12, suave(t / e["dur"])), 900, 470)
    asustado = t >= golpes[0]
    cara = dict(parpadeo=parpadeo(t, 2.5), mira=(1, -0.1) if t >= t_esc else (0, 0),
                ojos="wide" if asustado else "normal",
                boca="o" if t >= t_esc and not asustado else ("wavy" if t >= golpes[2] else ("open" if asustado else "smile")),
                cejas="up" if t >= t_esc else None, sudor=t >= golpes[2])
    sticky(ctx, 880 + sacudida * 6, 1150, 3.0, dict(head=sacudida * 3, aL1=-10, aR1=10), cara, t)
    if asustado:
        a = rebote(prog(t, golpes[0], golpes[0] + 0.3))
        exclamacion(ctx, 1170, 170, 170 * a, giro=12)
    ctx.restore()
    for k, g in enumerate(golpes):
        if t >= g:
            u = t - g
            r = 40 + u * 520
            ctx.arc(1600, 520, r, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 1, max(0, 0.6 - u * 0.8))
            ctx.set_line_width(10)
            ctx.stroke()
            texto(ctx, "TOC", 1560 + k * 70 - 70, 300 + k * 150, 110, BLANCO, borde=9,
                  escala=rebote(prog(t, g, g + 0.25)), giro=-10 + k * 10, alpha=min(1, max(0, 2.2 - u)))
    vineta(ctx)


def esc_senales(ctx, t, e):
    ctx.set_source_rgb(0.04, 0.11, 0.24)
    ctx.paint()
    ctx.set_source_rgba(1, 1, 1, 0.05)
    ctx.set_line_width(1.5)
    for x in range(0, W, 60):
        ctx.move_to(x, 0)
        ctx.line_to(x, H)
    for y in range(0, H, 60):
        ctx.move_to(0, y)
        ctx.line_to(W, y)
    ctx.stroke()
    a = rebote(prog(t, 0.0, 0.4))
    texto(ctx, "SEÑALES DE LA PATASOLA", W / 2, 120, 64, BLANCO, escala=a)
    ancho = 760 * suave(prog(t, 0.2, 0.7))
    ctx.rectangle(W / 2 - ancho / 2, 170, ancho, 6)
    ctx.set_source_rgb(*AZUL)
    ctx.fill()
    items = [("GOLPES SECOS", momento(e, "olpes", 0, 0.3)), ("SILENCIO RARO", momento(e, "silencio", 0, 1.2)),
             ("ANIMALES QUE HUYEN", momento(e, "animales", 0, 2.0))]
    nivel = 0.12
    for k, (nombre, tk) in enumerate(items):
        y = 330 + k * 180
        u = prog(t, tk, tk + 0.35)
        if u <= 0:
            continue
        nivel = max(nivel, lerp(0.12 + 0.27 * k, 0.12 + 0.27 * (k + 1), suave(prog(t, tk, tk + 0.6))))
        dx = (1 - suave(u)) * -120
        ctx.save()
        ctx.translate(dx, 0)
        redondeado(ctx, 220, y - 70, 1060, 140, 30)
        ctx.set_source_rgba(1, 1, 1, 0.08 * u)
        ctx.fill()
        ctx.arc(310, y, 52, 0, 2 * math.pi)
        ctx.set_source_rgba(*AZUL, u)
        ctx.fill()
        _icono(ctx, k, 310, y, t, u)
        texto(ctx, nombre, 400, y, 54, BLANCO, ancla="l", alpha=u)
        c = prog(t, tk + 0.35, tk + 0.7)
        if c > 0:
            ctx.move_to(1180, y)
            pts = [(1180, y), (1210, y + 30), (1260, y - 35)]
            largo = c * 2
            ctx.move_to(*pts[0])
            ctx.line_to(*[lerp(pts[0][i], pts[1][i], min(1, largo)) for i in (0, 1)])
            if largo > 1:
                ctx.line_to(*[lerp(pts[1][i], pts[2][i], largo - 1) for i in (0, 1)])
            ctx.set_source_rgb(0.25, 0.9, 0.45)
            ctx.set_line_width(16)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
        ctx.restore()
    nivel = max(nivel, 0.93 * suave(prog(t, momento(e, "señales", 0, 3.0), momento(e, "señales", 0, 3.0) + 0.5)))
    # medidor de miedo
    x0, y0, alto = 1500, 260, 520
    redondeado(ctx, x0, y0, 100, alto, 30)
    ctx.set_source_rgba(1, 1, 1, 0.12)
    ctx.fill_preserve()
    ctx.set_source_rgb(1, 1, 1)
    ctx.set_line_width(5)
    ctx.stroke()
    lleno = alto * nivel
    col = (lerp(0.2, 1, min(1, nivel * 1.6)), lerp(0.9, 0.2, max(0, nivel - 0.4) / 0.6), 0.25)
    redondeado(ctx, x0 + 12, y0 + alto - lleno + 12, 76, max(30, lleno - 24), 24)
    ctx.set_source_rgb(*col)
    ctx.fill()
    texto(ctx, "MIEDO", x0 + 50, y0 + alto + 60, 46, BLANCO)
    texto(ctx, f"{int(nivel * 100)}%", x0 + 50, y0 - 50, 50, col)
    # Sticky pequeño mirando el medidor
    sticky(ctx, 1770, 905, 0.5, dict(aR1=150, aR2=20), dict(cejas="worried", boca="wavy", mira=(-1, -0.5),
                                                              parpadeo=parpadeo(t), sudor=nivel > 0.6), t)


def _icono(ctx, k, x, y, t, a):
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.set_line_width(7)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    if k == 0:  # ondas de sonido
        for r in (14, 28, 42):
            ctx.arc(x - 16, y, r * (0.9 + 0.1 * math.sin(t * 8)), -0.6, 0.6)
            ctx.stroke()
    elif k == 1:  # silencio: parlante tachado
        ctx.move_to(x - 26, y - 12)
        ctx.line_to(x - 12, y - 12)
        ctx.line_to(x + 6, y - 28)
        ctx.line_to(x + 6, y + 28)
        ctx.line_to(x - 12, y + 12)
        ctx.line_to(x - 26, y + 12)
        ctx.close_path()
        ctx.fill()
        ctx.move_to(x - 34, y - 34)
        ctx.line_to(x + 34, y + 34)
        ctx.stroke()
    else:  # pájaros que huyen
        for i, (dx, dy) in enumerate(((-22, 12), (8, -10), (26, 14))):
            ala = math.sin(t * 14 + i) * 8
            ctx.move_to(x + dx - 14, y + dy - ala)
            ctx.line_to(x + dx, y + dy)
            ctx.line_to(x + dx + 14, y + dy - ala)
            ctx.stroke()


def esc_huellas(ctx, t, e):
    ctx.save()
    camara(ctx, lerp(1.0, 1.07, suave(t / e["dur"])), 1150, 820)
    fondo_selva(ctx, t, oscuro=0.15, desplaza=-60)
    t_sola = momento(e, "sola", 0, e["dur"] - 1.0)
    n = 6
    for k in range(n):
        tk = lerp(0.35, t_sola - 0.2, k / (n - 1))
        x = 1800 - k * 150
        y = SUELO + 40 + (12 if k % 2 else -8)
        if t >= tk:
            u = prog(t, tk, tk + 0.18)
            huella(ctx, x, y, 1.3 + 0.5 * rebote(u), 0.95)
            nube_polvo(ctx, x, y, prog(t, tk, tk + 0.6), 50)
    temblor = math.sin(t * 55) * 3 if t > 0.6 else 0
    sticky(ctx, 620 + temblor, SUELO - 216, 1.4, dict(aL1=-35, aL2=-110, aR1=35, aR2=110, lL1=-10, lR1=10),
           dict(cejas="worried", boca="wavy", sudor=t > 1.0, mira=(1, 0.5), parpadeo=parpadeo(t, 1.9)), t)
    ctx.restore()
    if t >= t_sola:
        a = rebote(prog(t, t_sola, t_sola + 0.3))
        texto(ctx, "¡UNA SOLA PATA!", 1300, 330, 110, AMARILLO, fuente="Segoe Print", borde=8, escala=a, giro=-5)
    vineta(ctx)


def esc_huye(ctx, t, e):
    ctx.save()
    camara(ctx, lerp(1.04, 1.0, suave(t / e["dur"])), 960, 700)
    fondo_selva(ctx, t, oscuro=0.2, desplaza=-60)
    ojos_rojos(ctx, 1480, 560, suave(prog(t, 0.0, 0.6)), cierre=max(0, 1 - abs(t - 1.4) / 0.08) if abs(t - 1.4) < 0.08 else 0)
    arranque = 0.75
    if t < arranque:
        a = rebote(prog(t, 0.15, 0.4))
        sticky(ctx, 820, SUELO - 216, 1.4, dict(head=-4, aL1=-60, aL2=-40, aR1=60, aR2=40),
               dict(ojos="wide", boca="open", cejas="worried", mira=(1, 0)), t)
        if t > 0.15:
            exclamacion(ctx, 900, 300, 170 * a)
    else:
        u = t - arranque
        x = 820 - u * 1300
        fase = u * 16
        sticky(ctx, x, SUELO - 216 + rebote_paso(fase, 14), 1.4, pose_correr(fase, -1),
               dict(ojos="wide", boca="open", cejas="worried", mira=(-1, 0)), t)
        for k in range(4):  # polvo detrás
            tk = arranque + k * 0.16
            if t >= tk:
                nube_polvo(ctx, 820 - (tk - arranque) * 1300 + 60, SUELO, prog(t, tk, tk + 0.5), 40)
        for k in range(3):  # líneas de velocidad
            yy = SUELO - 420 + k * 120
            ctx.move_to(x + 150, yy)
            ctx.line_to(x + 340, yy)
            ctx.set_source_rgba(1, 1, 1, 0.6)
            ctx.set_line_width(6)
            ctx.stroke()
    ctx.restore()
    vineta(ctx)


def esc_caida(ctx, t, e):
    ctx.save()
    camara(ctx, lerp(1.0, 1.05, suave(t / e["dur"])), 960, 700)
    fondo_selva(ctx, t, oscuro=0.1, desplaza=-120)
    tropieza, cae = 0.7, 1.05
    if t < tropieza:
        x = lerp(2150, 1250, t / tropieza)
        fase = t * 16
        sticky(ctx, x, SUELO - 216 + rebote_paso(fase, 14), 1.4, pose_correr(fase, -1),
               dict(ojos="wide", boca="open", cejas="worried", mira=(-1, 0)), t)
    else:
        u = prog(t, tropieza, cae)
        levanta = suave(prog(t, cae + 1.6, cae + 2.2))
        ang = -88 * (u * u) * (1 - levanta)
        pie_x = 1250 - 200 * u
        ctx.save()
        ctx.translate(pie_x, SUELO)
        ctx.rotate(math.radians(ang))
        ctx.translate(-pie_x, -SUELO)
        tirado = t > cae + 0.9
        if levanta >= 1:  # de pie, saluda con vergüenza
            ola = math.sin((t - cae - 2.2) * 9)
            pose = dict(aR1=118 + ola * 14, aR2=45 + ola * 15, aL1=-150, aL2=-60, head=ola * 3)
            cara = dict(ojos="happy", boca="big", rubor=True)
        else:
            pose = dict(aL1=-150, aL2=-10, aR1=-170, aR2=-10, lL1=20, lR1=-15, lR2=30)
            cara = dict(ojos="happy" if tirado else "wide", boca="big" if tirado else "open", rubor=tirado,
                        cejas=None if tirado else "worried")
        sticky(ctx, pie_x, SUELO - 216, 1.4, pose, cara, t)
        ctx.restore()
        if t >= cae:
            nube_polvo(ctx, pie_x - 420, SUELO - 10, prog(t, cae, cae + 0.6), 70)
        if cae <= t < cae + 1.7:
            cx, cy = pie_x - 520, SUELO - 120
            for k in range(3):
                ang2 = t * 4 + k * 2.09
                estrella(ctx, cx + math.cos(ang2) * 110, cy - 80 + math.sin(ang2) * 30, 26)
    ctx.restore()
    # tarjeta final
    tt = momento(e, "próximo", 0, 2.4) - 0.4
    if t >= tt:
        u = suave(prog(t, tt, tt + 0.45))
        y = lerp(-200, 150, u)
        redondeado(ctx, W / 2 - 480, y - 105, 960, 210, 40)
        ctx.set_source_rgba(0.02, 0.05, 0.12, 0.85)
        ctx.fill_preserve()
        ctx.set_source_rgb(*AZUL)
        ctx.set_line_width(8)
        ctx.stroke()
        texto(ctx, "LA PATASOLA", W / 2, y - 22, 105, BLANCO, borde=4, color_borde=AZUL)
        texto(ctx, "MUY PRONTO EN EL CANAL", W / 2, y + 62, 42, AMARILLO)
    vineta(ctx)


# ======================================================================== capas comunes


def hud(ctx, hora, t_cambio, t):
    a = rebote(prog(t, t_cambio, t_cambio + 0.3)) if t_cambio is not None else 1
    ctx.save()
    ctx.translate(40, 40)
    ctx.scale(a, a)
    redondeado(ctx, 0, 0, 330, 64, 32)
    ctx.set_source_rgba(0.02, 0.04, 0.10, 0.8)
    ctx.fill_preserve()
    ctx.set_source_rgb(*AMARILLO)
    ctx.set_line_width(3)
    ctx.stroke()
    ctx.arc(34, 32, 9, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 0.25, 0.2, 0.5 + 0.5 * math.sin(t * 6))
    ctx.fill()
    texto(ctx, f"HORA · {hora}", 58, 32, 30, AMARILLO, ancla="l")
    ctx.restore()


def subtitulos(ctx, grupos, T):
    for g in grupos:
        if g[0]["ini"] <= T < g[-1]["fin_g"]:
            tam = 64
            ctx.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(tam)
            palabras = [w["p"].upper() for w in g]
            anchos = [ctx.text_extents(p).x_advance for p in palabras]
            hueco = tam * 0.5
            x = W / 2 - (sum(anchos) + hueco * (len(anchos) - 1)) / 2
            for w, p, an in zip(g, palabras, anchos):
                activa = w["ini"] <= T < w["fin_p"]
                texto(ctx, p, x + an / 2, 990, tam, AMARILLO if activa else BLANCO, borde=7,
                      escala=1.12 if activa else 1.0)
                x += an + hueco
            return


def grupos_subs(escenas):
    pal = [dict(w, ini=w["ini"] + e["t0"], fin=w["fin"] + e["t0"], esc=e["i"]) for e in escenas for w in e["palabras"]]
    grupos, act = [], []
    for w in pal:
        if act and (len(act) >= 3 or w["esc"] != act[-1]["esc"]):
            grupos.append(act)
            act = []
        act.append(w)
        if w["p"][-1:] in ".,;:?!…":
            grupos.append(act)
            act = []
    if act:
        grupos.append(act)
    for k, g in enumerate(grupos):
        sig = grupos[k + 1][0]["ini"] if k + 1 < len(grupos) else 1e9
        for i, w in enumerate(g):
            w["fin_p"] = g[i + 1]["ini"] if i + 1 < len(g) else min(w["fin"] + 0.25, sig)
        g[-1]["fin_g"] = min(g[-1]["fin"] + 0.25, sig)
    return grupos


# ======================================================================== render


def main():
    escenas = preparar_voz()
    total = sum(e["dur"] for e in escenas)
    print(f"duración total: {total:.2f}s; escenas: {[round(e['dur'], 2) for e in escenas]}")
    e2, e4, e6 = escenas[1], escenas[3], escenas[5]
    efectos = [("golpe", e2["t0"] + momento(e2, "golpe", 0, 1.8), 0.9),
               ("golpe", e2["t0"] + momento(e2, "otro", 0, 2.6), 0.9),
               ("golpe", e2["t0"] + momento(e2, "otro", 1, 3.4), 0.9),
               ("whoosh", escenas[4]["t0"] + 0.7, 0.35),
               ("caida", e6["t0"] + 1.05, 1.0)]
    t_sola = momento(e4, "sola", 0, e4["dur"] - 1.0)
    for k in range(6):
        efectos.append(("golpe", e4["t0"] + lerp(0.35, t_sola - 0.2, k / 5), 0.35))
    audio = mezclar(escenas, total, efectos)
    grupos = grupos_subs(escenas)
    funciones = [esc_caminar, esc_escucha, esc_senales, esc_huellas, esc_huye, esc_caida]
    sup = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    salida = SALIDA / "video.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", str(salida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nframes = int(round(total * FPS))
    hora_ant, t_cambio = None, None
    for f in range(nframes):
        T = f / FPS
        e = next(x for x in reversed(escenas) if T >= x["t0"])
        t = T - e["t0"]
        ctx = cairo.Context(sup)
        fn = funciones[e["i"]]
        fn(ctx, t, e) if fn is not esc_escucha else fn(ctx, t, e, None)
        if HORAS[e["i"]] != hora_ant:
            hora_ant, t_cambio = HORAS[e["i"]], T
        if e["i"] != 2:
            hud(ctx, hora_ant, t_cambio, T)
        subtitulos(ctx, grupos, T)
        sup.flush()
        proc.stdin.write(bytes(sup.get_data()))
        if f % 150 == 0:
            print(f"  frame {f}/{nframes}", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg falló")
    print("listo:", salida)


if __name__ == "__main__":
    main()

"""Cierre animado de Sticky al final de cada video y Short: "¡Suscríbete!" + clic + campanita.

Se renderiza una vez por orientación (horizontal 1920x1080, vertical 1080x1920) en recursos/
y se reutiliza mientras el texto y la voz no cambien. `agregar()` lo pega al final de un mp4.
"""
import asyncio
import json
import math
import subprocess
import wave
from pathlib import Path

import cairo
import edge_tts
import numpy as np

from .animacion import (AMARILLO, AZUL, BLANCO, NEGRO, lerp, parpadeo, prog, rebote, redondeado, sticky, suave,
                        texto)
from .comun import RAIZ, PipelineError, ejecutar

RECURSOS = RAIZ / "recursos"
SR = 48000
VERSION = 3  # subir si cambia el dibujo, para que se vuelva a renderizar

# ------------------------------------------------------------------ voz y sonidos


async def _tts(txt, cfg, destino):
    v = cfg["voz"]
    com = edge_tts.Communicate(txt, v["nombre"], rate=v["velocidad"], pitch=v["tono"], volume=v["volumen"],
                               boundary="WordBoundary")
    pal = []
    with open(destino, "wb") as f:
        async for tr in com.stream():
            if tr["type"] == "audio":
                f.write(tr["data"])
            elif tr["type"] == "WordBoundary":
                ini = tr["offset"] / 1e7
                pal.append({"p": tr["text"], "ini": ini, "fin": ini + tr["duration"] / 1e7})
    return pal


def _decodificar(ruta):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ruta), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def _campana(dur=1.6):
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for f, a, d in ((1318, 1.0, 3.0), (2637, 0.45, 4.5), (3637, 0.30, 6.0), (7120, 0.12, 9.0)):
        s += a * np.sin(2 * math.pi * f * t) * np.exp(-t * d)
    golpe = np.random.default_rng(3).standard_normal(len(t)) * np.exp(-t * 300) * 0.2
    return (s + golpe) * 0.35


def _clic():
    t = np.arange(int(0.05 * SR)) / SR
    return np.random.default_rng(4).standard_normal(len(t)) * np.exp(-t * 180) * 0.5


def _pop():
    t = np.arange(int(0.12 * SR)) / SR
    return np.sin(2 * math.pi * (300 + 900 * t / 0.12) * t) * np.exp(-t * 30) * 0.4


def _momento(pal, trozo, defecto):
    for w in pal:
        if trozo in w["p"].lower():
            return w["ini"]
    return defecto

# ------------------------------------------------------------------ dibujo


def _campanita(ctx, x, y, tam, giro):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(math.radians(giro))
    s = tam / 100
    ctx.move_to(-42 * s, 30 * s)
    ctx.curve_to(-40 * s, -10 * s, -36 * s, -48 * s, 0, -50 * s)
    ctx.curve_to(36 * s, -48 * s, 40 * s, -10 * s, 42 * s, 30 * s)
    ctx.line_to(52 * s, 42 * s)
    ctx.line_to(-52 * s, 42 * s)
    ctx.close_path()
    ctx.set_source_rgb(*AMARILLO)
    ctx.fill_preserve()
    ctx.set_source_rgb(*NEGRO)
    ctx.set_line_width(6 * s)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()
    ctx.arc(0, -56 * s, 9 * s, 0, 2 * math.pi)
    ctx.arc(math.sin(math.radians(-giro)) * 8 * s, 52 * s, 12 * s, 0, 2 * math.pi)
    ctx.set_source_rgb(*AMARILLO)
    ctx.fill_preserve()
    ctx.set_source_rgb(*NEGRO)
    ctx.stroke()
    ctx.restore()


def _cursor(ctx, x, y, esc):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(esc, esc)
    pts = [(0, 0), (0, 62), (16, 48), (28, 74), (40, 68), (28, 43), (48, 43)]
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.set_source_rgb(*BLANCO)
    ctx.fill_preserve()
    ctx.set_source_rgb(*NEGRO)
    ctx.set_line_width(4)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()
    ctx.restore()


def _cuadro(ctx, W, H, t, dur, pal, tiempos):
    vertical = H > W
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, 0.03, 0.07, 0.18)
    g.add_color_stop_rgb(1, 0.08, 0.26, 0.58)
    ctx.set_source(g)
    ctx.paint()
    # rayos de luz que giran detrás de Sticky
    cx, cy = (W * 0.5, H * 0.56) if vertical else (W * 0.3, H * 0.5)
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(t * 0.25)
    for k in range(12):
        a = k * math.pi / 6
        ctx.move_to(0, 0)
        ctx.arc(0, 0, max(W, H), a, a + math.pi / 14)
        ctx.close_path()
    ctx.set_source_rgba(1, 1, 1, 0.045)
    ctx.fill()
    ctx.restore()
    for k in range(30):  # chispitas
        px = (k * 337 % W + math.sin(t + k) * 20)
        py = (k * 211 % H - t * 40 * (1 + k % 3)) % H
        ctx.arc(px, py, 3 + k % 3, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.25 + 0.2 * math.sin(t * 3 + k))
        ctx.fill()

    t_sus, t_clic, t_camp = tiempos
    hablando = any(w["ini"] <= t < w["fin"] for w in pal)
    boca = ("big" if int(t * 11) % 2 == 0 else "o") if hablando else "big"
    entra = rebote(prog(t, 0.0, 0.35))
    s = (2.1 if vertical else 1.6) * entra
    x, y = (W * 0.5, H * 0.78) if vertical else (W * 0.3, H * 0.70)
    if t < t_sus:  # saluda
        ola = math.sin(t * 10)
        pose = dict(aR1=95 + ola * 8, aR2=55 + ola * 12, head=ola * 3)
    else:  # señala el botón
        pose = dict(aR1=100, aR2=65) if vertical else dict(aR1=100, aR2=-10, head=4)
    cara = dict(ojos="happy" if t < 0.6 or t > t_clic + 0.4 else "normal", boca=boca,
                mira=(0.3, -1) if vertical else (1, -0.3), parpadeo=parpadeo(t, 2.0), rubor=True)
    if s > 0.05:
        sticky(ctx, x, y + (1 - entra) * 300, s, pose, cara, t)

    # botón de suscribirse
    bx, by = (W * 0.5, H * 0.20) if vertical else (W * 0.66, H * 0.42)
    bw, bh = (720, 170) if vertical else (640, 160)
    if t >= t_sus:
        a = rebote(prog(t, t_sus, t_sus + 0.3))
        presion = 1 - 0.08 * max(0, 1 - abs(t - t_clic) / 0.08)
        hecho = t >= t_clic
        ctx.save()
        ctx.translate(bx, by)
        ctx.scale(a * presion, a * presion)
        redondeado(ctx, -bw / 2, -bh / 2, bw, bh, bh / 2)
        ctx.set_source_rgb(*((0.32, 0.34, 0.40) if hecho else (0.86, 0.09, 0.12)))
        ctx.fill_preserve()
        ctx.set_source_rgb(*NEGRO)
        ctx.set_line_width(6)
        ctx.stroke()
        texto(ctx, "¡SUSCRITO!" if hecho else "SUSCRÍBETE", 0, 0, bh * 0.42, BLANCO)
        ctx.restore()
        # cursor que llega y hace clic
        if t < t_clic + 0.6:
            u = suave(prog(t, t_sus + 0.15, t_clic))
            cx0, cy0 = (W * 0.85, H * 0.45) if vertical else (W * 0.95, H * 0.85)
            _cursor(ctx, lerp(cx0, bx + bw * 0.25, u), lerp(cy0, by + 10, u),
                    (1.3 if vertical else 1.1) * (0.85 if abs(t - t_clic) < 0.08 else 1))
    # campanita
    if t >= t_camp:
        a = rebote(prog(t, t_camp, t_camp + 0.3))
        giro = math.sin((t - t_camp) * 28) * 28 * math.exp(-(t - t_camp) * 1.6)
        kx, ky = (W * 0.5, H * 0.20 + 230) if vertical else (W * 0.66 + 440, H * 0.42)
        _campanita(ctx, kx, ky, (150 if vertical else 140) * a, giro)
        for k in range(3):  # rayitas de sonido
            d = (t - t_camp) % 0.6
            ctx.set_source_rgba(*AMARILLO, max(0, 1 - d / 0.6))
            ctx.set_line_width(7)
            for lado in (-1, 1):
                ang = math.radians(-60 + k * 30) if lado > 0 else math.radians(-120 - k * 30)
                r0, r1 = 95 + d * 60, 125 + d * 60
                ctx.move_to(kx + math.cos(ang) * r0, ky + math.sin(ang) * r0)
                ctx.line_to(kx + math.cos(ang) * r1, ky + math.sin(ang) * r1)
                ctx.stroke()
    if t > dur - 1.1:
        a = rebote(prog(t, dur - 1.1, dur - 0.8))
        ty = H * 0.42 if vertical else H * 0.68
        tx = W * 0.5 if vertical else W * 0.66 + 200
        texto(ctx, "¡NOS VEMOS EN LA PRÓXIMA!", tx, ty, (64 if vertical else 56) * a, AMARILLO, borde=6)

# ------------------------------------------------------------------ generar / agregar


def generar(cfg, vertical=False):
    """Renderiza (o reutiliza) el cierre. Devuelve (ruta_mp4, duración)."""
    co = cfg.get("outro", {})
    txt = co.get("texto_short" if vertical else "texto_video",
                 "¡Suscríbete y activa la campanita para no perderte la próxima historia!")
    W, H = (1080, 1920) if vertical else (1920, 1080)
    fps = cfg["video"]["fps"]
    RECURSOS.mkdir(exist_ok=True)
    nombre = "outro_vertical" if vertical else "outro_horizontal"
    mp4, firma = RECURSOS / f"{nombre}.mp4", RECURSOS / f"{nombre}.json"
    clave = {"texto": txt, "voz": cfg["voz"], "version": VERSION, "fps": fps}
    if mp4.exists() and firma.exists():
        guardado = json.loads(firma.read_text(encoding="utf-8"))
        if guardado.get("clave") == clave:
            return mp4, guardado["duracion"]
    mp3 = RECURSOS / f"{nombre}_voz.mp3"
    pal = asyncio.run(_tts(txt, cfg, mp3))
    if not pal:
        raise PipelineError("edge-tts no devolvió palabras para el cierre de suscripción.")
    voz = _decodificar(mp3)
    rec = max(0.0, pal[0]["ini"] - 0.05)
    voz = voz[int(rec * SR):int((pal[-1]["fin"] + 0.15) * SR)]
    entrada = 0.35
    pal = [dict(w, ini=w["ini"] - rec + entrada, fin=w["fin"] - rec + entrada) for w in pal]
    dur = entrada + len(voz) / SR + 1.4
    t_sus = _momento(pal, "suscr", entrada + 0.5)
    t_camp = _momento(pal, "campan", t_sus + 1.0)
    t_clic = min(t_sus + 0.75, t_camp - 0.1)
    pista = np.zeros(int(dur * SR) + SR)

    def poner(m, t, v=1.0):
        a = int(t * SR)
        pista[a:a + len(m)] += m[:len(pista) - a] * v

    poner(voz, entrada)
    poner(_pop(), t_sus, 0.6)
    poner(_clic(), t_clic, 0.8)
    poner(_campana(), t_camp)
    poner(_campana(), t_camp + 0.45, 0.6)
    pista = pista[:int(dur * SR)]
    pista /= max(1.0, np.abs(pista).max() / 0.95)
    wav = RECURSOS / f"{nombre}.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((pista * 32767).astype(np.int16).tobytes())
    sup = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                             "-r", str(fps), "-i", "-", "-i", str(wav), "-map", "0:v", "-map", "1:a",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                             "-af", "loudnorm=" + cfg.get("sonido", {}).get("loudnorm", "I=-14:TP=-1.5:LRA=11"),
                             "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-t", f"{dur:.3f}", str(mp4)],
                            stdin=subprocess.PIPE)
    for f in range(int(round(dur * fps))):
        ctx = cairo.Context(sup)
        _cuadro(ctx, W, H, f / fps, dur, pal, (t_sus, t_clic, t_camp))
        sup.flush()
        proc.stdin.write(bytes(sup.get_data()))
    proc.stdin.close()
    if proc.wait() != 0:
        raise PipelineError("ffmpeg falló al renderizar el cierre de suscripción.")
    firma.write_text(json.dumps({"clave": clave, "duracion": round(dur, 3)}, ensure_ascii=False), encoding="utf-8")
    return mp4, round(dur, 3)


def agregar(cfg, ruta: Path, vertical=False) -> float:
    """Pega el cierre al final de `ruta` (lo reemplaza). Devuelve la duración agregada."""
    if not cfg.get("outro", {}).get("activo", True):
        return 0.0
    outro, dur = generar(cfg, vertical)
    W, H = (1080, 1920) if vertical else (1920, 1080)
    fps = cfg["video"]["fps"]
    norm_v = f"scale={W}:{H},fps={fps},format=yuv420p,setsar=1"
    norm_a = "aformat=sample_rates=48000:channel_layouts=stereo"
    tmp = ruta.with_name(ruta.stem + "_con_cierre.mp4")
    v = cfg["video"]
    ejecutar(["ffmpeg", "-y", "-v", "error", "-i", str(ruta), "-i", str(outro), "-filter_complex",
              f"[0:v]{norm_v}[v0];[1:v]{norm_v}[v1];[0:a]{norm_a}[a0];[1:a]{norm_a}[a1];"
              "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
              "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", v["preset"], "-crf", str(v["crf"]),
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)],
             f"Cierre de suscripción en {ruta.name}")
    tmp.replace(ruta)
    return dur

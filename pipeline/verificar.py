"""Paso 6: verificación final y reporte.md en la carpeta del video."""
import json
import re
from datetime import datetime

from PIL import Image, ImageStat

from .comun import RAIZ, SALIDA, TRABAJO, cargar_escenas, ejecutar


def _mmss(s: float) -> str:
    return f"{int(s // 60)}:{s % 60:05.2f}"


def generar(cfg: dict, prueba: bool = False, log=print) -> bool:
    datos = cargar_escenas()
    escenas = datos["escenas"]
    errores, avisos, checks = [], [], []

    def check(ok, nombre, detalle="", aviso=False):
        checks.append((ok, nombre, detalle, aviso and not ok))
        if not ok:
            (avisos if aviso else errores).append(f"{nombre}: {detalle}")

    # --- escenas: texto, audio, imagen, clip
    vacias, sin_audio, sin_img, sin_clip, img_planas = [], [], [], [], []
    for e in escenas:
        if not e.get("texto", "").strip():
            vacias.append(e["id"])
        a = RAIZ / e.get("audio", "_")
        if not a.exists() or e.get("duracion_audio", 0) < 0.2:
            sin_audio.append(e["id"])
        i = RAIZ / e.get("imagen", "_")
        if not i.exists():
            sin_img.append(e["id"])
        else:
            with Image.open(i) as im:
                if im.size != (1920, 1080) or max(ImageStat.Stat(im.convert("L")).stddev) < 3:
                    img_planas.append(e["id"])
        if not (TRABAJO / "clips" / f"escena_{e['id']:03d}.mp4").exists():
            sin_clip.append(e["id"])
    check(not vacias, "Ninguna escena vacía", f"escenas sin texto: {vacias}" if vacias else f"{len(escenas)} escenas con texto")
    check(not sin_audio, "No faltan audios", f"sin audio: {sin_audio}" if sin_audio else f"{len(escenas)} audios")
    check(not sin_img and not img_planas, "Imágenes 1920x1080 con contenido",
          f"faltan: {sin_img}, vacías o mal tamaño: {img_planas}" if (sin_img or img_planas) else f"{len(escenas)} imágenes")
    check(not sin_clip, "Clips de escena generados", f"faltan: {sin_clip}" if sin_clip else f"{len(escenas)} clips")

    # --- video final
    video = SALIDA / "video.mp4"
    dur_video = 0.0
    if not video.exists():
        check(False, "Existe video.mp4", "no se generó")
    else:
        info = json.loads(ejecutar(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                                    str(video)], "ffprobe del video final").stdout)
        vs = [s for s in info["streams"] if s["codec_type"] == "video"]
        aus = [s for s in info["streams"] if s["codec_type"] == "audio"]
        dur_video = float(info["format"]["duration"])
        check(bool(vs) and vs[0]["width"] == 1920 and vs[0]["height"] == 1080, "Video en 1080p",
              f"{vs[0]['width']}x{vs[0]['height']} {vs[0]['codec_name']}" if vs else "sin pista de video")
        check(bool(aus), "Tiene pista de audio", aus[0]["codec_name"] if aus else "sin audio")
        esperado = datos.get("duracion_total", 0) + datos.get("outro_s", 0)
        check(abs(dur_video - esperado) < 0.5, "Duración del video = escenas + cierre",
              f"video {dur_video:.2f}s vs escenas {esperado:.2f}s")
        r = ejecutar(["ffmpeg", "-v", "info", "-i", str(video), "-map", "0:a", "-af", "volumedetect",
                      "-f", "null", "-"], "Medición de volumen")
        m = re.search(r"mean_volume:\s*(-?[\d.]+)", r.stderr)
        vol = float(m.group(1)) if m else -99
        check(vol > -45, "El audio no está en silencio", f"volumen medio {vol:.1f} dB")

    for s in datos.get("shorts", []):
        ruta = SALIDA / s["archivo"]
        if not ruta.exists():
            check(False, f"Short {s['archivo']}", "no se generó")
            continue
        st = json.loads(ejecutar(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(ruta)],
                                 "ffprobe del Short").stdout)
        vs = [x for x in st["streams"] if x["codec_type"] == "video"][0]
        d = float(st["format"]["duration"])
        check(vs["width"] == 1080 and vs["height"] == 1920 and d <= 60, f"Short {s['archivo']} vertical y de máx. 60 s",
              f"{vs['width']}x{vs['height']}, {d:.1f}s")

    dmin, dmax = cfg["duracion"]["minimo_min"] * 60, cfg["duracion"]["maximo_min"] * 60
    en_rango = dmin <= dur_video <= dmax
    check(en_rango, f"Duración total entre {cfg['duracion']['minimo_min']} y {cfg['duracion']['maximo_min']} min",
          f"{_mmss(dur_video)}" + (" (modo prueba: se esperaba fuera de rango)" if prueba and not en_rango else ""),
          aviso=prueba)

    # --- reporte
    ok_total = not errores
    lineas = [
        f"# Reporte: {datos.get('titulo', '')}",
        "",
        f"- Generado: {datetime.now().isoformat(timespec='seconds')}",
        f"- Guion: `{datos.get('guion')}`" + ("  (**modo prueba**)" if prueba else ""),
        f"- Voz: `{cfg['voz']['nombre']}` ({cfg['voz']['velocidad']})",
        f"- Escenas: {len(escenas)} ({sum(e['visual']['movimiento'] for e in escenas)} con animación)",
        f"- Duración estimada: {_mmss(datos.get('duracion_estimada_total', 0))} · real: **{_mmss(dur_video)}**",
        f"- Escenas con imagen de Flow: {sum(e.get('fuente_imagen') == 'flow' for e in escenas)} de {len(escenas)}"
        f" ({datos.get('imagenes_distintas', len(escenas))} ilustraciones distintas; el resto, dibujo de respaldo)",
        f"- Shorts: {', '.join(s['archivo'] for s in datos.get('shorts', [])) or 'ninguno'}",
        f"- Clips de video de Flow: {sum(bool(e.get('clip_flow')) for e in escenas)}"
        f" (de {sum('prompt_clip' in e for e in escenas)} pedidos en el guion)",
        f"- Música de fondo: {datos.get('musica') or 'no (no existe musica/fondo.mp3)'}",
        f"- Resultado: **{'OK' if ok_total else 'CON ERRORES'}**",
        "",
        "## Comprobaciones",
        "",
        "| Estado | Comprobación | Detalle |",
        "|---|---|---|",
    ]
    for ok, nombre, detalle, es_aviso in checks:
        estado = "OK" if ok else ("AVISO" if es_aviso else "ERROR")
        lineas.append(f"| {estado} | {nombre} | {detalle} |")
    if errores or avisos:
        lineas += ["", "## Problemas", ""] + [f"- ERROR: {x}" for x in errores] + [f"- AVISO: {x}" for x in avisos]
    lineas += ["", "## Escenas", "", "| # | Inicio | Dur. | Imagen | Palabra clave | Texto |", "|---|---|---|---|---|---|"]
    t = 0.0
    for e in escenas:
        v = e["visual"]
        texto = e["texto"].replace("|", "/")
        plano = f"sigue {e['imagen_de']}" if "imagen_de" in e else e.get("fuente_imagen", "")
        lineas.append(f"| {e['id']} | {_mmss(t)} | {e.get('duracion', 0):.2f}s | {plano} | "
                      f"{v.get('texto', '').replace('|', '/')} | {texto[:90]}{'…' if len(texto) > 90 else ''} |")
        t += e.get("duracion", 0)
    (SALIDA / "reporte.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    for ok, nombre, detalle, es_aviso in checks:
        log(f"  [{'OK' if ok else ('AVISO' if es_aviso else 'ERROR')}] {nombre} — {detalle}")
    return ok_total

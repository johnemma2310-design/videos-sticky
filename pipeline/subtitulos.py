"""Subtítulos: PNG transparentes por página (se superponen con ffmpeg) y archivo .srt."""
from PIL import Image, ImageDraw

from .comun import ALTO, ANCHO, DIR_SUBS
from .dibujo import fuente


def _lineas(texto, f, max_ancho, d):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if d.textlength(prueba, font=f) <= max_ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def paginas(escena: dict, cfg: dict) -> list[dict]:
    """Divide el texto en páginas de N líneas, con tiempos proporcionales a su longitud."""
    cs = cfg["subtitulos"]
    f = fuente(cfg, cs["tamano"])
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lineas = _lineas(escena["texto"], f, cs["max_ancho"], d)
    n = cs["max_lineas"]
    grupos = [lineas[i:i + n] for i in range(0, len(lineas), n)]
    total_chars = sum(len(" ".join(g)) for g in grupos)
    hablado = escena["duracion_audio"]
    res, t = [], 0.0
    for i, g in enumerate(grupos):
        dur = hablado * len(" ".join(g)) / total_chars
        fin = escena["duracion"] if i == len(grupos) - 1 else t + dur
        res.append({"lineas": g, "inicio": round(t, 3), "fin": round(fin, 3)})
        t += dur
    return res


def render_png(escena_id: int, idx: int, lineas: list[str], cfg: dict):
    cs = cfg["subtitulos"]
    f = fuente(cfg, cs["tamano"])
    img = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    alto_linea = int(cs["tamano"] * 1.25)
    y_base = ALTO - cs["margen_inferior"] - alto_linea * len(lineas)
    ancho = max(d.textlength(l, font=f) for l in lineas)
    d.rounded_rectangle([ANCHO / 2 - ancho / 2 - 30, y_base - 18, ANCHO / 2 + ancho / 2 + 30,
                         y_base + alto_linea * len(lineas) + 12], radius=16, fill=(0, 0, 0, 150))
    for i, l in enumerate(lineas):
        d.text((ANCHO / 2, y_base + i * alto_linea + alto_linea / 2), l, font=f, anchor="mm",
               fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    ruta = DIR_SUBS / f"escena_{escena_id:03d}_{idx}.png"
    img.save(ruta)
    return ruta


def _ts(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _palabras_absolutas(escenas):
    """Todas las palabras con su tiempo en el video completo."""
    res, t0 = [], 0.0
    for e in escenas:
        for w in e.get("palabras", []):
            res.append({"p": w["p"], "ini": t0 + w["ini"], "fin": t0 + w["fin"], "escena": e["id"]})
        t0 += e["duracion"]
    return res


def _grupos(palabras, max_palabras, max_letras):
    """Grupos cortos de palabras (no cruzan de una escena a otra)."""
    grupos, actual = [], []
    for w in palabras:
        texto = " ".join(x["p"] for x in actual + [w])
        if actual and (len(actual) >= max_palabras or len(texto) > max_letras or w["escena"] != actual[-1]["escena"]):
            grupos.append(actual)
            actual = []
        actual.append(w)
        if w["p"][-1:] in ".,;:?!":
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos


def escribir_srt(escenas: list[dict], ruta):
    """Subtítulos para subir a YouTube, con los tiempos reales de cada palabra."""
    bloques = []
    for n, g in enumerate(_grupos(_palabras_absolutas(escenas), 9, 42), 1):
        bloques.append(f"{n}\n{_ts(g[0]['ini'])} --> {_ts(g[-1]['fin'] + 0.15)}\n" + " ".join(w["p"] for w in g) + "\n")
    ruta.write_text("\n".join(bloques), encoding="utf-8")


def _ass_t(s: float) -> str:
    cs = int(round(max(s, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    seg, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{seg:02d}.{cs:02d}"


def _ass_texto(t: str) -> str:
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def escribir_ass(escenas, ruta, cfg, ancho, alto, desde=0.0, hasta=None, extras=()):
    """Subtítulos palabra por palabra (la palabra que se dice va resaltada y un poco más grande).

    desde/hasta recortan un tramo (para los Shorts) y corren los tiempos para que empiecen en 0.
    extras: textos fijos [(texto, inicio, fin, estilo)] como el título de un Short.
    """
    cs = cfg["subtitulos"]
    vertical = alto > ancho
    tam = cs["palabras_tamano_vertical"] if vertical else cs["palabras_tamano"]
    margen = cs["palabras_margen_vertical"] if vertical else cs["palabras_margen"]
    resalte = cs["palabras_color_resalte"]  # formato ASS &HBBGGRR
    lineas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {ancho}", f"PlayResY: {alto}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Palabras,{cs['palabras_fuente']},{tam},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,"
        f"100,100,0,0,1,{max(4, tam // 12)},3,2,60,60,{margen},1",
        f"Style: Titulo,{cs['palabras_fuente']},{int(tam * 1.15)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,"
        f"100,100,0,0,1,{max(5, tam // 10)},4,8,60,60,{int(alto * 0.07)},1",
        f"Style: Hud,{cs['palabras_fuente']},{max(30, tam // 2)},&H0000DCFF,&H0000DCFF,&H90200A05,&H90200A05,-1,0,0,0,"
        f"100,100,0,0,3,10,0,7,170,60,40,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    hasta = hasta if hasta is not None else float("inf")
    palabras = [w for w in _palabras_absolutas(escenas) if desde <= w["ini"] < hasta]
    grupos = _grupos(palabras, cs["palabras_por_grupo"], cs["palabras_max_letras"])
    for k, g in enumerate(grupos):
        # el grupo se queda un momento al final, pero nunca encima del siguiente (se verían dos líneas)
        limite = grupos[k + 1][0]["ini"] if k + 1 < len(grupos) else float("inf")
        for i, w in enumerate(g):
            ini = w["ini"] - desde
            fin = (g[i + 1]["ini"] if i + 1 < len(g) else min(g[-1]["fin"] + 0.25, limite)) - desde
            partes = [(f"{{\\c{resalte}&\\fscx112\\fscy112}}{_ass_texto(x['p'])}{{\\r}}" if x is w else _ass_texto(x["p"]))
                      for x in g]
            lineas.append(f"Dialogue: 0,{_ass_t(ini)},{_ass_t(min(fin, hasta - desde))},Palabras,,0,0,0,,"
                          + " ".join(partes))
    if not vertical:  # marcador fijo (hud=) arriba a la izquierda
        t0, actual, desde_hud = 0.0, "", 0.0
        tramos = []
        for e in escenas:
            nuevo = e.get("visual", {}).get("hud", "")
            if nuevo and nuevo != actual:
                if actual:
                    tramos.append((actual, desde_hud, t0))
                actual, desde_hud = nuevo, t0
            t0 += e["duracion"]
        if actual:
            tramos.append((actual, desde_hud, t0))
        for txt, a, b in tramos:
            a2, b2 = max(a, desde) - desde, min(b, hasta) - desde
            if b2 > a2:
                lineas.append(f"Dialogue: 2,{_ass_t(a2)},{_ass_t(b2)},Hud,,0,0,0,,"
                              r"{\fscx40\fscy40\t(0,220,\fscx100\fscy100)}" + _ass_texto(txt.upper()))
    for texto, ini, fin, estilo in extras:
        lineas.append(f"Dialogue: 1,{_ass_t(ini)},{_ass_t(fin)},{estilo},,0,0,0,,{_ass_texto(texto)}")
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

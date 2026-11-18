"""Dibujo estilo stickman con Pillow: fondos, personaje fijo, criatura y rótulo.

Todo se dibuja a 1920x1080 con la paleta y el personaje de config.json, para que
el estilo sea igual en todas las escenas.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .comun import ALTO, ANCHO

SUELO_Y = 860  # línea del suelo (los pies del personaje tocan aquí)


def rgb(h: str, a: int | None = None):
    h = h.lstrip("#")
    c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return c + (a,) if a is not None else c


@lru_cache(maxsize=32)
def _fuente(rutas: tuple, tam: int):
    for r in rutas:
        try:
            return ImageFont.truetype(r, tam)
        except OSError:
            continue
    return ImageFont.load_default(tam)


def fuente(cfg, tam):
    return _fuente(tuple(cfg["estilo"]["fuentes"]), tam)


# --------------------------------------------------------------------------- fondos

def _degradado(ancho, alto, arriba, abajo):
    mascara = Image.linear_gradient("L").resize((ancho, alto))
    return Image.composite(Image.new("RGBA", (ancho, alto), rgb(abajo, 255)),
                           Image.new("RGBA", (ancho, alto), rgb(arriba, 255)), mascara)


def _suelo(img, pal, rng):
    d = ImageDraw.Draw(img)
    w = img.width
    d.rectangle([0, SUELO_Y, w, ALTO], fill=rgb(pal["suelo"]))
    d.line([0, SUELO_Y, w, SUELO_Y], fill=rgb(pal["linea_suelo"]), width=4)
    # piedritas: dan sensación de desplazamiento en las escenas animadas
    for _ in range(w // 60):
        x = rng.randint(0, w)
        y = rng.randint(SUELO_Y + 20, ALTO - 10)
        r = rng.randint(3, 9)
        d.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=rgb(pal["linea_suelo"]))


def _niebla(img, pal, rng, cantidad=7, alfa=40):
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    for _ in range(cantidad * img.width // ANCHO):
        x = rng.randint(-200, img.width)
        y = rng.randint(SUELO_Y - 260, SUELO_Y + 80)
        d.ellipse([x, y, x + rng.randint(400, 800), y + rng.randint(80, 160)], fill=rgb(pal["luz"], alfa))
    img.alpha_composite(capa.filter(ImageFilter.GaussianBlur(40)))


def _resplandor(img, xy, radio, color, alfa=90, blur=50):
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x, y = xy
    ImageDraw.Draw(capa).ellipse([x - radio, y - radio, x + radio, y + radio], fill=rgb(color, alfa))
    img.alpha_composite(capa.filter(ImageFilter.GaussianBlur(blur)))


def fondo_laboratorio(w, pal, rng):
    img = _degradado(w, ALTO, pal["siluetas"], pal["siluetas_lejanas"])
    d = ImageDraw.Draw(img)
    for x in range(0, w, 240):
        d.line([x, 0, x, SUELO_Y], fill=rgb(pal["linea_suelo"]), width=3)
    d.rectangle([0, 300, w, 316], fill=rgb(pal["linea_suelo"]))
    for cx in range(300, w, 900):
        # puerta de contención con franjas de advertencia
        x0, x1, y0 = cx + 400, cx + 700, SUELO_Y - 520
        d.rectangle([x0 - 20, y0 - 20, x1 + 20, SUELO_Y], fill=rgb(pal["linea_suelo"]))
        d.rectangle([x0, y0, x1, SUELO_Y], fill=rgb(pal["siluetas"]))
        d.line([(x0 + x1) // 2, y0, (x0 + x1) // 2, SUELO_Y], fill=rgb(pal["suelo"]), width=6)
        for i in range(0, x1 - x0, 50):
            d.polygon([(x0 + i, SUELO_Y - 60), (x0 + i + 25, SUELO_Y - 60),
                       (x0 + i + 5, SUELO_Y - 10), (x0 + i - 20, SUELO_Y - 10)], fill=rgb(pal["acento"]))
        d.ellipse([(x0 + x1) // 2 - 16, y0 - 70, (x0 + x1) // 2 + 16, y0 - 38], fill=rgb(pal["peligro"]))
        _resplandor(img, ((x0 + x1) // 2, y0 - 54), 60, pal["peligro"], 110, 25)
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    for cx in range(200, w, 700):  # conos de luz del techo
        dc.polygon([(cx - 40, 0), (cx + 40, 0), (cx + 260, SUELO_Y), (cx - 260, SUELO_Y)], fill=rgb(pal["luz"], 22))
    img.alpha_composite(capa.filter(ImageFilter.GaussianBlur(12)))
    _suelo(img, pal, rng)
    return img


def fondo_bosque(w, pal, rng):
    img = _degradado(w, ALTO, pal["cielo_arriba"], pal["cielo_abajo"])
    _resplandor(img, (int(w * 0.18), 190), 140, pal["luz"], 80, 60)
    d = ImageDraw.Draw(img)
    d.ellipse([w * 0.18 - 70, 120, w * 0.18 + 70, 260], fill=rgb(pal["luz"]))
    for capa, color, alto_min, alto_max, paso in ((0, pal["siluetas_lejanas"], 300, 480, 90),
                                                   (1, pal["siluetas"], 450, 700, 170)):
        x = rng.randint(-50, 50)
        while x < w + 100:
            h = rng.randint(alto_min, alto_max)
            ancho = h * 0.35
            base = SUELO_Y + (0 if capa else -10)
            d.polygon([(x, base - h), (x - ancho, base), (x + ancho, base)], fill=rgb(color))
            d.rectangle([x - 10, base - 30, x + 10, base], fill=rgb(color))
            x += paso + rng.randint(-30, 60)
    _niebla(img, pal, rng, 6, 30)
    _suelo(img, pal, rng)
    return img


def fondo_ciudad(w, pal, rng):
    img = _degradado(w, ALTO, pal["cielo_arriba"], pal["cielo_abajo"])
    d = ImageDraw.Draw(img)
    for color, hmin, hmax, luces in ((pal["siluetas_lejanas"], 250, 450, 0.08), (pal["siluetas"], 330, 640, 0.18)):
        x = rng.randint(-80, 0)
        while x < w:
            ancho = rng.randint(140, 280)
            h = rng.randint(hmin, hmax)
            d.rectangle([x, SUELO_Y - h, x + ancho, SUELO_Y], fill=rgb(color))
            for wy in range(SUELO_Y - h + 30, SUELO_Y - 40, 55):
                for wx in range(x + 20, x + ancho - 30, 45):
                    if rng.random() < luces:
                        d.rectangle([wx, wy, wx + 20, wy + 28], fill=rgb(pal["acento"]))
            x += ancho + rng.randint(5, 40)
    _suelo(img, pal, rng)
    d = ImageDraw.Draw(img)
    for x in range(0, w, 160):  # marcas de la calle
        d.rectangle([x, 960, x + 80, 972], fill=rgb(pal["linea_suelo"]))
    return img


def fondo_casa(w, pal, rng):
    img = Image.new("RGBA", (w, ALTO), rgb(pal["siluetas_lejanas"], 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, SUELO_Y - 40, w, SUELO_Y], fill=rgb(pal["siluetas"]))  # zócalo
    for base in range(0, w, 1600):
        # ventana con luz de luna
        vx, vy = base + 200, 200
        d.rectangle([vx - 14, vy - 14, vx + 334, vy + 354], fill=rgb(pal["siluetas"]))
        ventana = _degradado(320, 340, pal["cielo_arriba"], pal["cielo_abajo"])
        img.paste(ventana, (vx, vy))
        d.ellipse([vx + 200, vy + 40, vx + 270, vy + 110], fill=rgb(pal["luz"]))
        d.line([vx + 160, vy, vx + 160, vy + 340], fill=rgb(pal["siluetas"]), width=12)
        d.line([vx, vy + 170, vx + 320, vy + 170], fill=rgb(pal["siluetas"]), width=12)
        # puerta entreabierta
        px = base + 1150
        d.rectangle([px - 12, SUELO_Y - 480, px + 252, SUELO_Y], fill=rgb(pal["siluetas"]))
        d.rectangle([px, SUELO_Y - 468, px + 240, SUELO_Y], fill=rgb(pal["criatura"]))
        d.polygon([(px, SUELO_Y - 468), (px + 150, SUELO_Y - 440), (px + 150, SUELO_Y - 20), (px, SUELO_Y)],
                  fill=rgb(pal["linea_suelo"]))
        # cuadro torcido
        cx, cy = base + 750, 330
        cuadro = Image.new("RGBA", (200, 150), rgb(pal["siluetas"], 255))
        ImageDraw.Draw(cuadro).rectangle([14, 14, 186, 136], fill=rgb(pal["cielo_abajo"]))
        cuadro = cuadro.rotate(rng.choice([-7, 6, -4]), expand=True, resample=Image.BICUBIC)
        img.alpha_composite(cuadro, (cx, cy))
    _suelo(img, pal, rng)
    d = ImageDraw.Draw(img)
    for x in range(0, w, 120):  # tablas del piso
        d.line([x, SUELO_Y, x - 60, ALTO], fill=rgb(pal["siluetas"]), width=3)
    return img


def fondo_oscuridad(w, pal, rng):
    img = _degradado(w, ALTO, pal["criatura"], pal["suelo"])
    _niebla(img, pal, rng, 9, 22)
    _suelo(img, pal, rng)
    _resplandor(img, (int(w * 0.35), SUELO_Y - 250), 420, pal["luz"], 18, 90)
    return img


def fondo_vacio(w, pal, rng):
    img = _degradado(w, ALTO, pal["cielo_arriba"], pal["cielo_abajo"])
    _niebla(img, pal, rng, 5, 25)
    _suelo(img, pal, rng)
    return img


def fondo_documento(w, pal, rng, cfg):
    img = fondo_vacio(w, pal, rng)
    for base in range(0, w, ANCHO):
        hoja = Image.new("RGBA", (760, 880), rgb(pal["papel"], 255))
        d = ImageDraw.Draw(hoja)
        d.text((60, 50), "EXPEDIENTE", font=fuente(cfg, 64), fill=rgb(pal["tinta"]))
        d.line([60, 140, 700, 140], fill=rgb(pal["tinta"]), width=4)
        y = 190
        while y < 820:
            largo = rng.randint(300, 640)
            if rng.random() < 0.3:
                d.rectangle([60, y - 6, 60 + largo, y + 22], fill=rgb(pal["tinta"]))  # texto censurado
            else:
                d.line([60, y + 8, 60 + largo, y + 8], fill=(150, 145, 130), width=6)
            y += 52
        sello = Image.new("RGBA", (520, 130), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sello)
        ds.rectangle([4, 4, 516, 126], outline=rgb(pal["peligro"]), width=8)
        ds.text((260, 65), "CLASIFICADO", font=fuente(cfg, 64), fill=rgb(pal["peligro"]), anchor="mm")
        hoja.alpha_composite(sello.rotate(-14, expand=True, resample=Image.BICUBIC), (120, 380))
        hoja = hoja.rotate(4, expand=True, resample=Image.BICUBIC)
        sombra = Image.new("RGBA", hoja.size, (0, 0, 0, 0))
        sombra.paste((0, 0, 0, 140), mask=hoja.getchannel("A"))
        img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(18)), (base + 1060, 70))
        img.alpha_composite(hoja, (base + 1040, 50))
    return img


def fondo(escenario: str, cfg: dict, semilla: int, ancho: int = ANCHO) -> Image.Image:
    pal = cfg["estilo"]["paleta"]
    rng = random.Random(semilla)
    if escenario == "documento":
        return fondo_documento(ancho, pal, rng, cfg)
    funcs = {"laboratorio": fondo_laboratorio, "bosque": fondo_bosque, "ciudad": fondo_ciudad,
             "casa": fondo_casa, "oscuridad": fondo_oscuridad, "vacio": fondo_vacio}
    return funcs[escenario](ancho, pal, rng)


# --------------------------------------------------------------------------- personaje

# Ángulos (superior, inferior) en grados: 0 = hacia abajo, positivo = hacia donde mira (derecha).
POSES = {
    "de_pie":   dict(bd=(12, 4), bi=(-12, -4), pd=(9, 3), pi=(-9, -3), incl=0, cara="normal"),
    "habla":    dict(bd=(55, 115), bi=(-12, -4), pd=(9, 3), pi=(-9, -3), incl=0, cara="habla"),
    "senala":   dict(bd=(92, 88), bi=(-14, -5), pd=(10, 3), pi=(-10, -3), incl=4, cara="normal"),
    "asustado": dict(bd=(145, 170), bi=(-145, -170), pd=(20, 10), pi=(-20, -10), incl=-6, cara="asustado"),
    "piensa":   dict(bd=(20, 165), bi=(-10, -4), pd=(8, 3), pi=(-8, -3), incl=0, cara="piensa"),
}


def pose_corriendo(fase: float) -> dict:
    s = math.sin(fase)
    def pierna(f):
        sup = 42 * math.sin(f)
        return (sup, sup - 55 * (1 + math.cos(f)) / 2)
    def brazo(f):
        sup = -45 * math.sin(f)
        return (sup, sup + 80)
    return dict(bd=brazo(fase), bi=brazo(fase + math.pi), pd=pierna(fase), pi=pierna(fase + math.pi),
                incl=14, cara="asustado", rebote=abs(s) * 12)


def _punto(o, largo, ang):
    a = math.radians(ang)
    return (o[0] + largo * math.sin(a), o[1] + largo * math.cos(a))


def dibujar_personaje(img: Image.Image, x: float, pose: dict, cfg: dict, fase: float = 0.0):
    pj = cfg["personaje"]
    col = rgb(pj["color_cuerpo"])
    g = pj["grosor"]
    L_b, L_p, torso, r = pj["brazo"], pj["pierna"], pj["torso"], pj["radio_cabeza"]

    # sombra en el suelo
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).ellipse([x - 90, SUELO_Y - 14, x + 90, SUELO_Y + 14], fill=(0, 0, 0, 110))
    img.alpha_composite(capa.filter(ImageFilter.GaussianBlur(6)))

    # altura de cadera para que el pie más bajo toque el suelo
    def caida(p):
        return L_p * math.cos(math.radians(p[0])) + L_p * math.cos(math.radians(p[1]))
    cadera = (x, SUELO_Y - g / 2 - max(caida(pose["pd"]), caida(pose["pi"])) - pose.get("rebote", 0))
    incl = math.radians(pose["incl"])
    hombro = (cadera[0] + torso * math.sin(incl), cadera[1] - torso * math.cos(incl))
    cuello = (hombro[0] + 14 * math.sin(incl), hombro[1] - 14 * math.cos(incl))
    cabeza = (cuello[0] + r * math.sin(incl), cuello[1] - r * math.cos(incl))

    d = ImageDraw.Draw(img)

    def extremidad(origen, largo, angs):
        codo = _punto(origen, largo, angs[0])
        mano = _punto(codo, largo, angs[1])
        d.line([origen, codo, mano], fill=col, width=g, joint="curve")
        for p in (origen, codo, mano):
            d.ellipse([p[0] - g / 2, p[1] - g / 2, p[0] + g / 2, p[1] + g / 2], fill=col)

    extremidad(hombro, L_b, pose["bi"])
    extremidad(cadera, L_p, pose["pi"])
    d.line([cadera, cuello], fill=col, width=g)
    extremidad(cadera, L_p, pose["pd"])
    extremidad(hombro, L_b, pose["bd"])

    # accesorio fijo: bufanda
    if pj.get("accesorio") == "bufanda":
        ca = rgb(pj["color_accesorio"])
        ondula = math.sin(fase * 2) * 10
        cola = [(cuello[0] - 6, cuello[1] + 4), (cuello[0] - 60, cuello[1] + 20 + ondula),
                (cuello[0] - 100, cuello[1] + 8 - ondula), (cuello[0] - 96, cuello[1] + 30 - ondula),
                (cuello[0] - 56, cuello[1] + 40 + ondula), (cuello[0] - 4, cuello[1] + 22)]
        d.polygon(cola, fill=ca)
        d.rounded_rectangle([cuello[0] - 26, cuello[1] - 4, cuello[0] + 26, cuello[1] + 20], radius=10, fill=ca)

    # cabeza y cara (mira a la derecha)
    d.ellipse([cabeza[0] - r, cabeza[1] - r, cabeza[0] + r, cabeza[1] + r], fill=col)
    ojo = rgb(pj["color_ojos"])
    cara = pose["cara"]
    ro = 9 if cara == "asustado" else 6
    for dx in (8, 30):
        ex, ey = cabeza[0] + dx, cabeza[1] - 6
        d.ellipse([ex - ro, ey - ro, ex + ro, ey + ro], fill=ojo)
    if cara == "asustado":
        d.ellipse([cabeza[0] + 12, cabeza[1] + 14, cabeza[0] + 28, cabeza[1] + 32], fill=ojo)
    elif cara == "habla":
        d.ellipse([cabeza[0] + 12, cabeza[1] + 16, cabeza[0] + 30, cabeza[1] + 26], fill=ojo)
    elif cara == "piensa":
        d.line([cabeza[0] + 20, cabeza[1] - 24, cabeza[0] + 40, cabeza[1] - 30], fill=ojo, width=4)
        d.line([cabeza[0] + 14, cabeza[1] + 22, cabeza[0] + 30, cabeza[1] + 20], fill=ojo, width=4)
    else:
        d.line([cabeza[0] + 12, cabeza[1] + 20, cabeza[0] + 30, cabeza[1] + 20], fill=ojo, width=4)

    # pose "piensa": signo de pregunta
    if cara == "piensa":
        d.text((cabeza[0] + 50, cabeza[1] - 120), "?", font=fuente(cfg, 90), fill=rgb(pj["color_accesorio"]))


def dibujar_criatura(img: Image.Image, x: float, cfg: dict, fase: float = 0.0, altura: int = 560):
    pal = cfg["estilo"]["paleta"]
    c = rgb(pal["criatura"])
    vaiv = math.sin(fase * 0.7) * 8
    d = ImageDraw.Draw(img)
    top = SUELO_Y - altura
    cuerpo = [(x - 20 + vaiv, top + 120), (x + 20 + vaiv, top + 120), (x + 70, SUELO_Y - 140),
              (x + 40, SUELO_Y), (x - 40, SUELO_Y), (x - 70, SUELO_Y - 140)]
    d.polygon(cuerpo, fill=c)
    d.ellipse([x - 55 + vaiv, top, x + 55 + vaiv, top + 150], fill=c)
    for lado in (-1, 1):  # brazos largos y finos
        d.line([(x + lado * 40, top + 190), (x + lado * 120, top + 330 + vaiv),
                (x + lado * 105, SUELO_Y - 90)], fill=c, width=12, joint="curve")
    for dx in (-22, 22):  # ojos brillantes
        _resplandor(img, (int(x + dx + vaiv), top + 62), 22, pal["peligro"], 200, 10)
        ImageDraw.Draw(img).ellipse([x + dx + vaiv - 7, top + 55, x + dx + vaiv + 7, top + 69], fill=rgb(pal["luz"]))


# --------------------------------------------------------------------------- acabado

@lru_cache(maxsize=4)
def _vineta(fuerza: float) -> Image.Image:
    m = Image.radial_gradient("L").resize((ANCHO, ALTO))
    m = m.point(lambda v: int(min(255, max(0, (v - 90) * 1.6)) * fuerza))
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 255))
    capa.putalpha(m)
    return capa


def acabado(img: Image.Image, rotulo: str, cfg: dict):
    img.alpha_composite(_vineta(cfg["estilo"]["vineta"]))
    pal = cfg["estilo"]["paleta"]
    d = ImageDraw.Draw(img)
    f = fuente(cfg, 40)
    ancho = d.textlength(rotulo, font=f)
    d.rounded_rectangle([60, 50, 60 + ancho + 56, 120], radius=12, fill=rgb(pal["acento"]))
    d.text((88, 85), rotulo, font=f, fill=rgb(pal["suelo"]), anchor="lm")


def componer_estatica(escena: dict, cfg: dict) -> Image.Image:
    v = escena["visual"]
    img = fondo(v["escenario"], cfg, semilla=escena["id"] * 7919)
    x = cfg["personaje"]["posicion_x"]
    if v["escenario"] == "documento":
        x = 420
    if v["criatura"]:
        dibujar_criatura(img, 1500 if v["escenario"] != "documento" else 860, cfg)
    pose = pose_corriendo(0.6) if v["accion"] == "corre" else POSES[v["accion"]]
    dibujar_personaje(img, x, pose, cfg)
    acabado(img, v["rotulo"], cfg)
    return img.convert("RGB")

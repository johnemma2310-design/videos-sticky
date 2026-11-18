"""Paso 3: una imagen 1920x1080 por escena.

Si existe trabajo/flow/escena_NNN.(png|jpg|jpeg|webp) (descargada de Google Flow) se usa esa,
recortada a 16:9; una escena que continúa el plano anterior usa la imagen de ese plano.
Si no hay imagen de Flow, se dibuja el stickman con Pillow como respaldo.
Encima se escribe la palabra clave (`texto`) con letra de mano.
"""
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .comun import ALTO, ANCHO, DIR_FLOW, DIR_IMG, PipelineError, cargar_escenas, guardar_escenas, rel
from .dibujo import componer_estatica, fuente, rgb

EXTENSIONES = (".png", ".jpg", ".jpeg", ".webp")


def buscar_flow(escena_id):
    for ext in EXTENSIONES:
        p = DIR_FLOW / f"escena_{escena_id:03d}{ext}"
        if p.exists():
            return p
    return None


def _rotulo(img, texto, cfg):
    pal = cfg["estilo"]["paleta"]
    d = ImageDraw.Draw(img)
    f = fuente(cfg, 40)
    ancho = d.textlength(texto, font=f)
    d.rounded_rectangle([60, 50, 60 + ancho + 56, 120], radius=12, fill=rgb(pal["acento"]))
    d.text((88, 85), texto, font=f, fill=rgb(pal["suelo"]), anchor="lm")


def _fuente_mano(cfg, tam):
    for ruta in cfg["palabra_clave"]["fuentes"]:
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            continue
    return fuente(cfg, tam)


def palabra_clave(img, texto, cfg, tarjeta):
    """Escribe la palabra clave arriba a la izquierda, con letra de mano y borde blanco."""
    pc = cfg["palabra_clave"]
    f = _fuente_mano(cfg, pc["tamano_tarjeta"] if tarjeta else pc["tamano"])
    d = ImageDraw.Draw(img)
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if actual and d.textlength(prueba, font=f) > pc["max_ancho"]:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    lineas.append(actual)
    alto = int(f.size * 1.2)
    for i, l in enumerate(lineas):
        d.text((pc["margen"], pc["margen"] + i * alto), l, font=f, fill=rgb(pc["color"]),
               stroke_width=0 if tarjeta else pc["borde"], stroke_fill=(255, 255, 255))


def desde_flow(ruta, e, cfg):
    with Image.open(ruta) as im:
        img = ImageOps.fit(im.convert("RGB"), (ANCHO, ALTO), method=Image.LANCZOS)
    if cfg["flow"].get("rotulo_sobre_flow") and not e["visual"]["texto"]:
        _rotulo(img, e["visual"]["rotulo"], cfg)
    return img


def generar(cfg: dict, log=print) -> dict:
    datos = cargar_escenas()
    duenios = {e["id"]: e for e in datos["escenas"]}
    for e in datos["escenas"]:
        destino = DIR_IMG / f"escena_{e['id']:03d}.png"
        plano = duenios[e.get("imagen_de", e["id"])]
        origen = buscar_flow(plano["id"])
        try:
            img = desde_flow(origen, e, cfg) if origen else componer_estatica(plano, cfg)
            # la palabra clave va en una capa aparte: así no se mueve ni se corta con el zoom/paneo
            e.pop("texto_png", None)
            if e["visual"]["texto"]:
                capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
                palabra_clave(capa, e["visual"]["texto"], cfg, plano["visual"]["tarjeta"])
                ruta_capa = DIR_IMG / f"escena_{e['id']:03d}_texto.png"
                capa.save(ruta_capa)
                e["texto_png"] = rel(ruta_capa)
        except Exception as ex:
            raise PipelineError(f"No se pudo preparar la imagen de la escena {e['id']}: {type(ex).__name__}: {ex}")
        img.save(destino)
        e["imagen"] = rel(destino)
        e["fuente_imagen"] = "flow" if origen else "dibujo"
        continua = f" (sigue el plano {plano['id']})" if plano is not e else ""
        log(f"  img {e['id']:03d}: {'Flow' if origen else 'dibujo'}{continua}")
    guardar_escenas(datos)
    return datos

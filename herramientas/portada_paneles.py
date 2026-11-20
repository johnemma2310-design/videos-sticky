"""Portada de 3 paneles (estilo 'Día 1 → Día 50 → Día 100') con imágenes de Flow."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
SEP = 12
PW = (W - 2 * SEP) // 3
F = 'C:/Windows/Fonts/ariblk.ttf'
CELESTE = (56, 189, 248)


def panel(ruta, centro_x):
    im = Image.open(ruta).convert('RGB')
    h = im.height
    w = int(h * PW / H)
    cx = int(im.width * centro_x)
    x0 = max(0, min(im.width - w, cx - w // 2))
    return im.crop((x0, 0, x0 + w, h)).resize((PW, H), Image.LANCZOS)


def texto(lienzo, t, xy, tam, color, borde=8, anchor='mm', borde_color='black'):
    capa = Image.new('RGBA', lienzo.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.text(xy, t, font=ImageFont.truetype(F, tam), fill=color, stroke_width=borde, stroke_fill=borde_color, anchor=anchor)
    sombra = Image.new('RGBA', lienzo.size, (0, 0, 0, 0))
    sombra.putalpha(capa.getchannel('A').filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * 0.6)))
    lienzo.alpha_composite(sombra, (4, 6))
    lienzo.alpha_composite(capa)


def flecha(lienzo, x0, y0, x1, y1, curva=-60):
    d = ImageDraw.Draw(lienzo)
    pts = []
    for i in range(25):
        u = i / 24
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2 + curva
        x = (1 - u) ** 2 * x0 + 2 * (1 - u) * u * mx + u ** 2 * x1
        y = (1 - u) ** 2 * y0 + 2 * (1 - u) * u * my + u ** 2 * y1
        pts.append((x, y))
    ang = math.atan2(pts[-1][1] - pts[-3][1], pts[-1][0] - pts[-3][0])
    punta = [(x1 + 34 * math.cos(ang), y1 + 34 * math.sin(ang)),
             (x1 + 26 * math.cos(ang + 2.3), y1 + 26 * math.sin(ang + 2.3)),
             (x1 + 26 * math.cos(ang - 2.3), y1 + 26 * math.sin(ang - 2.3))]
    d.line(pts, fill='black', width=22, joint='curve')
    d.polygon(punta, fill='black', outline='black', width=8)
    d.line(pts, fill='white', width=12, joint='curve')
    d.polygon(punta, fill='white')


def portada(paneles, titulo_peq, titulo_grande, etiquetas, salida):
    lienzo = Image.new('RGBA', (W, H), CELESTE + (255,))
    for k, (ruta, cx) in enumerate(paneles):
        im = panel(ruta, cx)
        if k == 0:  # el primero se baja para que el título no tape a Sticky
            fondo = im.resize((int(PW * 1.3), int(H * 1.3))).crop((0, 0, PW, H)).filter(ImageFilter.GaussianBlur(14))
            peq = im.resize((int(PW * 0.82), int(H * 0.82)), Image.LANCZOS)
            fondo.paste(peq, ((PW - peq.width) // 2, H - peq.height))
            im = fondo
        lienzo.paste(im, (k * (PW + SEP), 0))
    texto(lienzo, titulo_peq, (25, 38), 34, 'white', borde=6, anchor='lm')
    texto(lienzo, titulo_grande, (22, 100), 84, (235, 30, 40), borde=8, anchor='lm', borde_color='white')
    colores = [(60, 220, 90), (255, 214, 0), (235, 30, 40)]
    ys = [655, 70, 60]
    for k, (et, col, y) in enumerate(zip(etiquetas, colores, ys)):
        texto(lienzo, et, (k * (PW + SEP) + PW // 2, y), 56 if k < 2 else 66, col, borde=7)
    flecha(lienzo, PW - 110, 560, PW + SEP + 60, 520)
    flecha(lienzo, 2 * PW + SEP - 100, 480, 2 * (PW + SEP) + 70, 430)
    lienzo.convert('RGB').save(salida, quality=93)


B = r'C:\Users\cit\OneDrive\Escritorio\videos stick\videos'
portada([(B + r'\100-dias-en-cama\trabajo\miniatura\portada_cama_1.jpg', 0.49),
         (B + r'\100-dias-en-cama\trabajo\miniatura\portada_cama_2.jpg', 0.5),
         (B + r'\100-dias-en-cama\trabajo\miniatura\portada_cama_3.jpg', 0.5)],
        'SIN LEVANTARME', '100 DÍAS', ['DÍA 1', 'DÍA 50', 'DÍA 100'],
        B + r'\100-dias-en-cama\portada_video_largo.jpg')
portada([(B + r'\mas-rapido-que-sonic-y-flash\trabajo\miniatura\portada_sonic_1.jpg', 0.5),
         (B + r'\mas-rapido-que-sonic-y-flash\trabajo\miniatura\portada_sonic_2.jpg', 0.6),
         (B + r'\mas-rapido-que-sonic-y-flash\trabajo\miniatura\portada_sonic_3.jpg', 0.5)],
        'CORRO EL DOBLE', 'CADA DÍA', ['DÍA 1', 'DÍA 8', 'DÍA 28'],
        B + r'\mas-rapido-que-sonic-y-flash\portada_video_largo.jpg')
print('ok')

"""Portada vertical de Short (1080x1920): 3 paneles apilados (Día 1 → … → Día N) con imágenes de Flow.

Cada panel muestra la imagen completa centrada sobre una versión difuminada de sí misma (así funcionan
igual las imágenes horizontales y las que Flow entregó en vertical dentro de un lienzo 16:9).
Uso: editar la lista PORTADAS al final y ejecutar  python herramientas/portada_short_paneles.py
"""
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1920
SEP = 14
CAB = 330  # alto de la franja del título
PH = (H - CAB - 2 * SEP) // 3
F = 'C:/Windows/Fonts/ariblk.ttf'
CELESTE = (56, 189, 248)


def panel(ruta, vertical=False, fy=0.5):
    """Horizontal: llena el panel. Vertical: la imagen a ~60% del ancho sobre un fondo difuminado de sí misma.
    fy = altura del foco (0 arriba, 1 abajo)."""
    im = Image.open(ruta).convert('RGB')
    if vertical:  # Flow puso la imagen vertical en el tercio central del lienzo
        im = im.crop((im.width // 3, 0, 2 * im.width // 3, im.height))

    def cover(img, w, h, fy):
        e = max(w / img.width, h / img.height)
        img = img.resize((int(img.width * e) + 1, int(img.height * e) + 1), Image.LANCZOS)
        y0 = int(min(max(0, img.height * fy - h / 2), img.height - h))
        x0 = (img.width - w) // 2
        return img.crop((x0, y0, x0 + w, y0 + h))

    if not vertical:
        return cover(im, W, PH, fy)
    fondo = ImageEnhance.Brightness(cover(im, W, PH, fy).filter(ImageFilter.GaussianBlur(20))).enhance(0.55)
    ancho = int(W * 0.6)
    e = ancho / im.width
    frente = im.resize((ancho, int(im.height * e)), Image.LANCZOS)
    y0 = int(min(max(0, frente.height * fy - PH / 2), frente.height - PH))
    frente = frente.crop((0, y0, ancho, y0 + PH))
    fondo.paste(frente, ((W - ancho) // 2, 0))
    return fondo


def texto(lienzo, t, xy, tam, color, borde=9, anchor='mm', borde_color='black'):
    capa = Image.new('RGBA', lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).text(xy, t, font=ImageFont.truetype(F, tam), fill=color, stroke_width=borde,
                              stroke_fill=borde_color, anchor=anchor)
    sombra = Image.new('RGBA', lienzo.size, (0, 0, 0, 0))
    sombra.putalpha(capa.getchannel('A').filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.6)))
    lienzo.alpha_composite(sombra, (5, 7))
    lienzo.alpha_composite(capa)


def flecha_abajo(lienzo, x, y):
    d = ImageDraw.Draw(lienzo)
    pts = [(x - 70, y - 70), (x - 20, y - 10), (x + 20, y + 30)]
    punta = [(x + 55, y + 60), (x - 5, y + 50), (x + 40, y)]
    d.line(pts, fill='black', width=26, joint='curve')
    d.polygon(punta, fill='black', outline='black', width=10)
    d.line(pts, fill='white', width=14, joint='curve')
    d.polygon(punta, fill='white')


def portada(paneles, titulo_peq, titulo_grande, etiquetas, salida):
    lienzo = Image.new('RGBA', (W, H), CELESTE + (255,))
    g = Image.new('RGBA', (W, CAB), (15, 30, 80, 255))
    lienzo.paste(g, (0, 0))
    for k, (ruta, vertical, fy) in enumerate(paneles):
        lienzo.paste(panel(ruta, vertical, fy), (0, CAB + k * (PH + SEP)))
    texto(lienzo, titulo_peq, (W // 2, 95), 70, 'white', borde=8)
    texto(lienzo, titulo_grande, (W // 2, 225), 130, (235, 30, 40), borde=11, borde_color='white')
    colores = [(60, 220, 90), (255, 214, 0), (235, 30, 40)]
    for k, (et, col) in enumerate(zip(etiquetas, colores)):
        y0 = CAB + k * (PH + SEP)
        texto(lienzo, et, (40, y0 + 70), 90, col, borde=9, anchor='lm')
    for k in range(2):
        flecha_abajo(lienzo, W - 140, CAB + (k + 1) * (PH + SEP) - 40)
    lienzo.convert('RGB').save(salida, quality=93)


B = r'C:\Users\cit\OneDrive\Escritorio\videos stick\videos'
C = B + r'\100-dias-en-cama'
S = B + r'\mas-rapido-que-sonic-y-flash'
PORTADAS = [
    ([(C + r'\trabajo\miniatura\portada_cama_1.jpg', False, 0.45), (C + r'\trabajo\miniatura\portada_cama_2.jpg', True, 0.45),
      (C + r'\trabajo\miniatura\portada_cama_3.jpg', True, 0.4)],
     '¿Y SI NO TE LEVANTAS', '100 DÍAS?', ['DÍA 1', 'DÍA 50', 'DÍA 100'], C + r'\portada_short_1.jpg'),
    ([(C + r'\trabajo\miniatura\portada_cama_1.jpg', False, 0.45), (C + r'\trabajo\miniatura\portada_cama_2.jpg', True, 0.45),
      (C + r'\trabajo\miniatura\portada_cama_3.jpg', True, 0.4)],
     'SE LEVANTÓ EL', 'DÍA 101…', ['DÍA 1', 'DÍA 100', 'DÍA 101'], C + r'\portada_short_2.jpg'),
    ([(S + r'\trabajo\miniatura\portada_sonic_1.jpg', False, 0.5), (S + r'\trabajo\miniatura\portada_sonic_2.jpg', False, 0.55),
      (S + r'\trabajo\miniatura\portada_sonic_3.jpg', True, 0.55)],
     'CORRO EL DOBLE', 'CADA DÍA', ['DÍA 1', 'DÍA 8', 'DÍA 28'], S + r'\portada_short_1.jpg'),
    ([(S + r'\trabajo\miniatura\portada_sonic_1.jpg', False, 0.5), (S + r'\trabajo\miniatura\portada_sonic_2.jpg', False, 0.55),
      (S + r'\trabajo\miniatura\portada_sonic_3.jpg', True, 0.55)],
     '¿MÁS RÁPIDO QUE EL', 'SONIDO?', ['DÍA 1', 'DÍA 8', 'DÍA 28'], S + r'\portada_short_2.jpg'),
]

if __name__ == '__main__':
    for p in PORTADAS:
        portada(*p)
    print('ok')

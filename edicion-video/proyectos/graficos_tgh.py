"""Gráficos de los reels TGH, siguiendo la línea gráfica de la referencia.

Tarjetas tipo "captura de pantalla" con marco blanco fino (como las capturas
web de la referencia), stickers con borde blanco y pastillas inclinadas.
Todo se exporta como PNG con alfa para usarlo también en After Effects.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

POPPINS = "/usr/local/share/fonts/poppins/Poppins-{}.ttf"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
OTRAS = ["/usr/share/fonts/truetype/montserrat/Montserrat-Black.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
AMARILLO, AZUL, VERDE, ROJO = (252, 252, 0), (59, 0, 239), (37, 208, 103), (240, 54, 53)
BLANCO, TINTA, GRIS, LINEA = (255, 255, 255), (17, 17, 24), (120, 120, 135), (232, 232, 238)


def f(peso, size):
    return ImageFont.truetype(POPPINS.format(peso), size)


def fuente(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return f("Bold", size)


def emoji(ch, size):
    fe = ImageFont.truetype(EMOJI, 109)
    im = Image.new("RGBA", (180, 180))
    ImageDraw.Draw(im).text((90, 90), ch, font=fe, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)


def npa(im):
    return np.asarray(im, dtype=np.float32)


def sombra(im, blur=18, alpha=0.38, dy=10, margen=40):
    """Añade sombra suave debajo de un RGBA (con margen para que no se corte)."""
    w, h = im.width + margen * 2, im.height + margen * 2
    a = Image.new("L", (w, h))
    a.paste(im.split()[3], (margen, margen + dy))
    a = a.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * alpha)
    out = Image.merge("RGBA", [Image.new("L", (w, h), 0)] * 3 + [a])
    out.alpha_composite(im, (margen, margen))
    return out


def marco(contenido, borde=10, radio=12):
    """Marco blanco fino como las capturas de la referencia."""
    w, h = contenido.width + borde * 2, contenido.height + borde * 2
    im = Image.new("RGBA", (w, h))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radio, fill=BLANCO + (255,))
    m = Image.new("L", contenido.size)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, contenido.width - 1, contenido.height - 1), max(radio - borde // 2, 2), fill=255)
    im.paste(contenido, (borde, borde), m)
    return im


def insignia(ok, s=92):
    im = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, s - 1, s - 1), fill=(VERDE if ok else ROJO) + (255,), outline=BLANCO + (255,), width=6)
    k = s / 96
    if ok:
        d.line((26 * k, 50 * k, 42 * k, 66 * k, 72 * k, 32 * k), fill=BLANCO, width=int(11 * k), joint="curve")
    else:
        d.line((30 * k, 30 * k, 66 * k, 66 * k), fill=BLANCO, width=int(11 * k))
        d.line((66 * k, 30 * k, 30 * k, 66 * k), fill=BLANCO, width=int(11 * k))
    return im


def tarjeta(contenido, ok=None):
    """Captura enmarcada + insignia opcional (✓ / ✕) + sombra."""
    im = marco(contenido)
    if ok is not None:
        lienzo = Image.new("RGBA", (im.width + 30, im.height + 30))
        lienzo.alpha_composite(im, (0, 30))
        lienzo.alpha_composite(insignia(ok), (im.width - 62, 0))
        im = lienzo
    return sombra(im)


# ============================================================ publicaciones
def post(size, estilo, semilla):
    """Miniatura de publicación. estilo: 'caos' (sin línea gráfica) o 'marca'."""
    rng = np.random.default_rng(semilla)
    im = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(im)
    if estilo == "marca":
        fondo, tinta, txt = [(AZUL, AMARILLO, "3 TIPS"), (AMARILLO, TINTA, "TU WEB"), (BLANCO, AZUL, "TIP #1"),
                             (TINTA, AMARILLO, "MARCA"), (AZUL, BLANCO, "VENDE+"), (AMARILLO, AZUL, "NUEVO")][semilla % 6]
        d.rectangle((0, 0, size, size), fill=fondo)
        d.text((size * 0.1, size * 0.62), txt, font=f("ExtraBold", int(size * 0.19)), fill=tinta, anchor="ls")
        d.rectangle((size * 0.1, size * 0.7, size * 0.45, size * 0.73), fill=tinta)
        if fondo == BLANCO:
            d.rectangle((0, 0, size - 1, size - 1), outline=LINEA, width=2)
        return im
    colores = [(255, 64, 160), (140, 255, 0), (120, 70, 30), (0, 220, 255), (255, 140, 0), (160, 0, 255),
               (255, 240, 200), (30, 120, 40), (255, 0, 0)]
    c1, c2, c3 = (colores[i] for i in rng.choice(len(colores), 3, replace=False))
    d.rectangle((0, 0, size, size), fill=c1)
    if rng.random() < 0.6:
        d.ellipse((size * 0.45, -size * 0.25, size * 1.3, size * 0.6), fill=c2)
    txt = ["¡OFERTA!", "hola :)", "PROMO!!", "Nuevo!!!", "SALE", "compra ya", "50%", "LINK"][semilla % 8]
    fu = fuente(OTRAS[semilla % len(OTRAS)], int(size * rng.uniform(0.14, 0.22)))
    d.text((size * 0.08, size * rng.uniform(0.4, 0.8)), txt, font=fu, fill=c3, anchor="ls")
    if rng.random() < 0.5:
        e = emoji(["🔥", "💥", "😱", "🎉", "⭐", "💯"][semilla % 6], int(size * 0.3))
        im.alpha_composite(e, (int(size * 0.62), int(size * 0.6)))
    return im


def _cabecera_perfil(d, w, verificado):
    d.text((w / 2, 40), "tumarca", font=f("Bold", 30), fill=TINTA, anchor="mm")
    d.ellipse((28, 84, 128, 184), fill=AZUL if verificado else (205, 205, 210))
    if verificado:
        d.text((78, 134), "TGH", font=f("ExtraBold", 28), fill=BLANCO, anchor="mm")
    for k, (n, l) in enumerate((("128", "posts"), ("2.4k", "seguidores"), ("310", "seguidos"))):
        d.text((200 + k * 100, 120), n, font=f("Bold", 26), fill=TINTA, anchor="mm")
        d.text((200 + k * 100, 152), l, font=f("Medium", 15), fill=GRIS, anchor="mm")


def captura_perfil(estilo, w=450, h=680):
    im = Image.new("RGBA", (w, h), BLANCO + (255,))
    d = ImageDraw.Draw(im)
    _cabecera_perfil(d, w, estilo == "marca")
    d.line((0, 214, w, 214), fill=LINEA, width=2)
    s = (w - 4) // 3
    for i in range(12):
        x, y = (i % 3) * (s + 2), 218 + (i // 3) * (s + 2)
        if y >= h:
            break
        im.paste(post(s, estilo, i + (0 if estilo == "caos" else 100)), (x, y))
    return im


def _iconos_post(d, y):
    # corazón, comentario y enviar dibujados como trazos simples
    d.ellipse((24, y, 44, y + 20), outline=TINTA, width=3)
    d.ellipse((38, y, 58, y + 20), outline=TINTA, width=3)
    d.polygon([(26, y + 14), (41, y + 34), (56, y + 14)], outline=TINTA, width=3)
    d.ellipse((80, y, 112, y + 32), outline=TINTA, width=3)
    d.polygon([(134, y + 2), (166, y + 16), (134, y + 30), (140, y + 16)], outline=TINTA, width=3)


def captura_post(cuadro, pie, w=450, h=680, avatar=(205, 205, 210)):
    im = Image.new("RGBA", (w, h), BLANCO + (255,))
    d = ImageDraw.Draw(im)
    d.ellipse((20, 18, 76, 74), fill=avatar)
    d.text((92, 46), "tumarca", font=f("SemiBold", 26), fill=TINTA, anchor="lm")
    d.text((w - 30, 46), "···", font=f("Bold", 30), fill=TINTA, anchor="mm")
    im.paste(cuadro.resize((w, w), Image.LANCZOS), (0, 92))
    _iconos_post(d, 92 + w + 22)
    y = 92 + w + 76
    for linea in pie:
        d.text((24, y), linea, font=f("Medium", 21), fill=TINTA)
        y += 30
    return im


def cuadro_saturado(s=450):
    im = Image.new("RGBA", (s, s), (255, 230, 0, 255))
    d = ImageDraw.Draw(im)
    textos = ["¡¡SUPER OFERTA!!", "Envíos a todo el país", "Llama ya 999-999", "50% DSCTO + REGALO",
              "Síguenos en todas", "nuestras redes!!!", "Promo válida hoy", "*Aplican condiciones",
              "¡NUEVO! ¡NUEVO!", "compra 2 lleva 3", "LINK EN BIO", "Escríbenos al DM", "#oferta #promo"]
    colores = [(255, 0, 0), (0, 0, 255), (0, 150, 0), (200, 0, 200), TINTA]
    y = 14
    for k, txt in enumerate(textos):
        fu = fuente(OTRAS[k % len(OTRAS)], 22 + (k * 7) % 12)
        d.text((14, y), txt, font=fu, fill=colores[k % 5])
        y += 33
    for e, (x, yy) in (("💥", (330, 30)), ("🔥", (350, 340)), ("😱", (250, 200))):
        im.alpha_composite(emoji(e, 80), (x, yy))
    return im


def cuadro_claro(s=450):
    im = Image.new("RGBA", (s, s), AZUL + (255,))
    d = ImageDraw.Draw(im)
    d.text((40, 190), "3 tips", font=f("ExtraBold", 96), fill=AMARILLO, anchor="ls")
    d.text((40, 250), "para vender más", font=f("SemiBold", 40), fill=BLANCO, anchor="ls")
    d.rectangle((40, 285, 170, 295), fill=AMARILLO)
    d.text((40, s - 40), "tumarca", font=f("SemiBold", 24), fill=(200, 190, 255), anchor="ls")
    return im


def captura_kit_marca(w=450, h=680):
    im = Image.new("RGBA", (w, h), BLANCO + (255,))
    d = ImageDraw.Draw(im)
    d.text((30, 34), "Línea gráfica", font=f("Bold", 34), fill=TINTA)
    d.text((30, 82), "Manual de marca", font=f("Medium", 20), fill=GRIS)
    for k, (c, hx, nombre) in enumerate(((AZUL, "#3B00EF", "Azul TGH"), (AMARILLO, "#FCFC00", "Amarillo"),
                                         (TINTA, "#111118", "Tinta"), (VERDE, "#25D067", "Verde"))):
        y = 140 + k * 92
        d.rounded_rectangle((30, y, 110, y + 72), 14, fill=c, outline=LINEA, width=2)
        d.text((130, y + 12), nombre, font=f("SemiBold", 24), fill=TINTA)
        d.text((130, y + 42), hx, font=f("Medium", 19), fill=GRIS)
    d.line((30, 520, w - 30, 520), fill=LINEA, width=2)
    d.text((30, 535), "Aa", font=f("Bold", 92), fill=TINTA)
    d.text((170, 556), "Poppins", font=f("Bold", 38), fill=TINTA)
    d.text((170, 606), "Bold · SemiBold", font=f("Medium", 20), fill=GRIS)
    return im


def captura_calendario(w=880, h=470):
    im = Image.new("RGBA", (w, h), BLANCO + (255,))
    d = ImageDraw.Draw(im)
    d.text((36, 30), "Calendario de contenidos", font=f("Bold", 34), fill=TINTA)
    d.text((w - 36, 42), "Semana 1", font=f("Medium", 22), fill=GRIS, anchor="ra")
    dias = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
    cw = (w - 72) / 7
    chips = {0: ("Reel", AZUL, 0), 1: ("Story", VERDE, 1), 2: ("Post", (255, 140, 0), 0), 3: ("Reel", AZUL, 1),
             4: ("Carrusel", (200, 40, 160), 0), 5: ("Story", VERDE, 2), 6: ("Live", ROJO, 1)}
    for k, dd in enumerate(dias):
        x = 36 + k * cw
        d.text((x + cw / 2, 112), dd, font=f("SemiBold", 22), fill=GRIS, anchor="mm")
        d.rounded_rectangle((x + 4, 134, x + cw - 4, h - 30), 14, fill=(244, 244, 250))
        txt, c, fila = chips[k]
        y = 150 + fila * 92
        d.rounded_rectangle((x + 10, y, x + cw - 10, y + 80), 12, fill=c)
        d.text((x + cw / 2, y + 40), txt, font=f("Bold", 17 if len(txt) > 5 else 21), fill=BLANCO, anchor="mm")
    return im


# =================================================================== piezas
def sticker_emoji(ch, size=200, angulo=8):
    return _sticker(emoji(ch, size), angulo)


def _sticker(im, angulo):
    pad = 26
    base = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2))
    base.paste(im, (pad, pad), im)
    borde = base.split()[3].filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1))
    out = Image.merge("RGBA", [Image.new("L", base.size, 255)] * 3 + [borde])
    out.alpha_composite(base)
    return sombra(out.rotate(angulo, expand=True, resample=Image.BICUBIC), 10, 0.4, 6, 20)


def sticker_robot(cierre_png, size=260, angulo=-8):
    """Mascota TGH recortada de la tarjeta final, como sticker sobre fondo blanco."""
    fr = Image.open(cierre_png).convert("RGB")
    robot = fr.crop((150, 530, 400, 805))
    lado = max(robot.size) + 50
    base = Image.new("RGBA", (lado, lado))
    ImageDraw.Draw(base).rounded_rectangle((0, 0, lado - 1, lado - 1), 46, fill=BLANCO + (255,))
    base.paste(robot, ((lado - robot.width) // 2, (lado - robot.height) // 2))
    base = base.resize((size, size), Image.LANCZOS)
    return sombra(base.rotate(angulo, expand=True, resample=Image.BICUBIC), 14, 0.42, 8, 24)


def pastilla(txt, color, size=50, angulo=-7, icono=None):
    fu = f("Bold", size)
    tw = fu.getlength(txt)
    ico = int(size * 1.0) if icono else 0
    w, h = int(tw + 60 + (ico + 16 if icono else 0)), int(size * 1.55)
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 14, fill=color + (255,))
    x = 30
    if icono == "check":
        cy = h / 2
        d.ellipse((x, cy - ico / 2, x + ico, cy + ico / 2), fill=BLANCO)
        k = ico / 96
        d.line((x + 26 * k, cy + 2 * k, x + 42 * k, cy + 18 * k, x + 72 * k, cy - 16 * k), fill=color, width=max(3, int(12 * k)))
        x += ico + 16
    d.text((x, h / 2), txt, font=fu, fill=BLANCO, anchor="lm")
    return sombra(im.rotate(-angulo, expand=True, resample=Image.BICUBIC), 8, 0.4, 5, 20)


def escrim(w=1080, h=1920, hasta=0.46, fuerza=0.62):
    """Degradado oscuro superior (para leer texto blanco sobre la pared blanca)."""
    t = np.clip(1 - np.arange(h) / (h * hasta), 0, 1)
    a = (fuerza * t ** 1.6 * 255).astype(np.uint8)
    alfa = Image.fromarray(np.repeat(a[:, None], w, 1), "L")
    return Image.merge("RGBA", [Image.new("L", (w, h), 0)] * 3 + [alfa])

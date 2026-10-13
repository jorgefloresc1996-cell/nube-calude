#!/usr/bin/env python3
"""Reel dinámico "3 errores en redes" — estilo de edición TGH.

Efectos: zooms punch-in, textos grandes blanco/amarillo neón, subtítulos con
palabra activa resaltada, emojis, flash + glitch en cada cambio de plano,
efecto cámara REC, SFX (whoosh/pop/click) y cierre con la tarjeta de TGH.

Uso: python3 tgh_3_errores.py crudo.mp4 referencia.mp4 transcripcion.json salida.mp4
"""
import json
import subprocess
import sys
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CRUDO, REFERENCIA, TRANSCRIPCION, SALIDA = sys.argv[1:5]
W, H, FPS = 1080, 1920, 30
SR = 48000
FONT_BLACK = "/usr/share/fonts/truetype/montserrat/Montserrat-Black.ttf"
FONT_XBOLD = "/usr/share/fonts/truetype/montserrat/Montserrat-ExtraBold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
AMARILLO = (255, 238, 0)
BLANCO = (255, 255, 255)
AZUL_TGH = (43, 43, 230)
ROJO = (235, 40, 50)
VERDE = (37, 190, 90)

# Cortes de plano del crudo (detectados) → transición flash + glitch + whoosh.
CORTES = [5.367, 10.833, 13.0, 16.0, 18.733, 20.933]
FIN_CRUDO = 23.933
FIN_REF_INICIO, FIN_REF_DUR = 26.0, 3.25  # tarjeta final de la referencia

# Texto corregido por bloque de la transcripción (mismo orden que el JSON).
TEXTO = [
    "Tres errores que hacen que tus redes se vean",
    "poco profesionales",
    "Puede que estés cometiendo estos tres errores.",
    "Error 1: Usar colores y estilos",
    "diferentes en cada publicación.",
    "Define tu línea gráfica.",
    "Error 2: Saturar tus diseños.",
    "Usa textos breves y",
    "claros para facilitar la lectura.",
    "Error 3:",
    "Publicar sin estrategia.",
    "Organiza tus contenidos con anticipación.",
    "¿Cometes alguno de estos errores?",
    "Coméntanos en los comentarios.",
]
CLAVE = {"errores", "profesionales", "colores", "estilos", "publicación", "línea", "gráfica",
         "saturar", "diseños", "breves", "claros", "lectura", "estrategia", "organiza",
         "anticipación", "coméntanos", "contenidos"}

# Textos grandes (inicio, fin, [(texto, color, tamaño)], emoji). Ocultan los subtítulos.
GRANDES = [
    (0.00, 1.05, [("3 ERRORES", AMARILLO, 190)], "😱"),
    (2.12, 3.36, [("POCO", BLANCO, 150), ("PROFESIONALES", AMARILLO, 118)], "😬"),
    (9.32, 10.83, [("Define tu", BLANCO, 110), ("LÍNEA GRÁFICA", AMARILLO, 128)], "✅"),
    (10.833, 12.98, [("SATURAR", BLANCO, 165), ("TUS DISEÑOS", AMARILLO, 140)], "🤯"),
    (17.02, 18.733, [("PUBLICAR", BLANCO, 160), ("SIN ESTRATEGIA", AMARILLO, 118)], "😰"),
    (20.933, 22.58, [("¿COMETES", BLANCO, 150), ("ALGUNO?", AMARILLO, 175)], "🤔"),
    (22.58, FIN_CRUDO, [("COMÉNTANOS", AMARILLO, 150), ("en los comentarios", BLANCO, 72)], "👇"),
]
# Insignias de sección (arriba).
INSIGNIAS = [(5.367, 10.833, "ERROR 1"), (10.833, 16.0, "ERROR 2"), (16.0, 20.933, "ERROR 3")]
EMOJIS_SUB = [(3.9, 5.3, "👀"), (6.0, 9.3, "🎨"), (13.0, 16.0, "✍️"), (18.9, 20.9, "📅")]
REC = (16.0, 17.02)


# ---------------------------------------------------------------- utilidades
def font(path, size):
    return ImageFont.truetype(path, size)


def emoji_img(ch, size):
    f = ImageFont.truetype(FONT_EMOJI, 109)
    im = Image.new("RGBA", (160, 160))
    ImageDraw.Draw(im).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)


def texto_img(lineas, ancho_max=1000):
    """Bloque de texto grande: tracking cerrado, sombra suave, glow en amarillo."""
    capas = []
    for txt, color, size in lineas:
        f = font(FONT_BLACK, size)
        while f.getlength(txt) > ancho_max and size > 40:
            size -= 4
            f = font(FONT_BLACK, size)
        track = -size * 0.04
        ancho = int(sum(f.getlength(c) + track for c in txt) - track) + 40
        alto = int(size * 1.15)
        txt_l = Image.new("L", (ancho, alto))
        d = ImageDraw.Draw(txt_l)
        x = 20
        for c in txt:
            d.text((x, alto / 2), c, font=f, fill=255, anchor="lm")
            x += f.getlength(c) + track
        capas.append((txt_l, color))
    pad = 60
    ancho = max(c[0].width for c in capas) + pad * 2
    gap = -10
    alto = sum(c[0].height for c in capas) + gap * (len(capas) - 1) + pad * 2
    out = Image.new("RGBA", (ancho, alto))
    y = pad
    for mask, color in capas:
        x = (ancho - mask.width) // 2
        full = Image.new("L", (ancho, alto))
        full.paste(mask, (x, y))
        sombra = full.filter(ImageFilter.GaussianBlur(16))
        out.alpha_composite(Image.merge("RGBA", [Image.new("L", (ancho, alto), 0)] * 3
                                        + [sombra.point(lambda v: min(255, v * 0.9))]), (0, 10))
        borde = full.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(1.5))
        out.alpha_composite(Image.merge("RGBA", [Image.new("L", (ancho, alto), c) for c in (25, 18, 10)]
                                        + [borde.point(lambda v: v * 0.85)]))
        if color == AMARILLO:
            glow = full.filter(ImageFilter.GaussianBlur(22)).point(lambda v: min(255, v * 1.3))
            out.alpha_composite(Image.merge("RGBA", [Image.new("L", (ancho, alto), c) for c in (255, 230, 0)] + [glow]))
        out.alpha_composite(Image.merge("RGBA", [Image.new("L", (ancho, alto), c) for c in color] + [full]))
        y += mask.height + gap
    return out


def pastilla(txt, fondo, size=58, emoji=None):
    f = font(FONT_BLACK, size)
    tw = int(f.getlength(txt))
    e = emoji_img(emoji, int(size * 1.1)) if emoji else None
    ew = e.width + 18 if e else 0
    w, h = tw + ew + 70, int(size * 1.6)
    im = Image.new("RGBA", (w + 30, h + 30))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((15, 22, 15 + w, 22 + h), h // 2, fill=(0, 0, 0, 90))
    im = im.filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((15, 15, 15 + w, 15 + h), h // 2, fill=fondo + (255,))
    if e:
        im.alpha_composite(e, (15 + 35, 15 + (h - e.height) // 2))
    d.text((15 + 35 + ew, 15 + h / 2), txt, font=f, fill=BLANCO, anchor="lm")
    return im


def subtitulo_img(palabras, activa):
    f = font(FONT_BLACK, 82)
    sp = 22
    anchos = [f.getlength(p) for p in palabras]
    w = int(sum(anchos) + sp * (len(palabras) - 1)) + 60
    h = 140
    mask_all = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(mask_all)
    x = 30
    for i, p in enumerate(palabras):
        clave = p.lower().strip("¿?.,:!¡") in CLAVE
        color = AMARILLO if (i == activa or clave) else BLANCO
        d.text((x, h / 2), p, font=f, fill=color + (255,), anchor="lm", stroke_width=7, stroke_fill=(0, 0, 0, 255))
        x += anchos[i] + sp
    sombra = mask_all.split()[3].filter(ImageFilter.GaussianBlur(10)).point(lambda v: v * 0.5)
    out = Image.new("RGBA", (w, h + 10))
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), 0)] * 3 + [sombra]), (0, 8))
    out.alpha_composite(mask_all)
    return out


def a_np(im):
    return np.asarray(im, dtype=np.float32)


def componer(frame, ov, cx, cy, escala=1.0, alpha=1.0):
    """Pega un RGBA (np float) centrado en (cx,cy) con escala y opacidad."""
    if escala != 1.0:
        ov = cv2.resize(ov, None, fx=escala, fy=escala, interpolation=cv2.INTER_LINEAR)
    h, w = ov.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    fx0, fy0 = max(x0, 0), max(y0, 0)
    fx1, fy1 = min(x0 + w, W), min(y0 + h, H)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    o = ov[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = o[..., 3:4] / 255.0 * alpha
    reg = frame[fy0:fy1, fx0:fx1]
    reg[:] = reg * (1 - a) + o[..., :3] * a


def pop(t, dur=0.22):
    """Escala con rebote: 0.55 → 1.08 → 1.0."""
    if t >= dur:
        return 1.0
    x = t / dur
    return 0.55 + 0.53 * np.sin(x * np.pi * 0.62) / np.sin(np.pi * 0.62) - 0.08 * max(0, x - 0.6) / 0.4


# ------------------------------------------------------------ transcripción
def tiempos_palabras():
    bloques = json.load(open(TRANSCRIPCION))
    w = wave.open("/dev/stdin" if False else AUDIO16K)
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    fr = 320
    rms = np.array([np.sqrt(np.mean(a[i:i + fr] ** 2)) for i in range(0, len(a) - fr, fr)])
    palabras = []
    for b, txt in zip(bloques, TEXTO):
        i0, i1 = int(b["start"] / 0.02), int(b["end"] / 0.02)
        seg = rms[i0:i1]
        voz = np.where(seg > seg.max() * 0.12)[0] + i0
        ws = txt.split()
        pesos = np.array([len(x) + 2 for x in ws], float)
        acum = np.concatenate([[0], np.cumsum(pesos)]) / pesos.sum()
        idx = (acum * (len(voz) - 1)).astype(int)
        for k, p in enumerate(ws):
            palabras.append((voz[idx[k]] * 0.02, voz[idx[k + 1]] * 0.02 + 0.02, p))
    # Grupos de máx 3 palabras, cortando en puntuación.
    grupos, g = [], []
    for p in palabras:
        g.append(p)
        if len(g) == 3 or p[2][-1] in ".:?,":
            grupos.append(g)
            g = []
    if g:
        grupos.append(g)
    return grupos


# --------------------------------------------------------------------- audio
def sfx_whoosh(d=0.45):
    n = int(SR * d)
    t = np.linspace(0, 1, n)
    ruido = np.random.default_rng(1).standard_normal(n)
    out = np.zeros(n)
    f = 0.0
    for i in range(n):  # paso bajo con corte que sube y baja
        k = 0.02 + 0.5 * np.sin(np.pi * t[i]) ** 2
        f += k * (ruido[i] - f)
        out[i] = f
    return out * np.sin(np.pi * t) ** 1.5 * 0.5


def sfx_pop(d=0.09):
    t = np.arange(int(SR * d)) / SR
    return np.sin(2 * np.pi * (900 - 5000 * t) * t) * np.exp(-t * 45) * 0.35


def sfx_click():
    t = np.arange(int(SR * 0.05)) / SR
    return np.random.default_rng(2).standard_normal(len(t)) * np.exp(-t * 120) * 0.4


def sfx_chime():
    t = np.arange(int(SR * 1.2)) / SR
    s = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((880, .5), (1320, .3), (1760, .15)))
    return s * np.exp(-t * 3.5) * 0.25


def preparar_audio(dur_total):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", CRUDO, "-t", str(FIN_CRUDO), "-af",
                    "highpass=f=80,afftdn=nf=-28,equalizer=f=3500:t=q:w=1:g=2.5,"
                    "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,"
                    "loudnorm=I=-15:TP=-2:LRA=9", "-ac", "2", "-ar", str(SR), VOZ_WAV], check=True)
    w = wave.open(VOZ_WAV)
    voz = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    mix = np.zeros((int(dur_total * SR) + SR, 2), np.float32)
    mix[:len(voz)] += voz

    def poner(s, t, g=1.0):
        i = int(t * SR)
        mix[i:i + len(s)] += (s[:len(mix) - i] * g)[:, None]
    wh = sfx_whoosh()
    for c in CORTES:
        poner(wh, c - 0.2, 0.55)
    for g in GRANDES:
        poner(sfx_pop(), g[0], 0.6)
    poner(sfx_click(), REC[0], 0.8)
    poner(wh, FIN_CRUDO - 0.2, 0.6)
    poner(sfx_chime(), FIN_CRUDO + 0.35, 0.8)
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)  # limitador suave
    mix = mix[:int(dur_total * SR)]
    out = wave.open(MIX_WAV, "wb")
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(SR)
    out.writeframes((mix * 32767).astype(np.int16).tobytes())
    out.close()


# --------------------------------------------------------------------- video
def zoom_base(t):
    """Zoom tipo jump-cut: cambia en cada frase, empuje lento dentro de ella."""
    inicios = [0, 1.05, 2.12, 3.36, 5.367, 7.3, 9.32, 10.833, 13.0, 14.18, 16.0, 17.02, 18.733, 20.933, 22.58]
    k = max(i for i, s in enumerate(inicios) if s <= t)
    base = [1.0, 1.14, 1.22, 1.0, 1.0, 1.15, 1.2, 1.12, 1.0, 1.14, 1.0, 1.2, 1.0, 1.12, 1.2][k]
    return base + 0.012 * (t - inicios[k])


def transformar(img, z, dx=0.0, dy=0.0):
    cx, cy = W / 2 + dx, H * 0.36 + dy  # ancla en la cara
    M = np.float32([[z, 0, cx - z * cx], [0, z, cy - z * cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def glitch(img, fuerza):
    s = int(28 * fuerza)
    out = img.copy()
    out[..., 0] = np.roll(img[..., 0], s, axis=1)
    out[..., 2] = np.roll(img[..., 2], -s, axis=1)
    rng = np.random.default_rng(int(fuerza * 1000))
    for _ in range(int(6 * fuerza)):
        y = rng.integers(0, H - 80)
        hh = rng.integers(10, 80)
        out[y:y + hh] = np.roll(out[y:y + hh], rng.integers(-90, 90), axis=1)
    return out


def rec_overlay():
    im = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(im)
    m, L, g = 70, 110, 8
    for (x, y, sx, sy) in ((m, 260, 1, 1), (W - m, 260, -1, 1), (m, H - 330, 1, -1), (W - m, H - 330, -1, -1)):
        d.line((x, y, x + L * sx, y), fill=BLANCO, width=g)
        d.line((x, y, x, y + L * sy), fill=BLANCO, width=g)
    f = font(FONT_MONO, 52)
    d.text((m + 95, 300), "REC", font=f, fill=BLANCO)
    d.text((W - m - 30, 300), "F 5.6\nISO 800", font=font(FONT_MONO, 40), fill=BLANCO, anchor="ra", align="right")
    d.text((m + 30, H - 460), "4K 3840 x 2160\n60fps", font=font(FONT_MONO, 44), fill=BLANCO)
    c = (W // 2, int(H * 0.36))
    d.rectangle((c[0] - 150, c[1] - 150, c[0] + 150, c[1] + 150), outline=BLANCO, width=4)
    return a_np(im)


def main():
    grupos = tiempos_palabras()
    dur_total = FIN_CRUDO + FIN_REF_DUR
    preparar_audio(dur_total)

    # Pre-render de gráficos.
    grandes = [(s, e, a_np(texto_img(l)), a_np(emoji_img(em, 140).rotate(-12, expand=True, resample=Image.BICUBIC))) for s, e, l, em in GRANDES]
    insignias = {n: a_np(pastilla(n, ROJO, 64, "❌")) for _, _, n in INSIGNIAS}
    emojis_sub = [(s, e, a_np(emoji_img(em, 130))) for s, e, em in EMOJIS_SUB]
    rec = rec_overlay()
    cache_sub = {}

    dec = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", CRUDO, "-t", str(FIN_CRUDO), "-vf",
         "scale=1080:1920,eq=contrast=1.07:saturation=1.12:gamma=0.98,"
         "colorbalance=rs=.03:gs=.01:bs=-.03,unsharp=5:5:0.5",
         "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    fin = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", str(FIN_REF_INICIO), "-i", REFERENCIA, "-t", str(FIN_REF_DUR),
         "-vf", "scale=1080:1920,drawbox=x=740:y=1790:w=340:h=120:color=white:t=fill",
         "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", MIX_WAV, "-c:v", "libx264", "-preset", "slow", "-crf", "17",
         "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", SALIDA], stdin=subprocess.PIPE)

    n_total = int(dur_total * FPS)
    prev = None
    for n in range(n_total):
        t = n / FPS
        raw = dec.stdout.read(W * H * 3) if t < FIN_CRUDO else b""
        if t >= FIN_CRUDO or len(raw) < W * H * 3:
            raw_fin = fin.stdout.read(W * H * 3)
            if len(raw_fin) < W * H * 3:
                break
            img = np.frombuffer(raw_fin, np.uint8).reshape(H, W, 3).astype(np.float32)
            tf = t - FIN_CRUDO
            if tf < 0.12:  # flash de entrada al cierre
                img = img * (tf / 0.12) + 255 * (1 - tf / 0.12)
            if prev is not None and tf < 0.2:
                img = img * (tf / 0.2) + prev * (1 - tf / 0.2)
            enc.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
            continue
        img = np.frombuffer(raw, np.uint8).reshape(H, W, 3)

        # Zoom + whip-zoom en cortes + micro sacudida.
        z = zoom_base(t)
        dx = dy = 0.0
        tc = min([t - c for c in CORTES if t >= c] or [99])
        if tc < 0.28:
            e = 1 - tc / 0.28
            z += 0.35 * e ** 2
            dy = -40 * e ** 2
        for g in GRANDES:
            if 0 <= t - g[0] < 0.18:
                dx += 9 * np.sin((t - g[0]) * 90)
        frame = transformar(img, z, dx, dy).astype(np.float32)

        if REC[0] <= t < REC[1]:
            gris = frame.mean(axis=2, keepdims=True)
            frame = np.repeat(gris, 3, axis=2) * 1.05
            componer(frame, rec, W / 2, H / 2)
            if int(t * 2) % 2 == 0:
                cv2.circle(frame, (95 + 70 - 30, 330), 20, (235, 40, 50), -1)

        # Insignia de sección.
        for s, e, nombre in INSIGNIAS:
            if s <= t < e and not (REC[0] <= t < REC[1]):
                ts = t - s
                x = W / 2 - max(0, 1 - ts / 0.25) ** 2 * 900
                componer(frame, insignias[nombre], x, 290)

        # Texto grande o subtítulos.
        activo = next((g for g in grandes if g[0] <= t < g[1]), None)
        if activo:
            s, e, txt, em = activo
            ts = t - s
            sc = pop(ts)
            cy = H * 0.72
            componer(frame, txt, W / 2, cy, sc, min(1, ts / 0.05))
            if ts > 0.12:  # emoji a un costado, sin tapar la cara
                componer(frame, em, min(W - 95, W / 2 + txt.shape[1] * 0.42), cy - txt.shape[0] * 0.5,
                          pop(ts - 0.12))
        elif not (REC[0] <= t < REC[1]):
            for gi, g in enumerate(grupos):
                fin_g = grupos[gi + 1][0][0] if gi + 1 < len(grupos) else g[-1][1] + 0.4
                if g[0][0] <= t < min(fin_g, g[-1][1] + 0.5):
                    act = max([i for i, p in enumerate(g) if p[0] <= t] or [0])
                    key = (gi, act)
                    if key not in cache_sub:
                        cache_sub[key] = a_np(subtitulo_img([p[2] for p in g], act))
                    ts = t - g[0][0]
                    componer(frame, cache_sub[key], W / 2, H * 0.66, 0.85 + 0.15 * min(1, ts / 0.08))
                    break
            for s, e, em in emojis_sub:
                if s <= t < e:
                    componer(frame, em, W / 2, H * 0.66 - 140, pop(t - s))

        # Flash + glitch en cortes.
        if tc < 0.25:
            if tc < 0.1:
                frame = frame * 0.35 + 255 * 0.65 * (1 - tc / 0.1) + frame * 0.65 * (tc / 0.1)
            frame = glitch(frame, 1 - tc / 0.25)
        prev = frame
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        if n % 60 == 0:
            print(f"  frame {n}/{n_total}", flush=True)
    enc.stdin.close()
    enc.wait()
    print("✔", SALIDA)


if __name__ == "__main__":
    import tempfile, os
    tmp = tempfile.mkdtemp(prefix="reel_")
    AUDIO16K = os.path.join(tmp, "a16k.wav")
    VOZ_WAV = os.path.join(tmp, "voz.wav")
    MIX_WAV = os.path.join(tmp, "mix.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", CRUDO, "-ac", "1", "-ar", "16000", AUDIO16K], check=True)
    main()

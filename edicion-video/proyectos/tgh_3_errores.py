#!/usr/bin/env python3
"""Reel "3 errores en redes" — sistema visual de la referencia TGH.

Tipografía Poppins con tracking cerrado; colores de la referencia
(amarillo #FCFC00 con glow, azul TGH #3B00EF, verde #25D067, rojo #F03635).
Recursos: subtítulo en dos niveles (línea chica blanca + palabra grande),
palabras a todo el ancho DETRÁS de la persona, fondo rojo con palabra
repetida (efecto "PERO PERO PERO"), efecto cámara REC, pastillas inclinadas,
stickers, flash blanco, zooms y tarjeta final TGH.

Uso: python3 tgh_3_errores.py crudo.mp4 referencia.mp4 transcripcion.json salida.mp4 modelo_segmentacion.tflite
"""
import json
import os
import subprocess
import sys
import tempfile
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CRUDO, REFERENCIA, TRANSCRIPCION, SALIDA, MODELO_SEG = sys.argv[1:6]
W, H, FPS, SR = 1080, 1920, 30, 48000
POPPINS = "/usr/local/share/fonts/poppins/Poppins-{}.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
AMARILLO = (252, 252, 0)
BLANCO = (255, 255, 255)
AZUL_TGH = (59, 0, 239)
VERDE = (37, 208, 103)
ROJO = (240, 54, 53)

CORTES = [5.367, 10.833, 13.0, 16.0, 18.733, 20.933]
FIN_CRUDO = 23.933
FIN_REF_INICIO, FIN_REF_DUR = 26.0, 3.25

TEXTO = [
    "Tres errores que hacen que tus redes se vean", "poco profesionales",
    "Puede que estés cometiendo estos tres errores.", "Error 1: Usar colores y estilos",
    "diferentes en cada publicación.", "Define tu línea gráfica.", "Error 2: Saturar tus diseños.",
    "Usa textos breves y", "claros para facilitar la lectura.", "Error 3:", "Publicar sin estrategia.",
    "Organiza tus contenidos con anticipación.", "¿Cometes alguno de estos errores?",
    "Coméntanos en los comentarios.",
]

# Guion visual. Inicio/fin = índice de palabra (int) o segundo (float).
# cap: (chica, grande) — *palabra* = amarillo; las palabras grandes aparecen al decirse.
# top: palabra(s) a todo el ancho detrás de la persona, fondo atenuado.
# rojo: fondo rojo + palabra repetida x3 detrás de la persona.
GUION = [
    dict(t="top", a=0, b=2, lineas=[("3 ERRORES", BLANCO)]),
    dict(t="cap", a=2, b=9, chica="que hacen que tus", grande="*redes* se vean", palabras=(6, 9)),
    dict(t="top", a=9, b=11, lineas=[("POCO", BLANCO), ("PROFESIONALES", AMARILLO)]),
    dict(t="cap", a=11, b=15, chica="Puede que estés", grande="cometiendo", palabras=(14, 15)),
    dict(t="cap", a=15, b=5.367, chica="estos", grande="*3* *errores*", palabras=(16, 18), emoji="😬"),
    dict(t="rojo", a=5.367, b=20, palabra="ERROR 1"),
    dict(t="cap", a=20, b=24, chica="Usar", grande="*colores* y *estilos*", palabras=(21, 24)),
    dict(t="cap", a=24, b=28, chica="diferentes en", grande="cada publicación", palabras=(26, 28)),
    dict(t="cap", a=28, b=10.833, chica="Define tu", grande="*línea* *gráfica*", palabras=(30, 32),
         pastilla=("Solución", VERDE)),
    dict(t="rojo", a=10.833, b=34, palabra="ERROR 2"),
    dict(t="top", a=34, b=35, lineas=[("SATURAR", BLANCO)]),
    dict(t="top", a=35, b=13.0, lineas=[("TUS DISEÑOS", AMARILLO)]),
    dict(t="cap", a=13.0, b=42, chica="Usa textos", grande="*breves* y *claros*", palabras=(39, 42)),
    dict(t="cap", a=42, b=16.0, chica="para facilitar", grande="la lectura", palabras=(44, 46),
         pastilla=("Solución", VERDE)),
    dict(t="rojo", a=16.0, b=48, palabra="ERROR 3"),
    dict(t="top", a=48, b=49, lineas=[("PUBLICAR", BLANCO)]),
    dict(t="top", a=49, b=18.733, lineas=[("SIN", BLANCO), ("ESTRATEGIA", AMARILLO)]),
    dict(t="cap", a=51, b=54, chica="Organiza tus", grande="contenidos", palabras=(53, 54), emoji="📅"),
    dict(t="cap", a=54, b=20.933, chica="con", grande="*anticipación*", palabras=(55, 56),
         pastilla=("Solución", VERDE)),
    dict(t="cap", a=20.933, b=58, chica="¿Cometes", grande="alguno", palabras=(57, 58)),
    dict(t="cap", a=58, b=61, chica="de estos", grande="*errores?*", palabras=(60, 61), emoji="🤔"),
    dict(t="cta", a=61, b=FIN_CRUDO, chica="Coméntanos", grande="¡AHORA!", pastilla=("en los comentarios", AZUL_TGH)),
]
REC = (18.733, 19.75)
INICIOS_ZOOM = [0, 1.05, 2.12, 3.36, 5.367, 6.3, 7.3, 9.32, 10.833, 11.9, 13.0, 14.18, 16.0, 17.02,
                18.733, 20.933, 22.58]
ZOOMS = [1.04, 1.12, 1.04, 1.16, 1.06, 1.0, 1.12, 1.18, 1.06, 1.0, 1.0, 1.12, 1.06, 1.0, 1.0, 1.1, 1.0]


# ------------------------------------------------------------------ tipografía
def f(peso, size):
    return ImageFont.truetype(POPPINS.format(peso), size)


def mascara_texto(txt, fuente, track):
    asc, desc = fuente.getmetrics()
    ancho = int(sum(fuente.getlength(c) + track for c in txt) - track) + 4
    m = Image.new("L", (max(ancho, 1), asc + desc))
    d = ImageDraw.Draw(m)
    x = 2
    for c in txt:
        d.text((x, 0), c, font=fuente, fill=255)
        x += fuente.getlength(c) + track
    bb = m.getbbox()
    return m.crop((0, bb[1], m.width, bb[3])) if bb else m


def estilizar(mask, color, pad=50, glow=None, sombra=0.8):
    """Texto con sombra suave (y glow amarillo, como en la referencia)."""
    w, h = mask.width + pad * 2, mask.height + pad * 2
    full = Image.new("L", (w, h))
    full.paste(mask, (pad, pad))
    out = Image.new("RGBA", (w, h))
    sh = full.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(11)).point(lambda v: min(255, v * sombra))
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), c) for c in (20, 12, 8)] + [sh]), (0, 7))
    if glow is None:
        glow = color == AMARILLO
    if glow:
        g = full.filter(ImageFilter.GaussianBlur(9)).point(lambda v: v * 0.75)
        out.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), c) for c in AMARILLO] + [g]))
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), c) for c in color] + [full]))
    return out


def palabra_ancha(txt, color, ancho=1010, alto_max=300):
    """Palabra condensada a todo el ancho (como PERDISTE / CALIDAD)."""
    m = mascara_texto(txt, f("Bold", 260), -10)
    esc_y = min(alto_max, 230 if len(txt) > 9 else 260) / m.height
    m = m.resize((min(ancho, int(m.width * esc_y * 0.86)), int(m.height * esc_y)), Image.LANCZOS)
    return estilizar(m, color)


def palabras_grandes(grande, size=150):
    """Lista de (img, ancho) por palabra de la línea grande; *x* = amarillo."""
    fu = f("Bold", size)
    res = []
    for p in grande.split():
        amarillo = p.startswith("*")
        p = p.strip("*")
        res.append((estilizar(mascara_texto(p, fu, -size * 0.06), AMARILLO if amarillo else BLANCO, pad=40),
                    fu.getlength(p) - size * 0.06 * len(p)))
    return res


def linea_chica(txt, size=58):
    return estilizar(mascara_texto(txt, f("SemiBold", size), -size * 0.05), BLANCO, pad=40)


def pastilla(txt, color, size=50, angulo=-7):
    fu = f("Bold", size)
    tw = fu.getlength(txt) - size * 0.03 * len(txt)
    w, h = int(tw + 60), int(size * 1.55)
    im = Image.new("RGBA", (w + 40, h + 40))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 20, 20 + w, 20 + h), 14, fill=color + (255,))
    m = mascara_texto(txt, fu, -size * 0.03)
    im.paste(Image.new("RGBA", m.size, BLANCO + (255,)), (20 + 30, 20 + (h - m.height) // 2), m)
    sh = im.split()[3].filter(ImageFilter.GaussianBlur(8)).point(lambda v: v * 0.4)
    out = Image.new("RGBA", im.size)
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", im.size, 0)] * 3 + [sh]), (0, 5))
    out.alpha_composite(im)
    return out.rotate(-angulo, expand=True, resample=Image.BICUBIC)


def sticker(ch, size=170):
    fe = ImageFont.truetype(FONT_EMOJI, 109)
    im = Image.new("RGBA", (180, 180))
    ImageDraw.Draw(im).text((90, 90), ch, font=fe, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox()).resize((size, size), Image.LANCZOS)
    pad = 24
    base = Image.new("RGBA", (size + pad * 2, size + pad * 2))
    base.paste(im, (pad, pad), im)
    borde = base.split()[3].filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1))
    sh = borde.filter(ImageFilter.GaussianBlur(10)).point(lambda v: v * 0.45)
    out = Image.new("RGBA", base.size)
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", base.size, 0)] * 3 + [sh]), (0, 6))
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", base.size, 255)] * 3 + [borde]))
    out.alpha_composite(base)
    return out.rotate(8, expand=True, resample=Image.BICUBIC)


def npa(im):
    return np.asarray(im, dtype=np.float32)


def componer(frame, ov, cx, cy, escala=1.0, alpha=1.0, mask_delante=None):
    """Pega RGBA centrado; mask_delante (persona) tapa el gráfico donde vale 1."""
    if escala != 1.0:
        ov = cv2.resize(ov, None, fx=escala, fy=escala, interpolation=cv2.INTER_LINEAR)
    h, w = ov.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    o = ov[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = o[..., 3:4] / 255.0 * alpha
    if mask_delante is not None:
        a = a * (1 - mask_delante[fy0:fy1, fx0:fx1, None])
    reg = frame[fy0:fy1, fx0:fx1]
    reg[:] = reg * (1 - a) + o[..., :3] * a


def pop(t, d=0.2):
    if t >= d:
        return 1.0
    x = t / d
    return 0.6 + 0.48 * np.sin(x * np.pi / 2) - 0.08 * max(0.0, x - 0.7) / 0.3


# ------------------------------------------------------------- transcripción
def tiempos_palabras(audio16k):
    bloques = json.load(open(TRANSCRIPCION))
    w = wave.open(audio16k)
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    rms = np.array([np.sqrt(np.mean(a[i:i + 320] ** 2)) for i in range(0, len(a) - 320, 320)])
    res = []
    for b, txt in zip(bloques, TEXTO):
        i0, i1 = int(b["start"] / 0.02), int(b["end"] / 0.02)
        seg = rms[i0:i1]
        voz = np.where(seg > seg.max() * 0.12)[0] + i0
        ws = txt.split()
        pesos = np.array([len(x) + 2 for x in ws], float)
        acum = np.concatenate([[0], np.cumsum(pesos)]) / pesos.sum()
        idx = (acum * (len(voz) - 1)).astype(int)
        res += [voz[idx[k]] * 0.02 for k in range(len(ws))]
    return res


# --------------------------------------------------------------------- audio
def sfx_whoosh(d=0.42):
    n = int(SR * d)
    t = np.linspace(0, 1, n)
    rz = np.random.default_rng(1).standard_normal(n)
    out, v = np.zeros(n), 0.0
    for i in range(n):
        v += (0.02 + 0.5 * np.sin(np.pi * t[i]) ** 2) * (rz[i] - v)
        out[i] = v
    return out * np.sin(np.pi * t) ** 1.5 * 0.5


def sfx_pop():
    t = np.arange(int(SR * 0.08)) / SR
    return np.sin(2 * np.pi * (900 - 5000 * t) * t) * np.exp(-t * 45) * 0.3


def sfx_impacto():
    t = np.arange(int(SR * 0.6)) / SR
    return (np.sin(2 * np.pi * (120 * np.exp(-t * 6) + 40) * t) * np.exp(-t * 7) * 0.8
            + np.random.default_rng(3).standard_normal(len(t)) * np.exp(-t * 40) * 0.25)


def sfx_click():
    t = np.arange(int(SR * 0.05)) / SR
    return np.random.default_rng(2).standard_normal(len(t)) * np.exp(-t * 120) * 0.4


def sfx_chime():
    t = np.arange(int(SR * 1.2)) / SR
    return sum(np.sin(2 * np.pi * fr * t) * a for fr, a in ((880, .5), (1320, .3), (1760, .15))) * np.exp(-t * 3.5) * 0.25


def preparar_audio(eventos, dur, voz_wav, mix_wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", CRUDO, "-t", str(FIN_CRUDO), "-af",
                    "highpass=f=80,afftdn=nf=-28,equalizer=f=3500:t=q:w=1:g=2.5,"
                    "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,"
                    "loudnorm=I=-15:TP=-2:LRA=9", "-ac", "2", "-ar", str(SR), voz_wav], check=True)
    w = wave.open(voz_wav)
    voz = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    mix = np.zeros((int(dur * SR) + SR, 2), np.float32)
    mix[:len(voz)] += voz * 0.92

    def poner(s, t, g):
        i = max(0, int(t * SR))
        n = min(len(s), len(mix) - i)
        mix[i:i + n] += (s[:n] * g)[:, None]
    wh = sfx_whoosh()
    for c in CORTES + [FIN_CRUDO]:
        poner(wh, c - 0.2, 0.5)
    for e in eventos:
        if e["t"] == "rojo":
            poner(sfx_impacto(), e["a"], 0.55)
        elif e["t"] in ("top", "cta"):
            poner(sfx_pop(), e["a"], 0.55)
    poner(sfx_click(), REC[0], 0.8)
    poner(sfx_chime(), FIN_CRUDO + 0.35, 0.8)
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    mix = mix[:int(dur * SR)] * 0.9
    o = wave.open(mix_wav, "wb")
    o.setnchannels(2)
    o.setsampwidth(2)
    o.setframerate(SR)
    o.writeframes((mix * 32767).astype(np.int16).tobytes())
    o.close()


# --------------------------------------------------------------------- video
class Segmentador:
    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self.mp = mp
        self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=MODELO_SEG), output_confidence_masks=True,
            running_mode=vision.RunningMode.IMAGE))
        self.prev = None
        self.prev_n = -10

    def __call__(self, frame_u8, n):
        small = np.ascontiguousarray(cv2.resize(frame_u8, (540, 960), interpolation=cv2.INTER_AREA))
        r = self.seg.segment(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=small))
        m = 1.0 - r.confidence_masks[0].numpy_view()
        m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
        m = np.clip((cv2.GaussianBlur(m, (0, 0), 2.0) - 0.42) / 0.38, 0, 1).astype(np.float32)
        if self.prev is not None and n - self.prev_n == 1:
            m = 0.6 * m + 0.4 * self.prev  # suaviza parpadeo
        self.prev, self.prev_n = m, n
        return m


def zoom_en(t):
    k = max(i for i, s in enumerate(INICIOS_ZOOM) if s <= t)
    return ZOOMS[k] + 0.012 * (t - INICIOS_ZOOM[k])


def transformar(img, z, dy=0.0):
    cx, cy = W / 2, H * 0.36 + dy
    M = np.float32([[z, 0, cx - z * cx], [0, z, cy - z * cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def rec_overlay():
    im = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(im)
    m, L, g = 60, 120, 6
    for (x, y, sx, sy) in ((m, 220, 1, 1), (W - m, 220, -1, 1), (m, H - 280, 1, -1), (W - m, H - 280, -1, -1)):
        d.line((x, y, x + L * sx, y), fill=BLANCO, width=g)
        d.line((x, y, x, y + L * sy), fill=BLANCO, width=g)
    d.text((m + 110, 250), "Rec", font=ImageFont.truetype(FONT_MONO, 64), fill=BLANCO)
    d.text((W - m - 40, 250), "F 5.6", font=ImageFont.truetype(FONT_MONO, 56), fill=BLANCO, anchor="ra")
    d.text((W - m - 40, 320), "Iso 800", font=ImageFont.truetype(FONT_MONO, 40), fill=BLANCO, anchor="ra")
    d.text((m + 40, H - 440), "4k 3840 x 2160\n60fps", font=ImageFont.truetype(FONT_MONO, 52), fill=BLANCO)
    c, s, l = (W // 2, int(H * 0.40)), 170, 50
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = c[0] + sx * s, c[1] + sy * s
            d.line((x, y, x - sx * l, y), fill=BLANCO, width=4)
            d.line((x, y, x, y - sy * l), fill=BLANCO, width=4)
    d.rounded_rectangle((W - m - 110, H - 360, W - m - 40, H - 325), 5, outline=BLANCO, width=4)
    d.rectangle((W - m - 102, H - 352, W - m - 60, H - 333), fill=BLANCO)
    return npa(im)


def main():
    tmp = tempfile.mkdtemp(prefix="reel_")
    a16 = os.path.join(tmp, "a16k.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", CRUDO, "-ac", "1", "-ar", "16000", a16], check=True)
    tw = tiempos_palabras(a16)

    def seg(x):
        return tw[x] if isinstance(x, int) else x
    eventos = []
    for e in GUION:
        e = dict(e, a=seg(e["a"]), b=seg(e["b"]))
        if e["t"] in ("top", "cta", "rojo"):
            e["a"] = max(e["a"] - 0.05, 0)
        eventos.append(e)
    # Cada evento dura hasta que empieza el siguiente (sin huecos ni solapes).
    for i in range(len(eventos) - 1):
        eventos[i]["b"] = min(eventos[i]["b"], eventos[i + 1]["a"])

    dur = FIN_CRUDO + FIN_REF_DUR
    preparar_audio(eventos, dur, os.path.join(tmp, "voz.wav"), os.path.join(tmp, "mix.wav"))

    # Pre-render de gráficos.
    for e in eventos:
        if e["t"] == "top":
            imgs = [palabra_ancha(t, c, alto_max=190 if len(e["lineas"]) > 1 else 300) for t, c in e["lineas"]]
            e["img"] = imgs
        elif e["t"] == "rojo":
            e["img"] = npa(palabra_ancha(e["palabra"], BLANCO))
        elif e["t"] in ("cap", "cta"):
            e["chica_img"] = npa(linea_chica(e["chica"], 66))
            if e["t"] == "cta":
                e["grande_img"] = npa(estilizar(mascara_texto(e["grande"], f("ExtraBold", 210), -13), AMARILLO))
            else:
                e["pals"] = [(npa(i), w) for i, w in palabras_grandes(e["grande"])]
                p0 = e["palabras"][0]
                e["t_pals"] = [tw[p0 + k] if p0 + k < len(tw) else e["a"] for k in range(len(e["pals"]))]
                e["t_pals"][0] = min(e["t_pals"][0], e["a"] + 0.25)
        if e.get("pastilla"):
            e["pas_img"] = npa(pastilla(*e["pastilla"]))
        if e.get("emoji"):
            e["emo_img"] = npa(sticker(e["emoji"]))
    rec = rec_overlay()
    segm = Segmentador()

    dec = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", CRUDO, "-t", str(FIN_CRUDO), "-vf",
         "scale=1080:1920,eq=contrast=1.08:saturation=1.12:gamma=0.98,"
         "colorbalance=rs=.035:gs=.01:bs=-.035,unsharp=5:5:0.5",
         "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    fin = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", str(FIN_REF_INICIO), "-i", REFERENCIA, "-t", str(FIN_REF_DUR),
         "-vf", "scale=1080:1920,drawbox=x=740:y=1790:w=340:h=120:color=white:t=fill",
         "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", os.path.join(tmp, "mix.wav"), "-c:v", "libx264", "-preset", "slow",
         "-crf", "17", "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", SALIDA], stdin=subprocess.PIPE)

    n_total = int(dur * FPS)
    prev = None
    for n in range(n_total):
        t = n / FPS
        if t >= FIN_CRUDO:
            raw = fin.stdout.read(W * H * 3)
            if len(raw) < W * H * 3:
                break
            img = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32)
            tf = t - FIN_CRUDO
            if tf < 0.15:
                img = img * (tf / 0.15) + 255 * (1 - tf / 0.15)
            enc.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
            continue
        raw = dec.stdout.read(W * H * 3)
        if len(raw) < W * H * 3:
            raw = prev.astype(np.uint8).tobytes()
        img = np.frombuffer(raw, np.uint8).reshape(H, W, 3)

        tc = min([t - c for c in CORTES if t >= c] or [99])
        z, dy = zoom_en(t), 0.0
        if tc < 0.25:
            e_ = (1 - tc / 0.25) ** 2
            z += 0.3 * e_
            dy = -30 * e_
        base_u8 = transformar(img, z, dy)
        frame = base_u8.astype(np.float32)

        ev = next((e for e in eventos if e["a"] <= t < e["b"]), None)
        persona = None
        if ev and ev["t"] in ("top", "rojo"):
            persona = segm(base_u8, n)
            p3 = persona[..., None]
            if ev["t"] == "rojo":
                gris = frame.mean(axis=2, keepdims=True) / 255.0
                fondo = gris * np.array(ROJO, np.float32) * 1.05 + np.array(ROJO, np.float32) * 0.12
            else:  # duotono azul TGH para que el texto blanco/amarillo resalte
                gris = frame.mean(axis=2, keepdims=True) / 255.0
                fondo = gris * np.array(AZUL_TGH, np.float32) * 1.1 + np.array((10, 0, 60), np.float32)
            frame = frame * p3 + fondo * (1 - p3)

        if REC[0] <= t < REC[1]:
            gris = frame.mean(axis=2, keepdims=True)
            frame = np.repeat(gris, 3, axis=2)
            componer(frame, rec, W / 2, H / 2)
            if int(t * 2.5) % 2 == 0:
                cv2.circle(frame, (60 + 70, 290), 22, ROJO, -1)
            tcode = f"01:34:{37 + int(t - REC[0]):02d}:{int((t * FPS) % FPS):02d}"
            tim = Image.new("RGBA", (420, 60))
            ImageDraw.Draw(tim).text((0, 0), tcode, font=ImageFont.truetype(FONT_MONO, 44), fill=BLANCO)
            componer(frame, npa(tim), 60 + 40 + 210, 400)

        if ev:
            ts = t - ev["a"]
            if ev["t"] == "top":
                imgs = ev["img"]
                alto = sum(i.height for i in imgs) - 70 * (len(imgs) - 1)
                y = 40 + (H * 0.06 if len(imgs) == 1 else 0)
                for k, im in enumerate(imgs):
                    componer(frame, npa(im), W / 2, y + im.height / 2, pop(ts - k * 0.12, 0.18),
                             1.0 if ts >= k * 0.12 else 0.0, persona)
                    y += im.height - 70
            elif ev["t"] == "rojo":
                im = ev["img"]
                hh = im.shape[0] - 80
                cy = H * 0.17
                for k, al in ((-1, 0.35), (0, 1.0), (1, 0.35)):
                    componer(frame, im, W / 2 + (ts * 60 * k), cy + k * hh, 1.0, al, persona)
            elif ev["t"] == "cap":
                cy = H * 0.56
                ch = ev["chica_img"]
                componer(frame, ch, W / 2, cy - 110, pop(ts, 0.15), min(1, ts / 0.06))
                pals = ev["pals"]
                fu_esp = 30
                total = sum(w for _, w in pals) + fu_esp * (len(pals) - 1)
                escala = min(1.0, 1000 / total)
                x = W / 2 - total * escala / 2
                for (pi, w), tp in zip(pals, ev["t_pals"]):
                    if t >= tp:
                        componer(frame, pi, x + w * escala / 2, cy + 20, escala * pop(t - tp, 0.16))
                    x += (w + fu_esp) * escala
                if ev.get("pas_img") is not None and ts > 0.3:
                    componer(frame, ev["pas_img"], W / 2 + 180, cy + 175, pop(ts - 0.3))
                if ev.get("emo_img") is not None and ts > 0.15:
                    componer(frame, ev["emo_img"], W / 2 + 330, cy - 230, pop(ts - 0.15))
            elif ev["t"] == "cta":
                cy = H * 0.56
                componer(frame, ev["chica_img"], W / 2, cy - 150, pop(ts, 0.15))
                componer(frame, ev["grande_img"], W / 2, cy, pop(max(0, ts - 0.1)), 1.0 if ts > 0.1 else 0)
                if ts > 0.35:
                    componer(frame, ev["pas_img"], W / 2 + 190, cy + 160, pop(ts - 0.35))

        if tc < 0.12:  # flash blanco en el corte
            k = 1 - tc / 0.12
            frame = frame * (1 - 0.85 * k) + 255 * 0.85 * k
        prev = frame
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        if n % 90 == 0:
            print(f"  frame {n}/{n_total}", flush=True)
    dec.kill()
    fin.kill()
    enc.stdin.close()
    enc.wait()
    print("✔", SALIDA)


if __name__ == "__main__":
    main()

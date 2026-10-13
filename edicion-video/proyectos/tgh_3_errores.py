#!/usr/bin/env python3
"""Reel "3 errores en redes" — línea gráfica de la referencia TGH.

Una sola línea de tiempo de CAPAS (texto, imágenes, ajustes, audio) alimenta:
  1) el render final en MP4, y
  2) la exportación a After Effects (timeline.json + recursos), para que el
     editor reciba exactamente lo mismo como proyecto editable.

Estilo (sacado de la referencia): fondo real siempre; subtítulo en dos niveles
(Poppins SemiBold blanco + Poppins Bold grande, amarillo #FCFC00 con glow);
palabras grandes condensadas DETRÁS de la persona; fondo rojo con palabra
repetida x3; capturas con marco blanco arriba, detrás de la persona; stickers
con borde blanco; pastillas inclinadas; efecto cámara REC; flash blanco y zoom
en cada corte; tarjeta final TGH.

Uso:
  python3 tgh_3_errores.py crudo.mp4 referencia.mp4 transcripcion.json salida.mp4 modelo.tflite \
      [--voz Voz_limpia.wav] [--exportar-ae carpeta]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio_tgh as A  # noqa: E402
import graficos_tgh as G  # noqa: E402

W, H, FPS, SR = 1080, 1920, 30, 48000
POPPINS = "/usr/local/share/fonts/poppins/Poppins-{}.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
AMARILLO, BLANCO, AZUL_TGH, VERDE, ROJO = (252, 252, 0), (255, 255, 255), (59, 0, 239), (37, 208, 103), (240, 54, 53)

CORTES = [5.367, 10.833, 13.0, 16.0, 18.733, 20.933]
FIN_CRUDO = 23.933
FIN_REF_INICIO, FIN_REF_DUR = 26.0, 3.25
DURACION = FIN_CRUDO + FIN_REF_DUR
REC = (18.733, 19.75)
ANCLA = (W / 2, H * 0.36)  # punto de zoom (la cara)

TEXTO = [
    "Tres errores que hacen que tus redes se vean", "poco profesionales",
    "Puede que estés cometiendo estos tres errores.", "Error 1: Usar colores y estilos",
    "diferentes en cada publicación.", "Define tu línea gráfica.", "Error 2: Saturar tus diseños.",
    "Usa textos breves y", "claros para facilitar la lectura.", "Error 3:", "Publicar sin estrategia.",
    "Organiza tus contenidos con anticipación.", "¿Cometes alguno de estos errores?",
    "Coméntanos en los comentarios.",
]

# Guion. a/b = índice de palabra (int) o segundo (float).
GUION = [
    dict(t="top", a=0, b=2, lineas=[("3 ERRORES", BLANCO)]),
    dict(t="cap", a=2, b=9, chica="que hacen que tus", grande="*redes* se vean", palabras=6),
    dict(t="top", a=9, b=11, lineas=[("POCO", BLANCO), ("PROFESIONALES", AMARILLO)], sticker="😥"),
    dict(t="cap", a=11, b=15, chica="Puede que estés", grande="cometiendo", palabras=14),
    dict(t="cap", a=15, b=5.367, chica="estos", grande="*3* *errores*", palabras=16),
    dict(t="rojo", a=5.367, b=20, palabra="ERROR 1"),
    dict(t="cap", a=20, b=24, chica="Usar", grande="*colores* y *estilos*", palabras=21),
    dict(t="cap", a=24, b=28, chica="diferentes en", grande="cada publicación", palabras=26),
    dict(t="cap", a=28, b=10.833, chica="Define tu", grande="*línea* *gráfica*", palabras=30, solucion=True),
    dict(t="rojo", a=10.833, b=34, palabra="ERROR 2"),
    dict(t="top", a=34, b=35, lineas=[("SATURAR", BLANCO)]),
    dict(t="top", a=35, b=13.0, lineas=[("TUS DISEÑOS", AMARILLO)], sigue=True),
    dict(t="cap", a=13.0, b=42, chica="Usa textos", grande="*breves* y *claros*", palabras=39),
    dict(t="cap", a=42, b=16.0, chica="para facilitar", grande="la lectura", palabras=44, solucion=True),
    dict(t="rojo", a=16.0, b=48, palabra="ERROR 3"),
    dict(t="top", a=48, b=49, lineas=[("PUBLICAR", BLANCO)]),
    dict(t="top", a=49, b=18.733, lineas=[("SIN", BLANCO), ("ESTRATEGIA", AMARILLO)], sigue=True),
    dict(t="cap", a=51, b=54, chica="Organiza tus", grande="contenidos", palabras=53),
    dict(t="cap", a=54, b=20.933, chica="con", grande="*anticipación*", palabras=55, solucion=True),
    dict(t="cap", a=20.933, b=58, chica="¿Cometes", grande="alguno", palabras=57),
    dict(t="cap", a=58, b=61, chica="de estos", grande="*errores?*", palabras=60, sticker="🤔"),
    dict(t="cta", a=61, b=FIN_CRUDO, chica="Coméntanos", grande="¡AHORA!", pastilla="en los comentarios"),
]

# Capturas con marco blanco, arriba y detrás de la persona (como la referencia).
# (inicio, fin, [(archivo, cx, cy, retraso: segundos o índice de palabra)])
TARJETAS = [
    (20, 28, [("Captura_perfil_incoherente", 290, 470, 0.0), ("Captura_post_incoherente", 790, 470, 0.35)]),
    (28, 10.833, [("Captura_kit_marca", 290, 470, 0.0), ("Captura_perfil_coherente", 790, 470, 0.2)]),
    (37, 16.0, [("Captura_post_saturado", 290, 405, 0.0), ("Captura_post_claro", 790, 405, 41)]),
    (19.75, 20.933, [("Captura_calendario", 540, 380, 0.0)]),
]

INICIOS_ZOOM = [0, 1.05, 2.12, 3.36, 5.367, 6.3, 7.3, 9.32, 10.833, 11.9, 13.0, 14.18, 16.0, 17.02,
                18.733, 20.933, 22.58]
ZOOMS = [1.04, 1.12, 1.04, 1.16, 1.06, 1.0, 1.12, 1.18, 1.06, 1.0, 1.0, 1.12, 1.06, 1.0, 1.0, 1.1, 1.0]


# ================================================================ tipografía
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


def estilizar(mask, color, glow, pad=50):
    """Texto con sombra suave y, si es amarillo, glow (como la referencia)."""
    w, h = mask.width + pad * 2, mask.height + pad * 2
    full = Image.new("L", (w, h))
    full.paste(mask, (pad, pad))
    out = Image.new("RGBA", (w, h))
    sh = full.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(11)).point(lambda v: min(255, v * 0.8))
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), c) for c in (20, 12, 8)] + [sh]), (0, 7))
    if glow:
        g = full.filter(ImageFilter.GaussianBlur(9)).point(lambda v: v * 0.75)
        out.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), c) for c in AMARILLO] + [g]))
    out.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), c) for c in color] + [full]))
    return out


PESOS = {"Poppins-SemiBold": "SemiBold", "Poppins-Bold": "Bold", "Poppins-ExtraBold": "ExtraBold"}


def render_texto(c):
    """Imagen RGBA de una capa de texto; el centro de la imagen = centro de la tinta."""
    fu = f(PESOS[c["fuente"]], c["tam"])
    m = mascara_texto(c["texto"], fu, c["tracking"] / 1000 * c["tam"])
    sx, sy = c["escala_base"]
    if (sx, sy) != (1, 1):
        m = m.resize((max(1, int(m.width * sx)), max(1, int(m.height * sy))), Image.LANCZOS)
    return estilizar(m, tuple(c["color"]), c["glow"])


def ancho_avance(txt, fuente, tam, tracking):
    fu = f(PESOS[fuente], tam)
    return sum(fu.getlength(ch) for ch in txt) + tracking / 1000 * tam * (len(txt) - 1)


# ================================================================ animación
def kf_pop(t0, dur=0.2, desde=60):
    """Escala en % (factor sobre la escala base): 60 → 108 → 100."""
    return [(t0, desde), (t0 + dur * 0.55, 108), (t0 + dur, 100)]


def kf_aparece(t0, fin, entrada=0.06, salida=0.0):
    k = [(t0, 0), (t0 + entrada, 100)]
    if salida:
        k += [(fin - salida, 100), (fin, 0)]
    return k


def evaluar(keys, t, defecto):
    if not keys:
        return defecto
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            x = (t - t0) / (t1 - t0) if t1 > t0 else 1
            if isinstance(v0, (list, tuple)):
                return [a + (b - a) * x for a, b in zip(v0, v1)]
            return v0 + (v1 - v0) * x
    return keys[-1][1]


def claves_zoom():
    """Keyframes de la toma: [(t, escala, dy)] — zoom por frase + latigazo en cada corte."""
    keys = []
    for i, s in enumerate(INICIOS_ZOOM):
        e = INICIOS_ZOOM[i + 1] if i + 1 < len(INICIOS_ZOOM) else FIN_CRUDO
        z = ZOOMS[i]
        if any(abs(s - c) < 1e-3 for c in CORTES):
            keys += [(s, z + 0.30, -30.0), (s + 2 / FPS, z + 0.161, -16.1), (s + 0.25, z + 0.003, 0.0)]
        else:
            keys.append((s, z, 0.0))
        keys.append((e - 1 / FPS, z + 0.012 * (e - s), 0.0))
    return keys


def evaluar_zoom(keys, t):
    z = evaluar([(k[0], k[1]) for k in keys], t, 1.0)
    dy = evaluar([(k[0], k[2]) for k in keys], t, 0.0)
    return z, dy


# ============================================================ transcripción
def tiempos_palabras(audio16k, transcripcion):
    bloques = json.load(open(transcripcion))
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


# ============================================================ línea de tiempo
def construir_timeline(tw):
    """Devuelve (eventos, capas). Cada capa tiene grupo: fondo_ajuste, detras, ajuste_global, frente, hud, flash."""
    def seg(x):
        return tw[x] if isinstance(x, int) else x
    ev = []
    for e in GUION:
        e = dict(e, a=seg(e["a"]), b=seg(e["b"]))
        if e["t"] in ("top", "cta", "rojo"):
            e["a"] = max(e["a"] - 0.05, 0)
        ev.append(e)
    for i in range(len(ev) - 1):
        ev[i]["b"] = min(ev[i]["b"], ev[i + 1]["a"])

    capas = []

    def texto(nombre, grupo, txt, fuente, tam, color, tracking, cx, cy, a, b, escala_base=(1, 1), glow=None,
              kf_escala=None, kf_opacidad=None, kf_pos=None, opacidad=100):
        base, k = nombre, 2
        while any(c["nombre"] == nombre for c in capas):
            nombre, k = f"{base}_{k}", k + 1
        capas.append(dict(tipo="texto", nombre=nombre, grupo=grupo, texto=txt, fuente=fuente, tam=tam,
                          color=list(color), tracking=round(tracking, 1),
                          glow=(tuple(color) == AMARILLO) if glow is None else glow,
                          escala_base=[round(escala_base[0], 4), round(escala_base[1], 4)],
                          cx=round(cx, 1), cy=round(cy, 1), inicio=round(a, 3), fin=round(b, 3), opacidad=opacidad,
                          kf_escala=kf_escala or [], kf_opacidad=kf_opacidad or [], kf_pos=kf_pos or []))

    def imagen(nombre, grupo, archivo, cx, cy, a, b, kf_escala=None, kf_opacidad=None, kf_pos=None, expr_opacidad=None):
        capas.append(dict(tipo="imagen", nombre=nombre, grupo=grupo, archivo=archivo, cx=round(cx, 1), cy=round(cy, 1),
                          inicio=round(a, 3), fin=round(b, 3), kf_escala=kf_escala or [], kf_opacidad=kf_opacidad or [],
                          kf_pos=kf_pos or [], expr_opacidad=expr_opacidad))

    def palabra_ancha(txt, alto_max):
        """Palabra condensada a todo el ancho (como PERDISTE / CALIDAD): Poppins Bold 260 escalado."""
        tam, track = 260, -38.5
        m = mascara_texto(txt, f("Bold", tam), track / 1000 * tam)
        sy = min(alto_max, 230 if len(txt) > 9 else 260) / m.height
        sx = min(1010, m.width * sy * 0.86) / m.width
        return tam, track, (sx, sy), m.height * sy

    for e in ev:
        a, b = e["a"], e["b"]
        if e["t"] == "top":
            lineas = e["lineas"]
            y = 40 + (H * 0.06 if len(lineas) == 1 else 0)
            for k, (txt, color) in enumerate(lineas):
                tam, track, esc, alto = palabra_ancha(txt, 190 if len(lineas) > 1 else 300)
                h_img = alto + 100
                texto(f"Grande_{txt}", "detras", txt, "Poppins-Bold", tam, color, track, W / 2, y + h_img / 2,
                      a + k * 0.12, b, esc, kf_escala=kf_pop(a + k * 0.12, 0.18))
                y += h_img - 70
            if e.get("sticker"):
                imagen("Sticker_triste", "frente", "Sticker_triste.png", W / 2 + 250, H * 0.6, a + 0.2, b,
                       kf_escala=kf_pop(a + 0.2))
        elif e["t"] == "rojo":
            tam, track, esc, alto = palabra_ancha(e["palabra"], 300)
            hh = alto + 100 - 80
            dur = b - a
            for k, op, nom in ((-1, 35, "arriba"), (0, 100, "centro"), (1, 35, "abajo")):
                cy = H * 0.17 + k * hh
                texto(f"{e['palabra']}_{nom}", "detras", e["palabra"], "Poppins-Bold", tam, BLANCO, track, W / 2, cy,
                      a, b, esc, opacidad=op, kf_pos=[(a, [W / 2, cy]), (b, [W / 2 + 60 * k * dur, cy])])
        elif e["t"] == "cap":
            cy = H * 0.56
            texto(f"Sub_{e['chica']}", "frente", e["chica"], "Poppins-SemiBold", 66, BLANCO, -50, W / 2, cy - 110, a, b,
                  kf_escala=kf_pop(a, 0.15), kf_opacidad=kf_aparece(a, b))
            pals = [(p.strip("*"), p.startswith("*")) for p in e["grande"].split()]
            anchos = [ancho_avance(p, "Poppins-Bold", 150, -60) for p, _ in pals]
            total = sum(anchos) + 30 * (len(pals) - 1)
            esc = min(1.0, 1000 / total)
            x = W / 2 - total * esc / 2
            p0 = e["palabras"]
            for k, ((p, am), w_) in enumerate(zip(pals, anchos)):
                tp = tw[p0 + k] if p0 + k < len(tw) else a
                if k == 0:
                    tp = min(tp, a + 0.25)
                tp = min(max(tp, a), b - 0.1)
                texto(f"Palabra_{p}", "frente", p, "Poppins-Bold", 150, AMARILLO if am else BLANCO, -60,
                      x + w_ * esc / 2, cy + 20, tp, b, (esc, esc), kf_escala=kf_pop(tp, 0.16))
                x += (w_ + 30) * esc
            if e.get("solucion"):
                imagen("Pastilla_Solucion", "frente", "Pastilla_Solucion.png", W / 2 + 190, cy + 185, a + 0.3, b,
                       kf_escala=kf_pop(a + 0.3))
            if e.get("sticker"):
                imagen("Sticker_pensando", "frente", "Sticker_pensando.png", W / 2 + 330, cy - 250, a + 0.15, b,
                       kf_escala=kf_pop(a + 0.15))
        elif e["t"] == "cta":
            texto("CTA_Comentanos", "frente", e["chica"], "Poppins-SemiBold", 70, BLANCO, -50, W / 2, 205, a, b,
                  kf_escala=kf_pop(a, 0.15))
            texto("CTA_Ahora", "frente", e["grande"], "Poppins-ExtraBold", 210, AMARILLO, -62, W / 2, 360, a + 0.1, b,
                  kf_escala=kf_pop(a + 0.1))
            imagen("Pastilla_Comentarios", "frente", "Pastilla_Comentarios.png", W / 2 + 200, 505, a + 0.35, b,
                   kf_escala=kf_pop(a + 0.35))
            imagen("Sticker_TGH", "frente", "Sticker_TGH.png", W / 2 + 300, H * 0.72, a + 0.55, b,
                   kf_escala=kf_pop(a + 0.55))

    # Degradado superior detrás de la persona cuando hay palabras grandes / CTA.
    rangos = []
    for e in ev:
        if e["t"] in ("top", "cta"):
            if rangos and abs(rangos[-1][1] - e["a"]) < 0.02:
                rangos[-1][1] = e["b"]
            else:
                rangos.append([e["a"], e["b"]])
    for k, (a, b) in enumerate(rangos):
        imagen(f"Degradado_superior_{k + 1}", "fondo_ajuste", "Degradado_superior.png", W / 2, H / 2, a, b,
               kf_opacidad=kf_aparece(a, b, 0.15, 0.15))
    for e in ev:
        if e["t"] == "rojo":
            capas.append(dict(tipo="tinte", nombre=f"Fondo_rojo_{e['palabra'].replace(' ', '_')}", grupo="fondo_ajuste",
                              inicio=round(e["a"], 3), fin=round(e["b"], 3),
                              negro=[round(c * 0.12, 2) for c in ROJO], blanco=[min(255, round(c * 1.17, 2)) for c in ROJO]))

    # Capturas (tarjetas) detrás de la persona.
    for a, b, piezas in TARJETAS:
        a, b = seg(a), seg(b)
        for archivo, cx, cy, ret in piezas:
            t0 = seg(ret) if isinstance(ret, int) else a + ret
            imagen(archivo, "detras", archivo + ".png", cx, cy, t0, b, kf_escala=[(t0, 94), (t0 + 0.25, 100)],
                   kf_pos=[(t0, [cx, cy - 50]), (t0 + 0.25, [cx, cy])], kf_opacidad=kf_aparece(t0, b, 0.2, 0.15))

    # Efecto cámara REC.
    capas.append(dict(tipo="byn", nombre="REC_blanco_y_negro", grupo="ajuste_global", inicio=REC[0], fin=REC[1]))
    imagen("REC_interfaz", "hud", "REC_interfaz.png", W / 2, H / 2, REC[0], REC[1])
    imagen("REC_punto", "hud", "REC_punto.png", 130, 290, REC[0], REC[1], expr_opacidad="(Math.floor(time*2.5)%2==0)?100:0")
    capas.append(dict(tipo="timecode", nombre="REC_codigo_tiempo", grupo="hud", inicio=REC[0], fin=REC[1],
                      x=100, y=420, tam=44, fuente="DejaVuSansMono",
                      expr=f"var s=37+Math.floor(time-{REC[0]}); var fr=Math.floor((time*30)%30); "
                           "'01:34:'+(s<10?'0':'')+s+':'+(fr<10?'0':'')+fr"))
    # Flash blanco en cada corte y al entrar a la tarjeta final.
    kf = []
    for c in CORTES:
        kf += [(round(c - 1 / FPS, 4), 0), (c, 85), (round(c + 0.12, 4), 0)]
    kf += [(round(FIN_CRUDO - 1 / FPS, 4), 0), (FIN_CRUDO, 100), (round(FIN_CRUDO + 0.15, 4), 0)]
    capas.append(dict(tipo="flash", nombre="Flash_blanco", grupo="flash", inicio=0, fin=round(DURACION, 3), kf_opacidad=kf))
    return ev, capas


# =================================================================== audio
def guardar_wav(ruta, x, bits=16):
    x = np.clip(np.asarray(x, np.float32), -1, 1)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    o = wave.open(ruta, "wb")
    o.setnchannels(2)
    o.setframerate(SR)
    if bits == 24:
        v = np.round(x * 8388607).astype(np.int32).reshape(-1)
        o.setsampwidth(3)
        o.writeframes(np.stack([v & 255, (v >> 8) & 255, (v >> 16) & 255], 1).astype(np.uint8).tobytes())
    else:
        o.setsampwidth(2)
        o.writeframes((x * 32767).astype(np.int16).tobytes())
    o.close()


def leer_wav(ruta):
    w = wave.open(ruta)
    n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        v = (b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16))
        v = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float32) / 8388608
    elif sw == 4:
        v = np.frombuffer(raw, np.int32).astype(np.float32) / 2147483648
    else:
        v = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    v = v.reshape(-1, ch)
    if w.getframerate() != SR:
        raise SystemExit(f"{ruta}: se esperaba {SR} Hz")
    return np.repeat(v, 2, 1) if ch == 1 else v[:, :2]


def lista_sonidos(ev, capas):
    """SFX (mini hooks auditivos): [(nombre, t, señal, volumen)]."""
    S = []
    for k, c in enumerate(CORTES):
        pan = -0.8 if k % 2 == 0 else 0.8
        S.append(("whoosh_corte", c - 0.28, A.whoosh(0.5, pan, -pan), 0.5))
    for e in ev:
        a = e["a"]
        if e["t"] == "top":
            S.append(("swish_palabra", a, A.swish(), 0.75))
            if e.get("sigue"):
                S.append(("pop_palabra", a, A.pop(0.8), 0.45))
            else:
                S.append(("impacto", a, A.impacto(), 0.5))
        elif e["t"] == "rojo":
            S.append(("riser_error", a - 0.7, A.riser(0.7), 0.45))
            S.append(("impacto_error", a, A.impacto(), 0.65))
            S.append(("buzz_error", a + 0.05, A.error_buzz(), 0.5))
        elif e["t"] == "cta":
            S.append(("riser_cta", a - 0.6, A.riser(0.6), 0.45))
            S.append(("impacto_cta", a, A.impacto(), 0.55))
            S.append(("exito_cta", a + 0.35, A.exito(), 0.55))
    k = 0
    for c in capas:
        nom = c["nombre"]
        if c["tipo"] == "texto" and nom.startswith("Sub_"):
            S.append(("tick_subtitulo", c["inicio"], A.tick(), 0.45))
        elif c["tipo"] == "texto" and nom.startswith("Palabra_"):
            k += 1
            S.append(("pop_subtitulo", c["inicio"], A.pop(0.9 + 0.1 * (k % 3)), 0.22))
        elif c["tipo"] == "imagen" and nom == "Pastilla_Solucion":
            S.append(("exito_solucion", c["inicio"], A.exito(), 0.5))
        elif c["tipo"] == "imagen" and nom.startswith("Sticker"):
            S.append(("pop_sticker", c["inicio"], A.pop(1.5), 0.4))
        elif c["tipo"] == "imagen" and nom.startswith("Captura"):
            S.append(("whoosh_captura", c["inicio"] - 0.05, A.whoosh(0.35, 0.3, -0.3), 0.3))
            S.append(("pop_captura", c["inicio"] + 0.12, A.pop(1.15), 0.35))
    S.append(("obturador_rec", REC[0], A.obturador(), 0.8))
    S.append(("beep_rec", REC[0] + 0.15, A.campana([93], dur=0.25, vol=0.25), 1.0))
    S.append(("platillo_reverso", FIN_CRUDO - 1.0, A.platillo_reverso(1.0), 0.55))
    S.append(("sting_logo", FIN_CRUDO + 0.05, A.sting_logo(), 0.65))
    return sorted(S, key=lambda s: s[1])


def preparar_audio(crudo, voz_limpia, ev, sonidos, tmp):
    """Mezcla: voz + música original con ducking + SFX. Devuelve los stems."""
    if voz_limpia:
        voz = leer_wav(voz_limpia)
    else:
        ruta = os.path.join(tmp, "voz.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", crudo, "-af",
                        "highpass=f=80,afftdn=nf=-28,acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,"
                        "loudnorm=I=-16:TP=-1.5:LRA=9", "-ac", "2", "-ar", str(SR), ruta], check=True)
        voz = leer_wav(ruta)
    voz = voz[:int(FIN_CRUDO * SR)]
    n = int(DURACION * SR)
    voz_full = np.zeros((n, 2), np.float32)
    voz_full[:len(voz)] = voz

    rojos = [(e["a"], e["b"]) for e in ev if e["t"] == "rojo"]
    musica = A.musica(DURACION + 0.5, filtrados=rojos, radio=[REC], cortes=CORTES + [FIN_CRUDO], fin_beat=FIN_CRUDO)[:n]
    env = np.abs(voz_full).mean(1)
    k = int(0.08 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    env = np.clip(env / (np.percentile(env[:len(voz)], 95) + 1e-6), 0, 1)
    k = int(0.25 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    gan = 0.28 * (1 - 0.5 * env)
    gan[int(FIN_CRUDO * SR):] = 0.42
    musica_duck = musica * gan[:, None]

    sfx = np.zeros((n, 2), np.float32)
    pistas = []
    for nombre, t0, s, vol in sonidos:
        i = max(0, int(round(t0 * SR)))
        recorte = max(0, -int(round(t0 * SR)))
        m = min(len(s) - recorte, n - i)
        if m > 0:
            sfx[i:i + m] += s[recorte:recorte + m] * vol
            pistas.append((nombre, t0, s * vol))
    mezcla = A._fx(voz_full + musica_duck + sfx, A.Pedalboard([A.Compressor(-10, 2, 5, 100), A.Limiter(-1.5)]))
    return dict(voz=voz_full, musica=musica * 0.28, musica_duck=musica_duck, sfx=sfx, pistas=pistas, mezcla=mezcla)


# ============================================================ segmentación
def mascaras_persona(crudo, modelo, ruta_cache):
    """Máscara de la persona por frame (540x960, uint8). Se guarda en caché."""
    if os.path.exists(ruta_cache):
        return limpiar_mascaras(np.load(ruta_cache))
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=modelo), output_confidence_masks=True,
        running_mode=vision.RunningMode.VIDEO))
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", crudo, "-t", str(FIN_CRUDO), "-vf", "scale=540:960",
                            "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out, prev, n = [], None, 0
    while True:
        raw = dec.stdout.read(540 * 960 * 3)
        if len(raw) < 540 * 960 * 3:
            break
        img = np.frombuffer(raw, np.uint8).reshape(960, 540, 3)
        r = seg.segment_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(img)),
                                  int(n * 1000 / FPS))
        m = 1.0 - r.confidence_masks[0].numpy_view()
        m = np.clip((cv2.GaussianBlur(m, (0, 0), 1.2) - 0.42) / 0.38, 0, 1)
        if prev is not None:
            m = 0.65 * m + 0.35 * prev
        prev = m
        out.append((m * 255).astype(np.uint8))
        n += 1
    arr = np.stack(out)
    np.save(ruta_cache, arr)
    return limpiar_mascaras(arr)


def limpiar_mascaras(arr):
    """Deja solo la silueta principal (quita el reloj de pared, etc.) y, en la toma
    con laptop (cámara fija), conserva la laptop y la mesa en primer plano."""
    arr = np.array(arr)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    for n in range(len(arr)):
        m = arr[n]
        _, lab, st, _ = cv2.connectedComponentsWithStats((m > 128).astype(np.uint8))
        if len(st) > 2:
            mayor = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            m = (m * cv2.dilate((lab == mayor).astype(np.uint8), k)).astype(np.uint8)
        if CORTES[3] <= n / FPS < CORTES[4]:
            rampa = np.clip((np.arange(960) - 548) / 8.0, 0, 1)[:, None]
            m = np.maximum(m, (rampa * 255).astype(np.uint8))
        arr[n] = m
    return arr


# ================================================================== render
def transformar(img, z, dy):
    ax, ay = ANCLA
    M = np.float32([[z, 0, ax - z * ax], [0, z, ay + dy - z * ay]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def componer(frame, ov, cx, cy, escala=1.0, alpha=1.0):
    if escala <= 0.01 or alpha <= 0.001:
        return
    if abs(escala - 1.0) > 1e-3:
        ov = cv2.resize(ov, None, fx=escala, fy=escala, interpolation=cv2.INTER_LINEAR)
    h, w = ov.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    o = ov[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = o[..., 3:4] / 255.0 * alpha
    reg = frame[fy0:fy1, fx0:fx1]
    reg[:] = reg * (1 - a) + o[..., :3] * a


def opacidad_expr(expr, t):
    if expr == "(Math.floor(time*2.5)%2==0)?100:0":
        return 100 if int(np.floor(t * 2.5)) % 2 == 0 else 0
    raise ValueError(expr)


def dibujar_capa(frame, c, t, imagenes):
    esc = evaluar(c["kf_escala"], t, 100) / 100
    op = c.get("opacidad", 100) / 100 * evaluar(c["kf_opacidad"], t, 100) / 100
    if c.get("expr_opacidad"):
        op *= opacidad_expr(c["expr_opacidad"], t) / 100
    cx, cy = evaluar(c["kf_pos"], t, [c["cx"], c["cy"]])
    componer(frame, imagenes[c["archivo"][:-4] if c["tipo"] == "imagen" else c["nombre"]], cx, cy, esc, op)


def rec_interfaz():
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
    return im


def rec_punto():
    im = Image.new("RGBA", (60, 60))
    ImageDraw.Draw(im).ellipse((8, 8, 52, 52), fill=ROJO + (255,))
    return im


def recursos_graficos(dir_g, cierre_png):
    """Genera todos los PNG de la línea gráfica (también van al paquete de AE)."""
    os.makedirs(dir_g, exist_ok=True)
    piezas = {
        "Captura_perfil_incoherente": G.tarjeta(G.captura_perfil("caos"), False),
        "Captura_post_incoherente": G.tarjeta(G.captura_post(G.post(450, "caos", 3),
                                                             ["¡¡OFERTA!! compra ya!!!", "#promo #sale #nuevo"])),
        "Captura_kit_marca": G.tarjeta(G.captura_kit_marca(), True),
        "Captura_perfil_coherente": G.tarjeta(G.captura_perfil("marca"), True),
        "Captura_post_saturado": G.tarjeta(G.captura_post(G.cuadro_saturado(),
                                                          ["Escríbenos!!! envíos a todo", "el país #oferta #promo"]), False),
        "Captura_post_claro": G.tarjeta(G.captura_post(G.cuadro_claro(), ["3 tips para vender más", "en redes sociales."],
                                                       avatar=AZUL_TGH), True),
        "Captura_calendario": G.tarjeta(G.captura_calendario(), True),
        "Sticker_triste": G.sticker_emoji("😥", 200, 8),
        "Sticker_pensando": G.sticker_emoji("🤔", 170, -6),
        "Sticker_TGH": G.sticker_robot(cierre_png),
        "Pastilla_Solucion": G.pastilla("Solución", VERDE, 50, -7, "check"),
        "Pastilla_Comentarios": G.pastilla("en los comentarios", AZUL_TGH, 46, -7),
        "Degradado_superior": G.escrim(),
        "REC_interfaz": rec_interfaz(),
        "REC_punto": rec_punto(),
    }
    for k, im in piezas.items():
        im.save(os.path.join(dir_g, k + ".png"))
    return {k: G.npa(v) for k, v in piezas.items()}


def tinte(img, c):
    lum = (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114)[..., None] / 255
    negro, blanco = np.array(c["negro"], np.float32), np.array(c["blanco"], np.float32)
    return negro + (blanco - negro) * lum


def render(args, capas, audio, mascaras, imagenes, tmp):
    keys = claves_zoom()
    for c in capas:
        if c["tipo"] == "texto":
            imagenes[c["nombre"]] = G.npa(render_texto(c))
    mix = os.path.join(tmp, "mezcla.wav")
    guardar_wav(mix, audio["mezcla"])

    grado = ("scale=1080:1920,eq=contrast=1.08:saturation=1.12:gamma=0.98,"
             "colorbalance=rs=.035:gs=.01:bs=-.035,unsharp=5:5:0.5")
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", args.crudo, "-t", str(FIN_CRUDO), "-vf", grado,
                            "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    fin = subprocess.Popen(["ffmpeg", "-v", "error", "-i", args.cierre, "-r", str(FPS), "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", mix, "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", "-shortest", args.salida], stdin=subprocess.PIPE)

    grupos = {g: [c for c in capas if c["grupo"] == g] for g in
              ("fondo_ajuste", "detras", "ajuste_global", "frente", "hud", "flash")}
    flash = grupos["flash"][0]
    fuente_tc = ImageFont.truetype(FONT_MONO, 44)
    prev = None
    total = int(round(DURACION * FPS))
    for n in range(total):
        t = n / FPS

        def activas(g):
            return [c for c in grupos[g] if c["inicio"] <= t < c["fin"]]
        if t >= FIN_CRUDO:
            raw = fin.stdout.read(W * H * 3)
            if len(raw) < W * H * 3:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32)
        else:
            raw = dec.stdout.read(W * H * 3)
            if len(raw) < W * H * 3:
                raw = prev
            prev = raw
            img = np.frombuffer(raw, np.uint8).reshape(H, W, 3)
            z, dy = evaluar_zoom(keys, t)
            fondo = transformar(img, z, dy).astype(np.float32)
            atras = activas("fondo_ajuste") + activas("detras")
            if atras:
                m = cv2.resize(mascaras[min(n, len(mascaras) - 1)].astype(np.float32) / 255, (W, H))
                m = np.clip(transformar(m, z, dy), 0, 1)[..., None]
                capa = fondo.copy()
                for c in atras:
                    if c["tipo"] == "tinte":
                        capa = tinte(capa, c)
                    else:
                        dibujar_capa(capa, c, t, imagenes)
                frame = fondo * m + capa * (1 - m)
            else:
                frame = fondo
            if activas("ajuste_global"):
                frame = np.repeat(frame.mean(axis=2, keepdims=True), 3, axis=2)
            for c in activas("frente"):
                dibujar_capa(frame, c, t, imagenes)
            for c in activas("hud"):
                if c["tipo"] == "timecode":
                    s = 37 + int(np.floor(t - REC[0]))
                    fr = int(np.floor((t * 30) % 30))
                    tim = Image.new("RGBA", (420, 60))
                    ImageDraw.Draw(tim).text((0, 0), f"01:34:{s:02d}:{fr:02d}", font=fuente_tc, fill=BLANCO)
                    componer(frame, G.npa(tim), c["x"] + 210, c["y"] - 14)
                else:
                    dibujar_capa(frame, c, t, imagenes)
        op = evaluar(flash["kf_opacidad"], t, 0) / 100
        if op > 0:
            frame = frame * (1 - op) + 255 * op
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        if n % 150 == 0:
            print(f"  frame {n}/{total}", flush=True)
    dec.kill()
    fin.kill()
    enc.stdin.close()
    enc.wait()


# ========================================================= export a After Effects
def exportar_ae(args, capas, audio, mascaras, dir_g):
    """Carpeta con recursos + timeline.json (lo consume generar_ae.py para crear el .jsx)."""
    raiz = args.exportar_ae
    dirs = {k: os.path.join(raiz, v) for k, v in dict(footage="02_Footage", audio="03_Audio", sfx="03_Audio/SFX",
                                                      graficos="04_Graficos", mates="05_Mates",
                                                      fuentes="06_Fuentes", ref="07_Referencia").items()}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    grado = "eq=contrast=1.08:saturation=1.12:gamma=0.98,colorbalance=rs=.035:gs=.01:bs=-.035,unsharp=5:5:0.5"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", args.crudo, "-t", str(FIN_CRUDO), "-vf", grado, "-an",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    os.path.join(dirs["footage"], "Toma_con_color.mp4")], check=True)
    shutil.copy(args.crudo, os.path.join(dirs["footage"], "Toma_original.mp4"))
    shutil.copy(args.cierre, os.path.join(dirs["footage"], "Cierre_TGH.mp4"))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "8",
                            "-pix_fmt", "yuv420p", os.path.join(dirs["mates"], "Mate_persona.mp4")], stdin=subprocess.PIPE)
    for m in mascaras:
        enc.stdin.write(cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR).tobytes())
    enc.stdin.close()
    enc.wait()
    for archivo in os.listdir(dir_g):
        shutil.copy(os.path.join(dir_g, archivo), dirs["graficos"])
    guardar_wav(os.path.join(dirs["audio"], "Voz_limpia.wav"), audio["voz"], 24)
    guardar_wav(os.path.join(dirs["audio"], "Musica_TGH_con_ducking.wav"), audio["musica_duck"], 24)
    guardar_wav(os.path.join(dirs["audio"], "Musica_TGH_sin_ducking.wav"), audio["musica"], 24)
    guardar_wav(os.path.join(dirs["audio"], "SFX_mezcla.wav"), audio["sfx"], 24)
    guardar_wav(os.path.join(dirs["audio"], "Mezcla_final.wav"), audio["mezcla"], 24)
    sfx = []
    for k, (nombre, t0, s) in enumerate(audio["pistas"]):
        arch = f"SFX_{k + 1:02d}_{nombre}_{max(t0, 0):05.2f}s.wav"
        guardar_wav(os.path.join(dirs["sfx"], arch), s, 24)
        sfx.append(dict(archivo="03_Audio/SFX/" + arch, nombre=nombre, inicio=round(t0, 3)))
    for peso in ("SemiBold", "Bold", "ExtraBold"):
        shutil.copy(POPPINS.format(peso), dirs["fuentes"])
    shutil.copy(FONT_MONO, dirs["fuentes"])
    for lic in (os.path.join(os.path.dirname(POPPINS), "OFL.txt"),):
        if os.path.exists(lic):
            shutil.copy(lic, os.path.join(dirs["fuentes"], "Poppins_OFL.txt"))
    shutil.copy(args.salida, os.path.join(dirs["ref"], "Render_final_referencia.mp4"))

    timeline = dict(
        proyecto="TGH_3_errores_en_redes", ancho=W, alto=H, fps=FPS, duracion=round(DURACION, 3),
        fin_toma=FIN_CRUDO, ancla_zoom=[ANCLA[0], round(ANCLA[1], 2)],
        zoom=[dict(t=round(t, 4), escala=round(z * 100, 3), dy=round(dy, 2)) for t, z, dy in claves_zoom()],
        footage=dict(toma="02_Footage/Toma_con_color.mp4", original="02_Footage/Toma_original.mp4",
                     mate="05_Mates/Mate_persona.mp4", cierre="02_Footage/Cierre_TGH.mp4"),
        audio=dict(voz="03_Audio/Voz_limpia.wav", musica="03_Audio/Musica_TGH_con_ducking.wav",
                   musica_sin_ducking="03_Audio/Musica_TGH_sin_ducking.wav", sfx_mezcla="03_Audio/SFX_mezcla.wav",
                   mezcla="03_Audio/Mezcla_final.wav", sfx=sfx),
        colores=dict(amarillo=AMARILLO, blanco=BLANCO, azul_tgh=AZUL_TGH, verde=VERDE, rojo=ROJO),
        estilo_texto=dict(sombra=dict(color=[20, 12, 8], opacidad_pct=80, distancia=7, direccion=180, suavidad=22),
                          glow_amarillo=dict(radio=18, intensidad=0.75, umbral_pct=60)),
        capas=[dict(c, archivo=("04_Graficos/" + c["archivo"]) if c.get("archivo") else None) for c in capas],
        orden_grupos=["fondo_ajuste", "detras", "persona", "ajuste_global", "frente", "hud", "flash"],
    )
    with open(os.path.join(raiz, "timeline.json"), "w", encoding="utf-8") as fh:
        json.dump(timeline, fh, ensure_ascii=False, indent=1)
    print("✔ exportación AE:", raiz)


# ==================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("crudo")
    ap.add_argument("referencia")
    ap.add_argument("transcripcion")
    ap.add_argument("salida")
    ap.add_argument("modelo")
    ap.add_argument("--voz", help="Voz ya limpia (wav 48 kHz); si no, se limpia con ffmpeg.")
    ap.add_argument("--exportar-ae", help="Carpeta donde exportar recursos + timeline.json para After Effects.")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="reel_")
    a16 = os.path.join(tmp, "a16k.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", args.crudo, "-ac", "1", "-ar", "16000", a16], check=True)
    tw = tiempos_palabras(a16, args.transcripcion)
    ev, capas = construir_timeline(tw)

    # Tarjeta final de la referencia (se tapa la marca de agua de clideo.com).
    args.cierre = os.path.join(tmp, "Cierre_TGH.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(FIN_REF_INICIO), "-i", args.referencia,
                    "-t", str(FIN_REF_DUR), "-vf", "scale=1080:1920,drawbox=x=740:y=1790:w=340:h=120:color=white:t=fill",
                    "-an", "-r", str(FPS), "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", args.cierre], check=True)
    cierre_png = os.path.join(tmp, "cierre.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.0", "-i", args.cierre, "-frames:v", "1", cierre_png], check=True)

    dir_g = os.path.join(tmp, "graficos")
    imagenes = recursos_graficos(dir_g, cierre_png)
    print("audio…", flush=True)
    audio = preparar_audio(args.crudo, args.voz, ev, lista_sonidos(ev, capas), tmp)
    print("máscaras…", flush=True)
    cache = os.path.join(os.path.dirname(os.path.abspath(args.salida)), "mascaras_cache.npy")
    mascaras = mascaras_persona(args.crudo, args.modelo, cache)
    print("render…", flush=True)
    render(args, capas, audio, mascaras, imagenes, tmp)
    print("✔", args.salida)
    if args.exportar_ae:
        exportar_ae(args, capas, audio, mascaras, dir_g)


if __name__ == "__main__":
    main()

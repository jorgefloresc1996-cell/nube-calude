#!/usr/bin/env python3
"""Limpieza y masterizado de VOZ para reels (Instagram / TikTok).

Cadena (todo sin cambiar la duración ni desfasar el audio respecto al video):
  1. Extracción a 48 kHz (acepta video o audio) y suma a mono.
  2. Reconstrucción de picos recortados (declipping por consistencia + dispersión STFT).
     Solo actúa si detecta la "acumulación" típica de un recorte duro en el histograma.
  3. Paso alto 80 Hz (24 dB/oct, fase cero) + recorte suave de "barro" (~320 Hz).
  4. Compresor de voz 3:1 (ataque 8 ms, release 100 ms) ADAPTATIVO: mide el LRA del crudo;
     si ya viene comprimido (LRA < 4 LU) solo controla picos, porque comprimir de nuevo
     levanta el ruido entre palabras (medido: DNSMOS OVRL -0.25 con 2 dB de GR extra).
  5. Realce de presencia (~4 kHz) y shelf de aire (~11 kHz).
  6. Reducción de ruido con IA: DeepFilterNet 3 (binario `deep-filter`) + PROTECCIÓN DE VOZ.
     Medido en español: DFN a pleno se "come" vocales y erres ("Tres errores", "Error 1",
     "redes" -> hasta -27 dB) y Whisper pasa de 4.6 % a 18-20 % de WER. Por eso en cada
     banda de frecuencia con voz se limita lo que DFN puede quitar (natural: 6 dB) usando DFN
     como máscara sobre la señal original; en pausas actúa a pleno. Respaldo: noisereduce / afftdn.
  7. De-esser: compresión dinámica SOLO de la banda 5.5-9 kHz.
  8. Expansor suave en pausas (1:2, rango limitado, con hold y look-ahead: no corta colas).
  9. Normalización a -16 LUFS integrados (medidos sobre el archivo tal como se entrega,
     mono o estéreo) + limitador true-peak (<= -1.5 dBTP).

Uso:
  python3 limpiar_voz.py entrada.(mp4|mov|wav|mp3...) salida.wav [--preset natural|intenso]
                         [--mono] [--lufs -16] [--tp -1.5] [--sin-ia]

Dependencias:
  - ffmpeg (en el PATH)
  - pip install numpy scipy soundfile pyloudnorm pedalboard   (respaldo opcional: noisereduce)
  - DeepFilterNet: se busca en $DEEP_FILTER, en el PATH (`deep-filter`) o en
    ~/.cache/limpiar_voz/bin/deep-filter. Si no está, se descarga automáticamente del release
    oficial v0.5.6 de GitHub (Rikorose/DeepFilterNet), binario autónomo con el modelo incluido.
"""
import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import warnings

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from pedalboard import Compressor, HighShelfFilter, PeakFilter, Pedalboard
from scipy import signal
from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d

SR = 48000
HOP = 48  # 1 ms: resolución de las envolventes de control

# Ajustes probados sobre el crudo TGH (ver reporte). "natural" es el elegido por defecto.
#   dfn_voz_db: máximo que DeepFilterNet puede atenuar un tramo con voz (protección).
#   comp_umbral: umbral del compresor relativo al nivel típico de la voz (normal / ya comprimido).
PRESETS = {
    "natural": dict(dfn_voz_db=6.0, barro_db=-2.5, presencia_db=2.5, aire_db=2.0,
                    deesser_max=6.0, deesser_ratio=4.0, deesser_pct=85,
                    comp_ratio=3.0, comp_umbral=(-2.0, 4.0), exp_rango=10.0, exp_umbral=18.0),
    "intenso": dict(dfn_voz_db=9.0, barro_db=-3.0, presencia_db=3.5, aire_db=3.0,
                    deesser_max=8.0, deesser_ratio=4.0, deesser_pct=85,
                    comp_ratio=3.0, comp_umbral=(-3.0, 2.0), exp_rango=14.0, exp_umbral=16.0),
}
LRA_COMPRIMIDO = 4.0  # LU: por debajo, el crudo ya viene comprimido/limitado

DFN_VERSION = "0.5.6"
DFN_ASSETS = {  # plataforma -> (nombre del asset, sha256 conocido o None)
    ("Linux", "x86_64"): ("deep-filter-0.5.6-x86_64-unknown-linux-musl",
                          "70775e251eee44c0f2451a1e833326cf8bcbbe304d3e7cd12851e6fce72ef7da"),
    ("Linux", "aarch64"): ("deep-filter-0.5.6-aarch64-unknown-linux-gnu", None),
    ("Darwin", "arm64"): ("deep-filter-0.5.6-aarch64-apple-darwin", None),
    ("Darwin", "x86_64"): ("deep-filter-0.5.6-x86_64-apple-darwin", None),
    ("Windows", "AMD64"): ("deep-filter-0.5.6-x86_64-pc-windows-msvc.exe", None),
}
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "limpiar_voz")


def log(*a):
    print("[limpiar_voz]", *a, flush=True)


def db(v):
    return 20 * np.log10(np.maximum(v, 1e-12))


# ============================================================ entrada / salida
def leer_entrada(ruta):
    """Extrae el audio (video o audio) a float32 48 kHz con ffmpeg. Devuelve (mono, n_muestras)."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "in.wav")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", ruta, "-vn",
                        "-map", "0:a:0", "-ar", str(SR), "-c:a", "pcm_f32le", wav], check=True)
        x, _ = sf.read(wav, dtype="float64", always_2d=True)
    if x.shape[1] == 1:
        return x[:, 0]
    c = np.corrcoef(x[:, 0], x[:, 1])[0, 1] if x[:, 0].std() > 0 and x[:, 1].std() > 0 else 0
    if c > 0.5:
        return x.mean(1)  # mismo micrófono en ambos canales
    # canales distintos (p.ej. solapa solo en uno): nos quedamos con el más fuerte
    return x[:, int(np.argmax((x ** 2).mean(0)))]


# ============================================================ 2. declipping
def detectar_recorte(x):
    """Busca la acumulación de muestras en un nivel fijo (firma de un recorte duro).
    Devuelve el umbral (lineal) o None si el audio no está recortado."""
    h, b = np.histogram(np.abs(x), bins=200, range=(0.3, 1.0))
    mejor, umbral = 1.0, None
    for i in range(10, 200):
        r = h[i] / (np.median(h[i - 10:i - 2]) + 5)
        if r > mejor and h[i] > 200:
            mejor, umbral = r, b[i]
    return umbral - 0.01 if mejor > 1.6 else None


def _declip_bloque(x, theta, iters=60, nper=1024, hop=256, techo=1.6):
    """Iteración consistente con umbral duro en STFT: las muestras fiables no se tocan,
    las recortadas deben quedar >= umbral (y <= techo*umbral para no inventar picos)."""
    fiable = np.convolve((np.abs(x) < theta).astype(float) - 1, np.ones(3), "same") == 0
    pos, neg = ~fiable & (x > 0), ~fiable & (x < 0)
    y = x.copy()
    pad = nper
    for it in range(iters):
        _, _, Z = signal.stft(np.pad(y, pad), nperseg=nper, noverlap=nper - hop, boundary=None, padded=False)
        mag = np.abs(Z)
        Z[mag < np.quantile(mag, 1 - (0.02 + 0.5 * (it / (iters - 1)) ** 2))] = 0
        _, z = signal.istft(Z, nperseg=nper, noverlap=nper - hop, boundary=False)
        z = z[pad:pad + len(x)]
        y = np.pad(z, (0, len(x) - len(z)))
        y[fiable] = x[fiable]
        y[pos] = np.clip(y[pos], np.minimum(x[pos], theta), theta * techo)
        y[neg] = np.clip(y[neg], -theta * techo, np.maximum(x[neg], -theta))
    return y


def declip(x):
    theta = detectar_recorte(x)
    if theta is None:
        log("declipping: no se detecta recorte, se omite")
        return x, 0
    y = x.copy()
    idx = np.flatnonzero(np.abs(x) >= theta)
    # agrupar zonas recortadas en bloques con 100 ms de contexto
    m = int(0.1 * SR)
    ini, fin = idx[0], idx[0]
    bloques = []
    for i in idx[1:]:
        if i - fin > 2 * m:
            bloques.append((ini, fin))
            ini = i
        fin = i
    bloques.append((ini, fin))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for a, b in bloques:
            a, b = max(0, a - m), min(len(x), b + m)
            y[a:b] = _declip_bloque(x[a:b], theta)
    log(f"declipping: recorte en {theta:.3f} ({db(theta):.1f} dBFS), {len(idx)} muestras reconstruidas")
    return y, len(idx)


# ============================================================ 3. reducción de ruido IA
def ubicar_deepfilter():
    exe = "deep-filter.exe" if platform.system() == "Windows" else "deep-filter"
    for c in (os.environ.get("DEEP_FILTER"), shutil.which("deep-filter"), os.path.join(CACHE, "bin", exe)):
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    clave = (platform.system(), platform.machine())
    if clave not in DFN_ASSETS:
        return None
    nombre, sha = DFN_ASSETS[clave]
    url = f"https://github.com/Rikorose/DeepFilterNet/releases/download/v{DFN_VERSION}/{nombre}"
    destino = os.path.join(CACHE, "bin", exe)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    try:
        log("descargando DeepFilterNet:", url)
        datos = urllib.request.urlopen(url, timeout=120).read()
    except Exception as e:  # sin red: se usa el respaldo
        log("no se pudo descargar DeepFilterNet:", e)
        return None
    if sha and hashlib.sha256(datos).hexdigest() != sha:
        log("ERROR: el binario descargado no coincide con el sha256 esperado; se descarta")
        return None
    with open(destino, "wb") as f:
        f.write(datos)
    os.chmod(destino, 0o755)
    return destino


def _lag(a, b, maxlag=4800):
    """Desfase (muestras) de b respecto a a por correlación cruzada (positivo = b llega tarde)."""
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    c = np.fft.irfft(np.fft.rfft(b, n) * np.conj(np.fft.rfft(a, n)), n)
    c = np.r_[c[-maxlag:], c[:maxlag + 1]]
    return int(np.argmax(np.abs(c)) - maxlag)


def _alinear(ref, y):
    """Corrige cualquier retardo residual y deja exactamente la longitud de ref."""
    L = _lag(ref, y)
    if L > 0:
        y = y[L:]
    elif L < 0:
        y = np.r_[np.zeros(-L), y]
    return np.pad(y, (0, max(0, len(ref) - len(y))))[:len(ref)], L


def proteger_voz(x, d, max_voz_db, snr_on=6.0, snr_full=14.0, nper=1024, hop=256, n_bandas=24):
    """Usa DFN como estimador de máscara y limita, POR BANDA, lo que puede quitar donde hay voz.
    STFT 21 ms; 24 bandas logarítmicas (60 Hz-24 kHz). En cada banda y frame: si la entrada está
    claramente por encima del piso de ruido de esa banda (voz), la ganancia no baja de -max_voz_db;
    cerca del piso (pausa, ruido) se usa la ganancia de DFN completa. Se aplica una máscara real
    sobre la señal original (sin mezclar fases distintas => sin cancelaciones ni huecos)."""
    kw = dict(fs=SR, nperseg=nper, noverlap=nper - hop, window="hann")
    f, _, X = signal.stft(x, **kw)
    _, _, D = signal.stft(d, **kw)
    G = np.clip(np.abs(D) / (np.abs(X) + 1e-12), 0, 1)
    bordes = np.r_[0, np.geomspace(60, SR / 2, n_bandas)]
    banda = np.clip(np.searchsorted(bordes, f, side="right") - 1, 0, n_bandas - 1)
    P = np.abs(X) ** 2
    Eb = np.stack([P[banda == b].mean(0) if (banda == b).any() else np.zeros(P.shape[1])
                   for b in range(n_bandas)])
    Eb = 10 * np.log10(Eb + 1e-20)
    snr = Eb - np.percentile(Eb, 5, axis=1, keepdims=True)  # distancia al piso de cada banda
    w = np.clip((snr - snr_on) / (snr_full - snr_on), 0, 1)
    # suavizado que nunca reduce la protección: en el tiempo (max+media, 3 frames) y entre
    # bandas vecinas (max: si una banda tiene voz, sus vecinas también se protegen)
    w = uniform_filter1d(maximum_filter1d(w, 3, axis=1), 3, axis=1)
    w = maximum_filter1d(w, 3, axis=0, mode="nearest")
    gmin = 10 ** (-(100 * (1 - w) + max_voz_db * w) / 20)
    Gp = np.maximum(G, gmin[banda])
    _, y = signal.istft(Gp * X, fs=SR, nperseg=nper, noverlap=nper - hop, window="hann")
    y = np.pad(y[:len(x)], (0, max(0, len(x) - len(y))))
    return y, float((Gp > G + 1e-6).mean())


def denoise(x, max_voz_db, usar_ia=True):
    escala = 0.5 / max(np.abs(x).max(), 1e-9)  # deep-filter escribe en 16 bits: evitar recortes
    binario = ubicar_deepfilter() if usar_ia else None
    if binario:
        with tempfile.TemporaryDirectory() as tmp:
            ent = os.path.join(tmp, "voz.wav")
            # se añade 0.2 s de silencio al final: -D compensa el retardo recortando el inicio
            sf.write(ent, np.r_[x * escala, np.zeros(int(0.2 * SR))].astype(np.float32), SR, subtype="FLOAT")
            subprocess.run([binario, "-D", "-a", "100", "-o", os.path.join(tmp, "out"), ent],
                           check=True, capture_output=True)
            y, sr = sf.read(os.path.join(tmp, "out", "voz.wav"), dtype="float64")
        assert sr == SR
        y, L = _alinear(x, y / escala)
        y, frac = proteger_voz(x, y, max_voz_db)
        log(f"reducción de ruido: DeepFilterNet3 + protección de voz ({max_voz_db:g} dB máx. en voz; "
            f"{frac * 100:.0f}% de las celdas tiempo-frecuencia protegidas), desfase corregido {L} muestras")
        return y, "DeepFilterNet3 protegido"
    try:
        import noisereduce as nr
        log("reducción de ruido: respaldo noisereduce (no estacionario, 0.7)")
        return nr.reduce_noise(y=x, sr=SR, stationary=False, prop_decrease=0.7, n_fft=2048), "noisereduce"
    except ImportError:
        pass
    log("reducción de ruido: respaldo ffmpeg afftdn")
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, "a.wav"), os.path.join(tmp, "b.wav")
        sf.write(a, x * escala, SR, subtype="FLOAT")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a, "-af",
                        "afftdn=nr=12:nf=-50:tn=1", "-c:a", "pcm_f32le", b], check=True)
        y, _ = sf.read(b, dtype="float64")
    return _alinear(x, y / escala)[0], "afftdn"


# ============================================================ utilidades de dinámica
def envolvente_db(x, ventana_ms):
    """RMS en dB con salto de 1 ms y ventana dada (centrada: sin retardo)."""
    n = len(x) // HOP + 1
    p = np.pad(x ** 2, (0, n * HOP - len(x)))
    p = p.reshape(n, HOP).mean(1)
    k = max(1, int(round(ventana_ms)))
    return db(np.sqrt(np.maximum(uniform_filter1d(p, k, mode="nearest"), 0)))  # evita -0.0 numérico


def suavizar(g, baja_ms, sube_ms):
    """Balística de una curva de ganancia en dB (1 valor por ms): constante de tiempo distinta
    cuando la ganancia baja (más reducción) y cuando sube (se recupera)."""
    a = np.exp(-1 / max(baja_ms, 1e-3))
    r = np.exp(-1 / max(sube_ms, 1e-3))
    out = np.empty_like(g)
    v = g[0]
    for i, t in enumerate(g):
        c = a if t < v else r
        v = c * v + (1 - c) * t
        out[i] = v
    return out


def a_muestras(g_db, n):
    """Interpola una curva de ganancia (dB, 1 por ms) a la tasa de muestreo."""
    t = (np.arange(n) - HOP / 2) / HOP  # cada valor de control está centrado en su milisegundo
    return 10 ** (np.interp(t, np.arange(len(g_db)), g_db) / 20)


def nivel_voz(env):
    """Nivel de referencia de la voz: mediana de las ventanas activas."""
    return float(np.median(env[env > np.percentile(env, 40)]))


# ============================================================ 4-8. cadena de mastering
def paso_alto(x, fc=80):
    sos = signal.butter(2, fc, "hp", fs=SR, output="sos")  # filtfilt => 24 dB/oct, fase cero
    return signal.sosfiltfilt(sos, x)


def _pb(x, efectos):
    return Pedalboard(efectos)(x[None, :].astype(np.float32), SR)[0].astype(np.float64)


def lra(x):
    """Loudness Range (EBU R128) medido con ffmpeg ebur128."""
    with tempfile.TemporaryDirectory() as tmp:
        w = os.path.join(tmp, "lra.wav")
        sf.write(w, x / max(np.abs(x).max(), 1e-9) * 0.5, SR, subtype="FLOAT")
        err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", w, "-af", "ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
    try:
        return float(err.rsplit("LRA:", 1)[1].split("LU")[0])
    except (IndexError, ValueError):
        return 10.0


def compresor(x, ratio, umbral_rel=0.0):
    """Umbral relativo al nivel típico de la voz (mediana de los tramos activos)."""
    env = envolvente_db(x, 10)
    ref = nivel_voz(env)
    umbral = ref + umbral_rel
    y = _pb(x, [Compressor(threshold_db=umbral, ratio=ratio, attack_ms=8, release_ms=100)])
    gr = envolvente_db(x, 10) - envolvente_db(y, 10)
    act = env > ref - 6
    return y, float(np.median(gr[act])), float(np.percentile(gr[act], 95))


def deesser(x, max_gr, ratio=4.0, percentil=85):
    """Divide en banda 5.5-9 kHz (fase cero, x = banda + resto exacto) y comprime solo la banda
    cuando supera el umbral (percentil de su envolvente durante la voz). Va después de la EQ
    de presencia/aire y de DeepFilterNet, que aclaran los agudos."""
    sos = signal.butter(4, [5500, 9000], "bp", fs=SR, output="sos")
    banda = signal.sosfiltfilt(sos, x)
    resto = x - banda
    eb = envolvente_db(banda, 5)
    ef = envolvente_db(x, 5)
    act = ef > nivel_voz(ef) - 20
    umbral = np.percentile(eb[act], percentil)
    gr = np.clip((eb - umbral) * (1 - 1 / ratio), 0, max_gr)
    gr = maximum_filter1d(gr, 3)  # 1-2 ms de look-ahead
    g = suavizar(-gr, 1, 40)  # reduce en 1 ms, recupera en 40 ms
    return resto + banda * a_muestras(g, len(x)), float(np.percentile(gr[act], 99))


def expansor(x, rango_db, umbral_rel, ratio=2.0, hold_ms=40, look_ms=10):
    """Expansor descendente suave: solo baja lo que queda >= umbral_rel dB bajo la voz.
    Look-ahead (abre 10 ms antes) y hold (40 ms) evitan cortar ataques y colas de palabras;
    cierra en ~30 ms porque las pausas de un reel duran 100-250 ms."""
    env = envolvente_db(x, 10)
    umbral = nivel_voz(env) - umbral_rel
    g = -np.clip((umbral - env) * (ratio - 1), 0, rango_db)
    # mantener abierto: máximo de ganancia en [t - hold, t + look]
    g = maximum_filter1d(g, hold_ms + look_ms, origin=(hold_ms - look_ms) // 2)
    g = suavizar(g, 30, 3)  # cierra en ~30 ms, abre en ~3 ms
    return x * a_muestras(g, len(x))


def limitador_tp(x, techo_dbtp):
    """Limitador true-peak offline (sobremuestreo x4, look-ahead 1.5 ms, release 60 ms)."""
    techo = 10 ** (techo_dbtp / 20)
    ov = np.abs(signal.resample_poly(x, 4, 1))
    pico = ov[:len(x) * 4].reshape(-1, 4).max(1)
    req = np.minimum(1.0, techo / np.maximum(pico, 1e-9))
    if req.min() >= 1.0:
        return x
    w = int(0.0015 * SR)
    g = uniform_filter1d(minimum_filter1d(req, 2 * w + 1), w + 1)  # suave y siempre <= req
    rel = np.exp(-1 / (0.060 * SR))
    out = np.empty_like(g)
    v = 1.0
    for i, t in enumerate(g):  # la ganancia vuelve a 1 con release
        v = t if t < v else rel * v + (1 - rel) * t
        out[i] = v
    return x * out


def true_peak_db(x):
    return float(db(np.abs(signal.resample_poly(x, 4, 1)).max()))


def sonoridad(x, canales=1):
    """LUFS integrados del archivo tal como se entrega (estéreo duplicado suma +3 dB)."""
    return float(pyln.Meter(SR).integrated_loudness(np.stack([x] * canales, 1)))


def normalizar(x, lufs, tp, canales=1):
    for _ in range(4):
        x = x * 10 ** ((lufs - sonoridad(x, canales)) / 20)
        x = limitador_tp(x, tp - 0.2)
        if abs(sonoridad(x, canales) - lufs) < 0.05:
            break
    return x


def procesar(x, preset="natural", lufs=-16.0, tp=-1.5, usar_ia=True, canales=2):
    p = PRESETS[preset]
    info = {}
    info["lra_entrada"] = lra(x)
    x, info["muestras_declip"] = declip(x)
    x = paso_alto(x, 80)
    x = _pb(x, [PeakFilter(320, p["barro_db"], 1.0)])
    ya_comprimido = info["lra_entrada"] < LRA_COMPRIMIDO
    info["comp_modo"] = "solo picos (crudo ya comprimido)" if ya_comprimido else "voz"
    x, info["comp_gr_mediana"], info["comp_gr_p95"] = compresor(x, p["comp_ratio"], p["comp_umbral"][ya_comprimido])
    x = _pb(x, [PeakFilter(4000, p["presencia_db"], 0.9), HighShelfFilter(11000, p["aire_db"], 0.7)])
    x, info["denoise"] = denoise(x, p["dfn_voz_db"], usar_ia)
    x, info["deesser_gr_p99"] = deesser(x, p["deesser_max"], p["deesser_ratio"], p["deesser_pct"])
    x = expansor(x, p["exp_rango"], p["exp_umbral"])
    x = normalizar(x, lufs, tp, canales)
    info["lufs"] = round(sonoridad(x, canales), 2)
    info["true_peak"] = round(true_peak_db(x), 2)
    return x, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--preset", default="natural", choices=sorted(PRESETS))
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--tp", type=float, default=-1.5)
    ap.add_argument("--mono", action="store_true", help="salida mono (por defecto estéreo duplicado)")
    ap.add_argument("--sin-ia", action="store_true", help="no usar DeepFilterNet (respaldo clásico)")
    a = ap.parse_args()

    x = leer_entrada(a.entrada)
    n = len(x)
    log(f"entrada: {a.entrada} ({n} muestras, {n / SR:.3f} s)")
    y, info = procesar(x, a.preset, a.lufs, a.tp, not a.sin_ia, 1 if a.mono else 2)
    assert len(y) == n
    sal = y if a.mono else np.stack([y, y], 1)
    sf.write(a.salida, sal, SR, subtype="PCM_24")
    log(f"salida: {a.salida} | 48 kHz 24 bit {'mono' if a.mono else 'estéreo'} | {n} muestras")
    for k, v in info.items():
        log(f"  {k}: {round(v, 2) if isinstance(v, float) else v}")


if __name__ == "__main__":
    sys.exit(main())

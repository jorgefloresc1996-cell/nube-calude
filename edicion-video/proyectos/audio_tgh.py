"""Música original y efectos de sonido (SFX) sintetizados para los reels TGH.

Todo se genera por código: sin licencias ni derechos de terceros.
"""
import numpy as np
from pedalboard import (Compressor, Delay, HighpassFilter, Limiter, LowpassFilter,
                        Pedalboard, Reverb)

SR = 48000
RNG = np.random.default_rng(7)


def _t(d):
    return np.arange(int(SR * d)) / SR


def _env(n, a=0.005, r=0.1, d=None):
    """Envolvente ataque / caída exponencial."""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    return e * np.exp(-t / r) if d is None else e * np.clip(1 - (t - d) / r, 0, 1) * (t < d + r)


def _saw(f, t, fase=0.0):
    return 2 * ((f * t + fase) % 1.0) - 1


def _fx(x, board):
    """Aplica pedalboard a señal mono/estéreo (n, 2)."""
    x = np.asarray(x, np.float32)
    est = x.ndim == 2
    y = board(x.T if est else x[None, :], SR)
    return y.T if est else y[0]


def _est(x, pan=0.0):
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    return np.stack([x * l * 1.414, x * r * 1.414], axis=1)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# ======================================================================= SFX
def whoosh(d=0.5, pan_ini=-0.7, pan_fin=0.7):
    n = int(SR * d)
    t = np.linspace(0, 1, n)
    ruido = RNG.standard_normal(n)
    # paso banda que barre hacia arriba
    out, lp = np.zeros(n), 0.0
    for i in range(n):
        lp += (0.01 + 0.35 * np.sin(np.pi * t[i]) ** 2) * (ruido[i] - lp)
        out[i] = lp
    env = np.sin(np.pi * t) ** 1.8
    m = out * env
    pan = pan_ini + (pan_fin - pan_ini) * t
    s = np.stack([m * np.cos((pan + 1) * np.pi / 4), m * np.sin((pan + 1) * np.pi / 4)], 1) * 1.4
    return _fx(s, Pedalboard([HighpassFilter(250), Reverb(room_size=0.3, wet_level=0.15)])) * 0.9


def swish():
    """Whoosh corto y brillante para palabras grandes."""
    n = int(SR * 0.16)
    t = np.linspace(0, 1, n)
    s = RNG.standard_normal(n) * np.sin(np.pi * t) ** 2
    return _est(_fx(s, Pedalboard([HighpassFilter(2500), LowpassFilter(9000)])) * 0.35)


def pop(tono=1.0):
    t = _t(0.09)
    f = (700 + 900 * np.exp(-t * 60)) * tono
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40)
    return _est(s * 0.55)


def tick():
    t = _t(0.03)
    s = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 300) + RNG.standard_normal(len(t)) * np.exp(-t * 500) * 0.3
    return _est(s * 0.35)


def impacto():
    t = _t(1.2)
    sub = np.sin(2 * np.pi * np.cumsum(38 + 110 * np.exp(-t * 12)) / SR) * np.exp(-t * 3.2)
    golpe = RNG.standard_normal(len(t)) * np.exp(-t * 30)
    s = sub * 0.9 + _fx(golpe, Pedalboard([LowpassFilter(3000)])) * 0.5
    return _fx(_est(s), Pedalboard([Reverb(room_size=0.6, wet_level=0.2, width=1.0), Limiter(-1)])) * 0.9


def riser(d=0.7):
    t = _t(d)
    x = t / d
    tono = np.sin(2 * np.pi * np.cumsum(300 + 1500 * x ** 2) / SR) * 0.25
    ruido = _fx(RNG.standard_normal(len(t)), Pedalboard([HighpassFilter(1500)])) * 0.5
    s = (tono + ruido) * x ** 2.5
    return _fx(_est(s), Pedalboard([Reverb(room_size=0.5, wet_level=0.25)])) * 0.6


def error_buzz():
    """'Ehh-eh' descendente: hook auditivo de error."""
    out = []
    for f, d in ((330, 0.13), (247, 0.22)):
        t = _t(d)
        sq = np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + np.sin(2 * np.pi * f * t) * 0.5
        out.append(sq * _env(len(t), 0.004, d * 0.7) * 0.9)
        out.append(np.zeros(int(SR * 0.02)))
    s = np.concatenate(out)
    return _fx(_est(s), Pedalboard([LowpassFilter(2500), Reverb(room_size=0.2, wet_level=0.1)])) * 0.35


def campana(notas, sep=0.09, dur=0.9, vol=0.4):
    tot = np.zeros(int(SR * (sep * len(notas) + dur)))
    for k, n in enumerate(notas):
        t = _t(dur)
        f = midi(n)
        s = sum(np.sin(2 * np.pi * f * m * t) * a * np.exp(-t * (4 + m * 2)) for m, a in ((1, 1), (2.76, .35), (5.4, .15)))
        i = int(SR * sep * k)
        tot[i:i + len(s)] += s
    return _fx(_est(tot * vol), Pedalboard([Reverb(room_size=0.4, wet_level=0.22)]))


def exito():
    return campana([76, 83], sep=0.08, vol=0.32)  # Mi - Si: "¡correcto!"


def notificacion():
    return campana([81, 88], sep=0.11, dur=0.6, vol=0.25)


def obturador():
    s = np.zeros(int(SR * 0.18))
    for i0 in (0, int(SR * 0.07)):
        t = _t(0.05)
        s[i0:i0 + len(t)] += RNG.standard_normal(len(t)) * np.exp(-t * 150)
    return _est(_fx(s, Pedalboard([HighpassFilter(1200)])) * 0.5)


def tecleo(n=8, sep=0.07):
    s = np.zeros(int(SR * (sep * n + 0.05)))
    for k in range(n):
        t = _t(0.025)
        i = int(SR * (sep * k + RNG.uniform(0, 0.02)))
        s[i:i + len(t)] += RNG.standard_normal(len(t)) * np.exp(-t * 400) * RNG.uniform(0.5, 1)
    return _est(_fx(s, Pedalboard([HighpassFilter(2000)])) * 0.25)


def platillo_reverso(d=1.0):
    t = _t(d)
    s = _fx(RNG.standard_normal(len(t)), Pedalboard([HighpassFilter(5000)])) * (t / d) ** 3
    return _est(s * 0.35)


def sting_logo():
    c = campana([69, 76, 81, 85], sep=0.05, dur=2.2, vol=0.3)
    t = _t(len(c) / SR)
    return c + _est(np.sin(2 * np.pi * 55 * t) * np.exp(-t * 2) * 0.6)[:len(c)]


# ===================================================================== MÚSICA
def musica(dur, bpm=122, filtrados=(), radio=(), cortes=(), fin_beat=None):
    """Pista pop/house original. filtrados: [(a,b)] con paso bajo (tensión);
    radio: [(a,b)] con filtro tipo radio; fin_beat: segundo donde se corta el ritmo."""
    beat = 60 / bpm
    n = int(SR * dur) + SR
    prog = [(57, 60, 64, 45), (53, 57, 60, 41), (55, 60, 64, 48), (55, 59, 62, 43)]  # Am F C G
    bar = beat * 4
    fin_beat = fin_beat or dur

    drums = np.zeros(n)
    bass = np.zeros(n)
    pad = np.zeros(n)
    arp = np.zeros(n)
    hats = np.zeros(n)

    def add(buf, s, t0):
        i = int(t0 * SR)
        if i >= n:
            return
        m = min(len(s), n - i)
        buf[i:i + m] += s[:m]

    # Batería
    tk = _t(0.35)
    kick = np.sin(2 * np.pi * np.cumsum(45 + 120 * np.exp(-tk * 35)) / SR) * np.exp(-tk * 8)
    kick += RNG.standard_normal(len(tk)) * np.exp(-tk * 400) * 0.2
    tc = _t(0.3)
    clap = np.zeros(len(tc))
    for d in (0, 0.011, 0.023):
        i = int(d * SR)
        clap[i:] += RNG.standard_normal(len(tc) - i) * np.exp(-tc[:len(tc) - i] * (60 if d < 0.02 else 18))
    clap = _fx(clap, Pedalboard([HighpassFilter(900), LowpassFilter(7000)])) * 0.5
    th = _t(0.05)
    hat_c = _fx(RNG.standard_normal(len(th)) * np.exp(-th * 90), Pedalboard([HighpassFilter(7000)])) * 0.25
    to = _t(0.22)
    hat_o = _fx(RNG.standard_normal(len(to)) * np.exp(-to * 14), Pedalboard([HighpassFilter(6500)])) * 0.22

    n_beats = int(fin_beat / beat)
    for b in range(n_beats):
        tb = b * beat
        add(drums, kick, tb)
        if b % 4 in (1, 3):
            add(drums, clap, tb)
        add(hats, hat_o, tb + beat / 2)
        for s16 in (0, 1, 3):
            add(hats, hat_c * (0.6 if s16 else 0.9), tb + s16 * beat / 4)
    # redoble antes de cada corte
    for c in cortes:
        for k in range(4):
            add(drums, clap * (0.4 + 0.15 * k), c - beat + k * beat / 4)

    # Armonía
    n_bars = int(np.ceil(dur / bar)) + 1
    for k in range(n_bars):
        c = prog[k % 4]
        t0 = k * bar
        if t0 >= dur + 0.5:
            break
        # pad
        tp = _t(bar)
        voz = sum(_saw(midi(m) * (1 + det), tp, RNG.random()) for m in c[:3] for det in (-0.006, 0, 0.006))
        env = np.minimum(1, tp / 0.15) * np.minimum(1, (bar - tp) / 0.05)
        add(pad, voz * env * 0.07, t0)
        # bajo en contratiempo (house)
        for b in range(4):
            tb = _t(beat / 2)
            f = midi(c[3])
            s = (np.sin(2 * np.pi * f * tb) + 0.4 * _saw(f, tb)) * _env(len(tb), 0.005, 0.18)
            if t0 + b * beat < fin_beat:
                add(bass, s * 0.5, t0 + b * beat + beat / 2)
        # arpegio 16avos
        patron = [0, 1, 2, 1, 2, 0, 1, 2]
        for s16 in range(16):
            tt = t0 + s16 * beat / 4
            if tt >= fin_beat:
                break
            nota = c[patron[s16 % 8]] + 12
            tn = _t(beat / 4 * 1.5)
            f = midi(nota)
            s = (_saw(f, tn) * 0.5 + np.sign(np.sin(2 * np.pi * f * tn)) * 0.3) * _env(len(tn), 0.002, 0.07)
            add(arp, s * 0.16, tt)

    # Sidechain (bombeo) desde el kick
    sc = np.ones(n)
    for b in range(n_beats):
        i = int(b * beat * SR)
        m = min(int(beat * SR), n - i)
        x = np.arange(m) / SR
        sc[i:i + m] = 1 - 0.7 * np.exp(-x / 0.09)

    pad = _fx(pad * sc, Pedalboard([LowpassFilter(2200), Reverb(room_size=0.7, wet_level=0.35, width=1.0)]))
    arp = _fx(_est(arp * sc), Pedalboard([LowpassFilter(5000), Delay(delay_seconds=beat * 0.75, feedback=0.3, mix=0.25),
                                          Reverb(room_size=0.5, wet_level=0.25, width=1.0)]))
    bass = _fx(bass * sc, Pedalboard([LowpassFilter(900)]))
    drums_s = _fx(_est(drums), Pedalboard([Compressor(-12, 3, 3, 60)]))
    hats_s = np.stack([hats * 0.8, hats * 1.0], 1)

    mezcla = drums_s * 0.9 + hats_s + _est(bass) * 0.8 + np.stack([pad, pad], 1) * 0.6 + arp * 0.9
    mezcla = mezcla[:n]

    def automatizar(base, alterna, rangos, rampa=0.12):
        g = np.zeros(n)
        for a, b in rangos:
            ia, ib = int(a * SR), int(b * SR)
            g[ia:ib] = 1
        k = int(rampa * SR)
        g = np.convolve(g, np.ones(k) / k, mode="same")
        return base * (1 - g[:, None]) + alterna * g[:, None]

    if filtrados:
        mezcla = automatizar(mezcla, _fx(mezcla, Pedalboard([LowpassFilter(450)])) * 1.2, filtrados)
    if radio:
        mezcla = automatizar(mezcla, _fx(mezcla, Pedalboard([HighpassFilter(700), LowpassFilter(2500)])) * 1.4, radio)
    # final: el ritmo se corta, queda la cola de reverb
    ifb = int(fin_beat * SR)
    cola = np.exp(-np.arange(n - ifb) / SR / 0.6)
    mezcla[ifb:] *= cola[:, None]
    mezcla = _fx(mezcla, Pedalboard([HighpassFilter(30), Compressor(-14, 2.5, 10, 120), Limiter(-1.0)]))
    return mezcla[:int(SR * dur)]

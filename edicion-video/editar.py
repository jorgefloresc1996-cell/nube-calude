#!/usr/bin/env python3
"""Editor de video profesional automatizado (ffmpeg + auto-editor + faster-whisper).

Ejemplo:
  python3 editar.py crudo.mp4 -o final.mp4 --formato vertical --cortar-silencios \
      --subtitulos auto --musica fondo.mp3 --logo logo.png --titulo "Agencia TGH"
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FORMATOS = {
    "vertical": (1080, 1920),   # Reels / TikTok / Shorts
    "horizontal": (1920, 1080), # YouTube
    "cuadrado": (1080, 1080),   # Feed
    "original": None,
}

# Looks de color hechos con filtros ffmpeg (sin LUT externo).
LOOKS = {
    "natural": "eq=contrast=1.05:saturation=1.08,unsharp=5:5:0.4",
    "calido": "eq=contrast=1.08:saturation=1.12,colorbalance=rs=.05:gs=.01:bs=-.05:rm=.04:bm=-.04,unsharp=5:5:0.4",
    "frio": "eq=contrast=1.08:saturation=1.0,colorbalance=rs=-.04:bs=.06:bm=.04,unsharp=5:5:0.4",
    "cine": "eq=contrast=1.12:saturation=0.9:gamma=0.97,colorbalance=rs=.03:bs=-.03:rh=-.03:bh=.05,vignette=PI/5,unsharp=5:5:0.4",
    "ninguno": "",
}


def run(cmd):
    print("→", " ".join(str(c) for c in cmd[:6]), "...")
    subprocess.run([str(c) for c in cmd], check=True)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    return v, a, float(data["format"]["duration"])


def cortar_silencios(entrada, salida, margen):
    run(["auto-editor", entrada, "--edit", "audio:threshold=0.04", "--margin", margen,
         "--no-open", "--progress", "none", "-o", salida])


def transcribir(entrada, srt, modelo, idioma):
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(modelo, device="cpu", compute_type="int8")
    except Exception as e:  # sin red / modelo no descargado
        sys.exit(f"No se pudo cargar el modelo Whisper '{modelo}': {e}\n"
                 "Usa --subtitulos ruta.srt o descarga el modelo con acceso a huggingface.co.")
    segs, _ = m.transcribe(str(entrada), language=idioma, word_timestamps=True, vad_filter=True)
    # Bloques cortos de máx. 4 palabras: estilo redes sociales.
    bloques = []
    for s in segs:
        palabras = list(s.words or [])
        for i in range(0, len(palabras), 4):
            g = palabras[i:i + 4]
            bloques.append((g[0].start, g[-1].end, "".join(w.word for w in g).strip()))
    with open(srt, "w", encoding="utf-8") as f:
        for n, (a, b, t) in enumerate(bloques, 1):
            f.write(f"{n}\n{ts(a)} --> {ts(b)}\n{t}\n\n")


def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def esc(path):
    """Escapa una ruta para usarla dentro de un filtro ffmpeg."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def editar(a):
    entrada = Path(a.entrada).resolve()
    salida = Path(a.salida).resolve()
    tmp = Path(tempfile.mkdtemp(prefix="edicion_"))
    try:
        fuente = entrada
        if a.cortar_silencios:
            fuente = tmp / "cortado.mp4"
            cortar_silencios(entrada, fuente, a.margen)

        v, au, dur = probe(fuente)
        if not v:
            sys.exit("El archivo no tiene video.")
        W, H = FORMATOS[a.formato] or (int(v["width"]) // 2 * 2, int(v["height"]) // 2 * 2)

        srt = None
        if a.subtitulos == "auto":
            srt = tmp / "subs.srt"
            transcribir(fuente, srt, a.modelo, a.idioma)
        elif a.subtitulos:
            srt = Path(a.subtitulos).resolve()

        inputs = ["-i", fuente]
        idx = 1
        musica_idx = logo_idx = None
        if a.musica:
            inputs += ["-stream_loop", "-1", "-i", Path(a.musica).resolve()]
            musica_idx, idx = idx, idx + 1
        if a.logo:
            inputs += ["-i", Path(a.logo).resolve()]
            logo_idx, idx = idx, idx + 1

        # ---------- VIDEO ----------
        vf = []
        if a.estabilizar:
            trf = tmp / "estab.trf"
            run(["ffmpeg", "-y", "-v", "error", "-i", fuente, "-vf",
                 f"vidstabdetect=shakiness=6:result={esc(trf)}", "-f", "null", "-"])
            vf.append(f"vidstabtransform=input={esc(trf)}:smoothing=20,unsharp=5:5:0.6")
        if a.formato != "original":
            if a.relleno == "desenfoque":
                # Fondo desenfocado + video completo encima (sin recortar al hablante).
                vf.append(f"split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
                          f"crop={W}:{H},boxblur=30:5,eq=brightness=-0.08[bg2];"
                          f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fg2];"
                          f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2")
            else:
                vf.append(f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")
        if LOOKS[a.look]:
            vf.append(LOOKS[a.look])
        vf.append("setsar=1,format=yuv420p")
        if a.fade > 0:
            vf.append(f"fade=t=in:st=0:d={a.fade},fade=t=out:st={max(dur - a.fade, 0):.3f}:d={a.fade}")
        if a.titulo:
            fuente_titulo = a.fuente.replace(":", "\\:")
            vf.append(
                f"drawtext=font='{fuente_titulo}':text='{a.titulo.replace(chr(39), '')}':fontcolor=white:"
                f"fontsize={int(H * 0.045)}:x=(w-text_w)/2:y=h*0.12:box=1:boxcolor={a.color}@0.85:"
                f"boxborderw={int(H * 0.018)}:enable='between(t,0.3,{a.duracion_titulo})':"
                f"alpha='if(lt(t,0.6),(t-0.3)/0.3,if(gt(t,{a.duracion_titulo - 0.3}),"
                f"({a.duracion_titulo}-t)/0.3,1))'")
        if srt:
            size = 16 if H > W else 11
            mv = int(H * 0.22) if H > W else int(H * 0.08)
            style = (f"FontName={a.fuente},FontSize={size},Bold=1,PrimaryColour=&H00FFFFFF,"
                     f"OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,"
                     f"Alignment=2,MarginV={mv // 4}")
            vf.append(f"subtitles={esc(srt)}:original_size={W}x{H}:force_style='{style}'")

        graph = f"[0:v]{','.join(vf)}[v0]"
        vout = "[v0]"
        if logo_idx is not None:
            lw = int(W * 0.14)
            graph += (f";[{logo_idx}:v]scale={lw}:-1,format=rgba,colorchannelmixer=aa=0.85[lg];"
                      f"[v0][lg]overlay=W-w-{int(W*0.04)}:{int(H*0.04)}[v1]")
            vout = "[v1]"

        # ---------- AUDIO ----------
        aout = None
        if au:
            voz = ("highpass=f=80,lowpass=f=14000,afftdn=nf=-25,"
                   "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=3,"
                   "loudnorm=I=-14:TP=-1.5:LRA=11")
            if a.fade > 0:
                voz += f",afade=t=in:d={a.fade},afade=t=out:st={max(dur - a.fade, 0):.3f}:d={a.fade}"
            graph += f";[0:a]{voz},asplit=2[voz][voz_sc]"
            aout = "[voz]"
            if musica_idx is not None:
                # La música baja automáticamente cuando hay voz (ducking).
                graph += (f";[{musica_idx}:a]volume={a.volumen_musica},"
                          f"afade=t=out:st={max(dur - 2, 0):.3f}:d=2[mus];"
                          f"[mus][voz_sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];"
                          f"[voz][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[aout]")
                aout = "[aout]"
            else:
                graph += ";[voz_sc]anullsink"

        cmd = ["ffmpeg", "-y", "-v", "error", "-stats", *inputs, "-filter_complex", graph,
               "-map", vout]
        if aout:
            cmd += ["-map", aout, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        cmd += ["-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf),
                "-profile:v", "high", "-r", str(a.fps), "-movflags", "+faststart", salida]
        run(cmd)
        if srt and a.guardar_srt:
            shutil.copy(srt, salida.with_suffix(".srt"))
        print(f"✔ Listo: {salida}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    p = argparse.ArgumentParser(description="Edición profesional automática de video.")
    p.add_argument("entrada")
    p.add_argument("-o", "--salida", default="final.mp4")
    p.add_argument("--formato", choices=FORMATOS, default="original")
    p.add_argument("--relleno", choices=["recortar", "desenfoque"], default="recortar",
                   help="Cómo adaptar a otro formato: recortar al centro o fondo desenfocado.")
    p.add_argument("--look", choices=LOOKS, default="natural", help="Corrección de color.")
    p.add_argument("--cortar-silencios", action="store_true", help="Elimina pausas y silencios.")
    p.add_argument("--margen", default="0.15s", help="Aire que se deja alrededor de cada corte.")
    p.add_argument("--estabilizar", action="store_true", help="Estabiliza video movido.")
    p.add_argument("--subtitulos", help="'auto' (Whisper) o ruta a un .srt existente.")
    p.add_argument("--modelo", default="small", help="Modelo Whisper: tiny/base/small/medium/large-v3.")
    p.add_argument("--idioma", default="es")
    p.add_argument("--guardar-srt", action="store_true")
    p.add_argument("--musica", help="Música de fondo (se ajusta sola bajo la voz).")
    p.add_argument("--volumen-musica", type=float, default=0.25)
    p.add_argument("--logo", help="PNG con transparencia (esquina superior derecha).")
    p.add_argument("--titulo", help="Texto de título animado al inicio.")
    p.add_argument("--duracion-titulo", type=float, default=3.5)
    p.add_argument("--color", default="0xF15A24", help="Color de marca para el título (hex).")
    p.add_argument("--fuente", default="Montserrat ExtraBold")
    p.add_argument("--fade", type=float, default=0.5, help="Fundido de entrada/salida (0 = no).")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--crf", type=int, default=18, help="Calidad: 16 (máxima) – 23 (ligera).")
    p.add_argument("--preset", default="slow")
    editar(p.parse_args())


if __name__ == "__main__":
    main()

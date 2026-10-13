# Edición de video profesional

Herramienta que aplica en un solo comando lo que hace un editor profesional:
quitar silencios, corregir color, limpiar y nivelar audio, poner subtítulos,
música con *ducking*, logo, título animado y exportar en calidad de plataforma.

## Herramientas instaladas

| Herramienta | Para qué sirve |
|---|---|
| **ffmpeg 6** (x264, x265, AV1, libass, vidstab, loudnorm) | Motor de edición, color, audio, subtítulos y exportación |
| **auto-editor** | Corta pausas y silencios automáticamente (estilo "jump cut") |
| **faster-whisper** | Transcribe la voz y genera subtítulos automáticos en español |
| **moviepy** | Montajes avanzados por código (varios clips, animaciones) |
| **Fuentes** Montserrat, Roboto, Open Sans, Noto Emoji | Tipografía para títulos y subtítulos |

Instalación en otra máquina: `./instalar.sh`

## Uso rápido

```bash
# Reel / TikTok completo
python3 editar.py crudo.mp4 -o reel.mp4 \
  --formato vertical --relleno desenfoque --cortar-silencios \
  --subtitulos auto --musica fondo.mp3 --logo logo.png \
  --titulo "Agencia TGH" --look calido

# Video de YouTube
python3 editar.py crudo.mp4 -o youtube.mp4 --formato horizontal --look cine --estabilizar
```

## Opciones

| Opción | Efecto |
|---|---|
| `--formato vertical / horizontal / cuadrado / original` | 1080×1920, 1920×1080, 1080×1080 |
| `--relleno recortar / desenfoque` | Recortar al centro o fondo desenfocado sin cortar al sujeto |
| `--cortar-silencios` `--margen 0.15s` | Quita pausas dejando un poco de aire |
| `--look natural / calido / frio / cine / ninguno` | Corrección y estilo de color |
| `--estabilizar` | Estabiliza tomas movidas (2 pasadas con vidstab) |
| `--subtitulos auto` o `--subtitulos archivo.srt` | Subtítulos quemados, 4 palabras por bloque, estilo redes |
| `--musica fondo.mp3 --volumen-musica 0.25` | Música que baja sola cuando hablas |
| `--logo logo.png` | Marca de agua en la esquina superior derecha |
| `--titulo "Texto" --color 0xF15A24` | Título animado con el color de marca |
| `--fade 0.5` | Fundido de entrada y salida |
| `--crf 18` `--preset slow` | Calidad de exportación (menor CRF = más calidad) |

## Qué hace automáticamente con el audio

1. Filtro paso alto y paso bajo (quita ruido grave y siseo)
2. Reducción de ruido de fondo (`afftdn`)
3. Compresor para que la voz suene pareja y con presencia
4. Normalización a **-14 LUFS** (estándar de Instagram, TikTok y YouTube)
5. Limitador final para que no sature

## Consejos para que se vea profesional

- **Graba bien:** luz de frente (ventana o aro), cámara a la altura de los ojos, micrófono cerca.
- **Hook en 3 segundos:** la primera frase debe enganchar; corta todo lo que vaya antes.
- **Ritmo:** usa `--cortar-silencios`; en redes, cada 2–4 s debería pasar algo (cambio de plano, texto, zoom).
- **Subtítulos siempre:** el 80 % ve los videos sin sonido.
- **Zona segura en Reels/TikTok:** evita texto en el 15 % inferior y superior (los botones lo tapan).
- **Música:** sin derechos de autor (biblioteca de YouTube, Pixabay, Epidemic Sound).
- **Exporta** en MP4 H.264, 30 fps, 1080p: es lo que mejor procesan las plataformas.

## Sistema visual TGH (según el video de referencia)

| Elemento | Especificación |
|---|---|
| Tipografía | **Poppins** — SemiBold (línea chica), Bold/ExtraBold (línea grande), tracking −5 % |
| Amarillo | `#FCFC00` con glow suave |
| Azul TGH | `#3B00EF` (pastillas y fondo duotono) |
| Verde | `#25D067` (pastilla "Solución", estilo WhatsApp) |
| Rojo | `#F03635` (fondo de énfasis negativo, palabra repetida x3) |
| Recursos | Subtítulo en 2 niveles, palabras a todo el ancho detrás de la persona (segmentación MediaPipe), efecto REC, stickers con borde blanco, flash blanco en cortes, tarjeta final TGH |

Render del reel: `python3 proyectos/tgh_3_errores.py crudo.mp4 referencia.mp4 proyectos/tgh_3_errores_transcripcion.json salida.mp4 selfie_multiclass.tflite`
(modelo: `storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite`; fuentes Poppins de github.com/google/fonts).

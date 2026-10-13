#!/usr/bin/env bash
# Instala todo lo necesario para editar video (Ubuntu/Debian).
set -e
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-montserrat fonts-roboto fonts-open-sans fonts-noto-color-emoji
pip install -r "$(dirname "$0")/requirements.txt"
# Modelo de subtítulos (requiere acceso a huggingface.co):
python3 -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
echo "✔ Entorno de edición listo"

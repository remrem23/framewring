#!/bin/bash
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "Install ffmpeg: sudo apt install ffmpeg"; echo "Установи ffmpeg: sudo apt install ffmpeg"; exit 1; }
python3 app.py

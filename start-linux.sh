#!/bin/bash
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "Установи ffmpeg: sudo apt install ffmpeg"; exit 1; }
python3 app.py

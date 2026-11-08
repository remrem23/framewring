#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] Python 3 не найден. Поставь: https://www.python.org/downloads/  (или: brew install python)"
  read -n1 -p "Нажми любую клавишу..."; exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x ./ffmpeg/bin/ffmpeg ] && [ ! -x ./ffmpeg ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "[!] FFmpeg не найден, ставлю через Homebrew..."; brew install ffmpeg
  else
    echo "[!] FFmpeg не найден. Поставь Homebrew (https://brew.sh), затем: brew install ffmpeg"
    read -n1 -p "Нажми любую клавишу..."; exit 1
  fi
fi
python3 app.py

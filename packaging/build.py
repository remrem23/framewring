"""Сборка Framewring.exe (PyInstaller, onedir) + FFmpeg рядом.

Запуск (из корня проекта):
    python -m venv build\\venv
    build\\venv\\Scripts\\python -m pip install pyinstaller pywebview pillow
    build\\venv\\Scripts\\python packaging\\build.py [--ffmpeg-dir ПАПКА_С_ffmpeg.exe]

Результат: build\\dist\\Framewring\\ (Framewring.exe, _internal\\, ffmpeg\\).
FFmpeg берётся из --ffmpeg-dir или из PATH (рекомендуется сборка Gyan: в ней x265, SVT-AV1, NVENC, libvmaf).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
BUILD = ROOT / "build"
DIST = BUILD / "dist" / "Framewring"

FFMPEG_NOTE = """FFmpeg в этой папке
===================

ffmpeg.exe и ffprobe.exe — программа FFmpeg (https://ffmpeg.org), сборка Gyan Doshi
(https://www.gyan.dev/ffmpeg/builds/), версия: {ver}.
Распространяется по лицензии GNU GPL v3 — её текст в файле LICENSE.txt рядом.

Исходный код FFmpeg: https://github.com/FFmpeg/FFmpeg
Архивы сборок Gyan и их исходники: https://github.com/GyanD/codexffmpeg/releases

Framewring вызывает FFmpeg как отдельную программу. Его можно заменить своей сборкой:
положи свои ffmpeg.exe и ffprobe.exe в эту папку вместо этих.
"""


def find_ffmpeg(arg):
    if arg:
        d = Path(arg)
        for c in (d, d / "bin"):
            if (c / "ffmpeg.exe").is_file() and (c / "ffprobe.exe").is_file():
                return c
        sys.exit("В %s нет ffmpeg.exe и ffprobe.exe" % d)
    w = shutil.which("ffmpeg")
    if not w:
        sys.exit("FFmpeg не найден в PATH: укажи --ffmpeg-dir")
    return Path(w).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffmpeg-dir")
    a = ap.parse_args()
    ff = find_ffmpeg(a.ffmpeg_dir)

    ico = PKG / "framewring.ico"
    if not ico.exists():
        subprocess.check_call([sys.executable, str(PKG / "make_icon.py")])

    subprocess.check_call([
        sys.executable, "-m", "PyInstaller", str(ROOT / "app.py"),
        "--name", "Framewring", "--onedir", "--windowed", "--noconfirm", "--clean",
        "--icon", str(ico),
        "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD / "work"), "--specpath", str(BUILD),
        "--exclude-module", "PIL",  # Pillow нужен только для иконки
    ])

    dst = DIST / "ffmpeg" / "bin"
    dst.mkdir(parents=True, exist_ok=True)
    for n in ("ffmpeg.exe", "ffprobe.exe"):
        shutil.copy2(ff / n, dst / n)
    lic = next((p for p in (ff / "LICENSE", ff.parent / "LICENSE", ff / "LICENSE.txt", ff.parent / "LICENSE.txt")
                if p.is_file()), None)
    if lic:
        shutil.copy2(lic, DIST / "ffmpeg" / "LICENSE.txt")
    else:
        print("ВНИМАНИЕ: не нашёл LICENSE рядом с FFmpeg — положи текст GPL в ffmpeg\\LICENSE.txt вручную")
    ver = subprocess.run([str(dst / "ffmpeg.exe"), "-hide_banner", "-version"], capture_output=True,
                         text=True).stdout.splitlines()[0]
    (DIST / "ffmpeg" / "README.txt").write_text(FFMPEG_NOTE.format(ver=ver), encoding="utf-8")

    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print("Готово: %s (%.0f МБ)" % (DIST, total / 1e6))


if __name__ == "__main__":
    main()

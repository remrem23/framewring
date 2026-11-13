"""Скачивает FFmpeg (сборка Gyan), указанный в packaging/ffmpeg.json, и сверяет SHA-256.

    python packaging/get_ffmpeg.py        -> печатает папку с ffmpeg.exe и ffprobe.exe

Результат: build/ffmpeg-<версия>/ (bin/ffmpeg.exe, bin/ffprobe.exe, LICENSE). Повторный запуск берёт уже скачанное.
Нужен для сборки на чистой машине (GitHub Actions): packaging/build.py --ffmpeg-dir <папка>.
"""
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "packaging" / "ffmpeg.json").read_text(encoding="utf-8"))
OUT = ROOT / "build" / ("ffmpeg-" + CFG["version"])
ZIP = ROOT / "build" / Path(CFG["url"]).name


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    if (OUT / "bin" / "ffmpeg.exe").is_file() and (OUT / "bin" / "ffprobe.exe").is_file():
        print(OUT)
        return
    ZIP.parent.mkdir(parents=True, exist_ok=True)
    if not ZIP.is_file() or sha256(ZIP) != CFG["sha256"]:
        print("Скачиваю", CFG["url"], file=sys.stderr)
        tmp = ZIP.with_suffix(".part")
        with urllib.request.urlopen(CFG["url"], timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        tmp.replace(ZIP)
    got = sha256(ZIP)
    if got != CFG["sha256"]:
        ZIP.unlink()
        sys.exit("SHA-256 архива FFmpeg не совпадает: %s, ожидалось %s" % (got, CFG["sha256"]))
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "bin").mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as z:
        for info in z.infolist():
            parts = info.filename.split("/")
            # внутри архива: ffmpeg-<версия>-full_build/bin/ffmpeg.exe, .../LICENSE
            rel = "/".join(parts[1:])
            if rel in ("bin/ffmpeg.exe", "bin/ffprobe.exe", "LICENSE"):
                with z.open(info) as src, open(OUT / rel, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    for n in ("bin/ffmpeg.exe", "bin/ffprobe.exe", "LICENSE"):
        if not (OUT / n).is_file():
            sys.exit("В архиве FFmpeg нет " + n)
    print(OUT)


if __name__ == "__main__":
    main()

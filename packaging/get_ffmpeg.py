"""Downloads the FFmpeg build (Gyan) specified in packaging/ffmpeg.json and verifies SHA-256.

    python packaging/get_ffmpeg.py        -> prints the folder with ffmpeg.exe and ffprobe.exe

Result: build/ffmpeg-<version>/ (bin/ffmpeg.exe, bin/ffprobe.exe, LICENSE). A repeated run reuses what is already downloaded.
Needed to build on a clean machine (GitHub Actions): packaging/build.py --ffmpeg-dir <folder>.
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
        print("Downloading", CFG["url"], file=sys.stderr)
        tmp = ZIP.with_suffix(".part")
        with urllib.request.urlopen(CFG["url"], timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        tmp.replace(ZIP)
    got = sha256(ZIP)
    if got != CFG["sha256"]:
        ZIP.unlink()
        sys.exit("SHA-256 of the FFmpeg archive does not match: %s, expected %s" % (got, CFG["sha256"]))
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "bin").mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as z:
        for info in z.infolist():
            parts = info.filename.split("/")
            # inside the archive: ffmpeg-<version>-full_build/bin/ffmpeg.exe, .../LICENSE
            rel = "/".join(parts[1:])
            if rel in ("bin/ffmpeg.exe", "bin/ffprobe.exe", "LICENSE"):
                with z.open(info) as src, open(OUT / rel, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    for n in ("bin/ffmpeg.exe", "bin/ffprobe.exe", "LICENSE"):
        if not (OUT / n).is_file():
            sys.exit("Not found in the FFmpeg archive: " + n)
    print(OUT)


if __name__ == "__main__":
    main()

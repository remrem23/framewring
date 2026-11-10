"""Релизные файлы из готовой сборки build\\dist\\Framewring (сначала packaging\\build.py):

    build\\release\\Framewring-<версия>-setup.exe     установщик (Inno Setup 6)
    build\\release\\Framewring-<версия>-portable.zip  портабл: данные в папке data рядом с exe
    build\\release\\SHA256SUMS.txt                    контрольные суммы

Запуск: python packaging\\release.py [--iscc ПУТЬ_К_ISCC.exe] [--no-setup] [--no-zip]
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
DIST = ROOT / "build" / "dist" / "Framewring"
OUT = ROOT / "build" / "release"

PORTABLE_NOTE = """Этот файл включает портабл-режим Framewring:
настройки, очередь и история хранятся в папке data рядом с Framewring.exe,
а не в %APPDATA%. Удалишь этот файл — программа начнёт хранить данные в %APPDATA%\\Framewring.
"""


def version():
    m = re.search(r'^__version__ = "([^"]+)"', (ROOT / "app.py").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def find_iscc(arg):
    cands = [arg] if arg else [
        shutil.which("ISCC"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%ProgramFiles%\Inno Setup 6\ISCC.exe"),
    ]
    for c in cands:
        if c and Path(c).is_file():
            return c
    sys.exit("Не найден ISCC.exe (Inno Setup 6): winget install JRSoftware.InnoSetup или --iscc ПУТЬ")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iscc")
    ap.add_argument("--no-setup", action="store_true")
    ap.add_argument("--no-zip", action="store_true")
    a = ap.parse_args()
    if not (DIST / "Framewring.exe").is_file():
        sys.exit("Нет сборки: сначала packaging\\build.py")
    if (DIST / "portable.txt").exists():
        sys.exit("В build\\dist\\Framewring лежит portable.txt — убери, иначе установленная версия станет портабл")
    ver = version()
    OUT.mkdir(parents=True, exist_ok=True)
    made = []

    if not a.no_setup:
        subprocess.check_call([find_iscc(a.iscc), "/Q", "/DAppVer=" + ver, str(PKG / "framewring.iss")])
        made.append(OUT / ("Framewring-%s-setup.exe" % ver))

    if not a.no_zip:
        z = OUT / ("Framewring-%s-portable.zip" % ver)
        top = "Framewring-%s" % ver
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for p in sorted(DIST.rglob("*")):
                if p.is_file():
                    zf.write(p, "%s/%s" % (top, p.relative_to(DIST).as_posix()))
            zf.writestr(top + "/portable.txt", PORTABLE_NOTE.replace("\n", "\r\n"))
        made.append(z)

    sums = OUT / "SHA256SUMS.txt"
    old = {}
    if sums.exists():
        for line in sums.read_text(encoding="utf-8").splitlines():
            if "  " in line:
                h, n = line.split("  ", 1)
                old[n] = h
    for p in made:
        old[p.name] = sha256(p)
    sums.write_text("".join("%s  %s\n" % (h, n) for n, h in sorted(old.items())
                            if (OUT / n).exists()), encoding="utf-8")
    for p in made:
        print("%-40s %7.1f МБ" % (p.name, p.stat().st_size / 1e6))
    print("Контрольные суммы:", sums)


if __name__ == "__main__":
    main()

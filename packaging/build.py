"""Сборка Framewring.exe (PyInstaller, onedir) + FFmpeg рядом.

Запуск (из корня проекта):
    py -3.12 -m venv build\\venv312          (Python 3.12+: свежий рантайм без устаревшего OpenSSL)
    build\\venv312\\Scripts\\python -m pip install pyinstaller pywebview pillow
    build\\venv312\\Scripts\\python packaging\\build.py [--ffmpeg-dir ПАПКА_С_ffmpeg.exe]

Результат: build\\dist\\Framewring\\ (Framewring.exe, _internal\\, ffmpeg\\).
FFmpeg берётся из --ffmpeg-dir или из PATH (рекомендуется сборка Gyan: в ней x265, SVT-AV1, NVENC, libvmaf).
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
BUILD = ROOT / "build"
DIST = BUILD / "dist" / "Framewring"

FFMPEG_NOTE = """FFmpeg in this folder
=====================

ffmpeg.exe and ffprobe.exe are FFmpeg (https://ffmpeg.org), build by Gyan Doshi
(https://www.gyan.dev/ffmpeg/builds/), version: {ver}.
Licensed under the GNU GPL v3 - see LICENSE.txt next to this file.

FFmpeg source code: https://github.com/FFmpeg/FFmpeg
Gyan build archives and sources: https://github.com/GyanD/codexffmpeg/releases

Framewring runs FFmpeg as a separate program. You can replace it with your own build:
put your ffmpeg.exe and ffprobe.exe into the bin folder instead of these.


FFmpeg в этой папке
===================

ffmpeg.exe и ffprobe.exe — программа FFmpeg (https://ffmpeg.org), сборка Gyan Doshi
(https://www.gyan.dev/ffmpeg/builds/), версия: {ver}.
Распространяется по лицензии GNU GPL v3 — её текст в файле LICENSE.txt рядом.

Исходный код FFmpeg: https://github.com/FFmpeg/FFmpeg
Архивы сборок Gyan и их исходники: https://github.com/GyanD/codexffmpeg/releases

Framewring вызывает FFmpeg как отдельную программу. Его можно заменить своей сборкой:
положи свои ffmpeg.exe и ffprobe.exe в папку bin вместо этих.
"""


VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v4}), prodvers=({v4}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Framewring'),
      StringStruct('FileDescription', 'Framewring - local video compressor'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'Framewring'),
      StringStruct('LegalCopyright', 'GNU GPL v3 - https://github.com/remrem23/framewring'),
      StringStruct('OriginalFilename', 'Framewring.exe'),
      StringStruct('ProductName', 'Framewring'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

# пакеты из сборки, чьи лицензии надо положить рядом (их тексты лежат в dist-info)
BUNDLED_PKGS = ("pywebview", "pythonnet", "clr_loader", "bottle", "proxy_tools", "cffi", "pycparser",
                "typing_extensions", "pyinstaller")


def app_version():
    m = re.search(r'^__version__ = "([^"]+)"', (ROOT / "app.py").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def copy_licenses():
    """Тексты лицензий всего, что входит в сборку: Python, пакеты, Tcl/Tk; FFmpeg — в своей папке."""
    import importlib.metadata as md
    out = DIST / "licenses"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", out / "Python-LICENSE.txt")
    for name in BUNDLED_PKGS:
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            print("нет пакета", name)
            continue
        files = [f for f in (dist.files or []) if re.search(r"(LICEN[CS]E|COPYING|NOTICE)", f.name, re.I)
                 and ".dist-info" in str(f)]
        for f in files:
            src = Path(dist.locate_file(f))
            if src.is_file():
                shutil.copy2(src, out / ("%s-%s" % (name, f.name if f.name.lower().endswith(".txt") else f.name + ".txt")))
        if not files:
            lic = dist.metadata.get("License") or dist.metadata.get("License-Expression") or "?"
            (out / ("%s-LICENSE.txt" % name)).write_text("%s %s: %s\n%s\n" % (
                name, dist.version, lic, dist.metadata.get("Home-page") or ""), encoding="utf-8")
    tk = DIST / "_internal" / "_tk_data" / "license.terms"
    if tk.is_file():
        shutil.copy2(tk, out / "Tcl-Tk-license.terms.txt")
    (out / "OpenSSL-NOTICE.txt").write_text(
        "OpenSSL (libssl/libcrypto, bundled with Python): Apache License 2.0\n"
        "https://www.openssl.org/source/license.html\n", encoding="utf-8")
    (out / "Microsoft-WebView2-NOTICE.txt").write_text(
        "Microsoft.Web.WebView2.Core.dll, Microsoft.Web.WebView2.WinForms.dll, WebView2Loader.dll\n"
        "Copyright (C) Microsoft Corporation. Redistributed as part of pywebview under the license of the\n"
        "Microsoft Edge WebView2 SDK: https://www.nuget.org/packages/Microsoft.Web.WebView2/ (License tab).\n",
        encoding="utf-8")


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

    v = app_version()
    nums = [int(x) for x in re.findall(r"\d+", v)[:3]] + [0]
    vf = BUILD / "version_info.txt"
    BUILD.mkdir(exist_ok=True)
    vf.write_text(VERSION_INFO.format(v=v, v4=", ".join(str(x) for x in (nums + [0, 0, 0])[:4])), encoding="utf-8")

    excl = []
    # Pillow — только для иконки. ssl не исключать: без него не грузится pywebview
    for m in ("PIL", "setuptools", "pkg_resources"):
        excl += ["--exclude-module", m]
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller", str(ROOT / "app.py"),
        "--name", "Framewring", "--onedir", "--windowed", "--noconfirm", "--clean", "--noupx",
        "--icon", str(ico), "--version-file", str(vf),
        "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD / "work"), "--specpath", str(BUILD),
    ] + excl)

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

    # своя лицензия, инструкция и уведомления о сторонних компонентах — рядом с exe
    shutil.copy2(ROOT / "LICENSE", DIST / "LICENSE.txt")
    for n in ("README.txt", "THIRD-PARTY-NOTICES.md"):
        if (ROOT / n).is_file():
            shutil.copy2(ROOT / n, DIST / n)
    copy_licenses()

    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print("Готово: %s (%.0f МБ)" % (DIST, total / 1e6))


if __name__ == "__main__":
    main()

"""Rebuilds PyInstaller with its bootloader compiled from source (used by the GitHub Actions build).

    python packaging/build_pyinstaller.py             -> compile the bootloader and install PyInstaller (fails without a compiler)
    python packaging/build_pyinstaller.py --optional  -> the same, but without a C compiler leaves the installed PyInstaller as is

Why: the ready-made bootloader inside the PyInstaller wheel is the same binary in thousands of programs
(malicious ones too), and antivirus heuristics fire on it. A bootloader compiled here is a different file.

What it does:
  1. takes the PyInstaller source archive from packaging/pyinstaller.json (same version as in
     packaging/requirements-build.txt) and checks its SHA-256, as get_ffmpeg.py does for FFmpeg;
  2. unpacks it to build/pyinstaller-src/ and compiles the bootloader (python ./waf configure all, MSVC);
  3. checks that the new run*.exe really differ from the ones shipped in the archive;
  4. installs that tree over the installed PyInstaller (pip install --no-deps) and checks that the installed
     bootloader is the compiled one.
Everything it does is printed, so the log shows that the bootloader was built from source.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
CFG = json.loads((PKG / "pyinstaller.json").read_text(encoding="utf-8"))
BUILD = ROOT / "build"
ARCHIVE = BUILD / Path(CFG["url"]).name
SRC = BUILD / "pyinstaller-src"
LOADERS = ("run.exe", "run_d.exe", "runw.exe", "runw_d.exe")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def have_compiler():
    """True if a Visual C++ compiler (x64) can be found: cl.exe in PATH or Visual Studio with the C++ tools."""
    if shutil.which("cl"):
        return True
    pf = os.environ.get("ProgramFiles(x86)")
    vswhere = Path(pf, "Microsoft Visual Studio", "Installer", "vswhere.exe") if pf else None
    if vswhere and vswhere.is_file():
        r = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires",
                            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                           capture_output=True, text=True)
        return bool(r.stdout.strip())
    return False


def pinned_version():
    """The pyinstaller version from requirements-build.txt - must be the same as in pyinstaller.json."""
    for line in (PKG / "requirements-build.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*pyinstaller\s*==\s*([^\s#]+)", line, re.I)
        if m:
            return m.group(1)
    return None


def fetch():
    BUILD.mkdir(exist_ok=True)
    if not ARCHIVE.is_file() or sha256(ARCHIVE) != CFG["sha256"]:
        print("Downloading", CFG["url"], flush=True)
        tmp = ARCHIVE.with_suffix(".part")
        with urllib.request.urlopen(CFG["url"], timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        tmp.replace(ARCHIVE)
    got = sha256(ARCHIVE)
    if got != CFG["sha256"]:
        ARCHIVE.unlink()
        sys.exit("SHA-256 of the PyInstaller archive does not match: %s, expected %s" % (got, CFG["sha256"]))
    print("PyInstaller %s source archive: SHA-256 %s (matches pyinstaller.json)" % (CFG["version"], got), flush=True)
    if SRC.exists():
        shutil.rmtree(SRC)
    SRC.mkdir(parents=True)
    with tarfile.open(ARCHIVE) as t:
        for m in t.getmembers():
            parts = m.name.split("/")
            m.name = "/".join(parts[1:])  # strip pyinstaller-<version>/
            if m.name:
                t.extract(m, SRC, filter="data")


def pe_info(p):
    try:
        import pefile
    except ImportError:
        return ""
    pe = pefile.PE(str(p), fast_load=True)
    try:
        return "linker %d.%d, timestamp %d" % (pe.OPTIONAL_HEADER.MajorLinkerVersion,
                                              pe.OPTIONAL_HEADER.MinorLinkerVersion, pe.FILE_HEADER.TimeDateStamp)
    finally:
        pe.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--optional", action="store_true",
                    help="without a C compiler leave the installed PyInstaller as is (exit code 0)")
    a = ap.parse_args()

    if pinned_version() != CFG["version"]:
        sys.exit("pyinstaller.json (%s) and requirements-build.txt (%s) have different PyInstaller versions"
                 % (CFG["version"], pinned_version()))
    if sys.platform != "win32":
        sys.exit("Only for Windows (the build of Framewring.exe)")
    if not have_compiler():
        msg = "No Visual C++ compiler found"
        if a.optional:
            print(msg + " - the standard PyInstaller bootloader stays", flush=True)
            return
        sys.exit(msg + " (install Visual Studio Build Tools with the 'Desktop development with C++' workload)")

    fetch()
    dest = SRC / "PyInstaller" / "bootloader" / "Windows-64bit-intel"
    before = {n: sha256(dest / n) for n in LOADERS if (dest / n).is_file()}
    if "runw.exe" not in before:
        sys.exit("The source archive has no ready runw.exe to compare with: " + str(dest))
    print("Bootloader from the archive: runw.exe SHA-256 %s (%s)" % (before["runw.exe"], pe_info(dest / "runw.exe")),
          flush=True)

    print("=== Compiling the bootloader from source: python ./waf configure all ===", flush=True)
    for n in LOADERS:
        (dest / n).unlink(missing_ok=True)  # so nothing old can pass for a new build
    rc = subprocess.call([sys.executable, "./waf", "configure", "all"], cwd=SRC / "bootloader")
    if rc:
        sys.exit("Compiling the PyInstaller bootloader failed (exit code %d)" % rc)
    after = {}
    for n in LOADERS:
        if not (dest / n).is_file():
            sys.exit("The compiler did not produce " + n)
        after[n] = sha256(dest / n)
        print("Compiled %-10s SHA-256 %s" % (n, after[n]), flush=True)
    if any(after[n] == before.get(n) for n in LOADERS):
        sys.exit("A compiled bootloader is identical to the one from the archive - not a fresh build")
    print("Compiled runw.exe (%s)" % pe_info(dest / "runw.exe"), flush=True)

    print("=== Installing PyInstaller %s with the compiled bootloader ===" % CFG["version"], flush=True)
    pip = [sys.executable, "-m", "pip", "--disable-pip-version-check"]
    # --no-deps: the other packages stay as pinned in requirements-build.txt.
    # The build hook sees the compiled bootloader and does not rebuild it (PYINSTALLER_COMPILE_BOOTLOADER is not set).
    env = {k: v for k, v in os.environ.items() if k != "PYINSTALLER_COMPILE_BOOTLOADER"}
    rc = subprocess.call(pip + ["install", "--no-deps", "--force-reinstall", "--no-cache-dir", str(SRC)], env=env)
    if rc:
        sys.exit("pip install of the rebuilt PyInstaller failed (exit code %d)" % rc)

    # the installed bootloader must be the compiled one
    out = subprocess.run([sys.executable, "-I", "-c",
                          "import PyInstaller, pathlib; print(pathlib.Path(PyInstaller.__file__).parent)"],
                         capture_output=True, text=True, cwd=BUILD)
    inst = Path(out.stdout.strip()) / "bootloader" / "Windows-64bit-intel"
    for n in LOADERS:
        if not (inst / n).is_file() or sha256(inst / n) != after[n]:
            sys.exit("The installed PyInstaller has a different %s than the compiled one: %s" % (n, inst))
    print("OK: installed PyInstaller %s uses the bootloader compiled from source (%s)" % (CFG["version"], inst),
          flush=True)
    print("OK: runw.exe SHA-256 %s (the standard one was %s)" % (after["runw.exe"], before["runw.exe"]), flush=True)


if __name__ == "__main__":
    main()

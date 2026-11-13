"""Shared helpers for the Framewring tests.

Every test script runs in its own process and works ONLY inside a fresh temporary folder:
  - a copy of app.py / i18n.py / locales/ is made there, so the program's data (settings, queue,
    history, backups) lands in that folder and never in the repository or in %APPDATA%;
  - the user profile (HOME / USERPROFILE) points to a folder inside it too;
  - test videos are generated with ffmpeg (lavfi), nothing from the user's disk is read.
Everything that went to the Windows Recycle Bin from the work folder is removed from the bin on exit.
Modes are CPU only (x265, av1 = SVT-AV1): no GPU, no Everything and no NVENC are needed.
"""
import atexit
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAST_SPEED = "fast"

# ----------------------------------------------------------------- Recycle Bin ----


def _long(p):
    """Long (not 8.3) real path - the Recycle Bin records the long form."""
    return os.path.realpath(p)


def clean_bin(prefix, dry=False):
    """Remove from the Recycle Bin ONLY entries whose original path is inside `prefix`. Returns the count."""
    if os.name != "nt":
        return 0
    prefix = os.path.normcase(_long(prefix)).rstrip("\/") + os.sep  # a folder, not a name prefix
    root = os.path.splitdrive(prefix)[0] + "\\"
    base = os.path.join(root, "$Recycle.Bin")
    n = 0
    try:
        sids = [os.path.join(base, d) for d in os.listdir(base)]
    except OSError:
        return 0
    for sd in sids:
        try:
            names = os.listdir(sd)
        except OSError:
            continue
        for f in names:
            if not f.startswith("$I"):
                continue
            ip = os.path.join(sd, f)
            try:
                with open(ip, "rb") as fh:
                    b = fh.read()
                if struct.unpack_from("<q", b, 0)[0] == 2:
                    ln = struct.unpack_from("<i", b, 24)[0]
                    path = b[28:28 + ln * 2].decode("utf-16-le").rstrip("\0")
                else:
                    path = b[24:24 + 520].decode("utf-16-le").split("\0")[0]
            except Exception:
                continue
            if os.path.normcase(path).startswith(prefix):
                if not dry:
                    for x in (os.path.join(sd, "$R" + f[2:]), ip):
                        try:
                            if os.path.isdir(x):
                                shutil.rmtree(x, ignore_errors=True)
                            else:
                                os.remove(x)
                        except OSError:
                            pass
                n += 1
    return n


# ------------------------------------------------------------------- Harness ----

class T:
    """One test run: work folder, imported app module, check() with a final verdict."""

    def __init__(self, name, need_bin=False):
        self.name = name
        self.ok = True
        self.fails = []
        self._cleaned = False
        self.work = self._make_work(need_bin)
        atexit.register(self.cleanup)
        self.prog = os.path.join(self.work, "prog")
        self.V = os.path.join(self.work, "vids")
        os.makedirs(self.V)
        os.makedirs(self.prog)
        for f in ("app.py", "i18n.py"):
            shutil.copy2(os.path.join(ROOT, f), os.path.join(self.prog, f))
        shutil.copytree(os.path.join(ROOT, "locales"), os.path.join(self.prog, "locales"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        home = os.path.join(self.work, "home")
        os.makedirs(os.path.join(home, "Documents"))
        for k in ("USERPROFILE", "HOME"):
            os.environ[k] = home
        sys.argv = ["x"]
        sys.path.insert(0, self.prog)
        os.chdir(self.work)
        import app  # the COPY inside the work folder
        self.app = app
        # safety guards (explicit, they must also work under python -O): never run against the real program folder
        if os.path.normcase(os.path.dirname(os.path.abspath(app.__file__))) != os.path.normcase(self.prog):
            raise SystemExit("SAFETY: app was imported from %s, not from the test copy" % app.__file__)
        if not os.path.normcase(str(app.DATA_DIR)).startswith(os.path.normcase(self.work)):
            raise SystemExit("SAFETY: program data folder %s is outside the work folder" % app.DATA_DIR)
        if not (app.FFMPEG and app.FFPROBE):
            raise SystemExit("ffmpeg/ffprobe not found in PATH")
        print("[%s] work folder: %s" % (name, self.work), flush=True)

    # work folder: temp dir; with need_bin - on a drive that has a usable Recycle Bin
    def _make_work(self, need_bin):
        cands = [tempfile.gettempdir()]
        if os.name == "nt":
            cands.append(os.environ.get("SystemDrive", "C:") + "\\")
        for base in cands:
            try:
                w = _long(tempfile.mkdtemp(prefix="fwtest_", dir=base))
            except OSError:
                continue
            if not need_bin or os.name != "nt" or self._bin_ok(w):
                return w
            shutil.rmtree(w, ignore_errors=True)
        raise SystemExit("no drive with a Recycle Bin available for the work folder")

    @staticmethod
    def _bin_ok(w):
        import ctypes
        root = os.path.splitdrive(w)[0] + "\\"
        return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 3  # DRIVE_FIXED

    def cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        try:
            os.chdir(tempfile.gettempdir())
        except OSError:
            pass
        n = clean_bin(self.work)
        if n:
            print("[%s] removed %d test item(s) from the Recycle Bin" % (self.name, n), flush=True)
        for _ in range(3):
            shutil.rmtree(self.work, ignore_errors=True)
            if not os.path.exists(self.work):
                break
            time.sleep(1)

    # ---- checks
    def check(self, name, cond, extra=""):
        cond = bool(cond)
        self.ok &= cond
        if not cond:
            self.fails.append(name)
        print("%-62s %s %s" % (name, "OK  " if cond else "FAIL", str(extra)[:110]), flush=True)

    def finish(self):
        print(("ALL OK" if self.ok else "FAILED: %s" % "; ".join(self.fails)), flush=True)
        self.cleanup()
        os._exit(0 if self.ok else 1)  # do not wait for the program's background threads

    # ---- video generation
    def ff(self, *a):
        subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *a], check=True)

    def mk(self, name, dur=4, size="854x480", rate=30, bitrate="12M", extra_in=(), extra=()):
        """Synthetic H.264 + AAC source with a bitrate high enough to be worth compressing."""
        path = os.path.join(self.V, name)
        self.ff("-f", "lavfi", "-i", "testsrc2=size=%s:rate=%d:duration=%s" % (size, rate, dur),
                "-f", "lavfi", "-i", "sine=frequency=500:duration=%s" % dur, *extra_in,
                "-c:v", "libx264", "-preset", "ultrafast", "-b:v", bitrate, "-c:a", "aac", *extra, path)
        return path

    # ---- app helpers
    def start(self):
        self.app.detect_caps()
        return self.app

    def settings(self, **kw):
        s = dict(self.app.SETTINGS, preset="x265", quality="balanced", speed=FAST_SPEED, outdir="", skip=False)
        s.update(kw)
        return s

    def compress(self, path, **kw):
        """Compress through the program's own pipeline (add_path + do_full). Returns the job."""
        app = self.app
        app.add_path(path)
        j = app.JOBS[-1]
        j["status"] = "running"
        app.do_full(j, self.settings(**kw))
        return j

    def compress_ok(self, path, **kw):
        j = self.compress(path, **kw)
        assert j["status"] == "done", (j["status"], j.get("error"), j.get("note"))
        return j

    def entry(self, src):
        app = self.app
        return next(h for h in reversed(app.HISTORY["items"]) if os.path.normcase(h["src"]) == os.path.normcase(src))

    def cand(self, src):
        app = self.app
        return next(c for c in app.replace_candidates() if os.path.normcase(c["src"]) == os.path.normcase(src))

    @staticmethod
    def keys(m):
        return [x["k"] for x in m]

    def wait_replace(self, limit=300):
        t0 = time.time()
        while self.app.REPLACE["running"]:
            if time.time() - t0 > limit:
                raise SystemExit("TIMEOUT: replace did not finish in %d s" % limit)
            time.sleep(0.3)

    def run_replace(self, src):
        app = self.app
        k = app._hkey(self.entry(src))
        app.replace_run([k])
        self.wait_replace()
        return app.REPLACE["items"][k]

    @staticmethod
    def free_letter(prefer="WVUTSRQP"):
        """A drive letter that is not in use (GetLogicalDrives bitmask), or None."""
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return next((c for c in prefer if not mask & (1 << (ord(c) - 65))), None)

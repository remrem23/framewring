#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Framewring - local video compressor with a web interface.
A wrapper around FFmpeg. Works only on your computer, files never leave it.
Requirements: Python 3.8+ and FFmpeg (in PATH or in an ffmpeg folder next to the script).
"""
import ctypes
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import hmac
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import i18n

__version__ = "0.9.3"
APP_NAMES = i18n.APP_NAMES  # window title (Russian name / plain name)
REPO_URL = "https://github.com/remrem23/framewring"  # official page of the program
DONATE_URL = REPO_URL + "/blob/main/DONATE.md"
EVERYTHING_URL = "https://www.voidtools.com/"
OPEN_URLS = (REPO_URL, DONATE_URL, EVERYTHING_URL)
RELEASES_URL = REPO_URL + "/releases/latest"
RELEASES_API = "https://api.github.com/repos/remrem23/framewring/releases/latest"
ISSUES_NEW = REPO_URL + "/issues/new"  # the interface may open only these links

FROZEN = bool(getattr(sys, "frozen", False))  # built into an .exe (PyInstaller)
APP_DIR = Path(__file__).resolve().parent  # code (in a build: the internal folder)
# Program folder: next to the exe in a build, next to app.py when run from source
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else APP_DIR


def _data_dir():
    """Where to keep settings, queue, history and cache.
    - run from source: next to app.py (as before, nothing is lost);
    - portable build (portable.txt next to the exe): a data folder next to the exe;
    - installed build: %APPDATA%\\Framewring (Program Files is not writable)."""
    if not FROZEN:
        return APP_DIR
    if (BASE_DIR / "portable.txt").exists():
        return BASE_DIR / "data"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home()) / "Framewring"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Framewring"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "framewring"


DATA_DIR = _data_dir()
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
SETTINGS_FILE = DATA_DIR / "settings.json"
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".ts", ".m2ts", ".m4v", ".wmv", ".mts"}
COPYABLE_AUDIO = {"aac", "mp3", "opus", "ac3", "eac3", "alac", "flac"}
TOKEN = secrets.token_hex(16)
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# ---------------------------------------------------------------- FFmpeg ----

def find_tool(name):
    exe = name + (".exe" if IS_WIN else "")
    for d in dict.fromkeys((BASE_DIR, APP_DIR)):  # next to exe/app.py, then inside the build
        for cand in (d / "ffmpeg" / "bin" / exe, d / "ffmpeg" / exe, d / exe):
            if cand.is_file():
                return str(cand)
    w = shutil.which(name)  # on Windows which also looks in the current folder - we don't want that
    return w if w and os.path.isabs(w) and Path(w).parent.resolve() != Path.cwd().resolve() else None


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")

NO_WINDOW = 0x08000000 if IS_WIN else 0
BELOW_NORMAL = 0x00004000


def run_quiet(args, timeout=60):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                          timeout=timeout, creationflags=NO_WINDOW,
                          universal_newlines=True, encoding="utf-8", errors="replace")


# ------------------------------------------------- Child processes ----
# On Windows, closing the console window kills Python, but ffmpeg (started without a window) would keep
# burning CPU and writing the .part file. A Job Object with KILL_ON_JOB_CLOSE kills it together with us.

_WIN_JOB = None


def _win_job():
    global _WIN_JOB
    if _WIN_JOB is not None:
        return _WIN_JOB or None
    _WIN_JOB = 0
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class EXT(ctypes.Structure):
            _fields_ = [("Basic", BASIC), ("Io", ctypes.c_uint64 * 6), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        h = k32.CreateJobObjectW(None, None)
        if h:
            info = EXT()
            info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if k32.SetInformationJobObject(h, 9, ctypes.byref(info), ctypes.sizeof(info)):
                _WIN_JOB = (k32, h)
    except Exception:
        pass
    return _WIN_JOB or None


def _posix_child_setup(lowprio):
    def f():
        if lowprio:
            try:
                os.nice(10)
            except Exception:
                pass
        if sys.platform.startswith("linux"):
            try:  # die together with the parent
                import ctypes
                import signal
                ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)
            except Exception:
                pass
    return f


def spawn(args, lowprio=False, **kw):
    """Popen for ffmpeg: no window, lowered priority, tied to the lifetime of the app."""
    if IS_WIN:
        kw["creationflags"] = NO_WINDOW | (BELOW_NORMAL if lowprio else 0)
    else:
        kw["preexec_fn"] = _posix_child_setup(lowprio)
    p = subprocess.Popen(args, **kw)
    if IS_WIN:
        j = _win_job()
        if j:
            try:
                j[0].AssignProcessToJobObject(j[1], int(p._handle))
            except Exception:
                pass
    return p


def avail_mem():
    """How much memory can really be allocated (bytes), or None if unknown."""
    try:
        if IS_WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                           [(n, ctypes.c_ulonglong) for n in ("TotalPhys", "AvailPhys", "TotalPageFile",
                                                              "AvailPageFile", "TotalVirtual", "AvailVirtual",
                                                              "AvailExtendedVirtual")]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                # AvailPageFile = free commit limit: when it runs out, allocation fails
                return min(m.AvailPageFile, m.AvailPhys + 2 * 2 ** 30)
        elif sys.platform.startswith("linux"):
            vals = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, _, v = line.partition(":")
                    vals[k] = int(v.split()[0]) * 1024
            return vals.get("MemAvailable", 0) + vals.get("SwapFree", 0) or None
    except Exception:
        pass
    return None


def pagefile_off():
    """Windows without a page file: the memory limit equals the RAM size, and on spikes ffmpeg fails with
    "Cannot allocate memory" even when plenty of physical memory is still free."""
    if not IS_WIN:
        return False
    try:
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                       [(n, ctypes.c_ulonglong) for n in ("TotalPhys", "AvailPhys", "TotalPageFile",
                                                          "AvailPageFile", "TotalVirtual", "AvailVirtual",
                                                          "AvailExtendedVirtual")]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return m.TotalPageFile - m.TotalPhys < 2 * 2 ** 30
    except Exception:
        pass
    return False


def svt_lp_for(info):
    """By default SVT-AV1 at 3440x1440 wants ~6.6 GB. If there is not that much, it fails with
    'allocate memory failed'. We pick the parallelism level (lp) to fit the free memory."""
    budget = avail_mem()
    if not budget or not info:
        return None
    budget *= 0.95
    mp = max(1, (info.get("width") or 1920) * (info.get("height") or 1080)) / 1e6

    def need(lp):  # measured on SVT-AV1 4.x, 10 bit, preset 6
        return (mp * (0.25 * lp + 0.07) + 0.3) * 2 ** 30
    if need(5) <= budget:
        return None  # enough for the default settings
    for lp in (4, 3, 2):
        if need(lp) <= budget:
            return lp
    return 1


# ---------------------------------------------------------------- Texts ----
# Everything the user sees is passed by the backend as a key with parameters: {"k": key, "p": {...}}.
# The page translates it (dictionary from i18n.py), so notes and errors in queue.json are not tied
# to a language and are shown in the new one after switching. Raw ffmpeg/OS texts are plain strings.

def M(key, **p):
    return {"k": key, "p": p}


class UserError(RuntimeError):
    """Error for the user: translation key + parameters."""

    def __init__(self, key, **p):
        super().__init__(key)
        self.k, self.p = key, p

    def msg(self):
        return M(self.k, **self.p)

    def __str__(self):
        return i18n.t(cur_lang(), self.k, **self.p)


def err_msg(e):
    """Exception -> what we put into job["error"]."""
    return e.msg() if isinstance(e, UserError) else str(e)


def add_note(job, m):
    """Add a note to the job (there can be several)."""
    cur = job.get("note")
    job["note"] = m if not cur else (cur if isinstance(cur, list) else [cur]) + [m]


SYS_LANG = i18n.sys_lang()


def cur_lang():
    return SETTINGS.get("lang") or SYS_LANG


def tr(key, **p):
    """Translation into the current language: for system windows and the console."""
    return i18n.t(cur_lang(), key, **p)


def app_name():
    return i18n.app_name(cur_lang())


# Presets (display order). Titles and descriptions: i18n.py, keys preset.<code>.title/.desc
PRESETS = ("nvenc_av1", "nvenc_hevc", "amf_av1", "amf_hevc", "qsv_av1", "qsv_hevc", "vt_hevc", "x265", "av1")
HW_VENDOR = {"nvenc": "nvidia", "amf": "amd", "qsv": "intel"}  # GPU mode -> vendor
# What to recommend: the video card, if present. The CPU compresses slightly tighter, but an order of magnitude slower.
# AV1 on AMD and Intel is below H.265 until tested on real video cards
RECOMMEND = ("nvenc_av1", "nvenc_hevc", "amf_hevc", "qsv_hevc", "amf_av1", "qsv_av1", "vt_hevc", "x265", "av1")

# Quality: high / balanced / compact
QUALITY = {
    "x265": {"high": 20, "balanced": 22, "compact": 24},
    "av1": {"high": 27, "balanced": 30, "compact": 33},
    "nvenc_hevc": {"high": 22, "balanced": 24, "compact": 27},
    "nvenc_av1": {"high": 27, "balanced": 30, "compact": 33},
    "vt_hevc": {"high": 70, "balanced": 62, "compact": 55},
    # AMD: constant QP. Measured (10 bit, same clip): QP 22/24/27 ~ NVENC CQ 22/24/27 in size and VMAF
    "amf_hevc": {"high": 22, "balanced": 24, "compact": 27},
    # AMF AV1 uses a 0-255 scale (~4x HEVC QP); not yet tested on a real RX 7000
    "amf_av1": {"high": 108, "balanced": 120, "compact": 132},  # ~4x of the 0-63 scale, like CQ 27/30/33 of other AV1 encoders
    # Intel: ICQ 1-51; not yet tested on real hardware
    "qsv_hevc": {"high": 22, "balanced": 24, "compact": 27},
    "qsv_av1": {"high": 24, "balanced": 27, "compact": 30},
}
SPEED = {
    "x265": {"slow": "slow", "normal": "medium", "fast": "fast"},
    "av1": {"slow": "4", "normal": "6", "fast": "8"},
    # NVENC: (preset, multipass). Measured at 2560x1440: p6+fullres is 2x slower than p5+qres with the same
    # size and VMAF, so "Normal" = p5+qres.
    "nvenc_hevc": {"slow": ("p7", "fullres"), "normal": ("p5", "qres"), "fast": ("p4", "disabled")},
    "nvenc_av1": {"slow": ("p7", "fullres"), "normal": ("p5", "qres"), "fast": ("p4", "disabled")},
    "vt_hevc": {"slow": None, "normal": None, "fast": None},
    "amf_hevc": {"slow": "quality", "normal": "balanced", "fast": "speed"},
    "amf_av1": {"slow": "quality", "normal": "balanced", "fast": "speed"},
    "qsv_hevc": {"slow": "slower", "normal": "medium", "fast": "faster"},
    "qsv_av1": {"slow": "slower", "normal": "medium", "fast": "faster"},
}
MEM_ERR = re.compile(r"allocate memory|insufficient resources|cannot allocate memory|out[ _]of[ _]memory", re.I)


def video_args(preset, quality, speed, lp=None):
    q = QUALITY[preset][quality]
    s = SPEED[preset][speed]
    if preset == "x265":
        return ["-c:v", "libx265", "-preset", s, "-crf", str(q), "-pix_fmt", "yuv420p10le",
                "-x265-params", "aq-mode=3:log-level=error", "-tag:v", "hvc1"]
    if preset == "av1":
        return ["-c:v", "libsvtav1", "-preset", s, "-crf", str(q), "-pix_fmt", "yuv420p10le",
                "-g", "300", "-svtav1-params", "tune=0" + (":lp=%d" % lp if lp else "")]
    if preset == "nvenc_hevc":
        return ["-c:v", "hevc_nvenc", "-preset", s[0], "-tune", "hq", "-rc", "vbr", "-cq", str(q), "-b:v", "0",
                "-multipass", s[1], "-spatial-aq", "1", "-temporal-aq", "1", "-rc-lookahead", "32",
                "-profile:v", "main10", "-pix_fmt", "p010le", "-tag:v", "hvc1"]
    if preset == "nvenc_av1":
        return ["-c:v", "av1_nvenc", "-preset", s[0], "-tune", "hq", "-rc", "vbr", "-cq", str(q), "-b:v", "0",
                "-multipass", s[1], "-spatial-aq", "1", "-rc-lookahead", "32", "-pix_fmt", "p010le"]
    if preset == "amf_hevc":  # 10 bit: in 8 bit AMF damaged the picture (VMAF 56 vs 99 in the measurement)
        return ["-c:v", "hevc_amf", "-usage", "transcoding", "-quality", s, "-rc", "cqp", "-qp_i", str(q),
                "-qp_p", str(q), "-profile:v", "main10", "-pix_fmt", "p010le", "-tag:v", "hvc1"]
    if preset == "amf_av1":
        return ["-c:v", "av1_amf", "-usage", "transcoding", "-quality", s, "-rc", "cqp", "-qp_i", str(q),
                "-qp_b", str(q),
                "-qp_p", str(q), "-pix_fmt", "p010le"]
    if preset == "qsv_hevc":
        return ["-c:v", "hevc_qsv", "-preset", s, "-global_quality", str(q), "-profile:v", "main10",
                "-pix_fmt", "p010le", "-tag:v", "hvc1"]
    if preset == "qsv_av1":
        return ["-c:v", "av1_qsv", "-preset", s, "-global_quality", str(q), "-pix_fmt", "p010le"]
    if preset == "vt_hevc":
        return ["-c:v", "hevc_videotoolbox", "-q:v", str(q), "-profile:v", "main10", "-pix_fmt", "p010le",
                "-tag:v", "hvc1"]
    raise ValueError(preset)


CAPS = {"ffmpeg": bool(FFMPEG), "ffprobe": bool(FFPROBE), "version": "", "presets": {}, "vmaf": False,
        "checked": False, "recommended": "", "pagefile_off": pagefile_off()}


def gpu_names():
    """Video card names from the driver descriptions in the registry (no WMI - it can be very slow).
    Virtual monitors and the like are dropped: only Nvidia / AMD / Intel."""
    names = []
    if not IS_WIN:
        return names
    try:
        import winreg
        base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            for i in range(64):
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                try:
                    with winreg.OpenKey(k, sub) as sk:
                        desc = str(winreg.QueryValueEx(sk, "DriverDesc")[0]).strip()
                except OSError:
                    continue
                low = desc.lower()
                if any(x in low for x in ("nvidia", "radeon", "amd", "intel")) and desc not in names:
                    names.append(desc)
    except Exception:
        pass
    return names


def gpu_vendors():
    """Which video cards are installed: nvidia / amd / intel."""
    found = set()
    for desc in gpu_names():
        d = desc.lower()
        if "nvidia" in d:
            found.add("nvidia")
        if "radeon" in d or "amd" in d:
            found.add("amd")
        if "intel" in d and ("graphics" in d or "arc" in d or "uhd" in d or "iris" in d):
            found.add("intel")
    return found


def detect_caps():
    if not FFMPEG:
        CAPS["checked"] = True
        return
    try:
        CAPS["version"] = run_quiet([FFMPEG, "-hide_banner", "-version"]).stdout.splitlines()[0]
        enc = run_quiet([FFMPEG, "-hide_banner", "-encoders"]).stdout
        flt = run_quiet([FFMPEG, "-hide_banner", "-filters"]).stdout
    except Exception:
        enc = flt = ""
    CAPS["vmaf"] = bool(re.search(r"\blibvmaf\b", flt))
    need = {"x265": "libx265", "av1": "libsvtav1", "nvenc_hevc": "hevc_nvenc",
            "nvenc_av1": "av1_nvenc", "vt_hevc": "hevc_videotoolbox", "amf_hevc": "hevc_amf",
            "amf_av1": "av1_amf", "qsv_hevc": "hevc_qsv", "qsv_av1": "av1_qsv"}
    vendors = gpu_vendors()

    def check(p, name):
        if not re.search(r"\b%s\b" % name, enc):
            return {"ok": False, "why": M("caps.no_encoder")}
        if p in ("x265", "av1"):
            return {"ok": True, "why": ""}
        # Check that the hardware really can do it, with the same flags
        try:
            r = run_quiet([FFMPEG, "-hide_banner", "-v", "error", "-f", "lavfi", "-i",
                           "color=black:s=1920x1080:r=30:d=0.5"] + video_args(p, "balanced", "normal")
                          + ["-f", "null", "-"], timeout=30)
            ok = r.returncode == 0
            return {"ok": ok, "why": "" if ok else M("caps.hw_unsupported")}
        except Exception:
            return {"ok": False, "why": M("caps.check_failed")}

    # hardware checks in parallel: faster startup
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(need)) as ex:
        res = {p: ex.submit(check, p, name) for p, name in need.items()}
    pres = {p: res[p].result() for p in need}
    for p, c in pres.items():
        # show: the CPU always; the video card if it works, and if not - only when such a
        # card is installed (so it is clear why it is unavailable). Other vendors do not clutter the list.
        v = HW_VENDOR.get(p.split("_")[0])
        c["show"] = p in ("x265", "av1") or c["ok"] or (v is not None and v in vendors)
    CAPS["presets"] = pres  # whole at once, so /api/status never sees a half-filled dict
    CAPS["recommended"] = next((p for p in RECOMMEND if CAPS["presets"][p]["ok"]), "")
    with LOCK:
        # first run (mode never chosen yet) or the chosen mode is unavailable -> the recommended one
        if (not PRESET_CHOSEN or not CAPS["presets"].get(SETTINGS["preset"], {}).get("ok")) and CAPS["recommended"]:
            SETTINGS["preset"] = CAPS["recommended"]
    CAPS["checked"] = True


def probe(path):
    r = run_quiet([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    if r.returncode != 0:
        tail = r.stderr.strip()[-400:]
        if tail:
            raise RuntimeError(tail)
        raise UserError("err.probe_failed")
    d = json.loads(r.stdout)
    fmt = d.get("format", {})
    info = {"duration": float(fmt.get("duration") or 0), "bitrate": int(fmt.get("bit_rate") or 0),
            "vcodec": "", "width": 0, "height": 0, "fps": 0, "vbitrate": 0, "audio": [], "subs": [],
            "interlaced": False}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and not info["vcodec"] and s.get("disposition", {}).get("attached_pic", 0) == 0:
            info["vcodec"] = s.get("codec_name", "")
            info["width"], info["height"] = s.get("width", 0), s.get("height", 0)
            try:
                n, dd = (s.get("avg_frame_rate") or "0/1").split("/")
                info["fps"] = round(float(n) / float(dd), 2) if float(dd) else 0
            except Exception:
                pass
            info["vbitrate"] = int(s.get("bit_rate") or 0)
            # AVCHD cameras (.mts), TV recordings: 1080i. Without deinterlacing the result keeps "combing"
            info["interlaced"] = s.get("field_order") in ("tt", "bb", "tb", "bt")
            if not info["duration"]:
                info["duration"] = float(s.get("duration") or 0)
        elif s.get("codec_type") == "subtitle":
            info["subs"].append(s.get("codec_name", ""))
        elif s.get("codec_type") == "audio":
            info["audio"].append({"codec": s.get("codec_name", ""), "channels": s.get("channels", 0),
                                  "rate": int(s.get("sample_rate") or 0), "bitrate": int(s.get("bit_rate") or 0)})
    if not info["vcodec"]:
        raise UserError("err.no_video")
    return info


# ----------------------------------------------------------------- State ----

LOCK = threading.RLock()
JOBS = []
WAKE = threading.Event()
CUR = {"proc": None, "cancel": False, "part": None}
DEFAULT_SETTINGS = {"preset": "x265", "quality": "balanced", "speed": "normal", "audio": "auto",
                    "outdir": "", "lowprio": True, "nosleep": True, "skip": True, "testlen": 120,
                    "update_check": True,
                    "lang": ""}  # lang: "" = as in the system, otherwise "ru" / "en"


def _backup_dir():
    """Backups are kept apart from the data folder: the installed version keeps them in %LOCALAPPDATA%,
    so even a completely deleted %APPDATA%\\Framewring is restored at startup."""
    if FROZEN and IS_WIN and not (BASE_DIR / "portable.txt").exists():
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Framewring" / "backup"
    return DATA_DIR / "backup"


BACKUP_DIR = _backup_dir()
BACKUP_KEEP = 3
_BK_LAST = {}


def _backup(path, text, every=0):
    """Copy of a data file in BACKUP_DIR: <name>.1.json is the newest, up to BACKUP_KEEP copies.
    every - no more often than once per this many seconds (the queue is saved every 2 s)."""
    now = time.time()
    if every and now - _BK_LAST.get(path.name, 0) < every:
        return
    _BK_LAST[path.name] = now
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        newest = BACKUP_DIR / ("%s.1.json" % path.stem)
        if newest.exists() and newest.read_text(encoding="utf-8") == text:
            return
        for i in range(BACKUP_KEEP, 1, -1):
            a = BACKUP_DIR / ("%s.%d.json" % (path.stem, i - 1))
            if a.exists():
                os.replace(str(a), str(BACKUP_DIR / ("%s.%d.json" % (path.stem, i))))
        tmp = newest.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(newest))
    except Exception as e:
        print(" backup %s: %s" % (path.name, e))


_WRITE_LOCK = threading.RLock()


def write_json(path, text, backup_every=0):
    """Atomic write (via a temp file) + backup. One write at a time: history can be
    updated concurrently from compression and from replacement."""
    with _WRITE_LOCK:
        tmp = path.with_name("%s.%d.tmp" % (path.name, threading.get_ident()))
        tmp.write_text(text, encoding="utf-8")
        for i in range(10):
            try:
                os.replace(str(tmp), str(path))
                break
            except PermissionError:  # the file is briefly held by an antivirus/indexer
                if i == 9:
                    raise
                time.sleep(0.2)
        _backup(path, text, backup_every)


def read_json(path, kind):
    """Reads a data file; if it is missing or corrupted - the newest intact backup.
    Returns (data, from_backup)."""
    cands = [path] + [BACKUP_DIR / ("%s.%d.json" % (path.stem, i)) for i in range(1, BACKUP_KEEP + 1)]
    for i, c in enumerate(cands):
        try:
            d = json.loads(c.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, kind):
            if i:
                print(" %s: восстановлено из резервной копии %s" % (path.name, c))
            return d, bool(i)
    return None, False


_RAW_SETTINGS = None


def load_settings():
    global _RAW_SETTINGS
    s = dict(DEFAULT_SETTINGS)
    raw, from_bak = read_json(SETTINGS_FILE, dict)
    _RAW_SETTINGS = raw or {}
    s.update(_RAW_SETTINGS)
    if from_bak:
        try:
            SETTINGS_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
    return s


SETTINGS = load_settings()


def save_settings():
    try:
        write_json(SETTINGS_FILE, json.dumps(SETTINGS, ensure_ascii=False, indent=1))
    except Exception:
        pass


def clean_settings(b):
    """Accept only valid values: garbage in settings.json must not break compression."""
    out = {}
    for k, v in b.items():
        if k not in DEFAULT_SETTINGS:
            continue
        if k in ("preset", "quality", "speed", "audio", "outdir", "lang") and not isinstance(v, str):
            continue
        if k == "lang" and v not in ("",) + i18n.LANGS:
            continue
        if k == "preset" and v not in PRESETS:
            continue
        if k == "quality" and v not in ("high", "balanced", "compact"):
            continue
        if k == "speed" and v not in ("slow", "normal", "fast"):
            continue
        if k == "audio" and v not in ("auto", "aac"):
            continue
        if k in ("lowprio", "nosleep", "skip", "update_check"):
            v = bool(v)
        if k == "outdir":
            v = os.path.expandvars(os.path.expanduser(v.strip().strip('"').strip("'")))
            if v and not os.path.isabs(v):  # "out" or "D:video" would end up in the program folder
                continue
        if k == "testlen":
            try:
                v = max(10.0, min(1800.0, float(v)))
            except (TypeError, ValueError):
                continue
        out[k] = v
    return out


_raw = dict(SETTINGS)
try:
    PRESET_CHOSEN = "preset" in (_RAW_SETTINGS or {})
except Exception:
    PRESET_CHOSEN = False
SETTINGS.clear()
SETTINGS.update(DEFAULT_SETTINGS)
SETTINGS.update(clean_settings(_raw))

_next_id = [1]
OUT_OWNERS = {}  # result path -> source (so two different files never write to one .mp4)


def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def add_path(p):
    p = p.strip().strip('"').strip("'")
    if not p:
        return []
    path = Path(os.path.expanduser(p))
    if path.is_dir():
        files = sorted((f for f in path.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXT
                        and not f.name.lower().endswith(".part.mp4")), key=lambda f: f.name.lower())
    elif path.is_file():
        files = [path]
    else:
        return [{"error": M("err.not_found_path", path=p)}]
    new = []
    with LOCK:
        busy = {_norm(j["path"]) for j in JOBS if j["status"] not in ("done", "skipped")}
        for f in files:
            if _norm(f) in busy:
                continue
            try:
                size = f.stat().st_size
            except OSError as e:
                new.append({"error": "%s: %s" % (f.name, e)})
                continue
            job = {"id": _next_id[0], "path": str(f), "name": f.name, "size": size,
                   "status": "probing", "info": None, "error": "", "note": "", "pct": 0, "fps": 0, "speed": 0,
                   "eta": None, "cur_size": 0, "elapsed": 0, "phase": "", "out_path": "", "out_size": 0,
                   "test": None, "settings": None, "mode": None}
            _next_id[0] += 1
            JOBS.append(job)
            busy.add(_norm(f))
            new.append(job)

    def do_probe(job):
        try:
            info = probe_cached(job["path"])
            with LOCK:
                job["info"] = info
                if job["status"] == "probing":
                    job["status"] = "ready"
        except Exception as e:
            with LOCK:
                job["status"], job["error"] = "error", err_msg(e)

    jobs = [j for j in new if "id" in j]
    if jobs:  # ffprobe in parallel: a folder of 100 files is added in seconds, not a minute
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as ex:
            list(ex.map(do_probe, jobs))
    return [j if "error" in j and "id" not in j else j["id"] for j in new]


def out_dir_for(job, s):
    if s.get("outdir"):
        return Path(os.path.expanduser(s["outdir"]))
    return Path(job["path"]).parent / "compressed"


def _same_dir(a, b):
    """The same folder, even under a different name (junction, mapped drive, 8.3 short name)."""
    try:
        return os.path.samefile(str(a), str(b))
    except OSError:
        return _norm(a) == _norm(b)


def _same_file(a, b):
    try:
        return os.path.samefile(str(a), str(b))
    except OSError:
        return _norm(a) == _norm(b)


def out_path_for(job, s):
    """Where to write the result. Main rule: never overwrite someone else's file, let alone the original."""
    d = out_dir_for(job, s)
    src = Path(job["path"])
    ks = _norm(src)
    same = _same_dir(d, src.parent)
    stem = src.stem
    if same:
        # writing next to the originals: "clip.mkv" -> "clip.mp4" would overwrite an original "clip.mp4" lying there
        # (OBS leaves files like that after a remux). So always with a suffix.
        stem += "_compressed"
    else:
        # "clip.mkv" and "clip.mov" in one folder would give the same "clip.mp4". We tell them apart by extension.
        try:
            low = src.stem.lower()
            if any(f.stem.lower() == low and f.suffix.lower() in VIDEO_EXT and f.suffix.lower() != src.suffix.lower()
                   for f in src.parent.iterdir()):
                stem = "%s_%s" % (src.stem, src.suffix.lstrip(".").lower())
        except OSError:
            pass
    # Shared folder of someone else (set in "Save to"): a file with no known owner is treated as foreign -
    # identical names from different memory cards (GH010001.MP4) are very common.
    shared = bool(s.get("outdir")) and not same
    o = base = d / (stem + ".mp4")
    n = 2
    with LOCK:
        while True:
            owner = OUT_OWNERS.get(_norm(o))
            if owner == ks:
                break
            if owner is None and not _same_file(o, src) and not (shared and o.exists()):
                break
            o = base.with_name("%s (%d).mp4" % (base.stem, n))
            n += 1
    return o


def audio_args(job, s):
    if s.get("audio") == "aac":
        return ["-c:a", "aac", "-b:a", "192k"]
    codecs = {a["codec"] for a in (job["info"] or {}).get("audio", [])}
    if codecs and not codecs <= COPYABLE_AUDIO:
        return ["-c:a", "aac", "-b:a", "192k"]
    return ["-c:a", "copy"]


# --------------------------------------------------------------- Scanner ----
# Search for heavy videos on the disks: folder walk, ffprobe of candidates, estimate of savings.

SKIP_DIRS = {
    # system
    "windows", "program files", "program files (x86)", "programdata", "appdata", "system volume information",
    "recovery", "msocache", "perflogs", "windowsapps", "winsxs", "$recycle.bin", "config.msi",
    # service / development
    "node_modules", "__pycache__", "venv", "site-packages", "dist-packages", "deriveddatacache", "ue-cache",
    # our own results
    "compressed", "_tests",
    # games: their videos must not be touched, or the game breaks
    "steamapps", "steamlibrary", "epic games", "riot games", "xboxgames", "gog games", "gog galaxy",
    "origin games", "ea games", "ubisoft game launcher", "battle.net", "games",
}
if not IS_WIN:
    SKIP_DIRS |= {"library", "applications", "system", "private", "proc", "sys", "dev", "usr", "bin", "sbin",
                  "lib", "lib64", "etc", "var", "run", "snap", "boot", "opt", "tmp"}
FILE_ATTR_REPARSE = 0x400
FILE_ATTR_CLOUD = 0x400000 | 0x40000 | 0x1000  # OneDrive "online only" / offline: reading would download the file
EFFICIENT = {"hevc", "av1", "vp9", "vvc"}

SCAN = {"running": False, "cancel": False, "phase": "", "dirs": 0, "cur": "", "candidates": 0, "probed": 0,
        "results": [], "ver": 0, "error": "", "finished": False, "skipped_cloud": 0, "method": [], "t0": 0,
        "took": 0, "ev_missing": False}
PROBE_CACHE = {}


def probe_cached(path):
    st = os.stat(path)
    key = _norm(path)
    c = PROBE_CACHE.get(key)
    if c and c[0] == (st.st_size, st.st_mtime):
        return c[1]
    info = probe(path)
    PROBE_CACHE[key] = ((st.st_size, st.st_mtime), info)
    return info


def _disk_usage_timeout(path, timeout):
    box = {}

    def f():
        try:
            box["v"] = shutil.disk_usage(path)
        except OSError:
            pass
    t = threading.Thread(target=f, daemon=True)
    t.start()
    t.join(timeout)
    return box.get("v")


def list_drives():
    out = []
    if IS_WIN:
        import ctypes
        import string
        k32 = ctypes.windll.kernel32
        mask = k32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if not (mask >> i) & 1:
                continue
            root = "%s:\\" % letter
            t = k32.GetDriveTypeW(ctypes.c_wchar_p(root))
            if t not in (2, 3, 4):  # removable, local, network
                continue
            du = _disk_usage_timeout(root, 2.0)  # a disconnected network drive takes tens of seconds to answer
            if du is None:
                continue
            out.append({"path": root, "label": letter + ":", "total": du.total, "free": du.free,
                        "net": t == 4, "removable": t == 2})
    else:
        import glob
        cands = [str(Path.home())] + sorted(glob.glob("/Volumes/*") if IS_MAC else
                                            glob.glob("/media/*/*") + glob.glob("/mnt/*"))
        for c in cands:
            if IS_MAC and os.path.realpath(c) == "/":
                continue
            try:
                du = shutil.disk_usage(c)
            except OSError:
                continue
            out.append({"path": c, "label": M("drive.home") if c == str(Path.home()) else os.path.basename(c),
                        "total": du.total, "free": du.free, "net": False, "removable": False})
    return out


def estimate(info, size):
    """Rough estimate of the size after "Quality - H.265 - Balanced". The exact forecast comes from "Test"."""
    dur = info.get("duration") or 0
    if dur <= 0 or size <= 0:
        return size
    w, h = info.get("width") or 1920, info.get("height") or 1080
    fps = min(max(info.get("fps") or 30, 1), 120)
    total_br = info.get("bitrate") or size * 8 / dur
    audio_src = sum(a.get("bitrate") or 160000 for a in info.get("audio", []))
    audio_out = sum((a.get("bitrate") or 160000) if a.get("codec") in COPYABLE_AUDIO else 192000
                    for a in info.get("audio", []))
    v_src = info.get("vbitrate") or max(total_br - audio_src, total_br * 0.5)
    # ~3 Mbit/s for 1080p30, grows slower than the number of pixels per second
    target = 3.0e6 * (w * h * fps / (1920 * 1080 * 30.0)) ** 0.75
    if info.get("vcodec") in EFFICIENT:
        target = max(target, v_src * 0.75)  # already a modern codec: not much can be squeezed out
    v_out = min(v_src, target)
    est = dur * (v_out + audio_out) / 8
    return int(min(size, est))


# Query to an already running Everything (voidtools) through its IPC (EV_WM_COPYDATA, QUERY2).
# No DLL and no es.exe: ctypes only.

EV_WM_COPYDATA = 0x004A
COPYDATA_QUERY2W = 18
REQ_FULL_PATH = 0x00000004
REQ_SIZE = 0x00000010
REQ_ATTRIBUTES = 0x00000100
REPLY_ID = 0x5A48  # our arbitrary reply identifier

LRESULT = ctypes.c_ssize_t
WNDPROC = (ctypes.WINFUNCTYPE if IS_WIN else ctypes.CFUNCTYPE)(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class EV_COPYDATA(ctypes.Structure):
    _fields_ = [("dwData", ctypes.c_size_t), ("cbData", wintypes.DWORD), ("lpData", ctypes.c_void_p)]


class EV_WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


def _ev_api():
    u = ctypes.WinDLL("user32", use_last_error=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    u.FindWindowW.restype = wintypes.HWND
    u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.CreateWindowExW.restype = wintypes.HWND
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                  wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    u.DefWindowProcW.restype = LRESULT
    u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.SendMessageTimeoutW.restype = LRESULT
    u.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                      wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    u.PeekMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    u.MsgWaitForMultipleObjects.argtypes = [wintypes.DWORD, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                                            wintypes.DWORD]
    u.DestroyWindow.argtypes = [wintypes.HWND]
    u.RegisterClassW.argtypes = [ctypes.POINTER(EV_WNDCLASS)]
    u.ChangeWindowMessageFilterEx.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.DWORD, ctypes.c_void_p]
    k.GetModuleHandleW.restype = wintypes.HMODULE
    k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    return u, k


def ev_window():
    u, _ = _ev_api()
    for cls in ("EVERYTHING_TASKBAR_NOTIFICATION", "EVERYTHING_TASKBAR_NOTIFICATION_(1.5a)"):
        h = u.FindWindowW(cls, None)
        if h:
            return h
    return None


def _ev_parse(buf):
    """EVERYTHING_IPC_LIST2 -> [(path, size, attrs)]"""
    hdr = (ctypes.c_uint32 * 5).from_buffer_copy(buf[:20])
    totitems, numitems, offset, req_flags, sort = hdr
    out = []
    for i in range(numitems):
        flags, data_off = (ctypes.c_uint32 * 2).from_buffer_copy(buf[20 + i * 8: 28 + i * 8])
        p = data_off
        path, size, attrs = None, None, 0
        if req_flags & REQ_FULL_PATH:
            n = int.from_bytes(buf[p:p + 4], "little"); p += 4
            path = buf[p:p + n * 2].decode("utf-16-le"); p += (n + 1) * 2
        if req_flags & REQ_SIZE:
            size = int.from_bytes(buf[p:p + 8], "little", signed=True); p += 8
        if req_flags & REQ_ATTRIBUTES:
            attrs = int.from_bytes(buf[p:p + 4], "little"); p += 4
        if flags & 0x1:  # EVERYTHING_IPC_FOLDER
            continue
        out.append((path, size, attrs))
    return out, totitems


_EV_CLASS = {}  # one registered window class and its handler live until the end of the process
_EV_CUR = {}


def _ev_class(u, k):
    if not _EV_CLASS:
        def wndproc(hwnd, msg, wp, lp):
            if msg == EV_WM_COPYDATA:
                cds = ctypes.cast(lp, ctypes.POINTER(EV_COPYDATA)).contents
                if cds.dwData == REPLY_ID and _EV_CUR.get("hwnd") == hwnd:
                    _EV_CUR["raw"] = ctypes.string_at(cds.lpData, cds.cbData)
                    _EV_CUR["got"].set()
                    return 1
            return u.DefWindowProcW(hwnd, msg, wp, lp)
        proc = WNDPROC(wndproc)
        wc = EV_WNDCLASS()
        wc.lpfnWndProc = proc
        wc.hInstance = k.GetModuleHandleW(None)
        wc.lpszClassName = "FramewringEverythingReply"
        u.RegisterClassW(ctypes.byref(wc))
        _EV_CLASS.update(proc=proc, wc=wc, name=wc.lpszClassName, hinst=wc.hInstance)
    return _EV_CLASS


_EV_LOCK = threading.Lock()


def ev_query(search, timeout=15.0, max_results=200000):
    """Runs a search in Everything. None = Everything is not running or did not answer."""
    with _EV_LOCK:
        return _ev_query(search, timeout, max_results)


def _ev_query(search, timeout, max_results):
    result = {}

    def run():
        try:
            u, k = _ev_api()
            target = ev_window()
            if not target:
                return
            got = threading.Event()
            c = _ev_class(u, k)
            hinst = c["hinst"]
            hwnd = u.CreateWindowExW(0, c["name"], "fw", 0, 0, 0, 0, 0, None, None, hinst, None)
            if not hwnd:
                return
            _EV_CUR.clear()
            _EV_CUR.update(hwnd=hwnd, got=got)
            try:
                # if Everything runs as administrator, allow it to send us the reply
                u.ChangeWindowMessageFilterEx(hwnd, EV_WM_COPYDATA, 1, None)
            except Exception:
                pass
            q = search.encode("utf-16-le") + b"\0\0"
            head = (ctypes.c_uint32 * 7)(hwnd & 0xFFFFFFFF, REPLY_ID, 0, 0, max_results,
                                         REQ_FULL_PATH | REQ_SIZE | REQ_ATTRIBUTES, 1)
            payload = bytes(head) + q
            buf = ctypes.create_string_buffer(payload, len(payload))
            cds = EV_COPYDATA(COPYDATA_QUERY2W, len(payload), ctypes.cast(buf, ctypes.c_void_p))
            res = ctypes.c_size_t(0)
            ok = u.SendMessageTimeoutW(target, EV_WM_COPYDATA, hwnd, ctypes.addressof(cds), 0x0002, 5000,
                                       ctypes.byref(res))
            if not ok or not res.value:
                u.DestroyWindow(hwnd)
                return
            import time
            msg = (ctypes.c_byte * 64)()
            t_end = time.time() + timeout
            while not got.is_set() and time.time() < t_end:
                u.MsgWaitForMultipleObjects(0, None, False, 100, 0x04FF)
                while u.PeekMessageW(msg, None, 0, 0, 1):
                    u.TranslateMessage(msg)
                    u.DispatchMessageW(msg)
            u.DestroyWindow(hwnd)
            if "raw" in _EV_CUR:
                result["raw"] = _EV_CUR["raw"]
            _EV_CUR.clear()
        except Exception as e:
            result["error"] = repr(e)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout + 7)
    if "raw" not in result:
        return None if "error" not in result else result["error"]
    return _ev_parse(result["raw"])



def ev_exe():
    for c in (r"C:\Program Files\Everything\Everything.exe", r"C:\Program Files (x86)\Everything\Everything.exe",
              r"C:\Program Files\Everything 1.5a\Everything64.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Everything\Everything.exe")):
        if os.path.isfile(c):
            return c
    return None


def everything_search(min_bytes):
    """All videos >= min_bytes from the Everything index: fractions of a second instead of minutes of disk walking.
    If Everything is installed but closed (only the service runs), we start it
    in the tray for the duration of the search and then close it. None if Everything is absent or did not answer."""
    if not IS_WIN:
        return None
    started = None
    try:
        if not ev_window():
            exe = ev_exe()
            if not exe:
                return None
            SCAN["phase"] = "ev_open"
            subprocess.Popen([exe, "-startup"], creationflags=NO_WINDOW)
            started = exe
        q = "file: ext:%s size:>=%d" % (";".join(sorted(e.lstrip(".") for e in VIDEO_EXT)), min_bytes)
        deadline = time.time() + 60
        while time.time() < deadline and not SCAN["cancel"]:
            r = ev_query(q, timeout=10.0) if ev_window() else None
            if isinstance(r, tuple):  # while the database is loading, Everything does not answer
                return r[0]
            time.sleep(1)
        return None
    except Exception:
        return None
    finally:
        if started:
            try:
                subprocess.Popen([started, "-exit"], creationflags=NO_WINDOW)
            except Exception:
                pass


def ev_ok_root(root):
    """By default Everything indexes only local NTFS drives."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        drive = os.path.splitdrive(os.path.abspath(root))[0] + "\\"
        if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(drive)) != 3:
            return False
        fs = ctypes.create_unicode_buffer(32)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(drive), None, 0, None, None, None, fs, 32)
        return bool(ok) and fs.value.upper() == "NTFS"
    except Exception:
        return False


def is_ssd(root):
    """True/False/None by the "has seek penalty" flag. Without administrator rights."""
    if not IS_WIN:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                        ctypes.c_void_p]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        drive = os.path.splitdrive(os.path.abspath(root))[0]
        h = k32.CreateFileW("\\\\.\\" + drive, 0, 3, None, 3, 0, None)
        if not h or h == wintypes.HANDLE(-1).value:
            return None
        try:
            q = (ctypes.c_uint32 * 3)(7, 0, 0)  # StorageDeviceSeekPenaltyProperty, PropertyStandardQuery
            out = (ctypes.c_uint8 * 12)()
            n = wintypes.DWORD()
            if not k32.DeviceIoControl(h, 0x2D1400, q, ctypes.sizeof(q), out, ctypes.sizeof(out), ctypes.byref(n),
                                       None):
                return None
            return out[8] == 0
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


_PROBE_FILE = DATA_DIR / "probe_cache.json"


def load_probe_cache():
    try:
        d = json.loads(_PROBE_FILE.read_text(encoding="utf-8"))
        for k, (size, mtime, info) in d.items():
            PROBE_CACHE.setdefault(k, ((size, mtime), info))
    except Exception:
        pass


def save_probe_cache():
    """Video parameters between runs: a repeated search does not run ffprobe over hundreds of files."""
    try:
        items = list(PROBE_CACHE.items())[-5000:]
        d = {k: [v[0][0], v[0][1], v[1]] for k, v in items}
        tmp = _PROBE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(_PROBE_FILE))
    except Exception:
        pass


def _walk_dir(d, min_bytes, seen, on_found, push):
    try:
        it = os.scandir(d)
    except OSError:
        return
    with LOCK:
        SCAN["dirs"] += 1
    SCAN["cur"] = d
    if True:
        with it:
            for e in it:
                if SCAN["cancel"]:
                    break
                try:
                    name = e.name.lower()
                    if e.is_dir(follow_symlinks=False):
                        if name in SKIP_DIRS or name[:1] in "$.":  # .git, .pnpm-store, .cache, $Recycle.Bin…
                            continue
                        if IS_WIN and e.stat(follow_symlinks=False).st_file_attributes & FILE_ATTR_REPARSE:
                            continue  # junction links: otherwise the same folders would be walked twice
                        push(e.path)
                    elif e.is_file(follow_symlinks=False):
                        if os.path.splitext(name)[1] not in VIDEO_EXT or name.endswith(".part.mp4"):
                            continue
                        st = e.stat(follow_symlinks=False)
                        if st.st_size < min_bytes:
                            continue
                        if IS_WIN and st.st_file_attributes & FILE_ATTR_CLOUD:
                            SCAN["skipped_cloud"] += 1
                            continue
                        k = _norm(e.path)
                        with LOCK:
                            if k in seen:
                                continue
                            seen.add(k)
                            SCAN["candidates"] += 1
                        on_found((e.path, st.st_size))
                except OSError:
                    continue


def _scan_walk(root, min_bytes, seen, on_found):
    """Multi-threaded walk: SSDs serve directories in parallel several times faster (measured: 44 s -> 13 s
    on 420 thousand folders), HDDs - moderately, so as not to thrash the head."""
    import queue
    q = queue.Queue()
    q.put(root)
    ssd = is_ssd(root)
    n = 8 if ssd else 3 if ssd is False else 4

    def work():
        while True:
            d = q.get()
            try:
                if d is not None and not SCAN["cancel"]:
                    _walk_dir(d, min_bytes, seen, on_found, q.put)
            finally:
                q.task_done()
            if d is None:
                return
    ts = [threading.Thread(target=work, daemon=True) for _ in range(n)]
    for t in ts:
        t.start()
    q.join()
    for _ in ts:
        q.put(None)


def _scan_one(item):
    path, size = item
    if SCAN["cancel"]:
        return
    try:
        size = os.stat(path).st_size  # the Everything index may lag behind: the file was rewritten or deleted
        info = probe_cached(path)
    except Exception:
        SCAN["probed"] += 1
        return
    est = estimate(info, size)
    try:
        has_out = out_path_for({"path": path}, dict(SETTINGS)).exists()
    except OSError:
        has_out = False
    p = Path(path)
    res = {"path": path, "name": p.name, "dir": str(p.parent), "size": size, "codec": info["vcodec"],
           "w": info["width"], "h": info["height"], "fps": info["fps"], "dur": info["duration"],
           "mbps": round((info["bitrate"] or (size * 8 / info["duration"] if info["duration"] else 0)) / 1e6, 1),
           "est": est, "save": size - est, "has_out": has_out}
    with LOCK:
        SCAN["probed"] += 1
        SCAN["results"].append(res)
        SCAN["ver"] += 1


def scan_thread(roots, min_bytes, use_ev=True):
    """Each disk is walked in its own thread (disks work in parallel), and the files found are
    passed straight to ffprobe: results appear as we go, not after all disks are walked."""
    from concurrent.futures import ThreadPoolExecutor
    try:
        seen = set()
        load_probe_cache()
        with ThreadPoolExecutor(max_workers=6) as probers:
            submit = lambda it: probers.submit(_scan_one, it)  # noqa: E731
            ev_roots = [r for r in roots if use_ev and ev_ok_root(r)]
            walk_roots = [r for r in roots if r not in ev_roots]
            if ev_roots:
                items = everything_search(min_bytes)
                if items is None:
                    SCAN["ev_missing"] = IS_WIN  # Everything is absent or does not answer
                    walk_roots += ev_roots
                else:
                    SCAN["method"] = ["everything"]
                    pref = [_norm(r).rstrip("\\/") + os.sep for r in ev_roots]
                    for path, size, attrs in items:
                        k = _norm(path)
                        root = next((p for p in pref if k.startswith(p)), None)
                        parts = k[len(root):].split(os.sep)[:-1] if root else []
                        if not root or attrs & FILE_ATTR_CLOUD or \
                                k.endswith(".part.mp4") or any(x in SKIP_DIRS or x[:1] in "$." for x in parts):
                            continue
                        with LOCK:
                            if k in seen:
                                continue
                            seen.add(k)
                            SCAN["candidates"] += 1
                        submit((path, size))
            if walk_roots:
                SCAN["phase"] = "walk"
                SCAN["method"] = SCAN["method"] + ["walk"]
            walkers = [threading.Thread(target=_scan_walk, daemon=True, args=(r, min_bytes, seen, submit))
                       for r in walk_roots]
            for t in walkers:
                t.start()
            for t in walkers:
                t.join()
            SCAN["phase"] = "probe"
    except Exception as e:
        SCAN["error"] = "%s: %s" % (type(e).__name__, e)
    finally:
        save_probe_cache()
        with LOCK:
            SCAN["running"], SCAN["finished"], SCAN["phase"], SCAN["cur"] = False, True, "", ""
            SCAN["took"] = time.time() - SCAN["t0"]
            SCAN["ver"] += 1


def start_scan(roots, min_mb, use_ev=True):
    roots = [str(Path(os.path.expanduser(r.strip().strip('"').strip("'")))) for r in roots if r and r.strip()]
    roots = [r for r in roots if os.path.isdir(r)]
    nr = sorted({_norm(r): r for r in roots}.items())
    roots = [r for i, (k, r) in enumerate(nr)
             if not any(k != pk and k.startswith(pk.rstrip("\\/") + os.sep) for pk, _ in nr[:i])]
    if not roots:
        raise UserError("err.scan_no_roots")
    if not FFPROBE:
        raise UserError("err.no_ffmpeg")
    try:
        min_bytes = max(50, int(float(min_mb))) * 10 ** 6
    except (TypeError, ValueError):
        min_bytes = 500 * 10 ** 6
    with LOCK:
        if SCAN["running"]:
            raise UserError("err.scan_running")
        SCAN.update(running=True, cancel=False, phase="walk", dirs=0, cur="", candidates=0,
                    probed=0, results=[], error="", finished=False, skipped_cloud=0, method=[], t0=time.time(),
                    ev_missing=False)
        SCAN["ver"] += 1
    threading.Thread(target=scan_thread, args=(roots, min_bytes, bool(use_ev)), daemon=True).start()


def scan_public(client_ver):
    with LOCK:
        d = {k: v for k, v in SCAN.items() if k != "results"}
        d["found"] = len(SCAN["results"])
        d["results"] = list(SCAN["results"]) if client_ver != SCAN["ver"] else None
    return d


# ------------------------------------------------------------ Sleep lock ----

def keep_awake(on):
    if IS_WIN:
        try:
            import ctypes
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
        except Exception:
            pass


# --------------------------------------------------------------- Encoding ----

def proc_io(p):
    """(read, written) bytes by the process; None if the OS does not say."""
    try:
        if IS_WIN:
            class IOC(ctypes.Structure):
                _fields_ = [(n, ctypes.c_uint64) for n in ("RO", "WO", "OO", "RB", "WB", "OB")]
            c = IOC()
            k32 = ctypes.WinDLL("kernel32")
            k32.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
            if k32.GetProcessIoCounters(int(p._handle), ctypes.byref(c)):
                return c.RB, c.WB
    except Exception:
        pass
    return None


def proc_written(p):
    """How many bytes the process has already written to disk (None if the OS does not say)."""
    try:
        if IS_WIN:
            class IOC(ctypes.Structure):
                _fields_ = [(n, ctypes.c_uint64) for n in ("RO", "WO", "OO", "RB", "WB", "OB")]
            c = IOC()
            k32 = ctypes.WinDLL("kernel32")
            k32.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
            if k32.GetProcessIoCounters(int(p._handle), ctypes.byref(c)):
                return c.WB
        elif sys.platform.startswith("linux"):
            with open("/proc/%d/io" % p.pid) as f:
                for line in f:
                    if line.startswith("wchar:"):
                        return int(line.split()[1])
    except Exception:
        pass
    return None


def _finish_watch(p, job, base_phase, last):
    """After 100% ffmpeg silently rewrites the whole file so that the index (moov) ends up at the start
    (+faststart): on tens of GB this is minutes without a single progress line. We estimate this stage
    ourselves from the number of bytes written by the process: roughly the whole written volume has to be rewritten."""
    base = None
    while p.poll() is None:
        time.sleep(1)
        with LOCK:
            pct, size = job["pct"], job["cur_size"]
        if pct < 90 or time.time() - last[0] < 3:  # ffmpeg went quiet near the end = the index is being moved
            continue
        w = proc_written(p)
        now = time.time()
        if base is None:
            base = (w, now)
        fin = {"pct": None, "eta": None}
        if w is not None and base[0] is not None and size > 0:
            done = max(0, w - base[0])
            fin["pct"] = min(99.0, done / size * 100)
            rate = done / max(0.5, now - base[1])
            if rate > 0 and done > 0:
                fin["eta"] = max(0.0, (size - done) / rate)
        with LOCK:
            job["fin"] = fin
            job["phase"] = M("phase.finish")


def run_ffmpeg(args, job, total, phase, s):
    """Runs ffmpeg with progress into the job. Returns (ok, error_text, log_tail).
    error_text == "cancel" if the user pressed "Stop"."""
    log = tempfile.TemporaryFile()
    try:
        full = [FFMPEG, "-hide_banner", "-nostdin", "-y"] + args
        with LOCK:
            if CUR["cancel"]:
                return False, "cancel", ""
            p = spawn(full, lowprio=bool(s.get("lowprio")), stdout=subprocess.PIPE, stderr=log,
                      stdin=subprocess.DEVNULL, universal_newlines=True, encoding="utf-8", errors="replace")
            CUR["proc"] = p
            job["phase"] = phase
            job["pct"], job["fps"], job["speed"], job["eta"], job["cur_size"], job["elapsed"] = 0, 0, 0, None, 0, 0
            job["fin"] = None
        last = [time.time()]
        if "+faststart" in args:
            threading.Thread(target=_finish_watch, args=(p, job, phase, last), daemon=True).start()
        caf = None
        if IS_MAC and s.get("nosleep"):
            try:
                caf = subprocess.Popen(["caffeinate", "-i", "-w", str(p.pid)])
            except Exception:
                pass
        t0 = time.time()
        for line in p.stdout:
            last[0] = time.time()
            k, _, v = line.strip().partition("=")
            if k not in ("out_time_us", "out_time_ms", "fps", "speed", "total_size", "progress"):
                continue
            with LOCK:
                job["elapsed"] = time.time() - t0
                if k in ("out_time_us", "out_time_ms") and v.lstrip("-").isdigit():
                    done = int(v) / 1e6  # in ffmpeg out_time_ms is also in microseconds (a historical bug)
                    if total > 0:
                        job["pct"] = max(0.0, min(100.0, done / total * 100))
                        sp = job["speed"] or (done / job["elapsed"] if job["elapsed"] > 1 else 0)
                        if sp > 0:
                            job["eta"] = max(0.0, (total - done) / sp)
                elif k == "fps":
                    try:
                        job["fps"] = float(v)
                    except ValueError:
                        pass
                elif k == "speed":
                    try:
                        job["speed"] = float(v.rstrip("x"))
                    except ValueError:
                        pass
                elif k == "total_size" and v.isdigit():
                    job["cur_size"] = int(v)
                elif k == "progress" and v == "end":
                    job["pct"], job["eta"] = 100.0, 0
        p.wait()
        if caf:
            try:
                caf.terminate()
            except Exception:
                pass
        with LOCK:
            CUR["proc"] = None
            cancelled = CUR["cancel"]
            job["fin"] = None
        log.seek(0, 2)
        size = log.tell()
        log.seek(max(0, size - 16000))
        tail = log.read().decode("utf-8", "replace")
        if cancelled:
            return False, "cancel", tail
        if p.returncode != 0:
            # remove SVT-AV1 chatter and other noise, keep the essence
            lines = [l for l in tail.splitlines() if l.strip() and not l.startswith("Svt[info]")]
            err = "\n".join(lines)[-1500:]
            return False, err or M("err.ffmpeg_code", code=str(p.returncode)), tail
        return True, "", tail
    finally:
        log.close()


TEXT_SUBS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}


def vfilters(info):
    """Video filter chain. The same chain is applied to the original when computing VMAF."""
    f = []
    if info.get("interlaced"):
        f.append("bwdif=mode=send_field")  # 50i -> 50p: motion as smooth as in the original
    # yuv420 needs even dimensions: 1366x767 and the like would otherwise fail in the encoder
    if (info.get("width") or 0) % 2 or (info.get("height") or 0) % 2:
        f.append("crop=trunc(iw/2)*2:trunc(ih/2)*2")
    return f


def sub_args(info):
    """Text subtitles are carried into MP4 (mov_text). MP4 cannot hold image subtitles (PGS/DVD)."""
    a = []
    for i, c in enumerate(info.get("subs") or []):
        if c in TEXT_SUBS:
            a += ["-map", "0:s:%d" % i]
    return a + ["-c:s", "mov_text"] if a else []


def encode(job, s, src, dst, total, phase, extra, subs=False):
    """Compresses src into dst. For AV1 picks lp to fit memory and retries with a smaller one on shortage.
    Returns (ok, err, encoding_seconds)."""
    info = job["info"]
    lp = svt_lp_for(info) if s["preset"] == "av1" else None
    if lp:
        with LOCK:
            job["note"] = M("note.av1_lp_low", lp=lp)
    pre = ["-hwaccel", "cuda"] if s["preset"].startswith("nvenc") else []
    mem_tries = 0
    while True:
        vf = vfilters(info)
        args = pre + ["-i", src, "-map", "0:V:0", "-map", "0:a?"] + (sub_args(info) if subs else []) + \
            (["-vf", ",".join(vf)] if vf else []) + \
            video_args(s["preset"], s["quality"], s["speed"], lp) + ["-fps_mode", "passthrough"] + \
            audio_args(job, s) + extra + \
            ["-progress", "pipe:1", "-nostats", dst]
        t0 = time.time()
        ok, err, _ = run_ffmpeg(args, job, total, phase, s)
        took = time.time() - t0
        if ok or err == "cancel" or not isinstance(err, str) or not MEM_ERR.search(err):
            return ok, err, took
        if s["preset"] != "av1":
            # "Cannot allocate memory" in the middle of compression: Windows gave no memory (often with the page
            # file turned off). This is a one-off failure: we retry, without GPU decoding the second time.
            mem_tries += 1
            if mem_tries > 2:
                return False, M("err.mem3", detail=err), took
            if mem_tries == 2:
                pre = []
            with LOCK:
                job["note"] = M("note.mem_retry_cpu" if mem_tries == 2 and s["preset"].startswith("nvenc")
                                else "note.mem_retry", n=mem_tries + 1)
            time.sleep(5)
            continue
        cur = lp or 5
        if cur <= 1:
            return False, M("err.av1_mem", res="%dx%d" % (info["width"], info["height"]), detail=err), took
        lp = cur - 1
        with LOCK:
            job["note"] = M("note.av1_lp_retry", lp=lp)


def _rm_part(p):
    """Delete an unfinished result - only our "*.part.mp4", nothing else."""
    if p and str(p).lower().endswith(".part.mp4"):
        _rm(p)


def _stop_current():
    """Exit in the middle of compression: stop ffmpeg and remove the unfinished .part.mp4."""
    p, part = CUR.get("proc"), CUR.get("part")
    if p:
        try:
            p.terminate()
            p.wait(5)
        except Exception:
            pass
    _rm_part(part)


def _rm(p):
    try:
        Path(p).unlink()
    except Exception:
        pass


def free_bytes(d):
    d = Path(d)
    while not d.exists() and d.parent != d:
        d = d.parent
    try:
        return shutil.disk_usage(str(d)).free
    except OSError:
        return None


def finalize(part, out, job):
    """part -> out. Right after writing, a big file is often held by an antivirus (scanning) or Explorer
    (building a preview), and the final file may be open in a player. This used to give an "Error" after
    an hour of compression. Now we wait, say what is happening, and in the worst case leave the finished file as is."""
    t0 = time.time()
    alt = None
    while True:
        target = alt or out
        try:
            os.replace(str(part), str(target))
            if alt:
                with LOCK:
                    add_note(job, M("note.saved_as", out=out.name, alt=alt.name))
            return target
        except OSError as e:
            if not isinstance(e, PermissionError) and getattr(e, "winerror", None) not in (5, 32, 33):
                raise
        waited = time.time() - t0
        with LOCK:
            job["phase"] = M("phase.save_wait", secs=int(waited))
        if waited > 60 and alt is None:
            n = 2
            while True:  # maybe the old result itself is busy: try another name
                alt = out.with_name("%s (%d).mp4" % (out.stem, n))
                with LOCK:
                    free_name = OUT_OWNERS.get(_norm(alt)) in (None, _norm(job["path"]))
                if not alt.exists() and free_name:
                    break
                n += 1
        if waited > 600:  # 10 minutes: give up, but the work is not lost
            with LOCK:
                add_note(job, M("note.rename_failed", name=part.name))
            return part
        time.sleep(2)


NO_GAIN = 0.97  # result larger than 97% of the original - no point compressing, keep the original


def _gain_watch(job, size, stop):
    """Watches the size during compression. If it is already clear the result will not be smaller than the original
    (the source is already efficiently compressed), stops ffmpeg - we do not spend hours on a file that will not shrink."""
    # The time fraction misleads: for a video with a complex start and a static rest the result grows
    # unevenly. So we compare what is written with what has already been READ from the source (the same part of the video).
    while not stop.wait(2):
        if job.get("fin"):
            continue
        with LOCK:
            p = CUR.get("proc")
        if p is None or p.poll() is not None:  # between attempts (retry after a memory failure) - do not touch
            continue
        cur = job.get("cur_size") or 0
        io = proc_io(p)
        if io and io[0] > 0:
            rd = io[0]
            ratio = cur / float(rd)
            frac = rd / float(size) if size else 0
            hit = (frac >= 0.10 and ratio >= 1.10) or (frac >= 0.30 and ratio >= 1.02)
            done_pct, proj = job.get("pct") or frac * 100, ratio * 100  # the note shows compression progress, not read-ahead
        else:  # no read counters - stop only when the result is already not smaller than the original
            hit = cur >= size * NO_GAIN
            done_pct, proj = job.get("pct") or 0, cur * 100.0 / size if size else 0
        if hit:
            with LOCK:
                job["_nogain"] = (round(min(done_pct, 99)), round(proj))
            try:
                p.terminate()
            except Exception:
                pass
            return


def _keep_original(job, note):
    with LOCK:
        job["status"], job["pct"], job["out_path"], job["out_size"] = "kept", 100, "", 0
        job["error"] = ""
        add_note(job, note)


def do_full(job, s):
    out = out_path_for(job, s)
    if _same_file(out, job["path"]):  # should not happen, but the original is the most valuable
        with LOCK:
            job["status"], job["error"] = "error", M("err.same_as_src")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    if s.get("skip") and out.exists():
        with LOCK:
            OUT_OWNERS[_norm(out)] = _norm(job["path"])
            job["status"], job["out_path"], job["out_size"] = "skipped", str(out), out.stat().st_size
        return
    # Disk space: if it won't fit even by the optimistic estimate, don't waste hours
    need = estimate(job["info"], job["size"])
    free = free_bytes(out.parent)
    if free is not None and free < need + 200 * 10 ** 6:
        with LOCK:
            job["status"], job["error"] = "error", M("err.no_space", need=round(need / 1e9, 1),
                                                     free=round(free / 1e9, 1), dir=str(out.parent))
        return
    if free is not None and free < need * 2:
        with LOCK:
            job["note"] = M("note.space_tight", free=round(free / 1e9, 1))
    with LOCK:
        OUT_OWNERS[_norm(out)] = _norm(job["path"])
    part = out.with_name(out.stem + ".part.mp4")
    try:
        job["src_sig"] = src_sig(job["path"])
        job["size"] = job["src_sig"][0]  # the file may have grown after being added to the list
    except OSError:
        job["src_sig"] = None
    with LOCK:
        job["part"], CUR["part"] = str(part), str(part)
    job.pop("_nogain", None)
    stop = threading.Event()
    threading.Thread(target=_gain_watch, args=(job, job["size"], stop), daemon=True).start()
    try:
        ok, err, took = encode(job, s, job["path"], str(part), job["info"]["duration"], M("phase.compress"),
                               ["-map_metadata", "0", "-movflags", "+faststart"], subs=True)
    finally:
        stop.set()
        with LOCK:
            job["part"], CUR["part"] = "", None
    if not ok and job.get("_nogain") and err != "cancel":
        _rm(part)
        with LOCK:
            OUT_OWNERS.pop(_norm(out), None)
        done, pct = job.pop("_nogain")
        _keep_original(job, M("note.no_gain_early", done=done, pct=pct))
        return
    if ok and part.exists() and part.stat().st_size >= job["size"] * NO_GAIN:
        pct = round(part.stat().st_size * 100.0 / job["size"])
        _rm(part)
        with LOCK:
            OUT_OWNERS.pop(_norm(out), None)
        _keep_original(job, M("note.no_gain", pct=pct))
        return
    if ok:
        with LOCK:
            job["phase"], job["fin"] = M("phase.save"), None
        out = finalize(part, out, job)
        with LOCK:
            OUT_OWNERS[_norm(out)] = _norm(job["path"])
        try:  # modification date as in the original: sorting by date in Explorer stays intact
            st = os.stat(job["path"])
            os.utime(str(out), (st.st_atime, st.st_mtime))
        except OSError:
            pass
        img = [c for c in (job["info"].get("subs") or []) if c not in TEXT_SUBS]
        if img:
            with LOCK:
                add_note(job, M("note.image_subs", codecs=", ".join(sorted(set(img)))))
        with LOCK:
            job["status"], job["pct"], job["out_path"], job["out_size"] = "done", 100, str(out), out.stat().st_size
        tst = job.get("test") or {}
        # VMAF of the test is used only if the test had the same mode and quality as the compression
        tv = tst.get("vmaf") if tst.get("preset") == s["preset"] and tst.get("quality") == s["quality"] else None
        try:
            out_sig = src_sig(str(out))
        except OSError:
            out_sig = None
        with LOCK:
            job["phase"] = M("phase.hash")
        out_hash = file_sha256(str(out), job)
        add_history({"t": time.time(), "src": job["path"], "out": str(out), "name": job["name"],
                     "src_sig": job.get("src_sig"), "out_sig": out_sig, "out_hash": out_hash,
                     "src_codec": (job["info"] or {}).get("vcodec"),
                     "vmaf": tv,
                     "size": job["size"], "out_size": job["out_size"], "duration": job["info"]["duration"],
                     "preset": s["preset"], "quality": s["quality"], "speed": s["speed"], "secs": round(took, 1)})
    else:
        _rm(part)
        with LOCK:
            if err == "cancel":
                job["status"] = "cancelled"
            else:
                job["status"], job["error"] = "error", err


# ------------------------------------------------------------- Replace originals ----
# Replacement - only on the person's explicit choice in the "Replace originals" window. Order: full check of the compressed
# file -> comparison of fingerprints of the original and compressed -> check that the original will DEFINITELY fit in the Recycle Bin ->
# compressed file next to the original under a temporary name (recorded in history as an "intent") -> original to the
# Windows Recycle Bin (and check that it is there) -> the temporary name becomes the original's name (.mp4).
# Any failure before the Recycle Bin changes nothing; a failure/exit in the middle is completed at the next start.

EDIT_CODECS = {"prores", "qtrle", "dnxhd", "cfhd", "ffv1", "huffyuv", "utvideo", "rawvideo", "v210", "png", "mjpeg"}
REPLACE = {"running": False, "items": {}, "ver": 0}


def src_sig(path):
    """File fingerprint: size and modification time (to the second)."""
    st = os.stat(path)
    return [st.st_size, int(st.st_mtime)]


def _hkey(h):
    """Stable key of a history entry (the list index may shift - e.g. after an import)."""
    return "%s|%s" % (h.get("t"), _norm(h.get("src") or ""))


def _hist_find(key):
    with LOCK:
        return next((i for i, h in enumerate(HISTORY["items"]) if _hkey(h) == key), None)


def _real_path(path):
    """The real path: subst drive -> its folder, junction/symlink -> target, network drive -> \\\\server.
    The Recycle Bin depends on the real volume, not on the letter under which it is seen."""
    p = os.path.abspath(str(path))
    if IS_WIN:
        drive, rest = os.path.splitdrive(p)
        if len(drive) == 2 and drive[1] == ":":
            buf = ctypes.create_unicode_buffer(2048)
            if ctypes.windll.kernel32.QueryDosDeviceW(drive, buf, 2048) and buf.value.startswith("\\??\\"):
                dev = buf.value[4:]
                p = ("\\\\" + dev[4:] if dev.upper().startswith("UNC\\") else dev) + rest
    try:
        p = os.path.realpath(p)
    except (OSError, ValueError):
        pass
    return p


def has_recycle_bin(path):
    """The Recycle Bin exists only on local fixed drives (by the real path, not by the letter)."""
    if not IS_WIN:
        return False
    try:
        rp = _real_path(path)
        if rp.startswith("\\\\"):
            return False
        root = os.path.splitdrive(rp)[0] + "\\"
        return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 3  # DRIVE_FIXED
    except Exception:
        return False


def _bin_used(root):
    class SHQUERYRBINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]
    q = SHQUERYRBINFO(ctypes.sizeof(SHQUERYRBINFO), 0, 0)
    if ctypes.windll.shell32.SHQueryRecycleBinW(ctypes.c_wchar_p(root), ctypes.byref(q)) != 0:
        return None
    return q.i64Size


def bin_check(path, size):
    """None - a file of size `size` from this drive will certainly go to the Recycle Bin. Otherwise - the reason.
    Windows deletes PERMANENTLY if the file is larger than the free space of the Recycle Bin, the bin is disabled
    ("delete immediately") or the drive is network/removable/subst - we check all of this in advance."""
    if not has_recycle_bin(path):
        return M("rep.b.no_bin")
    try:
        import winreg
        rp = _real_path(path)
        root = os.path.splitdrive(rp)[0] + "\\"
        buf = ctypes.create_unicode_buffer(64)
        if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(ctypes.c_wchar_p(root), buf, 64):
            return M("rep.b.no_bin")
        m = re.search(r"\{[0-9A-Fa-f-]+\}", buf.value)
        if not m:
            return M("rep.b.no_bin")
        total = shutil.disk_usage(root).total
        nuke, cap = 0, None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer"
                                "\\BitBucket\\Volume\\" + m.group(0)) as k:
                for name in ("NukeOnDelete", "MaxCapacity"):
                    try:
                        v = winreg.QueryValueEx(k, name)[0]
                    except OSError:
                        continue
                    if name == "NukeOnDelete":
                        nuke = v
                    else:
                        cap = v * 1024 * 1024
        except OSError:
            pass
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):  # group policies
            try:
                with winreg.OpenKey(hive, "Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer") as k:
                    try:
                        if winreg.QueryValueEx(k, "NoRecycleFiles")[0]:
                            nuke = 1
                    except OSError:
                        pass
                    try:
                        pc = winreg.QueryValueEx(k, "RecycleBinSize")[0]
                        cap = min(cap if cap is not None else total, total * pc / 100.0)
                    except OSError:
                        pass
            except OSError:
                pass
        if nuke:
            return M("rep.b.bin_off")
        if cap is None:
            cap = total * 0.05  # settings not found - be careful: 5% of the disk
        used = _bin_used(root)
        if used is None:
            return M("rep.b.no_bin")
        free = cap - used
        if size > free:
            return M("rep.b.bin_small", need=round(size / 1e9, 1), free=round(max(free, 0) / 1e9, 1))
        return None
    except Exception as e:
        print(" bin_check: %s" % e)
        return M("rep.b.no_bin")


def recycle(path):
    """Send a file to the Windows Recycle Bin (SHFileOperation + FOF_ALLOWUNDO + FOF_WANTNUKEWARNING:
    if Windows still decides to delete permanently, it asks instead of doing it silently)."""
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
    FO_DELETE = 3
    FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI, FOF_WANTNUKEWARNING = 0x4, 0x10, 0x40, 0x400, 0x4000
    # by the REAL path: via a subst drive letter Windows would delete the file bypassing the Recycle Bin
    owner = (_own_windows() or [None])[0]
    op = SHFILEOPSTRUCTW(owner, FO_DELETE, _real_path(path) + "\0", None,
                         FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI | FOF_WANTNUKEWARNING,
                         False, None, None)
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return rc == 0 and not op.fAnyOperationsAborted and not os.path.exists(str(path))


def in_recycle_bin(path, since):
    """Whether the Recycle Bin has an entry for this file, deleted after `since` (we check the $I entries of the bin)."""
    import struct
    want = {os.path.normcase(os.path.abspath(str(path))), os.path.normcase(_real_path(path))}
    root = os.path.splitdrive(_real_path(path))[0] + "\\"
    base = os.path.join(root, "$Recycle.Bin")
    try:
        dirs = [os.path.join(base, d) for d in os.listdir(base)]
    except OSError:
        return False
    for d in dirs:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for f in names:
            if not f.startswith("$I"):
                continue
            fp = os.path.join(d, f)
            try:
                b = open(fp, "rb").read()
                # the deletion time is inside the entry (FILETIME), not the date of the $I file itself
                deleted = (struct.unpack_from("<q", b, 16)[0] - 116444736000000000) / 1e7
                if deleted < since - 5:
                    continue
                if struct.unpack_from("<q", b, 0)[0] == 2:
                    n = struct.unpack_from("<i", b, 24)[0]
                    orig = b[28:28 + n * 2].decode("utf-16-le").rstrip("\0")
                else:
                    orig = b[24:24 + 520].decode("utf-16-le").split("\0")[0]
            except Exception:
                continue
            if os.path.normcase(orig) in want:
                return True
    return False


_STREAMS_CACHE = {}


def stream_counts(path):
    """How many tracks of each kind are in the file: video (without covers), audio, subtitles, data, attachments."""
    try:
        key = (_norm(path),) + tuple(src_sig(path))
    except OSError:
        return None
    if key in _STREAMS_CACHE:
        return _STREAMS_CACHE[key]
    r = run_quiet([FFPROBE, "-v", "error", "-show_entries", "stream=codec_type:stream_disposition=attached_pic",
                   "-of", "json", str(path)])
    c = {"video": 0, "audio": 0, "subtitle": 0, "data": 0, "attachment": 0}
    try:
        for s in json.loads(r.stdout or "{}").get("streams", []):
            t = s.get("codec_type")
            if t == "video" and (s.get("disposition") or {}).get("attached_pic"):
                continue
            if t in c:
                c[t] += 1
    except Exception:
        return None
    _STREAMS_CACHE[key] = c
    return c


def _decode_check(out, maps, total, item=None):
    """Decodes the chosen tracks completely. Returns (errors_as_text, up_to_which_second_it_got)."""
    p = subprocess.Popen([FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-i", str(out)] + maps +
                         ["-f", "null", "-", "-progress", "pipe:1", "-nostats"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW | BELOW_NORMAL)
    errs, last = [], [0.0]
    t = threading.Thread(target=lambda: errs.append(p.stderr.read().decode("utf-8", "replace")), daemon=True)
    t.start()
    for line in p.stdout:
        line = line.decode("utf-8", "replace").strip()
        if line.startswith("out_time_us="):
            try:
                last[0] = max(last[0], int(line.split("=")[1]) / 1e6)
                if item is not None:
                    item["pct"] = max(0.0, min(100.0, last[0] / total * 100))
            except ValueError:
                pass
    p.wait()
    t.join(5)
    err = (errs[0] if errs else "").strip()
    if p.returncode != 0 and not err:
        err = "exit %d" % p.returncode
    return err, last[0]


def verify_output(out, src_info, item, src_path=None):
    """Full check of the compressed file: it is readable; duration and number of audio tracks as in the original;
    video decodes COMPLETELY and reaches the end (not truncated); audio decodes without errors.
    None - all good, otherwise a message."""
    try:
        oi = probe(str(out))
    except Exception as e:
        return M("verify.probe", detail=str(e)[:200])
    sd, od = src_info.get("duration") or 0, oi.get("duration") or 0
    tol = max(1.0, min(3.0, sd * 0.001))  # re-encoding does not change the duration by more than a fraction of a second
    if sd and abs(od - sd) > tol:
        return M("verify.duration", a=round(sd, 1), b=round(od, 1))
    if len(oi["audio"]) != len(src_info.get("audio") or []):
        return M("verify.audio", a=len(src_info.get("audio") or []), b=len(oi["audio"]))
    total = sd or od or 1
    err, reached = _decode_check(out, ["-map", "0:V:0"], total, item)
    if err:
        return M("verify.decode", detail=err[-300:])
    if sd and reached < sd - tol:
        return M("verify.short", a=round(sd, 1), b=round(reached, 1))
    if oi["audio"]:
        err, out_a = _decode_check(out, ["-map", "0:a"], total)
        if err:
            return M("verify.decode", detail=err[-300:])
        _, src_a = _decode_check(src_path, ["-map", "0:a"], total)  # how much audio the original has
        if src_a and out_a < src_a - tol:
            return M("verify.audio_short", a=round(src_a, 1), b=round(out_a, 1))
    return None


def _documents_dir():
    """The user's "Documents" folder (including one moved by OneDrive)."""
    if IS_WIN:
        try:
            class GUID(ctypes.Structure):
                _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16),
                            ("d", ctypes.c_ubyte * 8)]
            g = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            ptr = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(ptr)) == 0:
                path = ptr.value
                ctypes.windll.ole32.CoTaskMemFree(ptr)
                if path and os.path.isdir(path):
                    return Path(path)
        except Exception:
            pass
    docs = Path(os.path.expanduser("~")) / "Documents"
    return docs if docs.is_dir() else Path(os.path.expanduser("~"))


def file_sha256(path, job=None, item=None):
    """SHA-256 of a file (for the compressed one - right after compression; before replacing we compare: any change of bytes is visible)."""
    import hashlib
    h = hashlib.sha256()
    total = os.path.getsize(path) or 1
    done = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(8 << 20)
            if not b:
                break
            h.update(b)
            done += len(b)
            if item is not None:
                item["pct"] = done * 100.0 / total
            elif job is not None:
                job["pct"] = 100
    return h.hexdigest()


def _replace_target(src):
    """Where the compressed file will go: same folder and name as the original, extension .mp4."""
    return Path(src).with_suffix(".mp4")


def _tmp_for(src):
    return Path(src).with_name(Path(src).stem + ".framewring-new.mp4")


def _check_entry(h):
    """Blocks and warnings for one history entry (a fresh check of files on disk)."""
    src, o = h.get("src"), h.get("out")
    c = {"key": _hkey(h), "name": h.get("name") or Path(src).name, "src": src, "out": o,
         "size": h.get("size") or 0, "out_size": h.get("out_size") or 0, "warn": [], "block": []}
    if h.get("replaced"):
        c["block"].append(M("rep.b.replaced"))
        return c
    if not os.path.isfile(src):
        c["block"].append(M("rep.b.src_missing"))
        return c
    if not os.path.isfile(o):
        c["block"].append(M("rep.b.out_missing"))
        return c
    c["size"], c["out_size"] = os.path.getsize(src), os.path.getsize(o)
    if h.get("imported"):
        c["block"].append(M("rep.b.imported"))  # from a foreign history file: authenticity cannot be confirmed
    elif not h.get("src_sig") or not h.get("out_sig") or not h.get("out_hash"):
        c["block"].append(M("rep.b.old_entry"))  # entry of an old version: authenticity cannot be confirmed
    else:
        if src_sig(src) != h["src_sig"]:
            c["block"].append(M("rep.b.src_changed"))
        if src_sig(o) != h["out_sig"]:
            c["block"].append(M("rep.b.out_changed"))
    if c["out_size"] >= c["size"]:
        c["block"].append(M("rep.b.not_smaller"))
    # paths longer than ~260 characters: Windows "deletes to the Recycle Bin" bypassing it - permanently (verified)
    if max(len(_real_path(src)), len(str(_tmp_for(src))), len(str(_replace_target(src)))) >= 250:
        c["block"].append(M("rep.b.long_path"))
    if c["block"]:  # expensive checks follow (ffprobe, Recycle Bin) - not needed for blocked ones
        return c
    with LOCK:
        busy = any(_norm(j["path"]) == _norm(src) and j["status"] in ("queued", "running", "probing") for j in JOBS)
    if busy:
        c["block"].append(M("rep.b.busy"))
    b = bin_check(src, c["size"])
    if b:
        c["block"].append(b)
    tgt = _replace_target(src)
    if tgt.exists() and not _same_file(tgt, src):
        c["block"].append(M("rep.b.collision", name=tgt.name))
    if _tmp_for(src).exists():
        c["block"].append(M("rep.b.leftover", name=_tmp_for(src).name))
    v = h.get("vmaf")
    if v is None:
        c["warn"].append(M("rep.w.no_test"))
    elif v < 93:
        c["warn"].append(M("rep.w.vmaf", v=round(v, 1)))
    codec = h.get("src_codec")
    if not codec:
        try:
            codec = probe_cached(src).get("vcodec")
        except Exception:
            codec = ""
    if codec in EDIT_CODECS:
        c["warn"].append(M("rep.w.edit", codec=codec))
    sc, oc = stream_counts(src), stream_counts(o)
    if sc and oc:
        for kind, k in (("video", "rep.w.lost_video"), ("subtitle", "rep.w.lost_subs"),
                        ("data", "rep.w.lost_data"), ("attachment", "rep.w.lost_att")):
            if sc[kind] > oc[kind]:
                c["warn"].append(M(k, n=sc[kind] - oc[kind]))
    if c["size"] and c["out_size"] / c["size"] > 0.8 and not c["block"]:
        c["warn"].append(M("rep.w.small", pct=round((1 - c["out_size"] / c["size"]) * 100)))
    return c


def replace_candidates():
    """What can be replaced: from history (it survives "Remove finished" and restart); one original - one row."""
    with LOCK:
        items = [dict(h) for h in HISTORY["items"]]
    out, seen = [], set()
    for h in reversed(items):
        if not h.get("src") or not h.get("out") or _norm(h["src"]) in seen:
            continue
        seen.add(_norm(h["src"]))
        try:
            c = _check_entry(h)
        except Exception as e:  # one entry must not break the whole window
            c = {"key": _hkey(h), "name": h.get("name") or "", "src": h.get("src"), "out": h.get("out"),
                 "size": h.get("size") or 0, "out_size": h.get("out_size") or 0, "warn": [],
                 "block": [M("rep.b.check_failed", detail=str(e)[:150])]}
        c["state"] = REPLACE["items"].get(c["key"])
        out.append(c)
    return out


def _set_hist(key, **kw):
    """Update a history entry by key and save to disk."""
    with LOCK:
        i = next((n for n, h in enumerate(HISTORY["items"]) if _hkey(h) == key), None)
        if i is None:
            return False
        for k, v in kw.items():
            if v is None:
                HISTORY["items"][i].pop(k, None)
            else:
                HISTORY["items"][i][k] = v
        HISTORY["ver"] += 1
        data = json.dumps(HISTORY["items"], ensure_ascii=False, indent=0)
    write_json(HISTORY_FILE, data)
    return True


def _replace_one(key, item):
    i = _hist_find(key)
    if i is None:
        raise _ItemError(M("rep.err.blocked"))
    with LOCK:
        h = dict(HISTORY["items"][i])
    c = _check_entry(h)
    if c["block"]:
        raise _ItemError(c["block"][0])
    src, out = Path(h["src"]), Path(h["out"])
    item["state"] = "verify"
    if file_sha256(str(out), item=item) != h["out_hash"]:  # any change of bytes after compression
        _set_hist(key, verify_failed=True)
        raise _ItemError(M("verify.hash"))
    item["pct"] = 0
    bad = verify_output(out, probe_cached(str(src)), item, src_path=str(src))
    if bad:
        _set_hist(key, verify_failed=True)
        raise _ItemError(bad)
    item["state"], item["pct"] = "replace", 100
    # the check took long: compare everything once more right before the move
    c = _check_entry(h)
    if c["block"]:
        raise _ItemError(c["block"][0])
    target, tmp = _replace_target(src), _tmp_for(src)
    same_vol = os.stat(str(out)).st_dev == os.stat(str(src.parent)).st_dev
    _set_hist(key, replace_tmp=str(tmp), replace_copy=not same_vol)  # intent: in case of a failure in the middle
    try:
        if same_vol:
            os.rename(str(out), str(tmp))  # rename does not overwrite: if the place is taken - an error
        else:
            shutil.copy2(str(out), str(tmp))
            import filecmp
            if not filecmp.cmp(str(out), str(tmp), shallow=False):
                raise OSError("copy differs from the compressed file")
        if os.path.getsize(str(tmp)) != h["out_sig"][0]:
            raise OSError("size changed while moving")
    except OSError as e:
        try:
            if same_vol and tmp.exists() and not out.exists():
                os.rename(str(tmp), str(out))
            elif not same_vol:
                _rm(tmp)
        except OSError:
            pass
        _set_hist(key, replace_tmp=None, replace_copy=None)
        raise _ItemError(M("rep.err.move", detail=str(e)[:200]))
    # the original goes to the Recycle Bin; first make sure once more that it will fit there
    b = bin_check(src, os.path.getsize(str(src)))
    t0 = time.time()
    if b or not recycle(src):
        try:
            if same_vol:
                os.rename(str(tmp), str(out))
            else:
                _rm(tmp)
        except OSError:
            _set_hist(key, replace_tmp=str(tmp))
            raise _ItemError(M("rep.err.rollback", tmp=str(tmp)))
        _set_hist(key, replace_tmp=None, replace_copy=None)
        raise _ItemError(b or M("rep.err.recycle"))
    binned = False
    for _ in range(15):  # Windows appends the Recycle Bin entry slightly later than the deletion finishes
        if in_recycle_bin(src, t0):
            binned = True
            break
        time.sleep(0.3)
    try:
        os.rename(str(tmp), str(target))  # will not overwrite if the name is suddenly taken
    except OSError as e:
        raise _ItemError(M("rep.err.final", tmp=str(tmp), detail=str(e)[:200]), after=True)
    if not same_vol:
        _rm(out)
    try:  # remove the empty "compressed" folder (never the output folder you chose)
        if out.parent.name.lower() == "compressed" and not any(out.parent.iterdir()):
            out.parent.rmdir()
    except OSError:
        pass
    _set_hist(key, replaced=True, out=str(target), replaced_t=time.time(), out_size=os.path.getsize(str(target)),
              replace_tmp=None, replace_copy=None, out_sig=src_sig(str(target)))
    with LOCK:
        OUT_OWNERS.pop(_norm(out), None)
        OUT_OWNERS[_norm(target)] = _norm(str(src))
        for j in JOBS:
            if _norm(j["path"]) == _norm(str(src)):
                j["replaced"], j["out_path"] = True, str(target)
    if not binned:
        raise _ItemError(M("rep.err.not_in_bin"), after=True)
    item["state"] = "done"


def replace_recover():
    """At startup: finish or roll back a replacement interrupted by closing the program or by a failure."""
    with LOCK:
        pending = [dict(h) for h in HISTORY["items"] if h.get("replace_tmp")]
    for h in pending:
        try:
            _recover_one(h)
        except Exception as e:
            print(" replace_recover: %s" % e)


def _recover_one(h):
    if True:
        key, src, out, tmp = _hkey(h), Path(h["src"]), Path(h["out"]), Path(h["replace_tmp"])
        if os.path.normcase(str(tmp)) != os.path.normcase(str(_tmp_for(src))) or \
                not str(tmp).lower().endswith(".framewring-new.mp4"):
            _set_hist(key, replace_tmp=None, replace_copy=None)
            return
        try:
            if tmp.exists():
                if src.exists():  # original untouched - restore as it was
                    if h.get("replace_copy"):
                        _rm(tmp)
                    elif not out.exists():
                        os.rename(str(tmp), str(out))
                    _set_hist(key, replace_tmp=None, replace_copy=None)
                else:  # original already in the Recycle Bin - put the compressed one in its place
                    target = _replace_target(src)
                    if not target.exists():
                        os.rename(str(tmp), str(target))
                        if h.get("replace_copy"):
                            _rm(out)
                        _set_hist(key, replaced=True, out=str(target), replaced_t=time.time(), replace_tmp=None,
                                  replace_copy=None, out_sig=src_sig(str(target)))
            else:
                target = _replace_target(src)
                if not src.exists() and target.exists() and h.get("out_sig") and \
                        os.path.getsize(str(target)) == h["out_sig"][0]:
                    _set_hist(key, replaced=True, out=str(target), replaced_t=time.time(), replace_tmp=None,
                              replace_copy=None, out_sig=src_sig(str(target)))
                elif src.exists() and h.get("out_sig") and target == src and \
                        os.path.getsize(str(src)) == h["out_sig"][0] and src_sig(str(src)) != h.get("src_sig"):
                    # .mp4 original: the compressed file is already in its place - the replacement was completed
                    _set_hist(key, replaced=True, out=str(src), replaced_t=time.time(), replace_tmp=None,
                              replace_copy=None, out_sig=src_sig(str(src)))
                elif src.exists():
                    _set_hist(key, replace_tmp=None, replace_copy=None)
        except OSError as e:
            print(" replace_recover %s: %s" % (src, e))


class _ItemError(Exception):
    def __init__(self, m, after=False):
        super().__init__(str(m))
        self.m, self.after = m, after  # after - the original is already in the Recycle Bin, the compressed file is in place


def replace_run(keys):
    """Replaces the chosen ones in turn; each file on its own: an error in one does not affect the others."""
    with LOCK:
        if REPLACE["running"]:
            raise UserError("rep.err.busy")
        REPLACE["running"] = True
        REPLACE["items"] = {k: {"state": "queued", "pct": 0, "err": None} for k in keys}
        REPLACE["ver"] += 1

    def run():
        try:
            for k in keys:
                item = REPLACE["items"][k]
                try:
                    _replace_one(k, item)
                except _ItemError as e:
                    item.update(state="warn" if e.after else "error", err=e.m)
                except UserError as e:
                    item.update(state="error", err=e.msg())
                except Exception as e:
                    item.update(state="error", err="%s: %s" % (type(e).__name__, e))
                REPLACE["ver"] += 1
        finally:
            with LOCK:
                REPLACE["running"] = False
                REPLACE["ver"] += 1
    threading.Thread(target=run, daemon=True).start()


def do_test(job, s):
    info = job["info"]
    tdir = out_dir_for(job, s) / "_tests"
    tdir.mkdir(parents=True, exist_ok=True)
    stem = Path(out_path_for(job, s)).stem
    length = min(float(s.get("testlen") or 120), info["duration"] or 120)
    start = max(0.0, (info["duration"] - length) * 0.4) if info["duration"] > length else 0.0
    ref = tdir / ("%s_original_cut.mkv" % stem)
    tag = "%s_%s_%s" % (s["preset"], s["quality"], s["speed"])
    test = tdir / ("%s_test_%s.mp4" % (stem, tag))

    def fail(err):
        with LOCK:
            job["status"] = "cancelled" if err == "cancel" else "error"
            job["error"] = "" if err == "cancel" else err

    # 1) cut out a piece without re-encoding (via run_ffmpeg: progress is visible and "Stop" works)
    ok, err, _ = run_ffmpeg(["-ss", "%.3f" % start, "-i", job["path"], "-t", "%.3f" % length,
                             "-map", "0:V:0", "-map", "0:a?", "-c", "copy",
                             "-progress", "pipe:1", "-nostats", str(ref)], job, length, M("phase.test_cut"), s)
    if not ok:
        _rm(ref)
        return fail(err)
    try:
        ref_dur = probe(str(ref))["duration"] or length
    except Exception:
        ref_dur = length
    # 2) compress the piece with the same settings
    ok, err, enc_time = encode(job, s, str(ref), str(test), ref_dur, M("phase.test_enc"),
                               ["-movflags", "+faststart"])
    if not ok:
        _rm(test)
        return fail(err)
    ts, rs = test.stat().st_size, ref.stat().st_size
    factor = (info["duration"] or ref_dur) / ref_dur
    res = {"preset": s["preset"], "quality": s["quality"],  # the page builds the test caption in its own language
           "test_size": ts, "ref_size": rs, "est_size": int(ts * factor), "ratio": ts / rs if rs else 0,
           "est_time": enc_time * factor, "vmaf": None, "test_path": str(test), "ref_path": str(ref)}
    # 3) VMAF, if available. Above 1080p we compare at 1080p: the vmaf_v0.6.1 model is designed for it,
    #    and it is computed 2-3 times faster.
    #    Frames are matched by NUMBER, not by time: in a cut MKV the timestamps are rounded to 1 ms,
    #    in MP4 they are exact, and libvmaf compared every 3rd frame with its neighbour (VMAF dropped from ~95 to ~75).
    if CAPS["vmaf"]:
        threads = max(1, (os.cpu_count() or 4) - 1)
        sc = ",scale=-2:1080:flags=bicubic" if (info.get("height") or 0) > 1080 else ""
        rf = "".join(f + "," for f in vfilters(info))  # bring the original to the same form as the result
        lav = ("[0:v]setpts=N/(30*TB)%s,format=yuv420p[d];[1:v]%ssetpts=N/(30*TB)%s,format=yuv420p[r];"
               "[d][r]libvmaf=n_subsample=5:n_threads=%d" % (sc, rf, sc, threads))
        ok, err, tail = run_ffmpeg(["-i", str(test), "-i", str(ref), "-lavfi", lav, "-an", "-sn",
                                    "-progress", "pipe:1", "-nostats", "-f", "null", "-"],
                                   job, ref_dur * (info.get("fps") or 30) * (2 if info.get("interlaced") else 1) / 30,
                                   M("phase.vmaf"), s)
        if err == "cancel":
            return fail(err)
        m = re.search(r"VMAF score[:=]\s*([\d.]+)", tail)
        if m:
            res["vmaf"] = float(m.group(1))
    with LOCK:
        job["test"], job["status"], job["pct"] = res, "tested", 100


HISTORY_FILE = DATA_DIR / "history.json"
HISTORY = {"items": [], "ver": 0}


def load_history():
    items, from_bak = read_json(HISTORY_FILE, list)
    if items is not None:
        HISTORY["items"] = [x for x in items if isinstance(x, dict) and isinstance(x.get("src"), str)
                            and isinstance(x.get("out"), str) and x.get("src") and x.get("out")]
        if from_bak:  # the main file is missing or corrupted - put it back at once
            try:
                write_json(HISTORY_FILE, json.dumps(HISTORY["items"], ensure_ascii=False, indent=0))
            except Exception:
                pass
    with LOCK:  # results of earlier sessions belong to their own sources
        for h in HISTORY["items"]:
            if h.get("out"):
                OUT_OWNERS.setdefault(_norm(h["out"]), _norm(h["src"]))


def add_history(entry):
    """Log of everything compressed: independent of the job list, "Remove finished" does not touch it."""
    with LOCK:
        HISTORY["items"].append(entry)
        HISTORY["ver"] += 1
        data = json.dumps(HISTORY["items"], ensure_ascii=False, indent=0)
    try:
        write_json(HISTORY_FILE, data)
    except Exception:
        pass


QUEUE_FILE = DATA_DIR / "queue.json"
KEEP = ("id", "path", "name", "size", "status", "info", "error", "note", "out_path", "out_size", "test", "mode",
        "part", "src_sig", "replaced")


def _queue_payload():
    with LOCK:
        return [{k: j.get(k) for k in KEEP} for j in JOBS]


_QSAVE = threading.Lock()


def save_queue(payload=None):
    with _QSAVE:
        return _save_queue(payload)


def _save_queue(payload=None):
    try:
        data = json.dumps(payload if payload is not None else _queue_payload(), ensure_ascii=False)
        write_json(QUEUE_FILE, data, backup_every=300)
        return data
    except Exception:
        return None


def queue_saver():
    """Every 2 seconds save the list if it changed: close the window and everything is in place at the next start."""
    last = None
    while True:
        time.sleep(2)
        payload = _queue_payload()
        cur = json.dumps(payload, ensure_ascii=False)
        if cur != last:
            if save_queue(payload) is not None:
                last = cur


def _restore_job(d):
    """One queue entry of the previous session -> a job (or None if the entry is corrupted)."""
    if not isinstance(d, dict):
        return None
    path = d.get("path")
    if not isinstance(path, str) or not path:
        return None
    job = {"id": 0, "path": path, "name": d.get("name") or Path(path).name, "size": d.get("size") or 0,
           "status": d.get("status") or "ready", "info": d.get("info") if isinstance(d.get("info"), dict) else None,
           "error": d.get("error") or "", "note": d.get("note") or "", "pct": 0, "fps": 0, "speed": 0, "eta": None,
           "cur_size": 0, "elapsed": 0, "phase": "", "out_path": d.get("out_path") or "",
           "out_size": d.get("out_size") or 0, "test": d.get("test"), "settings": None, "mode": d.get("mode"),
           "fin": None, "replaced": bool(d.get("replaced")), "src_sig": d.get("src_sig")}
    if d.get("status") == "running" and d.get("part"):  # the previous session broke off in the middle of compression
        _rm_part(d.get("part"))
    if job["status"] in ("running", "queued", "probing"):
        job["status"] = "cancelled" if job["status"] == "running" else "ready"
        if d.get("status") == "running":
            job["note"] = M("note.interrupted")
    if not os.path.isfile(path):
        if job["status"] not in ("done", "skipped", "kept"):
            job["status"], job["error"] = "error", M("err.file_gone")
    elif not job["replaced"]:
        try:
            size = os.path.getsize(path)
        except OSError:
            size = job["size"]
        if size != job["size"] or not job["info"]:  # the file was swapped: re-read the parameters
            job["size"], job["info"] = size, None
            if job["status"] not in ("done", "skipped", "kept"):
                job["status"] = "probing"
    return job


def load_queue():
    """Restore the list of the previous session. What was "running" or "queued" waits for "Compress all".
    A corrupted entry is skipped - it must not prevent startup."""
    saved, _ = read_json(QUEUE_FILE, list)
    if saved is None:
        return 0
    restored = []
    for d in saved:
        try:
            job = _restore_job(d)
        except Exception as e:
            print(" queue entry skipped: %s" % e)
            job = None
        if job:
            restored.append(job)
    with LOCK:
        for job in restored:
            job["id"] = _next_id[0]
            _next_id[0] += 1
            JOBS.append(job)
            if job["status"] in ("done", "skipped") and job["out_path"]:
                OUT_OWNERS[_norm(job["out_path"])] = _norm(job["path"])

    def reprobe(job):
        try:
            info = probe_cached(job["path"])
            with LOCK:
                job["info"] = info
                if job["status"] == "probing":
                    job["status"] = "ready"
        except Exception as e:
            with LOCK:
                job["status"], job["error"] = "error", err_msg(e)
    for job in restored:
        if job["status"] == "probing":
            threading.Thread(target=reprobe, args=(job,), daemon=True).start()
    return len(restored)


def worker():
    while True:
        WAKE.wait()
        with LOCK:
            job = next((j for j in JOBS if j["status"] == "queued"), None)
            if job is None:
                WAKE.clear()
            else:
                job["status"], job["error"], job["note"] = "running", "", ""
                s = dict(job["settings"])
                CUR["cancel"] = False
        if job is None:
            keep_awake(False)
            continue
        keep_awake(bool(s.get("nosleep")))
        try:
            if job["mode"] == "test":
                do_test(job, s)
            else:
                do_full(job, s)
        except Exception as e:
            with LOCK:
                job["status"], job["error"] = "error", (e.msg() if isinstance(e, UserError)
                                                        else "%s: %s" % (type(e).__name__, e))
        with LOCK:
            job["phase"] = ""
            if job["status"] == "running":  # just in case: do not leave "running forever"
                job["status"] = "error"
                job["error"] = job["error"] or M("err.no_result")


# ------------------------------------------------------------- Pickers ----

VIDEO_MASK = "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.ts *.m2ts *.m4v *.wmv *.mts"
WINDOW = {"w": None}  # program window (pywebview), if run in its own window
_PICK_LOCK = threading.Lock()


def _pick_webview(win, kind):
    import webview
    fd = getattr(webview, "FileDialog", None)
    if kind == "history":
        r = win.create_file_dialog(fd.OPEN if fd else webview.OPEN_DIALOG, file_types=("JSON (*.json)",))
    elif kind == "files":
        r = win.create_file_dialog(fd.OPEN if fd else webview.OPEN_DIALOG, allow_multiple=True, file_types=(
            "%s (%s)" % (tr("pick.video"), VIDEO_MASK.replace(" ", ";")), "%s (*.*)" % tr("pick.all")))
    else:
        r = win.create_file_dialog(fd.FOLDER if fd else webview.FOLDER_DIALOG)
    return [str(x) for x in (r or [])]


def _pick_tk(kind):
    """tkinter in a separate thread of this same process (in an exe we cannot run sys.executable -c)."""
    out, err = [], []

    def run():
        try:
            import tkinter as tk
            from tkinter import filedialog
            r = tk.Tk()
            r.withdraw()
            try:
                r.attributes("-topmost", True)
            except Exception:
                pass
            r.update()
            if kind == "history":
                f = filedialog.askopenfilename(parent=r, filetypes=[("JSON", "*.json")])
                if f:
                    out.append(f)
            elif kind == "files":
                out.extend(filedialog.askopenfilenames(parent=r, title=tr("pick.title_files"), filetypes=[
                    (tr("pick.video"), VIDEO_MASK), (tr("pick.all"), "*.*")]))
            else:
                d = filedialog.askdirectory(parent=r, title=tr("pick.title_folder"))
                if d:
                    out.append(d)
            r.destroy()
        except Exception as e:
            err.append(e)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join()
    if err:
        raise UserError("err.pick_failed", detail=str(err[0]))
    return [str(x) for x in out]


def pick(kind):
    if IS_MAC:
        if kind == "files":
            script = ['set fs to choose file with prompt "%s" with multiple selections allowed' % tr("pick.title_files"),
                      'set out to ""', 'repeat with f in fs', 'set out to out & POSIX path of f & linefeed',
                      'end repeat', 'return out']
        else:
            script = ['return POSIX path of (choose folder with prompt "%s")' % tr("pick.title_folder")]
        args = ["osascript"]
        for l in script:
            args += ["-e", l]
        r = run_quiet(args, timeout=3600)
        return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []
    if sys.platform.startswith("linux") and shutil.which("zenity"):
        a = ["zenity", "--file-selection", "--multiple", "--separator=\n"] if kind == "files" else \
            ["zenity", "--file-selection", "--directory"]
        r = run_quiet(a, timeout=3600)
        return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []
    with _PICK_LOCK:  # one picker window at a time
        win = WINDOW["w"]
        if win is not None:
            try:
                return _pick_webview(win, kind)
            except Exception:
                pass
        return _pick_tk(kind)


def open_folder(path):
    p = Path(path)
    target = str(p.parent if p.is_file() else p)
    if IS_WIN:
        if p.is_file():
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            os.startfile(target)
    elif IS_MAC:
        subprocess.Popen(["open", "-R", str(p)] if p.is_file() else ["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


# ------------------------------------------------------------- HTTP ----

_DISK_CACHE = {"key": None, "t": 0, "val": None}


def disk_info(target):
    """Free space; cached for 5 s, and without LOCK: a network drive must not slow compression down."""
    if target is None:
        return None
    key = str(target)
    now = time.time()
    if _DISK_CACHE["key"] == key and now - _DISK_CACHE["t"] < 5:
        return _DISK_CACHE["val"]
    probe_dir = target
    while not probe_dir.exists() and probe_dir.parent != probe_dir:
        probe_dir = probe_dir.parent
    try:
        val = {"path": key, "free": shutil.disk_usage(str(probe_dir)).free}
    except Exception:
        val = None
    _DISK_CACHE.update(key=key, t=now, val=val)
    return val


def snapshot(scan_ver=None):
    with LOCK:
        jobs = [dict(j, settings=None) for j in JOBS]
        running = any(j["status"] == "running" for j in JOBS)
        settings = dict(SETTINGS)
        caps = dict(CAPS)
        target = None
        if JOBS:
            target = out_dir_for(JOBS[0], settings)
        elif settings.get("outdir"):
            target = Path(os.path.expanduser(settings["outdir"]))
    return {"caps": caps, "jobs": jobs, "running": running, "settings": settings, "disk": disk_info(target),
            "presets": list(PRESETS), "sys_lang": SYS_LANG,
            "quality": QUALITY, "scan": scan_public(scan_ver), "hist_ver": HISTORY["ver"],
            "replace": {"running": REPLACE["running"], "ver": REPLACE["ver"],
                        "items": dict(REPLACE["items"])}, "version": __version__, "update": {k: UPDATE[k] for k in ("latest", "state", "pct", "err")},
            "install_kind": install_kind(), "repo": REPO_URL, "donate": DONATE_URL, "window": WINDOW["w"] is not None,
            "hist_count": len(HISTORY["items"])}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _from_browser(self):
        """The request came from a page in the browser (not from a second launch of the program via urllib)."""
        return bool(self.headers.get("Origin") or self.headers.get("Sec-Fetch-Site") or self.headers.get("Referer"))

    def _tok_ok(self, given):
        return hmac.compare_digest(str(given or "").encode(), TOKEN.encode())

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        if self.path == "/api/ping" and not self._from_browser():  # second launch: "Framewring is already running here"
            return self._send(200, {"app": "Framewring"})
        if self.path == "/" or self.path.startswith("/?"):
            m = re.search(r"[?&]t=([0-9a-f]+)", self.path)
            if not m or not self._tok_ok(m.group(1)):  # the page with the key - only via a link from the program itself
                return self._send(403, STALE_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return self._send(200, page_html().encode("utf-8"), "text/html; charset=utf-8")
        if not self._tok_ok(self.headers.get("X-Token")):
            return self._send(403, {"error": "forbidden"})
        if self.path.split("?")[0] == "/api/status":
            m = re.search(r"[?&]sv=(-?\d+)", self.path)
            return self._send(200, snapshot(int(m.group(1)) if m else None))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        if self.path == "/api/show" and not self._from_browser():  # the second launch asks to show the window
            threading.Thread(target=show_self, daemon=True).start()
            return self._send(200, {"ok": True})
        if not self._tok_ok(self.headers.get("X-Token")):
            return self._send(403, {"error": "forbidden"})
        try:
            n = max(0, min(int(self.headers.get("Content-Length") or 0), 1 << 20))
        except ValueError:
            n = 0
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            if not isinstance(body, dict):
                body = {}
        except Exception:
            body = {}
        try:
            res = self.route(self.path, body)
            self._send(200, res if res is not None else {"ok": True})
        except UserError as e:  # the page shows it in its own language by key, error is the fallback text
            self._send(400, {"error": str(e), "msg": e.msg()})
        except Exception as e:
            self._send(400, {"error": str(e)})

    def route(self, path, b):
        if path == "/api/pick":
            paths = pick(b.get("kind", "files"))
            errs = []
            for p in paths:
                for x in add_path(p):
                    if isinstance(x, dict):
                        errs.append(x["error"])
            return {"added": len(paths), "errors": errs}  # errors: strings or {"k","p"}
        if path == "/api/add":
            errs = []
            for p in b.get("paths", []):
                for x in add_path(p):
                    if isinstance(x, dict):
                        errs.append(x["error"])
            return {"errors": errs}
        if path == "/api/settings":
            global PRESET_CHOSEN
            if "preset" in b:
                PRESET_CHOSEN = True
            with LOCK:
                SETTINGS.update(clean_settings(b))
                save_settings()
            if "lang" in b and WINDOW["w"] is not None:
                try:
                    WINDOW["w"].set_title(app_name())
                except Exception:
                    pass
            return None
        if path == "/api/start":
            mode = "test" if b.get("mode") == "test" else "full"
            if not FFMPEG or not FFPROBE:
                raise UserError("err.no_ffmpeg")
            if not CAPS["checked"]:
                raise UserError("api.checking")
            pr = SETTINGS["preset"]
            if not CAPS["presets"].get(pr, {}).get("ok"):
                raise UserError("api.mode_unavailable")
            n = 0
            with LOCK:
                for j in JOBS:
                    if j["info"] and j["status"] in ("ready", "tested", "cancelled", "error"):
                        j["status"], j["mode"], j["settings"] = "queued", mode, dict(SETTINGS)
                        j["error"], j["note"], j["pct"] = "", "", 0
                        if mode == "test":
                            j["test"] = None
                        n += 1
            WAKE.set()
            return {"queued": n}
        if path == "/api/cancel":
            with LOCK:
                if any(j["status"] == "running" for j in JOBS):
                    CUR["cancel"] = True
                for j in JOBS:
                    if j["status"] == "queued":
                        j["status"] = "ready"
                p = CUR["proc"]
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass

                def _kill_later(proc=p):
                    time.sleep(5)
                    if proc.poll() is None:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                threading.Thread(target=_kill_later, daemon=True).start()
            return None
        if path == "/api/quit":  # only for browser mode: there is no window, and in an exe no console either
            threading.Thread(target=quit_app, daemon=True).start()
            return None
        if path == "/api/drives":
            return {"drives": list_drives()}
        if path == "/api/scan":
            start_scan(b.get("roots") or [], b.get("min_mb", 500), b.get("everything", True))
            return None
        if path == "/api/scan_cancel":
            SCAN["cancel"] = True
            return None
        if path == "/api/retry":
            if not CAPS["checked"]:
                raise UserError("api.checking")
            if not CAPS["presets"].get(SETTINGS["preset"], {}).get("ok"):
                raise UserError("api.mode_unavailable")
            with LOCK:
                j = next((x for x in JOBS if x["id"] == b.get("id")), None)
                if not j or j["status"] not in ("error", "cancelled", "ready", "tested", "kept"):
                    raise UserError("api.cant_retry")
                if not j["info"]:
                    raise UserError("api.unreadable", detail=j["error"] or M("api.no_info"))
                j["status"], j["settings"] = "queued", dict(SETTINGS)
                j["mode"] = j["mode"] if j["mode"] in ("test", "full") else "full"
                j["error"], j["note"], j["pct"] = "", "", 0
                if j["mode"] == "test":
                    j["test"] = None
            WAKE.set()
            return None
        if path == "/api/remove":
            with LOCK:
                JOBS[:] = [j for j in JOBS if not (j["id"] == b.get("id") and j["status"] != "running")]
            return None
        if path == "/api/clear":
            with LOCK:
                JOBS[:] = [j for j in JOBS if j["status"] not in ("done", "skipped", "kept")]
            return None
        if path == "/api/report":
            webbrowser.open(report_url())
            return None
        if path == "/api/open_log":
            log = DATA_DIR / "framewring.log"
            if not log.exists():
                raise UserError("api.no_log")
            open_folder(str(log))
            return None
        if path == "/api/update_page":
            webbrowser.open(UPDATE["notes_url"] or RELEASES_URL)
            return None
        if path == "/api/update_install":
            if UPDATE["state"] in ("download", "install"):
                return None
            install_update()
            return None
        if path == "/api/url":
            url = b.get("url")
            if url not in OPEN_URLS:
                raise UserError("api.url_denied")
            webbrowser.open(url)
            return {"ok": True}
        if path == "/api/open":
            which = b.get("which")
            with LOCK:
                if "hist" in b:  # a history row: the job may no longer be in the list
                    i = b.get("hist")
                    h = HISTORY["items"][i] if isinstance(i, int) and 0 <= i < len(HISTORY["items"]) else None
                    target = h and (h["src"] if which == "src" else h["out"])
                else:
                    j = next((x for x in JOBS if x["id"] == b.get("id")), None)
                    target = j and (j["path"] if which == "src" else
                                    which == "test" and j.get("test") and j["test"]["test_path"] or
                                    j["out_path"] or j["path"])
            if target:
                if not Path(target).exists():
                    raise UserError("api.open_missing", path=str(target))
                open_folder(target)
            return None
        if path == "/api/replace_list":
            return {"items": replace_candidates(), "running": REPLACE["running"]}
        if path == "/api/replace":
            keys = [k for k in (b.get("keys") or []) if isinstance(k, str)]
            if not keys:
                raise UserError("rep.err.none")
            if any(_hist_find(k) is None for k in keys):
                raise UserError("rep.err.blocked")
            replace_run(keys)
            return None
        if path == "/api/hist_export":
            d = _documents_dir()
            f = d / ("Framewring-history-%s.json" % time.strftime("%Y-%m-%d_%H-%M-%S"))
            with LOCK:
                data = json.dumps(HISTORY["items"], ensure_ascii=False, indent=1)
            f.write_text(data, encoding="utf-8")
            open_folder(str(f))
            return {"path": str(f)}
        if path == "/api/hist_import":
            if REPLACE["running"]:
                raise UserError("rep.err.busy")
            files = pick("history") if b.get("path") is None else [b.get("path")]
            if not files:
                return {"added": 0}
            try:
                items = json.loads(Path(files[0]).read_text(encoding="utf-8"))
                if not isinstance(items, list):
                    raise ValueError
                items = [x for x in items if isinstance(x, dict) and isinstance(x.get("src"), str)
                         and isinstance(x.get("out"), str) and x.get("src") and x.get("out")]
                for x in items:  # imported entries cannot be replaced until the file is re-compressed
                    for k in ("replace_tmp", "replace_copy", "src_sig", "out_sig", "out_hash", "verify_failed"):
                        x.pop(k, None)
                    x["imported"] = True
            except Exception:
                raise UserError("hist.import_bad")
            with LOCK:
                have = {(_norm(h["src"]), _norm(h["out"]), h.get("t")) for h in HISTORY["items"]}
                new = [x for x in items if (_norm(x["src"]), _norm(x["out"]), x.get("t")) not in have]
                HISTORY["items"].extend(new)
                HISTORY["items"].sort(key=lambda h: h.get("t") or 0)
                HISTORY["ver"] += 1
                data = json.dumps(HISTORY["items"], ensure_ascii=False, indent=0)
                for h in new:
                    OUT_OWNERS.setdefault(_norm(h["out"]), _norm(h["src"]))
            write_json(HISTORY_FILE, data)
            return {"added": len(new)}
        if path == "/api/history":
            with LOCK:
                items = [dict(x, idx=i) for i, x in enumerate(HISTORY["items"])]
                ver = HISTORY["ver"]
            return {"items": items[::-1], "ver": ver}
        raise RuntimeError("unknown endpoint")


STALE_HTML = """<!doctype html><meta charset="utf-8"><title>Framewring</title>
<body style="font:16px system-ui;background:#0f1115;color:#e8eaf0;padding:40px">
<h2>Framewring</h2><p>This page is out of date. Open the program from its shortcut.</p>
<p>Эта вкладка устарела. Открой программу заново через ярлык.</p></body>"""

HTML = r"""<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Framewring</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--line:#262b36;--fg:#e8eaf0;--mut:#8b93a7;--acc:#7c5cff;--acc2:#2bd9a8;--warn:#ffb347;--err:#ff5d6c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1400px;margin:0 auto;padding:18px 22px 0;height:100vh;display:flex;flex-direction:column}
body{overflow:hidden}
.grid>.col{overflow-y:auto;min-height:0;padding-bottom:18px;scrollbar-width:thin;scrollbar-color:#2c3240 transparent}
.grid>.col::-webkit-scrollbar{width:9px}.grid>.col::-webkit-scrollbar-thumb{background:#2c3240;border-radius:9px}
.grid>.col::-webkit-scrollbar-thumb:hover{background:#3a4152}
@media(max-width:700px){body{overflow:auto}.wrap{height:auto;padding-bottom:22px}.grid>.col{overflow:visible}}
h1{margin:0;font-size:22px;letter-spacing:.2px}h1 span{color:var(--acc)}
.sub{color:var(--mut);margin-top:2px}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin-bottom:16px;flex-wrap:wrap}
.pill{font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:99px;padding:4px 10px}
.grid{display:grid;grid-template-columns:380px minmax(0,1fr);grid-template-rows:minmax(0,1fr);gap:16px;flex:1;min-height:0}@media(max-width:1000px){.grid{grid-template-columns:300px minmax(0,1fr)}}@media(max-width:700px){.grid{grid-template-columns:1fr}.grid>:last-child{order:-1}}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:0 0 10px}
.opt{display:block;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:8px;cursor:pointer}
.opt:hover{border-color:#3a4152}.opt.on{border-color:var(--acc);background:#7c5cff14}
.opt.off{opacity:.45;cursor:not-allowed}.opt b{display:block}.opt small{color:var(--mut)}
.opt input{display:none}
.seg{display:flex;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:6px}
.seg button{flex:1;background:none;border:0;color:var(--fg);padding:8px 4px;cursor:pointer;font:inherit;border-right:1px solid var(--line)}
.seg button:last-child{border-right:0}.seg button.on{background:var(--acc);color:#fff}
.hint{color:var(--mut);font-size:12px;margin:0 0 12px}
label.chk{display:flex;gap:8px;align-items:center;margin:6px 0;cursor:pointer}
input[type=text]{width:100%;background:#0f1115;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px 10px;font:inherit}
.row{display:flex;gap:8px;flex-wrap:wrap}
.btn{background:#232836;border:1px solid var(--line);color:var(--fg);padding:9px 14px;border-radius:10px;cursor:pointer;font:inherit}
.btn:hover{border-color:#3a4152}.btn.pri{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.btn.go{background:var(--acc2);border-color:var(--acc2);color:#062a20;font-weight:700}
.btn.red{background:#ff5d6c22;border-color:var(--err);color:var(--err)}
.btn:disabled{opacity:.4;cursor:not-allowed}.btn.sm{padding:4px 9px;font-size:12px;border-radius:8px}
.big{font-size:16px;padding:12px 20px}
.job{border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px}
.jh{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.jn{font-weight:600;overflow-wrap:anywhere}.meta{color:var(--mut);font-size:12px;margin-top:2px}
.bar{height:8px;background:#0f1115;border-radius:99px;overflow:hidden;margin:10px 0 6px;border:1px solid var(--line)}
.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--acc2));width:0;transition:width .6s}
.bar.busy i{background:repeating-linear-gradient(45deg,var(--acc) 0 12px,var(--acc2) 12px 24px);background-size:34px 34px;animation:stripes 1s linear infinite}
@keyframes stripes{to{background-position:34px 0}}
.st{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}
.st.done{color:var(--acc2);border-color:var(--acc2)}.st.kept{color:var(--mut);border-color:var(--mut)}.st.error{color:var(--err);border-color:var(--err)}
.st.running{color:#fff;background:var(--acc);border-color:var(--acc)}.st.tested{color:var(--warn);border-color:var(--warn)}
.res{margin-top:8px;padding:10px;border-radius:10px;background:#0f1115;border:1px dashed var(--line);font-size:13px}
.res b{color:var(--acc2)}.err{color:var(--err);white-space:pre-wrap;font:12px/1.4 ui-monospace,Consolas,monospace;max-height:160px;overflow:auto;margin-top:8px}
.empty{color:var(--mut);text-align:center;padding:40px 10px;border:1px dashed var(--line);border-radius:12px}
.ok{color:var(--acc2)}.intro{margin-bottom:16px;border-color:var(--acc)}.intro ol{margin:10px 0 0;padding-left:20px;line-height:1.7}
.mbox.repbox{max-width:820px;width:94vw}.rrow{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:start;padding:8px 10px;border-bottom:1px solid var(--line)}
.rrow:last-child{border-bottom:0}.rrow.off>input,.rrow.off .sname,.rrow.off .num{opacity:.55}.rrow .tag{margin:4px 6px 0 0;display:inline-block;white-space:normal}
.rrow .blk{color:var(--err);font-size:12px;margin-top:4px}.rrow .wrn{color:var(--warn);font-size:12px;margin-top:4px}.rrow.pre{outline:1px solid var(--acc);outline-offset:-1px}
.updbox{border:1px solid var(--acc);background:#7c5cff18;padding:10px 12px;border-radius:12px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.warnbox{border:1px solid var(--warn);background:#ffb34714;color:var(--warn);padding:12px;border-radius:12px;margin-bottom:14px}
.foot{color:var(--mut);font-size:12px;margin-top:14px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
@media(max-width:1200px){.hrow{grid-template-columns:minmax(120px,1fr) auto!important}.hrow>:nth-child(1),.hrow>:nth-child(4){display:none}.hrow>:nth-child(3){grid-column:1}}.toast{overflow-wrap:anywhere}
.hrow>.row{flex-direction:column;align-items:stretch;gap:4px}.hrow .btn{white-space:nowrap}
.hrow{display:grid;grid-template-columns:88px minmax(160px,1fr) 150px 130px auto;gap:10px;align-items:center;padding:8px 10px;border-bottom:1px solid var(--line)}
.hrow:last-child{border-bottom:0}.hrow .meta{margin:0;overflow-wrap:anywhere}
.don{border-color:#ff6b9a55;color:#ff9abb}.don:hover{border-color:#ff6b9a;background:#ff6b9a14}
.modal{position:fixed;inset:0;background:#000a;display:none;align-items:center;justify-content:center;z-index:50;padding:16px}
.modal.on{display:flex}.mbox{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;max-width:560px;width:100%}
.mbox h3{margin:0 0 4px;font-size:18px}.wal{border:1px solid var(--line);border-radius:12px;padding:12px;margin-top:12px}
.wal b{display:block;margin-bottom:6px}.addr{display:flex;gap:8px;align-items:center}
.addr code{flex:1;background:#0f1115;border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:13px ui-monospace,Consolas,monospace;overflow-wrap:anywhere;user-select:all}
a{color:var(--acc)}:root{color-scheme:dark}.jh .btn{white-space:nowrap}
.toast{z-index:60;position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#232836;border:1px solid var(--line);padding:10px 16px;border-radius:10px;display:none;max-width:90%}
.note{color:var(--warn);font-size:12px;margin-top:6px}
.scanlist{max-height:min(440px,calc(100vh - 260px));min-height:160px;overflow:auto;border:1px solid var(--line);border-radius:10px;margin-top:8px}
@media(max-width:1100px){.srow{grid-template-columns:22px minmax(0,1fr) auto!important}.srow>:nth-child(3),.srow>:nth-child(4){display:none}}
.srow{display:grid;grid-template-columns:22px minmax(0,1fr) 86px 120px auto;gap:10px;align-items:center;padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer}
.srow:last-child{border-bottom:0}.srow:hover{background:#ffffff06}.srow .meta{margin:0;overflow-wrap:anywhere}
.srow.dim{opacity:.55}.sname{font-weight:600;overflow-wrap:anywhere}.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{font-size:11px;padding:1px 7px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}
.tag.g{color:var(--acc2);border-color:var(--acc2)}.tag.y{color:var(--warn);border-color:var(--warn)}.tag.m{color:var(--mut)}
.drv{display:inline-flex;gap:6px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:6px 10px;cursor:pointer}
.drv.on{border-color:var(--acc);background:#7c5cff14}.drv input{margin:0}
.vm{font-weight:700}.vm.g{color:var(--acc2)}.vm.y{color:var(--warn)}.vm.r{color:var(--err)}
.lng{font-size:12px;font-weight:400;margin-left:10px;vertical-align:middle;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:2px 4px;cursor:pointer}
.lng:hover{border-color:#3a4152}
</style></head><body><div class="wrap">
<div class="top"><div><h1><span>Framewring</span><span data-t="app.suffix"></span> <small id="appver" style="font-size:12px;color:var(--mut);font-weight:400"></small><select class="lng" id="lng" data-tt="lang.title">__LANGOPTS__</select></h1>
<div class="sub" data-t="app.sub"></div></div>
<div class="row" style="align-items:center"><button class="btn sm" onclick="report(true)" data-t="report.btn" data-tt="report.btn_title"></button><button class="btn sm don" onclick="donate(true)" data-t="donate.btn" data-tt="donate.btn_title"></button><div class="pill" id="ver" data-t="ver.checking"></div></div></div>
<div id="warn"></div><div id="upd"></div>
<div class="grid">
<div class="col">
 <div class="card">
  <h2 data-t="set.mode"></h2><div id="presets"></div>
  <h2 style="margin-top:14px" data-t="set.quality"></h2>
  <div class="seg" id="q"><button data-v="high" data-t="quality.high"></button><button data-v="balanced" data-t="quality.balanced"></button><button data-v="compact" data-t="quality.compact"></button></div>
  <p class="hint" id="qhint"></p>
  <h2 data-t="set.speed"></h2>
  <div class="seg" id="sp"><button data-v="slow" data-t="speed.slow"></button><button data-v="normal" data-t="speed.normal"></button><button data-v="fast" data-t="speed.fast"></button></div>
  <p class="hint" data-t="set.speed_hint"></p>
  <h2 data-t="set.audio"></h2>
  <div class="seg" id="au"><button data-v="auto" data-t="audio.auto"></button><button data-v="aac" data-t="audio.aac"></button></div>
  <p class="hint" data-t="set.audio_hint"></p>
  <h2 data-t="set.outdir"></h2>
  <input type="text" id="outdir" data-tp="set.outdir_ph">
  <div style="margin-top:10px">
   <label class="chk"><input type="checkbox" id="lowprio"> <span data-t="set.lowprio"></span></label>
   <label class="chk"><input type="checkbox" id="nosleep"> <span data-t="set.nosleep"></span></label>
<label class="chk"><input type="checkbox" id="update_check"> <span data-t="set.update_check"></span></label>
   <label class="chk"><input type="checkbox" id="skip"> <span data-t="set.skip"></span></label>
  </div>
 </div>
</div>
<div class="col" id="rcol">
<div class="card" id="scanCard" style="display:none;margin-bottom:16px">
  <div class="row" style="justify-content:space-between;align-items:center"><h2 style="margin:0" data-t="scan.title"></h2><button class="btn sm" onclick="toggleScan(false)" data-t="common.collapse"></button></div>
  <p class="hint" style="margin-top:8px" data-t="scan.hint"></p>
  <div class="row" id="drives"></div>
  <div class="row" style="margin-top:8px"><input type="text" id="scanPath" data-tp="scan.path_ph" style="flex:1"></div>
  <div class="row" style="margin-top:8px;align-items:center"><span class="meta" style="margin:0" data-t="scan.min_label"></span>
   <div class="seg" id="minmb" style="margin:0;flex:1;min-width:260px"><button data-v="200" data-t="scan.min200"></button><button data-v="500" data-t="scan.min500"></button><button data-v="1000" data-t="scan.min1000"></button><button data-v="3000" data-t="scan.min3000"></button></div>
   <label class="chk" style="margin:0" data-tt="scan.ev_title"><input type="checkbox" id="useEv" checked> <span data-t="scan.ev_label"></span></label>
   <button class="btn pri" id="btnScan" onclick="scanStart()" data-t="scan.search"></button><button class="btn red" id="btnScanStop" onclick="api('/api/scan_cancel')" style="display:none" data-t="common.stop"></button></div>
  <div class="meta" id="scanInfo" style="margin-top:10px"></div>
  <div id="scanBar" class="row" style="margin-top:8px;align-items:center;display:none"></div>
  <div class="scanlist" id="scanList" style="display:none"></div>
 </div>
<div class="card" id="histCard" style="display:none;margin-bottom:16px">
  <div class="row" style="justify-content:space-between;align-items:center"><h2 style="margin:0" data-t="hist.title"></h2><button class="btn sm" onclick="toggleHist(false)" data-t="common.collapse"></button></div>
  <div class="meta" id="histSum" style="margin-top:8px"></div>
  <div class="row" style="margin-top:6px"><button class="btn sm" onclick="histExport()" data-t="hist.export"></button><button class="btn sm" onclick="histImport()" data-t="hist.import"></button></div>
  <div class="scanlist" id="histList" style="margin-top:8px"></div>
 </div>
 <div class="card">
  <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:12px">
   <div class="row"><button class="btn pri" onclick="pick('files')" data-t="btn.files"></button><button class="btn" onclick="pick('folder')" data-t="btn.folder"></button><button class="btn" onclick="toggleScan()" data-t="btn.scan" data-tt="btn.scan_title"></button><button class="btn" onclick="toggleHist()" data-t="btn.hist" data-tt="btn.hist_title"></button></div>
   <div class="row"><button class="btn" id="btnTest" onclick="start('test')" data-tt="btn.test_title"></button>
   <button class="btn go big" id="btnGo" onclick="start('full')" data-t="btn.go"></button>
   <button class="btn red" id="btnStop" onclick="cancel()" style="display:none" data-t="common.stop"></button></div>
  </div>
  <div class="row" style="margin-bottom:12px"><input type="text" id="manual" data-tp="manual.ph" style="flex:1"><button class="btn" onclick="addManual()" data-t="manual.add"></button></div>
  <div id="intro"></div>
<div id="jobs"></div>
  <div class="foot"><span><span id="disk"></span> <span id="qinfo" style="margin-left:10px"></span></span><span><a href="#" onclick="openReplace();return false" data-t="rep.btn_all"></a> · <a href="#" onclick="api('/api/clear');return false" style="color:var(--mut)" data-t="btn.clear"></a></span></div>
 </div>
</div></div></div>
<div class="modal" id="donate" onclick="if(event.target===this)donate(false)"><div class="mbox" role="dialog" data-ta="donate.title">
 <div class="row" style="justify-content:space-between;align-items:flex-start;flex-wrap:nowrap"><div><h3 data-t="donate.title"></h3><div class="meta" data-t="donate.text"></div></div><button class="btn sm" onclick="donate(false)" data-ta="common.close">✕</button></div>
  <p style="margin:14px 0 10px" data-t="donate.ways"></p>
 <button class="btn pri" onclick="openUrl(S.donate)" data-t="donate.open"></button>
 <p class="hint" style="margin:14px 0 0"><span data-t="donate.official"></span> <b id="repoUrl">github.com/remrem23/framewring</b>. <span data-t="donate.official2"></span></p>
</div></div>
<div class="modal" id="replace" onclick="if(event.target===this)closeReplace()"><div class="mbox repbox" role="dialog" aria-modal="true" data-ta="rep.title">
 <div class="row" style="justify-content:space-between;align-items:flex-start;flex-wrap:nowrap"><div><h3 data-t="rep.title"></h3><div class="meta" data-t="rep.text"></div></div><button class="btn sm" onclick="closeReplace()" data-ta="common.close">✕</button></div>
 <div class="row" style="margin:10px 0 6px;align-items:center"><button class="btn sm" id="repSafe" onclick="repPick('safe')" data-t="rep.pick_safe"></button><button class="btn sm" id="repNone" onclick="repPick('none')" data-t="rep.pick_none"></button></div>
 <div id="repList" class="scanlist"></div>
 <div class="row" style="justify-content:space-between;align-items:center;margin-top:10px"><span id="repSum" class="meta"></span><button class="btn pri" id="repGo" onclick="doReplace()"></button></div>
</div></div>
<div class="modal" id="report" onclick="if(event.target===this)report(false)"><div class="mbox" role="dialog" data-ta="report.title">
 <div class="row" style="justify-content:space-between;align-items:flex-start;flex-wrap:nowrap"><div><h3 data-t="report.title"></h3><div class="meta" data-t="report.text"></div></div><button class="btn sm" onclick="report(false)" data-ta="common.close">✕</button></div>
 <p style="margin:14px 0 10px" data-t="report.log"></p>
 <div class="row"><button class="btn pri" onclick="api('/api/report')" data-t="report.open"></button><button class="btn" onclick="api('/api/open_log')" data-t="report.open_log"></button></div>
</div></div>
<div class="toast" id="toast"></div>
<script>
const T="__TOKEN__";let S=null;
// ---------------- language: dictionary from i18n.py (the same as in the backend)
const I18N=__I18N__;let LANG="__LANG__";
const LOCS={ru:"ru-RU",en:"en-US",de:"de-DE",fr:"fr-FR",es:"es-ES",pt:"pt-BR",zh:"zh-CN"};const LOC=()=>LOCS[LANG]||"en-US";
const nf=(x,d=0)=>Number(x||0).toLocaleString(LOC(),{minimumFractionDigits:d,maximumFractionDigits:d});
const nfm=(x,m)=>Number(x||0).toLocaleString(LOC(),{maximumFractionDigits:m});
function tr(k,p){let s=(I18N[LANG]||{})[k];if(s==null&&LANG!=="ru")s=I18N.en[k];if(s==null)s=I18N.ru[k];if(s==null)s=k;return p?s.replace(/\{(\w+)\}/g,(m,n)=>n in p?fmtP(p[n]):m):s}
function fmtP(v){return v&&typeof v==="object"?msg(v):typeof v==="number"?nfm(v,1):String(v)}
// backend message: a string (old entries, raw ffmpeg text), {k,p} or a list of those
function msg(x){if(x==null||x==="")return"";if(typeof x==="string")return x;if(Array.isArray(x))return x.map(msg).filter(Boolean).join(" ");if(x.k)return tr(x.k,x.p||{});return String(x)}
function applyStatic(){document.documentElement.lang=LANG;
 document.querySelectorAll("[data-t]").forEach(e=>e.textContent=tr(e.dataset.t));
 document.querySelectorAll("[data-tt]").forEach(e=>e.title=tr(e.dataset.tt));
 document.querySelectorAll("[data-tp]").forEach(e=>e.placeholder=tr(e.dataset.tp));
 document.querySelectorAll("[data-ta]").forEach(e=>e.setAttribute("aria-label",tr(e.dataset.ta)));
 $("lng").value=LANG;
 $("btnTest").textContent=testLabel(S?S.settings.testlen:120);
 if(S){render();renderScan({...S.scan,results:null})}else document.title=tr("app.title");
 if(drives)renderDrives()}
function setLang(l){if(!S||l===LANG)return;LANG=l;histVer=-1;setS("lang",l);applyStatic();if(histOpen)loadHist()}
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
// innerHTML only on a real change: otherwise buttons are recreated every second and a click gets "lost"
function setHTML(el,h){if(el._h!==h){el.innerHTML=h;el._h=h}}
async function api(p,b){try{const r=await fetch(p,{method:"POST",headers:{"X-Token":T,"Content-Type":"application/json"},body:JSON.stringify(b||{})});const j=await r.json().catch(()=>({}));if(r.status===403){stale();return {}}if(!r.ok)toast(j.msg?msg(j.msg):(j.error||tr("err.generic")));return j}catch(e){toast(tr("err.no_response"));return {}}}
function stale(){document.body.innerHTML=`<div style="padding:40px;font-size:16px">${esc(tr("stale.text"))}</div>`}
function toasts(a){a=(a||[]).map(msg).filter(Boolean);if(a.length)toast(a.slice(0,4).join(" · ")+(a.length>4?` (+${a.length-4})`:""))}
// drag and drop: without this the window would open the video itself instead of the program
["dragover","drop"].forEach(ev=>window.addEventListener(ev,e=>{e.preventDefault();if(ev==="drop"&&!S?.window)toast(tr("drop.browser"))}));
function donate(on){const d=$("donate");if(d)d.classList.toggle("on",on)}
function report(on){const d=$("report");if(d)d.classList.toggle("on",on)}
async function histExport(){const r=await api("/api/hist_export");if(r.path)toast(tr("hist.exported",{path:r.path}))}
async function histImport(){const r=await api("/api/hist_import");if(r.added!=null){toast(tr("hist.imported",{n:r.added}));histVer=-1;if(histOpen)loadHist()}}
function renderIntro(){const el=$("intro");if(!el)return;if(localStorage.getItem("fw_intro")==="1"){setHTML(el,"");return}
 setHTML(el,`<div class="card intro"><div class="row" style="justify-content:space-between;align-items:center;flex-wrap:nowrap"><h2 style="margin:0">${esc(tr("intro.title"))}</h2><button class="btn sm" onclick="localStorage.setItem('fw_intro','1');renderIntro()">${esc(tr("intro.ok"))}</button></div>
 <ol>${["intro.s1","intro.s2","intro.s3","intro.s4"].map(k=>`<li>${esc(tr(k))}</li>`).join("")}</ol></div>`)}
// ---------------- replacing originals: only what the person ticked themselves
let repList=[],repSel=new Set(),repWasRunning=false;
let repPre=null,repLoading=false,repFailed=false;
async function openReplace(pre,preOut){repSel.clear();repPre=null;repLoading=true;repFailed=false;repList=[];
 $("replace").classList.add("on");renderReplace();setTimeout(()=>{const b=$("repNone");if(b)b.focus()},0);
 const r=await api("/api/replace_list");repLoading=false;repFailed=!r.items;repList=r.items||[];
 // button at a file: highlight its row; tick by ourselves only when there are no warnings
 if(pre){const c=repList.find(c=>pk(c.src)===pk(pre)&&(!preOut||pk(c.out)===pk(preOut)));
  if(c){repPre=c.key;if(!c.block.length&&!c.warn.length)repSel.add(c.key)}}
 renderReplace();if(repPre){const el=document.querySelector(`#repList [data-k="${CSS.escape(repPre)}"]`);if(el)el.closest(".rrow").scrollIntoView({block:"center"})}}
function closeReplace(){$("replace").classList.remove("on")}
function repPick(m){repSel.clear();if(m==="safe")for(const c of repList)if(!c.block.length&&!c.warn.length&&!repDone(c))repSel.add(c.key);renderReplace()}
const repState=c=>((S&&S.replace&&S.replace.items)||{})[c.key];
const repDone=c=>{const s=repState(c);return s&&s.state==="done"};
function renderReplace(){if(!$("replace").classList.contains("on"))return;
 const running=!!(S&&S.replace&&S.replace.running);
 $("repSafe").disabled=$("repNone").disabled=running||repLoading;
 if(repLoading||repFailed||!repList.length){setHTML($("repList"),`<div class="empty">${esc(tr(repLoading?"rep.loading":repFailed?"rep.load_failed":"rep.none"))}</div>`)}else
 setHTML($("repList"),repList.map(c=>{const st=repState(c);const off=c.block.length||running||repDone(c);
  const fin=(st&&(st.state==="done"||st.state==="warn"))||c.block.some(b=>b.k==="rep.b.replaced");
  const d=c.size?Math.round((1-c.out_size/c.size)*100):0;
  let status="";if(st){status=st.state==="verify"?tr("rep.s.verify",{pct:nf(st.pct,0)}):st.state==="replace"?tr("rep.s.replace"):st.state==="done"?tr("rep.s.done"):st.state==="error"?tr("rep.s.error",{err:msg(st.err)}):st.state==="warn"?tr("rep.s.warn",{err:msg(st.err)}):tr("rep.s.queued");
   status=`<div class="${st.state==="error"?"blk":st.state==="done"?"ok":st.state==="warn"?"wrn":"meta"}">${esc(status)}</div>`}
  const checked=repSel.has(c.key)&&(!off||(running&&st));
  return `<div class="rrow ${off?"off":""} ${c.key===repPre?"pre":""}"><input type="checkbox" data-k="${esc(c.key)}" ${checked?"checked":""} ${off?"disabled":""}>
   <div><div class="sname">${esc(c.name)}</div><div class="meta">${esc(c.src.replace(/[\\/][^\\/]*$/,""))}</div>
   <div class="meta">→ ${esc(c.out||"")}</div>
   ${fin?"":c.warn.map(w=>`<span class="tag y">⚠ ${esc(msg(w))}</span>`).join("")}${st&&st.state==="done"?"":c.block.map(b=>b.k==="rep.b.replaced"?`<div class="ok">✓ ${esc(msg(b))}</div>`:`<div class="blk">${esc(msg(b))}</div>`).join("")}${status}</div>
   <div class="num"><b>${gb(c.size)} → ${gb(c.out_size)}</b><div class="meta">${c.out_size<c.size?"−"+d+"%":""}</div></div></div>`}).join(""));
 const sel=repList.filter(c=>repSel.has(c.key)&&!c.block.length&&!repDone(c));
 $("repSum").textContent=running?tr("rep.running"):tr("rep.summary",{n:sel.length,size:gb(sel.reduce((a,c)=>a+c.size-c.out_size,0))});
 const g=$("repGo");g.textContent=running?tr("rep.s.replace"):tr("rep.go",{n:sel.length});g.disabled=running||repLoading||!sel.length}
async function doReplace(){const sel=repList.filter(c=>repSel.has(c.key)&&!c.block.length&&!repDone(c));if(!sel.length)return;
 const warned=sel.filter(c=>c.warn.length);
 // confirmation is always required: no file is replaced without a separate "yes"
 const lim=(a,f)=>a.slice(0,12).map(f).join("\n")+(a.length>12?"\n"+tr("rep.confirm_more",{n:a.length-12}):"");
 let q=tr("rep.confirm",{n:sel.length,list:lim(sel,c=>"• "+c.name)});
 if(warned.length)q+="\n\n"+tr("rep.confirm_warn",{list:lim(warned,c=>"• "+c.name+" — "+c.warn.map(msg).join("; "))});
 if(!confirm(q))return;
 const g=$("repGo");g.disabled=true;
 const r=await api("/api/replace",{keys:sel.map(c=>c.key)});
 if(r&&!r.error&&!r.msg)repWasRunning=true;else g.disabled=false;refresh()}
async function repTick(){const running=!!(S&&S.replace&&S.replace.running);
 if(repWasRunning&&!running){repWasRunning=false;const it=Object.values(S.replace.items||{});
  const okN=it.filter(x=>x.state==="done").length;toast(tr(okN===it.length?"rep.done_sum":"rep.done_partial",{ok:okN,n:it.length}));
  const r=await api("/api/replace_list");const keep=repList;repList=r.items||keep;repSel.clear();histVer=-1}
 renderReplace()}
async function updInstall(){if(S.running&&!confirm(tr("upd.confirm_running")))return;await api("/api/update_install");refresh()}
function renderUpd(){const u=S.update||{};let h="";
 if(u.latest&&localStorage.getItem("fw_upd_skip")!==u.latest){
  const inst=S.install_kind==="installer";let act;
  if(u.state==="download")act=`<span>${esc(tr("upd.downloading",{pct:nf(u.pct,0)}))}</span>`;
  else if(u.state==="install")act=`<span>${esc(tr("upd.installing"))}</span>`;
  else act=(u.state==="error"?`<span style="color:var(--err)">${esc(tr("upd.failed",{err:msg(u.err)}))}</span> `:"")+
   (inst?`<button class="btn sm pri" onclick="updInstall()">${esc(tr("upd.install"))}</button>`:`<button class="btn sm pri" onclick="api('/api/update_page')">${esc(tr("upd.download"))}</button>`)+
   `<button class="btn sm" onclick="api('/api/update_page')">${esc(tr("upd.notes"))}</button><button class="btn sm" onclick="localStorage.setItem('fw_upd_skip','${esc(u.latest)}');renderUpd()">${esc(tr("upd.later"))}</button>`;
  h=`<div class="updbox"><b>${esc(tr("upd.available",{v:u.latest}))}</b><div class="row" style="align-items:center">${act}</div></div>`}
 setHTML($("upd"),h)}
document.addEventListener("keydown",e=>{if(e.key==="Escape"){donate(false);report(false);closeReplace()}});
$("repList").addEventListener("change",e=>{const k=e.target.dataset&&e.target.dataset.k;if(k==null)return;e.target.checked?repSel.add(k):repSel.delete(k);renderReplace()});
$("lng").addEventListener("change",e=>setLang(e.target.value));
async function openUrl(u){if(u)await api("/api/url",{url:u})}
function toast(m){const t=$("toast");if(!t)return;t.textContent=m;t.style.display="block";clearTimeout(t._h);t._h=setTimeout(()=>t.style.display="none",5000)}
const gb=b=>{const n=Math.abs(b||0),sg=b<0?"−":"";return sg+(n>=1e9?nf(n/1e9,2)+" "+tr("unit.gb"):n>=1e7?nf(n/1e6,0)+" "+tr("unit.mb"):nf(n/1e6,1)+" "+tr("unit.mb"))};
const tm=s=>{if(s==null||!isFinite(s))return"—";s=Math.round(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return h?tr("time.hm",{h:String(h),m:String(m)}):m?tr("time.ms",{m:String(m),s:String(x)}):tr("time.s",{s:String(x)})};
const dur=s=>{s=Math.round(s||0);return`${Math.floor(s/3600)}:${String(Math.floor(s%3600/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`};
const pctS=d=>(d<0?"+":"−")+nf(Math.abs(d),0); // -37 (smaller) / +5 (bigger)
const testLabel=tl=>{tl=tl||120;return tl<60?tr("btn.test_sec",{n:String(Math.round(tl))}):tr("btn.test_min",{n:nfm(Math.round(tl/6)/10,1)})};
const presetTitle=k=>I18N.ru["preset."+k+".title"]!=null?tr("preset."+k+".title"):k;
let pending=0,sver=0;
async function setS(k,v){S.settings[k]=v;sver++;pending++;renderSettings();try{await api("/api/settings",{[k]:v})}finally{pending--}}
async function pick(kind){toast(S.window?tr("pick.opening"):tr("pick.opening_browser"));const r=await api("/api/pick",{kind});toasts(r.errors);refresh()}
async function addManual(){const el=$("manual");if(!el.value.trim())return;const v=el.value;el.value="";toast(tr("add.adding"));
 const paths=[...v.matchAll(/"([^"]+)"|([^"\r\n]+)/g)].map(m=>(m[1]||m[2]).trim()).filter(Boolean); // "Copy as path" from Explorer: "a" "b"
 const r=await api("/api/add",{paths});toasts(r.errors);refresh()}
$("manual").addEventListener("keydown",e=>{if(e.key==="Enter")addManual()});
async function start(mode){const r=await api("/api/start",{mode});if(r.queued===0)toast(S.jobs.some(j=>j.status==="probing")?tr("start.probing"):tr("start.nothing"));refresh()}
async function cancel(){const j=S&&S.jobs.find(x=>x.status==="running");if(j&&j.mode!=="test"&&j.pct>2&&!confirm(tr("stop.confirm",{name:j.name,pct:nf(j.pct,0)})))return;await api("/api/cancel");refresh()}
// ---------------- history
let histVer=-1,histOpen=false;
async function toggleHist(show){const c=$("histCard");histOpen=show==null?c.style.display==="none":show;c.style.display=histOpen?"block":"none";if(histOpen){histVer=-1;await loadHist();c.scrollIntoView({behavior:"smooth",block:"start"})}}
const fdate=t=>new Date(t*1000).toLocaleString(LOC(),{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"});
async function loadHist(){const r=await api("/api/history");if(!r.items)return;histVer=r.ver;const it=r.items;
 const tot=it.reduce((a,x)=>a+x.size,0),out=it.reduce((a,x)=>a+x.out_size,0);
 setHTML($("histSum"),it.length?unB(esc(tr("hist.sum",{n:B(String(it.length)),before:gb(tot),after:gb(out),saved:B(gb(tot-out),"color:var(--acc2)"),pct:pctS(tot?(1-out/tot)*100:0)}))):esc(tr("hist.empty")));
 $("histList").style.display=it.length?"block":"none";
 setHTML($("histList"),it.map(x=>{const pr=S&&S.presets.includes(x.preset);const d=x.size?(1-x.out_size/x.size)*100:0;
  return `<div class="hrow"><div class="meta">${esc(fdate(x.t))}</div><div><div class="sname">${esc(x.name)}</div><div class="meta">${esc(x.src.replace(/[\\/][^\\/]*$/,""))}</div></div>
  <div class="num"><b>${gb(x.size)} → ${gb(x.out_size)}</b><div class="meta">${pctS(d)}%${x.duration?" · "+dur(x.duration):""}</div></div>
  <div class="meta">${esc(pr?presetTitle(x.preset):(x.preset||tr("hist.unknown_mode")))}${x.secs?`<br>${esc(tr("hist.took",{t:tm(x.secs)}))}`:""}</div>
  <div class="row" style="flex-wrap:nowrap"><button class="btn sm" title="${esc(tr("btn.open_out_title"))}" onclick="api('/api/open',{hist:${x.idx}})">${esc(tr("btn.open_out"))}</button>${x.replaced?`<span class="meta" style="text-align:center">${esc(tr("hist.in_bin"))}</span>`:`<button class="btn sm" title="${esc(tr("btn.open_src_title"))}" onclick="api('/api/open',{hist:${x.idx},which:'src'})">${esc(tr("btn.open_src"))}</button>`}</div></div>`}).join(""))}
async function retryJob(id){await api("/api/retry",{id});refresh()}
async function removeJob(id){await api("/api/remove",{id});refresh()}
let builtSettings=false;
function renderSettings(){
 const st=S.settings,caps=S.caps;
 const ord=k=>{const c=caps.presets[k]||{};return (caps.checked&&!c.ok?100:0)+S.presets.indexOf(k)};
 setHTML($("presets"),S.presets.filter(k=>{const c=caps.presets[k];return c?c.show!==false:(k==="x265"||k==="av1")}).sort((a,b)=>ord(a)-ord(b)).map(k=>{const c=caps.presets[k]||{};const off=caps.checked&&!c.ok;
  return `<label class="opt ${st.preset===k?"on":""} ${off?"off":""}" ${off?"":`onclick="setS('preset','${k}')"`}><b>${esc(presetTitle(k))}${k===caps.recommended?esc(tr("preset.recommended")):""}</b><small>${esc(tr("preset."+k+".desc"))}${off?` <br>${esc(tr("preset.unavailable",{why:msg(c.why)}))}`:""}</small></label>`}).join(""));
 for(const [id,key] of [["q","quality"],["sp","speed"],["au","audio"]]){document.querySelectorAll(`#${id} button`).forEach(b=>{b.classList.toggle("on",b.dataset.v===st[key]);b.onclick=()=>setS(key,b.dataset.v)})}
 const qv=S.quality[st.preset]||{};const unit=st.preset==="vt_hevc"?"q":st.preset.startsWith("nvenc")?"CQ":st.preset.startsWith("amf")?"QP":st.preset.startsWith("qsv")?"ICQ":"CRF";
 $("qhint").textContent=tr("set.qhint",{unit,high:String(qv.high),balanced:String(qv.balanced),compact:String(qv.compact)});
 $("sp").style.display=st.preset==="vt_hevc"?"none":"flex";
 $("btnTest").textContent=testLabel(st.testlen);
 if(!builtSettings){$("outdir").value=st.outdir||"";["lowprio","nosleep","skip","update_check"].forEach(k=>$(k).checked=!!st[k]);builtSettings=true}
}
$("outdir").addEventListener("change",e=>setS("outdir",e.target.value.trim()));
["lowprio","nosleep","skip","update_check"].forEach(k=>$(k).addEventListener("change",e=>setS(k,e.target.checked)));
function vmafCls(v){return v>=95?"g":v>=92?"y":"r"}
const phk=j=>j.phase&&j.phase.k||""; // work phase: key (phase.save, phase.save_wait, ...)
function jobStatic(j){
 const i=j.info;
 const meta=i?`${i.width}×${i.height} · ${esc(nfm(i.fps,2))} fps · ${esc(i.vcodec.toUpperCase())} · ${esc(nf(i.bitrate/1e6,1))} ${esc(tr("unit.mbps"))} · ${dur(i.duration)} · ${gb(j.size)} · ${esc(tr("job.audio",{list:i.audio.map(a=>`${a.codec} ${a.bitrate?Math.round(a.bitrate/1000)+tr("unit.k"):""}`).join(", ")||tr("job.no_audio")}))}`:gb(j.size);
 let body="";
 if(j.replaced){body=`<div class="res ok">${esc(tr("job.replaced"))} <button class="btn sm" onclick="api('/api/open',{id:${j.id}})">${esc(tr("btn.open_out"))}</button></div>`}else
 if(j.status==="done"||j.status==="skipped"){const d=(1-j.out_size/j.size)*100;const bigger=d<0;
  body=`<div class="res">${j.status==="skipped"?esc(tr("job.skipped_prefix")):""}<b>${gb(j.size)} → ${gb(j.out_size)}</b> (${pctS(d)}%) <button class="btn sm" title="${esc(tr("btn.open_out_title"))}" onclick="api('/api/open',{id:${j.id}})">${esc(tr("btn.open_out"))}</button> <button class="btn sm" title="${esc(tr("btn.open_src_title"))}" onclick="api('/api/open',{id:${j.id},which:'src'})">${esc(tr("btn.open_src"))}</button>${!bigger&&j.status==="done"?` <button class="btn sm" title="${esc(tr("rep.btn_one_title"))}" onclick="openReplace(${esc(JSON.stringify(j.path))},${esc(JSON.stringify(j.out_path))})">${esc(tr("rep.btn_one"))}</button>`:""}${bigger?`<div class="note">${esc(tr("job.bigger"))}</div>`:""}</div>`}
 if(j.test){const x=j.test;const tb=x.ratio>=1;const label=x.preset?`${presetTitle(x.preset)} · ${tr("quality.name."+x.quality)}`:(x.label||"");
  body+=`<div class="res">${esc(tr("test.head",{label:"\u0001"}))
   .replace("\u0001",`<i>${esc(label)}</i>`)}<br>${esc(tr("test.clip",{a:gb(x.ref_size),b:gb(x.test_size),pct:pctS((1-x.ratio)*100)}))} <b>${esc(tr("test.forecast",{size:gb(x.est_size)}))}</b>${esc(tr("test.time",{t:tm(x.est_time)}))}
  ${x.vmaf!=null?`<br>VMAF: <span class="vm ${vmafCls(x.vmaf)}">${esc(nf(x.vmaf,1))}</span> ${esc(tr("test.vmaf_scale"))}`:`<br>${esc(tr("test.eyes"))}`}
  ${tb?`<div class="note">${esc(tr("test.not_smaller"))}</div>`:""}
  <br><button class="btn sm" style="margin-top:6px" onclick="api('/api/open',{id:${j.id},which:'test'})">${esc(tr("test.open"))}</button></div>`}
 const note=msg(j.note),err=msg(j.error);
 if(note)body+=`<div class="note">${esc(note)}</div>`;
 if(err)body+=`<div class="err">${esc(err)}</div>`;
 const rt=(j.status==="error"||j.status==="cancelled"||j.status==="kept")&&j.info?`<button class="btn sm pri" title="${esc(tr("job.retry_title"))}" onclick="retryJob(${j.id})">${esc(tr("job.retry"))}</button>`:"";
 const rm=j.status!=="running"?rt+`<button class="btn sm" title="${esc(tr("job.remove_title"))}" onclick="removeJob(${j.id})">✕</button>`:"";
 const st=I18N.ru["status."+j.status]!=null?tr("status."+j.status):j.status;
 return `<div class="jh"><div><div class="jn">${esc(j.name)}</div><div class="meta">${meta}</div></div><div class="row" style="align-items:center"><span class="st ${esc(j.status)}">${esc(st)}</span>${rm}</div></div>${body}`;
}
function renderJobs(){
 const el=$("jobs");
 if(!S.jobs.length){el._map=null;setHTML(el,`<div class="empty">${esc(tr("jobs.empty1"))}<br>${esc(tr("jobs.empty2"))}</div>`);return}
 if(!el._map){el.innerHTML="";el._h=null;el._map=new Map()}
 const seen=new Set();
 S.jobs.forEach((j,idx)=>{
  let n=el._map.get(j.id);
  if(!n){n=document.createElement("div");n.className="job";n.innerHTML=`<div class="js"></div><div class="jp" style="display:none"><div class="bar"><i></i></div><div class="meta"></div></div>`;n._s=n.firstChild;n._p=n.lastChild;n._bar=n._p.querySelector("i");n._m=n._p.querySelector(".meta");el._map.set(j.id,n)}
  if(el.children[idx]!==n)el.insertBefore(n,el.children[idx]||null);
  seen.add(j.id);
  setHTML(n._s,jobStatic(j));
  const run=j.status==="running";n._p.style.display=run?"block":"none";
  const saving=phk(j)==="phase.save"||phk(j)==="phase.save_wait";
  const fin=run&&(j.fin||saving);n._bar.parentNode.classList.toggle("busy",!!fin);
  if(fin){const f=j.fin||{};n._bar.style.width=(f.pct!=null?Math.max(3,f.pct):100)+"%";
   n._m.textContent=saving?msg(j.phase):[tr("progress.finish"),f.pct!=null?nf(f.pct,0)+"%":"",f.eta!=null?tr("progress.left_approx",{t:tm(f.eta)}):tr("progress.big_files"),tr("progress.ok")].filter(Boolean).join(" · ")}
  else if(run){n._bar.style.width=j.pct.toFixed(1)+"%";
   n._m.textContent=[msg(j.phase),nf(j.pct,1)+"%",j.fps?nf(j.fps,0)+" fps":"",tr("progress.speed",{v:j.speed?nf(j.speed,2)+"×":"—"}),tr("progress.left",{t:tm(j.eta)}),tr("progress.elapsed",{t:tm(j.elapsed)}),j.cur_size?tr("progress.so_far",{size:gb(j.cur_size)}):""].filter(Boolean).join(" · ")}
 });
 for(const [id,n] of el._map)if(!seen.has(id)){n.remove();el._map.delete(id)}
}
function render(){renderUpd();repTick();renderIntro();
 const c=S.caps;$("ver").textContent=c.ffmpeg?(c.version||tr("ver.found")).replace(/Copyright.*/,"").slice(0,60):tr("ver.missing");
 setHTML($("warn"),!c.ffmpeg||!c.ffprobe?`<div class="warnbox"><b>${esc(tr("warn.ffmpeg_t"))}</b> ${esc(tr("warn.ffmpeg_1"))}<br>Windows: <code>winget install Gyan.FFmpeg</code> · Mac: <code>brew install ffmpeg</code><br>${esc(tr("warn.ffmpeg_2"))}</div>`:c.pagefile_off&&localStorage.getItem("fw_nopf")!=="1"?`<div class="warnbox"><button class="btn sm" style="float:right;margin-left:10px" title="${esc(tr("common.close"))}" onclick="localStorage.setItem('fw_nopf','1');render()">✕</button><b>${esc(tr("warn.pf_t"))}</b> ${esc(tr("warn.pf_1"))}<br>Win+R → <code>sysdm.cpl</code> ${esc(tr("warn.pf_2"))}</div>`:"");
 renderSettings();renderJobs();
 $("btnStop").style.display=S.running?"inline-block":"none";
 // buttons are not blocked while working: new files queue up behind the current one
 $("btnGo").disabled=$("btnTest").disabled=!c.ffmpeg;
 const q=S.jobs.filter(j=>j.status==="queued");
 const left=q.reduce((a,j)=>a+(j.info?j.info.duration:0),0);
 $("qinfo").textContent=q.length?tr("foot.queue",{n:String(q.length),d:dur(left)}):"";
 $("disk").textContent=S.disk?tr("foot.disk",{size:gb(S.disk.free)}):"";
 document.title=S.running?`${(S.jobs.find(j=>j.status==="running")||{pct:0}).pct.toFixed(0)}% · Framewring`:tr("app.title");
 if(S.version)$("appver").textContent="v"+S.version;
}
// ---------------- search for heavy videos
let scanVer=-1,scanRes=[],scanRows=[],drives=null,driveSel=new Set(),minMb=500;
const sel=new Set(),seenP=new Set(),pk=p=>p.toLowerCase();
const EDIT_CODECS=new Set(["prores","qtrle","dnxhd","cfhd","ffv1","huffyuv","utvideo","rawvideo","v210","png","mjpeg"]);
const dkey=r=>r.name.toLowerCase()+"|"+r.size;
const good=r=>r.save/r.size>=.3&&!r.has_out&&!EDIT_CODECS.has(r.codec);
async function toggleScan(show){const c=$("scanCard");show=show==null?c.style.display==="none":show;c.style.display=show?"block":"none";
 if(show&&!drives){const r=await api("/api/drives");drives=r.drives||[];drives.forEach(d=>{if(!d.net&&!d.removable)driveSel.add(d.path)});renderDrives()}
 if(show)c.scrollIntoView({behavior:"smooth",block:"start"})}
function renderDrives(){
 setHTML($("drives"),(drives||[]).map((d,i)=>`<label class="drv ${driveSel.has(d.path)?"on":""}"><input type="checkbox" data-d="${i}" ${driveSel.has(d.path)?"checked":""}> <b>${esc(msg(d.label))}</b> <span class="meta" style="margin:0">${esc(tr("drive.free",{free:gb(d.free),total:gb(d.total)}))}${d.net?" · "+esc(tr("drive.net")):d.removable?" · "+esc(tr("drive.removable")):""}</span></label>`).join("")||`<span class="meta">${esc(tr("drive.none"))}</span>`);
 document.querySelectorAll("#minmb button").forEach(b=>{b.classList.toggle("on",+b.dataset.v===minMb);b.onclick=()=>{minMb=+b.dataset.v;renderDrives()}})}
$("drives").addEventListener("change",e=>{const i=e.target.dataset.d;if(i==null)return;const p=drives[i].path;e.target.checked?driveSel.add(p):driveSel.delete(p);renderDrives()});
async function scanStart(){const roots=[...driveSel];const cp=$("scanPath").value.trim();if(cp)roots.push(cp);
 if(!roots.length){toast(tr("scan.need_root"));return}
 sel.clear();seenP.clear();const r=await api("/api/scan",{roots,min_mb:minMb,everything:$("useEv").checked});if(!r.error)refresh()}
const pct=(a,b)=>b?Math.round(a/b*100):0;
function verdict(r){const p=r.save/r.size;return p>=.5?["g",tr("scan.v.g")]:p>=.2?["y",tr("scan.v.y")]:["m",tr("scan.v.m")]}
const B=(s,st)=>"\u0001"+(st||"")+"\u0004"+s+"\u0002"; // bold inside a translated string: esc() expands it later
const unB=h=>h.replace(/\u0001([^\u0004]*)\u0004/g,(m,st)=>st?`<b style="${st}">`:"<b>").replace(/\u0002/g,"</b>");
function renderScan(sc){
 if(!sc)return;
 if(sc.results){scanRes=sc.results;scanVer=sc.ver;
  const taken=new Set(scanRes.filter(r=>sel.has(pk(r.path))).map(dkey));
  for(const r of scanRes){const k=pk(r.path);if(!seenP.has(k)){seenP.add(k);if(good(r)&&!taken.has(dkey(r))){sel.add(k);taken.add(dkey(r))}}}}
 $("btnScan").style.display=sc.running?"none":"inline-block";$("btnScanStop").style.display=sc.running?"inline-block":"none";
 let info="";
 const method=Array.isArray(sc.method)&&sc.method.length?" ("+sc.method.map(m=>tr("scan.method."+m)).join(" + ")+")":"";
 if(sc.running)info=esc(tr("scan.running",{phase:sc.phase?tr("scan.phase."+sc.phase):"",dirs:nf(sc.dirs,0),cand:String(sc.candidates)}))+(sc.candidates?" · "+esc(tr("scan.read",{n:String(sc.probed)})):"")+(sc.cur&&sc.phase!=="probe"?`<br><span style="opacity:.7">${esc(sc.cur.slice(-110))}</span>`:"");
 else if(sc.finished){const tot=scanRes.reduce((a,r)=>a+r.size,0),sv=scanRes.reduce((a,r)=>a+r.save,0);
  info=sc.error?`<span style="color:var(--err)">${esc(tr("scan.error",{e:sc.error}))}</span>`:scanRes.length?unB(esc(tr("scan.found",{n:String(scanRes.length),size:gb(tot),t:tm(sc.took),method,save:B(gb(sv),"color:var(--acc2)")}))):esc(tr("scan.none"));
  if(sc.cancel&&!sc.error)info=esc(tr("scan.stopped"))+" "+info;
  if(sc.ev_missing&&sc.took>20&&!sc.error&&localStorage.getItem("fw_noev")!=="1")info+=`<div class="hint" style="margin-top:8px">${unB(esc(tr("scan.ev_tip",{ev:B("Everything"),t:tm(sc.took)})))} <a href="#" onclick="openUrl('https://www.voidtools.com/');return false">voidtools.com</a> · <a href="#" onclick="localStorage.setItem('fw_noev','1');renderScan({...S.scan,results:null});return false">${esc(tr("scan.ev_hide"))}</a></div>`;
  const dk={};scanRes.forEach(r=>{const k=r.name.toLowerCase()+"|"+r.size;dk[k]=(dk[k]||0)+1});const dupB=Object.entries(dk).filter(([k,n])=>n>1).reduce((a,[k,n])=>a+(+k.split("|").pop())*(n-1),0);
  if(dupB>1e9)info+="<br>"+unB(esc(tr("scan.dups",{size:B(gb(dupB),"color:var(--warn)")})));
  if(sc.skipped_cloud)info+="<br>"+esc(tr("scan.cloud",{n:String(sc.skipped_cloud)}))}
 setHTML($("scanInfo"),info);
 const inQ=new Set(S.jobs.filter(j=>!["done","skipped"].includes(j.status)).map(j=>pk(j.path)));
 scanRows=[...scanRes].sort((a,b)=>b.save-a.save);
 const dup={};for(const r of scanRows){const k=r.name.toLowerCase()+"|"+r.size;(dup[k]=dup[k]||[]).push(r.dir.slice(0,2))}
 $("scanList").style.display=scanRows.length?"block":"none";
 setHTML($("scanList"),scanRows.map((r,i)=>{const k=pk(r.path),q=inQ.has(k),[vc,vt]=verdict(r);
  return `<label class="srow ${q||r.has_out?"dim":""}"><input type="checkbox" data-i="${i}" ${sel.has(k)&&!q?"checked":""} ${q?"disabled":""}>
  <div><div class="sname">${esc(r.name)}</div><div class="meta">${esc(r.dir)}</div>${(d=>d.length>1?`<span class="tag y" title="${esc(tr("scan.copies_title"))}">${esc(tr("scan.copies",{n:String(d.length),drives:[...new Set(d)].join(" ")}))}</span> `:"")(dup[r.name.toLowerCase()+"|"+r.size])}${EDIT_CODECS.has(r.codec)?`<span class="tag m" title="${esc(tr("scan.edit_title"))}">${esc(tr("scan.edit"))}</span>`:""}</div>
  <div class="num">${gb(r.size)}</div>
  <div class="meta">${esc((r.codec||"").toUpperCase())} · ${r.w}×${r.h}${r.fps?" · "+Math.round(r.fps):""}<br>${esc(nfm(r.mbps,1))} ${esc(tr("unit.mbps"))} · ${dur(r.dur)}</div>
  <div class="num">${q?`<span class="tag m">${esc(tr("scan.in_list"))}</span>`:r.has_out?`<span class="tag m">${esc(tr("scan.has_out"))}</span>`:`−${gb(r.save)} <span class="tag ${vc}">${esc(vt)}</span><div class="meta">≈ ${gb(r.est)} (−${pct(r.save,r.size)}%)</div>`}</div></label>`}).join(""));
 const chosen=scanRows.filter(r=>sel.has(pk(r.path))&&!inQ.has(pk(r.path)));
 $("scanBar").style.display=scanRows.length?"flex":"none";
 setHTML($("scanBar"),`<span class="meta" style="margin:0;flex:1">${unB(esc(tr("scan.selected",{n:String(chosen.length),size:gb(chosen.reduce((a,r)=>a+r.size,0)),save:B(gb(chosen.reduce((a,r)=>a+r.save,0)),"color:var(--acc2)")})))}</span>
  <button class="btn sm" onclick="scanPick('good')">${esc(tr("scan.pick_good"))}</button><button class="btn sm" onclick="scanPick('all')">${esc(tr("scan.pick_all"))}</button><button class="btn sm" onclick="scanPick('none')">${esc(tr("scan.pick_none"))}</button>
  <button class="btn go" onclick="scanAdd()" ${chosen.length?"":"disabled"}>${esc(tr("scan.add",{n:String(chosen.length)}))}</button>`);
}
$("scanList").addEventListener("change",e=>{const i=e.target.dataset.i;if(i==null)return;const k=pk(scanRows[i].path);e.target.checked?sel.add(k):sel.delete(k);renderScan({...S.scan,results:null})});
function scanPick(m){sel.clear();const taken=new Set();if(m!=="none")for(const r of scanRows)if(m==="all"||(good(r)&&!taken.has(dkey(r)))){sel.add(pk(r.path));taken.add(dkey(r))}renderScan({...S.scan,results:null})}
async function scanAdd(){const inQ=new Set(S.jobs.filter(j=>!["done","skipped"].includes(j.status)).map(j=>pk(j.path)));const paths=scanRows.filter(r=>sel.has(pk(r.path))&&!inQ.has(pk(r.path))).map(r=>r.path);
 if(!paths.length)return;toast(tr("scan.adding",{n:String(paths.length)}));const r=await api("/api/add",{paths});toasts(r.errors);
 await refresh();toast(tr("scan.added",{n:String(paths.length)}))}
async function refresh(){
 const v=sver;
 try{const r=await fetch("/api/status?sv="+scanVer,{headers:{"X-Token":T}});if(r.status===403){stale();return}const d=await r.json();
  if(pending||v!==sver)d.settings=S?S.settings:d.settings; // do not roll back the setting that was just chosen
  S=d;const want=S.settings.lang||S.sys_lang;const lg=I18N[want]?want:"en";
  if(lg!==LANG){LANG=lg;histVer=-1;applyStatic()}else render();
  renderScan(d.scan);if(histOpen&&d.hist_ver!==histVer)loadHist()}
 catch(e){$("ver").textContent=tr("ver.no_response")}
}
async function loop(){await refresh();if(document.body.querySelector("#jobs"))setTimeout(loop,document.hidden?3000:1000)}
applyStatic();
loop();
</script></body></html>
"""


def page_html():
    """Page with the access key, the current language and the dictionary of both languages (switching without reload)."""
    cat = json.dumps(i18n.CATALOG, ensure_ascii=False).replace("</", "<\\/")
    opts = "".join('<option value="%s">%s</option>' % (c, i18n.LANG_NAMES[c]) for c in i18n.LANGS)
    return HTML.replace("__TOKEN__", TOKEN).replace("__LANG__", cur_lang()).replace("__LANGOPTS__", opts) \
        .replace("__I18N__", cat)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second process bind an ALREADY used port: two instances shared
    # 8765, and the browser landed in one or the other. We take the port exclusively.
    allow_reuse_address = not IS_WIN

    def server_bind(self):
        if IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def zhmyh_at(port):
    """Whether a Framewring is already running on this port."""
    import urllib.request
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:%d/api/ping" % port, timeout=2) as r:
            return json.loads(r.read(200).decode("utf-8", "replace")).get("app") == "Framewring"
    except Exception:
        return False


def ask_show(port):
    """Second launch: ask the already running instance to show itself (only it knows the access key)."""
    import urllib.request
    try:
        if IS_WIN:
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: allow it to come to the foreground
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request("http://127.0.0.1:%d/api/show" % port, data=b"{}", method="POST")
        opener.open(req, timeout=3).read()
        return True
    except Exception:
        return False


APP_URL = {"url": None}

# ------------------------------------------------------------- Updates / bug report ----

UPDATE = {"latest": "", "notes_url": "", "setup": None, "sums": None, "state": "", "pct": 0, "err": None}


def install_kind():
    """How the program was launched: installer (installed via the installer), portable or source."""
    if not FROZEN:
        return "source"
    if (BASE_DIR / "portable.txt").exists():
        return "portable"
    return "installer" if (BASE_DIR / "unins000.exe").exists() else "portable"


def _ver_tuple(v):
    nums = [int(x) for x in re.findall(r"\d+", str(v))[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def _http_get(url, timeout=15):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Framewring/" + __version__,
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def check_update():
    """Once per launch ask GitHub for the number of the latest version. Nothing else is sent."""
    if not SETTINGS.get("update_check", True):
        return
    try:
        with _http_get(RELEASES_API) as r:
            rel = json.loads(r.read().decode("utf-8"))
        tag = str(rel.get("tag_name") or "")
        if rel.get("draft") or rel.get("prerelease") or _ver_tuple(tag) <= _ver_tuple(__version__):
            return
        ok = REPO_URL + "/releases/download/"
        assets = {a.get("name", ""): a.get("browser_download_url", "") for a in rel.get("assets") or []}
        setup = next((u for n, u in assets.items() if n.lower().endswith("-setup.exe") and u.startswith(ok)), None)
        sums = assets.get("SHA256SUMS.txt")
        notes = rel.get("html_url") or ""
        with LOCK:
            UPDATE.update(latest=tag.lstrip("vV"), notes_url=notes if notes.startswith(REPO_URL + "/") else RELEASES_URL,
                          setup=setup, sums=sums if sums and sums.startswith(ok) else None)
        print(" Доступна новая версия: %s" % tag)
    except Exception as e:
        print(" update check: %s" % e)


def _spawn_detached(cmd):
    """A process that will outlive us (the installer). Without a Job Object, detached from our console."""
    flags = NO_WINDOW | 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(cmd, creationflags=flags | 0x01000000, close_fds=True)  # CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen(cmd, creationflags=flags, close_fds=True)


def install_update():
    """Download the installer of the new version, verify SHA-256 from SHA256SUMS.txt of the same release,
    install silently over the top and restart. Settings, queue and history stay in %APPDATA%."""
    def run():
        try:
            setup, sums = UPDATE["setup"], UPDATE["sums"]
            if install_kind() != "installer" or not setup or not sums:
                raise UserError("upd.manual")
            with LOCK:
                UPDATE.update(state="download", pct=0, err=None)
            import hashlib
            import tempfile
            name = setup.rsplit("/", 1)[1]
            with _http_get(sums) as r:
                lines = r.read().decode("utf-8", "replace").splitlines()
            want = next((ln.split()[0].lower() for ln in lines if ln.strip().endswith(name)), None)
            if not want:
                raise RuntimeError("no checksum for " + name)
            d = Path(tempfile.gettempdir()) / "FramewringUpdate"
            d.mkdir(exist_ok=True)
            dst = d / name
            h = hashlib.sha256()
            with _http_get(setup, timeout=60) as r, open(dst, "wb") as f:
                total, done = int(r.headers.get("Content-Length") or 0), 0
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    h.update(b)
                    done += len(b)
                    if total:
                        UPDATE["pct"] = done * 100.0 / total
            if h.hexdigest().lower() != want:
                _rm(dst)
                raise RuntimeError("checksum mismatch")
            with LOCK:
                UPDATE["state"] = "install"
            # Release the mutex (otherwise the installer asks to "close the program") and exit at once: before replacing
            # the files the installer needs a few seconds to unpack, by which time we are already gone.
            # /FWUPDATE=1 - after a silent install, start the new version (a normal silent install does not do that).
            for h in _MUTEX:
                try:
                    ctypes.windll.kernel32.CloseHandle(h)
                except Exception:
                    pass
            _MUTEX.clear()
            _spawn_detached([str(dst), "/SILENT", "/SP-", "/NOCANCEL", "/NORESTART", "/FWUPDATE=1"])
            quit_app()
        except Exception as e:
            with LOCK:
                UPDATE.update(state="error", err=e.msg() if isinstance(e, UserError) else str(e))
    threading.Thread(target=run, daemon=True).start()


def report_url():
    """The "Report a bug" form on GitHub, with the version, Windows, video cards and mode already filled in.
    Nothing is sent automatically: the person sees everything in the browser and decides whether to submit."""
    import platform
    import urllib.parse
    try:
        build = sys.getwindowsversion().build if IS_WIN else 0
        win = ("Windows %s (build %d)" % ("11" if build >= 22000 else "10", build)) if IS_WIN else platform.platform()
    except Exception:
        win = platform.platform()
    s = SETTINGS
    q = {"template": "bug_report.yml", "version": "%s (%s)" % (__version__, install_kind()), "windows": win,
         "gpu": ", ".join(gpu_names()) or "?", "ffmpeg": (CAPS.get("version") or "")[:150],
         "mode": "%s · %s · %s" % (s.get("preset"), s.get("quality"), s.get("speed"))}
    return ISSUES_NEW + "?" + urllib.parse.urlencode(q)


def _own_windows():
    """Visible windows of our process (the pywebview program window)."""
    found = []
    if not IS_WIN:
        return found
    from ctypes import wintypes
    u = ctypes.windll.user32
    pid = os.getpid()
    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h) and u.GetWindowTextLengthW(h):
            found.append(h)
        return True
    u.EnumWindows(proto(cb), 0)
    return found


def show_self():
    win = WINDOW["w"]
    if win is not None:
        try:
            win.restore()
        except Exception:
            pass
        for h in _own_windows():
            try:
                ctypes.windll.user32.ShowWindow(h, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(h)
            except Exception:
                pass
        return
    if APP_URL["url"]:
        webbrowser.open(APP_URL["url"])


def quit_app():
    time.sleep(0.3)
    try:
        save_queue()
        _stop_current()
    finally:
        os._exit(0)


def _win_msg(text, title, flags):
    """System message box (MessageBoxW) on top of everything; returns the button code."""
    try:
        return ctypes.windll.user32.MessageBoxW(None, text, title, flags | 0x40000)  # MB_TOPMOST
    except Exception:
        return 0


_MUTEX = []


def _hold_mutex():
    """Named mutex: the installer uses it to know the program is running (AppMutex), and a second
    launch uses it to know the first copy is already working (even if it has not opened the server yet). True - already exists."""
    if IS_WIN:
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            h = k32.CreateMutexW(None, False, "FramewringRunning")
            already = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
            _MUTEX.append(h)
            return already
        except Exception:
            pass
    return False


def _setup_log():
    """In a build without a console print has nowhere to go: we write to framewring.log in the data folder."""
    if sys.stdout is not None and sys.stderr is not None:
        for st in (sys.stdout, sys.stderr):
            try:
                st.reconfigure(errors="replace")
            except Exception:
                pass
        return
    try:
        log = DATA_DIR / "framewring.log"
        if log.exists() and log.stat().st_size > 1_000_000:
            log.unlink()
        f = open(log, "a", encoding="utf-8", buffering=1)
        print("\n--- %s ---" % time.strftime("%Y-%m-%d %H:%M:%S"), file=f)
        sys.stdout = sys.stderr = f
    except Exception:
        pass


def _style_titlebar():
    """Window title bar in the program's colour: dark theme (Windows 10/11), background, text and border colour
    (Windows 11). Buttons, edge snapping and resizing stay system ones."""
    if not IS_WIN:
        return
    try:
        dwm = ctypes.windll.dwmapi
        for h in _own_windows():
            for attr, val in ((20, 1), (19, 1), (35, 0x0015110F), (36, 0x00F0EAE8), (34, 0x00362B26)):
                v = ctypes.c_int(val)
                dwm.DwmSetWindowAttribute(ctypes.c_void_p(h), attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception as e:
        print(" titlebar: %s" % e)


def run_window(url):
    """The program's own window on the Edge engine (WebView2). False - failed, we will open the browser."""
    if "--browser" in sys.argv or not IS_WIN:
        return False
    try:
        import webview
        from webview.platforms import winforms as _wf
        if not _wf._is_chromium():
            _win_msg(tr("native.webview2_missing") + "\nhttps://developer.microsoft.com/microsoft-edge/webview2/",
                     app_name(), 0x40)
            return False
    except Exception as e:
        print(tr("con.window_unavail", e=str(e)))
        return False

    def on_drop(e):  # files or folders dragged into the window
        try:
            for f in e.get("dataTransfer", {}).get("files", []):
                fp = f.get("pywebviewFullPath")
                if fp:
                    add_path(fp)
        except Exception as ex:
            print(" drop: %s" % ex)

    def on_loaded():
        _style_titlebar()
        try:
            from webview.dom import DOMEventHandler
            win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
        except Exception as ex:
            print(tr("con.dnd_unavail", e=str(ex)))

    def on_closing():
        if any(j["status"] == "running" for j in JOBS):
            r = _win_msg(tr("native.close_confirm"),
                         app_name(), 0x4 | 0x30 | 0x100)  # MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2
            if r != 6:  # IDYES
                return False
        return True

    try:
        win = webview.create_window(app_name(), url, width=1180, height=860, min_size=(760, 560),
                                    background_color="#0f1115", text_select=True)
        win.events.closing += on_closing
        win.events.loaded += on_loaded
        win.events.shown += _style_titlebar
        WINDOW["w"] = win
        webview.start(gui="edgechromium", private_mode=False,
                      storage_path=str(DATA_DIR / "webview"))
        return True
    except Exception as e:
        WINDOW["w"] = None
        print(tr("con.window_failed", e=str(e)))
        return False


def main():
    _setup_log()
    if _hold_mutex():  # another copy is already running: find it and show it, and exit ourselves
        for _ in range(20):
            port = next((pt for pt in range(8765, 8800) if zhmyh_at(pt)), None)
            if port:
                print(tr("con.already", url="http://127.0.0.1:%d/" % port))
                if "--no-browser" not in sys.argv:
                    ask_show(port)
                return
            time.sleep(0.5)
        return
    srv = None
    for port in range(8765, 8800):
        try:
            srv = Server(("127.0.0.1", port), H)
            break
        except OSError:
            if zhmyh_at(port):
                url = "http://127.0.0.1:%d/" % port
                print(tr("con.already", url=url))
                if "--no-browser" not in sys.argv:
                    ask_show(port)
                    time.sleep(2)
                return
            continue
    load_history()
    replace_recover()
    n = load_queue()
    threading.Thread(target=detect_caps, daemon=True).start()
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=queue_saver, daemon=True).start()
    threading.Timer(4.0, check_update).start()
    if not srv:
        print(tr("con.no_port"))
        sys.exit(1)
    url = "http://127.0.0.1:%d/?t=%s" % (srv.server_address[1], TOKEN)
    APP_URL["url"] = url
    print("=" * 60)
    print(tr("con.started", name=app_name(), ver=__version__, url=url.split("?")[0]))
    print(tr("con.data", dir=str(DATA_DIR)))
    print(tr("con.ffmpeg", path=FFMPEG or tr("con.ffmpeg_missing")))
    if n:
        print(tr("con.restored", n=n))
    print("=" * 60)
    try:
        if "--no-browser" in sys.argv:
            srv.serve_forever()
        else:
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            if not run_window(url):
                print(tr("con.keep_open"))
                print(tr("con.how_quit"))
                webbrowser.open(url)
                while True:
                    time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        save_queue()
        _stop_current()


if __name__ == "__main__":
    main()

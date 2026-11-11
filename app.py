#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Framewring Жмых — локальный компрессор видео с веб-интерфейсом.
Обёртка над FFmpeg. Работает только на твоём компьютере, файлы никуда не уходят.
Требования: Python 3.8+ и FFmpeg (в PATH или в папке ffmpeg рядом со скриптом).
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

__version__ = "0.9.0"
APP_NAMES = i18n.APP_NAMES  # заголовок окна: «Framewring Жмых» / «Framewring»
REPO_URL = "https://github.com/remrem23/framewring"  # официальная страница программы
DONATE_URL = REPO_URL + "/blob/main/DONATE.md"
EVERYTHING_URL = "https://www.voidtools.com/"
OPEN_URLS = (REPO_URL, DONATE_URL, EVERYTHING_URL)  # только эти ссылки интерфейс может открыть

FROZEN = bool(getattr(sys, "frozen", False))  # собрано в .exe (PyInstaller)
APP_DIR = Path(__file__).resolve().parent  # код (в сборке — внутренняя папка)
# Папка программы: рядом с exe в сборке, рядом с app.py при запуске из исходников
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else APP_DIR


def _data_dir():
    """Где хранить настройки, очередь, историю и кэш.
    - запуск из исходников: рядом с app.py (как раньше, ничего не теряется);
    - портабл-сборка (рядом с exe лежит portable.txt): папка data рядом с exe;
    - установленная сборка: %APPDATA%\\Framewring (в Program Files писать нельзя)."""
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
    for d in dict.fromkeys((BASE_DIR, APP_DIR)):  # рядом с exe/app.py, затем внутри сборки
        for cand in (d / "ffmpeg" / "bin" / exe, d / "ffmpeg" / exe, d / exe):
            if cand.is_file():
                return str(cand)
    w = shutil.which(name)  # на Windows which смотрит и в текущую папку — её не берём
    return w if w and os.path.isabs(w) and Path(w).parent.resolve() != Path.cwd().resolve() else None


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")

NO_WINDOW = 0x08000000 if IS_WIN else 0
BELOW_NORMAL = 0x00004000


def run_quiet(args, timeout=60):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                          timeout=timeout, creationflags=NO_WINDOW,
                          universal_newlines=True, encoding="utf-8", errors="replace")


# ------------------------------------------------- Дочерние процессы ----
# На Windows закрытие окна консоли убивает Python, но ffmpeg (запущенный без окна) продолжал бы
# жечь процессор и писать .part-файл. Job Object с KILL_ON_JOB_CLOSE гасит его вместе с нами.

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
            try:  # умереть вместе с родителем
                import ctypes
                import signal
                ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)
            except Exception:
                pass
    return f


def spawn(args, lowprio=False, **kw):
    """Popen для ffmpeg: без окна, с пониженным приоритетом, привязан к жизни Жмыха."""
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
    """Сколько памяти реально можно выделить (байт) или None, если неизвестно."""
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
                # AvailPageFile = свободный commit-лимит: при его нехватке аллокация падает
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
    """Windows без файла подкачки: лимит памяти = объём ОЗУ, и при всплесках ffmpeg падает с
    «Cannot allocate memory», даже когда физической памяти ещё полно."""
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
    """SVT-AV1 по умолчанию на 3440×1440 хочет ~6,6 ГБ. Если столько нет, он падает с
    'allocate memory failed'. Подбираем уровень параллельности (lp) под свободную память."""
    budget = avail_mem()
    if not budget or not info:
        return None
    budget *= 0.95
    mp = max(1, (info.get("width") or 1920) * (info.get("height") or 1080)) / 1e6

    def need(lp):  # замерено на SVT-AV1 4.x, 10 бит, preset 6
        return (mp * (0.25 * lp + 0.07) + 0.3) * 2 ** 30
    if need(5) <= budget:
        return None  # хватает на настройки по умолчанию
    for lp in (4, 3, 2):
        if need(lp) <= budget:
            return lp
    return 1


# ---------------------------------------------------------------- Тексты ----
# Всё, что видит пользователь, бэкенд отдаёт ключом с параметрами: {"k": ключ, "p": {...}}.
# Переводит страница (словарь из i18n.py), поэтому заметки и ошибки в queue.json не привязаны
# к языку и после переключения языка показываются на новом. Сырые тексты ffmpeg/ОС — обычные строки.

def M(key, **p):
    return {"k": key, "p": p}


class UserError(RuntimeError):
    """Ошибка для пользователя: ключ перевода + параметры."""

    def __init__(self, key, **p):
        super().__init__(key)
        self.k, self.p = key, p

    def msg(self):
        return M(self.k, **self.p)

    def __str__(self):
        return i18n.t(cur_lang(), self.k, **self.p)


def err_msg(e):
    """Исключение -> то, что кладём в job["error"]."""
    return e.msg() if isinstance(e, UserError) else str(e)


def add_note(job, m):
    """Добавить заметку к задаче (их может быть несколько)."""
    cur = job.get("note")
    job["note"] = m if not cur else (cur if isinstance(cur, list) else [cur]) + [m]


SYS_LANG = i18n.sys_lang()


def cur_lang():
    return SETTINGS.get("lang") or SYS_LANG


def tr(key, **p):
    """Перевод на текущий язык: для системных окон и консоли."""
    return i18n.t(cur_lang(), key, **p)


def app_name():
    return i18n.app_name(cur_lang())


# Пресеты (порядок показа). Названия и описания: i18n.py, ключи preset.<код>.title/.desc
PRESETS = ("nvenc_av1", "nvenc_hevc", "amf_av1", "amf_hevc", "qsv_av1", "qsv_hevc", "vt_hevc", "x265", "av1")
HW_VENDOR = {"nvenc": "nvidia", "amf": "amd", "qsv": "intel"}  # режим видеокарты -> производитель
# Что рекомендовать: видеокарта, если есть. Процессор жмёт чуть плотнее, но на порядок дольше.
RECOMMEND = ("nvenc_av1", "amf_av1", "qsv_av1", "nvenc_hevc", "amf_hevc", "qsv_hevc", "vt_hevc", "x265", "av1")

# Качество: high / balanced / compact
QUALITY = {
    "x265": {"high": 20, "balanced": 22, "compact": 24},
    "av1": {"high": 27, "balanced": 30, "compact": 33},
    "nvenc_hevc": {"high": 22, "balanced": 24, "compact": 27},
    "nvenc_av1": {"high": 27, "balanced": 30, "compact": 33},
    "vt_hevc": {"high": 70, "balanced": 62, "compact": 55},
    # AMD: постоянный QP. Замер (10 бит, тот же ролик): QP 22/24/27 ≈ NVENC CQ 22/24/27 по размеру и VMAF
    "amf_hevc": {"high": 22, "balanced": 24, "compact": 27},
    # AV1 у AMF — шкала 0–255 (≈ 4×QP HEVC); на настоящем RX 7000 ещё не проверено
    "amf_av1": {"high": 88, "balanced": 100, "compact": 116},
    # Intel: ICQ 1–51; на настоящем железе ещё не проверено
    "qsv_hevc": {"high": 22, "balanced": 24, "compact": 27},
    "qsv_av1": {"high": 24, "balanced": 27, "compact": 30},
}
SPEED = {
    "x265": {"slow": "slow", "normal": "medium", "fast": "fast"},
    "av1": {"slow": "5", "normal": "6", "fast": "8"},
    # NVENC: (пресет, multipass). Замер на 2560×1440: p6+fullres в 2× медленнее p5+qres при том же
    # размере и VMAF, поэтому «Обычно» = p5+qres.
    "nvenc_hevc": {"slow": ("p7", "fullres"), "normal": ("p5", "qres"), "fast": ("p4", "disabled")},
    "nvenc_av1": {"slow": ("p7", "fullres"), "normal": ("p5", "qres"), "fast": ("p4", "disabled")},
    "vt_hevc": {"slow": None, "normal": None, "fast": None},
    "amf_hevc": {"slow": "quality", "normal": "balanced", "fast": "speed"},
    "amf_av1": {"slow": "quality", "normal": "balanced", "fast": "speed"},
    "qsv_hevc": {"slow": "slower", "normal": "medium", "fast": "faster"},
    "qsv_av1": {"slow": "slower", "normal": "medium", "fast": "faster"},
}
MEM_ERR = re.compile(r"allocate memory|insufficient resources|cannot allocate memory|out of memory", re.I)


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
    if preset == "amf_hevc":  # 10 бит: в 8 битах AMF портил картинку (VMAF 56 против 99 в замере)
        return ["-c:v", "hevc_amf", "-usage", "transcoding", "-quality", s, "-rc", "cqp", "-qp_i", str(q),
                "-qp_p", str(q), "-profile:v", "main10", "-pix_fmt", "p010le", "-tag:v", "hvc1"]
    if preset == "amf_av1":
        return ["-c:v", "av1_amf", "-usage", "transcoding", "-quality", s, "-rc", "cqp", "-qp_i", str(q),
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


def gpu_vendors():
    """Какие видеокарты стоят (по описаниям драйверов в реестре, без WMI — он бывает очень медленным)."""
    found = set()
    if not IS_WIN:
        return found
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
                        desc = str(winreg.QueryValueEx(sk, "DriverDesc")[0]).lower()
                except OSError:
                    continue
                if "nvidia" in desc:
                    found.add("nvidia")
                if "radeon" in desc or "amd" in desc:
                    found.add("amd")
                if "intel" in desc and ("graphics" in desc or "arc" in desc or "uhd" in desc or "iris" in desc):
                    found.add("intel")
    except Exception:
        pass
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
        # Проверяем, что железо реально умеет, теми же флагами
        try:
            r = run_quiet([FFMPEG, "-hide_banner", "-v", "error", "-f", "lavfi", "-i",
                           "color=black:s=1280x720:r=60:d=0.5"] + video_args(p, "balanced", "normal")
                          + ["-f", "null", "-"], timeout=30)
            ok = r.returncode == 0
            return {"ok": ok, "why": "" if ok else M("caps.hw_unsupported")}
        except Exception:
            return {"ok": False, "why": M("caps.check_failed")}

    # аппаратные проверки параллельно: запуск быстрее
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(need)) as ex:
        res = {p: ex.submit(check, p, name) for p, name in need.items()}
    pres = {p: res[p].result() for p in need}
    for p, c in pres.items():
        # показываем: процессор — всегда; видеокарту — если работает, а если нет — только когда такая
        # видеокарта стоит (тогда видно, почему недоступно). Чужие производители не захламляют список.
        v = HW_VENDOR.get(p.split("_")[0])
        c["show"] = p in ("x265", "av1") or c["ok"] or (v is not None and v in vendors)
    CAPS["presets"] = pres  # целиком, чтобы /api/status не видел полсловаря
    CAPS["recommended"] = next((p for p in RECOMMEND if CAPS["presets"][p]["ok"]), "")
    with LOCK:
        # первый запуск (режим ещё ни разу не выбирали) или выбранный режим недоступен -> рекомендуемый
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
            # камеры AVCHD (.mts), ТВ-записи: 1080i. Без деинтерлейса в результате остаётся «гребёнка»
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
CUR = {"proc": None, "cancel": False}
DEFAULT_SETTINGS = {"preset": "x265", "quality": "balanced", "speed": "normal", "audio": "auto",
                    "outdir": "", "lowprio": True, "nosleep": True, "skip": True, "testlen": 120,
                    "lang": ""}  # lang: "" = как в системе, иначе "ru" / "en"


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        s.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return s


SETTINGS = load_settings()


def save_settings():
    try:
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(SETTINGS, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(str(tmp), str(SETTINGS_FILE))
    except Exception:
        pass


def clean_settings(b):
    """Пропускаем только допустимые значения: мусор в settings.json не должен ронять сжатие."""
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
        if k in ("lowprio", "nosleep", "skip"):
            v = bool(v)
        if k == "outdir":
            v = os.path.expandvars(os.path.expanduser(v.strip().strip('"').strip("'")))
            if v and not os.path.isabs(v):  # «out» или «D:video» ушли бы в папку программы
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
    PRESET_CHOSEN = "preset" in json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
except Exception:
    PRESET_CHOSEN = False
SETTINGS.clear()
SETTINGS.update(DEFAULT_SETTINGS)
SETTINGS.update(clean_settings(_raw))

_next_id = [1]
OUT_OWNERS = {}  # путь результата -> исходник (чтобы два разных файла не писали в один .mp4)


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
    if jobs:  # ffprobe параллельно: папка на 100 файлов добавляется за секунды, а не за минуту
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as ex:
            list(ex.map(do_probe, jobs))
    return [j if "error" in j and "id" not in j else j["id"] for j in new]


def out_dir_for(job, s):
    if s.get("outdir"):
        return Path(os.path.expanduser(s["outdir"]))
    return Path(job["path"]).parent / "compressed"


def _same_dir(a, b):
    """Та же папка, даже под другим именем (junction, подключённый диск, короткое имя 8.3)."""
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
    """Куда писать результат. Главное правило: никогда не затирать чужой файл и тем более оригинал."""
    d = out_dir_for(job, s)
    src = Path(job["path"])
    ks = _norm(src)
    same = _same_dir(d, src.parent)
    stem = src.stem
    if same:
        # пишем рядом с оригиналами: «клип.mkv» → «клип.mp4» затёр бы лежащий рядом оригинал «клип.mp4»
        # (так оставляет файлы OBS после ремукса). Поэтому всегда с суффиксом.
        stem += "_compressed"
    else:
        # «клип.mkv» и «клип.mov» в одной папке дали бы один «клип.mp4». Различаем по расширению.
        try:
            low = src.stem.lower()
            if any(f.stem.lower() == low and f.suffix.lower() in VIDEO_EXT and f.suffix.lower() != src.suffix.lower()
                   for f in src.parent.iterdir()):
                stem = "%s_%s" % (src.stem, src.suffix.lstrip(".").lower())
        except OSError:
            pass
    # Чужая общая папка (задана в «Куда сохранять»): файл без известного хозяина считаем чужим —
    # одинаковые имена с разных карт памяти (GH010001.MP4) встречаются постоянно.
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
# Поиск тяжёлых видео по дискам: обход папок, ffprobe кандидатов, прикидка экономии.

SKIP_DIRS = {
    # системное
    "windows", "program files", "program files (x86)", "programdata", "appdata", "system volume information",
    "recovery", "msocache", "perflogs", "windowsapps", "winsxs", "$recycle.bin", "config.msi",
    # служебное / разработка
    "node_modules", "__pycache__", "venv", "site-packages", "dist-packages", "deriveddatacache", "ue-cache",
    # наши же результаты
    "compressed", "_tests",
    # игры: их ролики трогать нельзя, иначе игра сломается
    "steamapps", "steamlibrary", "epic games", "riot games", "xboxgames", "gog games", "gog galaxy",
    "origin games", "ea games", "ubisoft game launcher", "battle.net", "games",
}
if not IS_WIN:
    SKIP_DIRS |= {"library", "applications", "system", "private", "proc", "sys", "dev", "usr", "bin", "sbin",
                  "lib", "lib64", "etc", "var", "run", "snap", "boot", "opt", "tmp"}
FILE_ATTR_REPARSE = 0x400
FILE_ATTR_CLOUD = 0x400000 | 0x40000 | 0x1000  # OneDrive «только в облаке» / offline: чтение скачает файл
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
            if t not in (2, 3, 4):  # съёмный, локальный, сетевой
                continue
            du = _disk_usage_timeout(root, 2.0)  # отключённый сетевой диск отвечает десятки секунд
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
    """Грубая прикидка размера после «Качество · H.265 · Баланс». Точный прогноз даёт «Тест»."""
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
    # ~3 Мбит/с для 1080p30, растёт медленнее, чем число пикселей в секунду
    target = 3.0e6 * (w * h * fps / (1920 * 1080 * 30.0)) ** 0.75
    if info.get("vcodec") in EFFICIENT:
        target = max(target, v_src * 0.75)  # уже современный кодек: много не выжать
    v_out = min(v_src, target)
    est = dur * (v_out + audio_out) / 8
    return int(min(size, est))


# Запрос к уже запущенному Everything (voidtools) через его IPC (EV_WM_COPYDATA, QUERY2).
# Без DLL и без es.exe: только ctypes.

EV_WM_COPYDATA = 0x004A
COPYDATA_QUERY2W = 18
REQ_FULL_PATH = 0x00000004
REQ_SIZE = 0x00000010
REQ_ATTRIBUTES = 0x00000100
REPLY_ID = 0x5A48  # наш произвольный идентификатор ответа

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


_EV_CLASS = {}  # один зарегистрированный класс окна и его обработчик живут до конца процесса
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
    """Выполняет поиск в Everything. None = Everything не запущен или не ответил."""
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
                # если Everything запущен от администратора, разрешаем ему прислать нам ответ
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
    """Все видео >= min_bytes из индекса Everything: доли секунды вместо минут обхода дисков.
    Если программа Everything установлена, но закрыта (работает только служба), запускаем её
    в трей на время поиска и потом закрываем. None, если Everything нет или он не ответил."""
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
            if isinstance(r, tuple):  # пока база грузится, Everything не отвечает
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
    """Everything по умолчанию индексирует только локальные NTFS-диски."""
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
    """True/False/None по признаку «есть задержка позиционирования головки». Без прав администратора."""
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
    """Параметры видео между запусками: повторный поиск не гоняет ffprobe по сотням файлов."""
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
                            continue  # junction-ссылки: иначе одни и те же папки обходились бы дважды
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
    """Обход в несколько потоков: SSD отдают каталоги параллельно в разы быстрее (замер: 44 с -> 13 с
    на 420 тыс. папок), HDD — умеренно, чтобы не гонять головку."""
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
        size = os.stat(path).st_size  # индекс Everything мог отстать: файл переписан или удалён
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
    """Каждый диск обходим в своём потоке (диски работают параллельно), а найденные файлы
    сразу отдаём ffprobe: результаты появляются по ходу, а не после обхода всех дисков."""
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
                    SCAN["ev_missing"] = IS_WIN  # Everything нет или он не отвечает
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

def proc_written(p):
    """Сколько байт процесс уже записал на диск (None, если ОС не говорит)."""
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
    """После 100% ffmpeg молча переписывает весь файл, чтобы индекс (moov) оказался в начале
    (+faststart): на десятках ГБ это минуты без единой строки прогресса. Считаем этот этап сами
    по числу записанных процессом байт: переписать нужно примерно весь уже записанный объём."""
    base = None
    while p.poll() is None:
        time.sleep(1)
        with LOCK:
            pct, size = job["pct"], job["cur_size"]
        if pct < 90 or time.time() - last[0] < 3:  # ffmpeg замолчал под конец = идёт перенос индекса
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
    """Запускает ffmpeg с прогрессом в job. Возвращает (ok, error_text, log_tail).
    error_text == "cancel", если пользователь нажал «Стоп»."""
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
                    done = int(v) / 1e6  # в ffmpeg out_time_ms тоже в микросекундах (исторический баг)
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
            # убираем болтовню SVT-AV1 и прочий шум, оставляем суть
            lines = [l for l in tail.splitlines() if l.strip() and not l.startswith("Svt[info]")]
            err = "\n".join(lines)[-1500:]
            return False, err or M("err.ffmpeg_code", code=str(p.returncode)), tail
        return True, "", tail
    finally:
        log.close()


TEXT_SUBS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}


def vfilters(info):
    """Цепочка видеофильтров. Та же цепочка применяется к оригиналу при подсчёте VMAF."""
    f = []
    if info.get("interlaced"):
        f.append("bwdif=mode=send_field")  # 50i -> 50p: плавность движения как в оригинале
    # yuv420 требует чётных размеров: 1366×767 и подобное иначе падает в энкодере
    if (info.get("width") or 0) % 2 or (info.get("height") or 0) % 2:
        f.append("crop=trunc(iw/2)*2:trunc(ih/2)*2")
    return f


def sub_args(info):
    """Текстовые субтитры переносим в MP4 (mov_text). Картинки (PGS/DVD) MP4 не умеет."""
    a = []
    for i, c in enumerate(info.get("subs") or []):
        if c in TEXT_SUBS:
            a += ["-map", "0:s:%d" % i]
    return a + ["-c:s", "mov_text"] if a else []


def encode(job, s, src, dst, total, phase, extra, subs=False):
    """Сжимает src в dst. Для AV1 подбирает lp под память и при нехватке повторяет с меньшим.
    Возвращает (ok, err, секунды_кодирования)."""
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
            # «Cannot allocate memory» посреди сжатия: Windows не дала памяти (часто при выключенном файле
            # подкачки). Это разовый сбой: повторяем, со второго раза без декодирования на видеокарте.
            mem_tries += 1
            if mem_tries > 2:
                return False, M("err.mem3", detail=err), took
            if mem_tries == 2:
                pre = []
            with LOCK:
                job["note"] = M("note.mem_retry" if pre else "note.mem_retry_cpu", n=mem_tries + 1)
            time.sleep(5)
            continue
        cur = lp or 5
        if cur <= 1:
            return False, M("err.av1_mem", res="%dx%d" % (info["width"], info["height"]), detail=err), took
        lp = cur - 1
        with LOCK:
            job["note"] = M("note.av1_lp_retry", lp=lp)


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
    """part -> out. Сразу после записи большой файл часто держит антивирус (проверяет) или проводник
    (строит превью), а итоговый файл может быть открыт в плеере. Раньше это давало «Ошибку» после
    часа сжатия. Теперь ждём, пишем, что происходит, и в худшем случае оставляем готовый файл как есть."""
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
            while True:  # возможно, занят именно старый результат: пробуем другое имя
                alt = out.with_name("%s (%d).mp4" % (out.stem, n))
                if not alt.exists():
                    break
                n += 1
        if waited > 600:  # 10 минут: сдаёмся, но работу не теряем
            with LOCK:
                add_note(job, M("note.rename_failed", name=part.name))
            return part
        time.sleep(2)


def do_full(job, s):
    out = out_path_for(job, s)
    if _same_file(out, job["path"]):  # не должно случиться, но оригинал дороже всего
        with LOCK:
            job["status"], job["error"] = "error", M("err.same_as_src")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    if s.get("skip") and out.exists():
        with LOCK:
            OUT_OWNERS[_norm(out)] = _norm(job["path"])
            job["status"], job["out_path"], job["out_size"] = "skipped", str(out), out.stat().st_size
        return
    # Место на диске: если не влезет даже по оптимистичной оценке, не тратим часы впустую
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
    ok, err, took = encode(job, s, job["path"], str(part), job["info"]["duration"], M("phase.compress"),
                        ["-map_metadata", "0", "-movflags", "+faststart"], subs=True)
    if ok:
        with LOCK:
            job["phase"], job["fin"] = M("phase.save"), None
        out = finalize(part, out, job)
        with LOCK:
            OUT_OWNERS[_norm(out)] = _norm(job["path"])
        try:  # дата изменения как у оригинала: сортировка по дате в проводнике не ломается
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
        add_history({"t": time.time(), "src": job["path"], "out": str(out), "name": job["name"],
                     "size": job["size"], "out_size": job["out_size"], "duration": job["info"]["duration"],
                     "preset": s["preset"], "quality": s["quality"], "speed": s["speed"], "secs": round(took, 1)})
    else:
        _rm(part)
        with LOCK:
            if err == "cancel":
                job["status"] = "cancelled"
            else:
                job["status"], job["error"] = "error", err


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

    # 1) вырезаем кусок без пережатия (через run_ffmpeg: виден прогресс и работает «Стоп»)
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
    # 2) жмём кусок теми же настройками
    ok, err, enc_time = encode(job, s, str(ref), str(test), ref_dur, M("phase.test_enc"),
                               ["-movflags", "+faststart"])
    if not ok:
        _rm(test)
        return fail(err)
    ts, rs = test.stat().st_size, ref.stat().st_size
    factor = (info["duration"] or ref_dur) / ref_dur
    res = {"preset": s["preset"], "quality": s["quality"],  # подпись теста собирает страница на своём языке
           "test_size": ts, "ref_size": rs, "est_size": int(ts * factor), "ratio": ts / rs if rs else 0,
           "est_time": enc_time * factor, "vmaf": None, "test_path": str(test), "ref_path": str(ref)}
    # 3) VMAF, если есть. Выше 1080p сравниваем в 1080p: модель vmaf_v0.6.1 рассчитана на неё,
    #    а считается в 2–3 раза быстрее.
    #    Кадры сопоставляем по НОМЕРУ, а не по времени: у вырезанного MKV метки округлены до 1 мс,
    #    у MP4 точные, и libvmaf сравнивал каждый 3-й кадр с соседним (VMAF занижался с ~95 до ~75).
    if CAPS["vmaf"]:
        threads = max(1, (os.cpu_count() or 4) - 1)
        sc = ",scale=-2:1080:flags=bicubic" if (info.get("height") or 0) > 1080 else ""
        rf = "".join(f + "," for f in vfilters(info))  # оригинал приводим к тому же виду, что и результат
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
    try:
        items = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(items, list):
            HISTORY["items"] = [x for x in items if isinstance(x, dict) and x.get("src")]
    except Exception:
        pass
    with LOCK:  # результаты прошлых сеансов принадлежат своим исходникам
        for h in HISTORY["items"]:
            if h.get("out"):
                OUT_OWNERS.setdefault(_norm(h["out"]), _norm(h["src"]))


def add_history(entry):
    """Журнал всего, что сжато: не зависит от списка задач, «Убрать готовые» его не трогает."""
    with LOCK:
        HISTORY["items"].append(entry)
        HISTORY["ver"] += 1
        data = json.dumps(HISTORY["items"], ensure_ascii=False, indent=0)
    try:
        tmp = HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text(data, encoding="utf-8")
        os.replace(str(tmp), str(HISTORY_FILE))
    except Exception:
        pass


QUEUE_FILE = DATA_DIR / "queue.json"
KEEP = ("id", "path", "name", "size", "status", "info", "error", "note", "out_path", "out_size", "test", "mode")


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
        tmp = QUEUE_FILE.with_suffix(".tmp")
        tmp.write_text(data, encoding="utf-8")
        os.replace(str(tmp), str(QUEUE_FILE))
        return data
    except Exception:
        return None


def queue_saver():
    """Раз в 2 секунды сохраняем список, если он изменился: закрыл окно — при следующем запуске всё на месте."""
    last = None
    while True:
        time.sleep(2)
        payload = _queue_payload()
        cur = json.dumps(payload, ensure_ascii=False)
        if cur != last:
            if save_queue(payload) is not None:
                last = cur


def load_queue():
    """Восстанавливаем список прошлого сеанса. Что было «в работе» или «в очереди», ждёт «Сжать всё»."""
    try:
        saved = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return 0
    restored = []
    for d in saved if isinstance(saved, list) else []:
        try:
            path = d["path"]
            job = {"id": 0, "path": path, "name": d.get("name") or Path(path).name, "size": d.get("size") or 0,
                   "status": d.get("status") or "ready", "info": d.get("info"), "error": d.get("error") or "",
                   "note": d.get("note") or "", "pct": 0, "fps": 0, "speed": 0, "eta": None, "cur_size": 0,
                   "elapsed": 0, "phase": "", "out_path": d.get("out_path") or "", "out_size": d.get("out_size") or 0,
                   "test": d.get("test"), "settings": None, "mode": d.get("mode"), "fin": None}
        except (KeyError, TypeError):
            continue
        if job["status"] in ("running", "queued", "probing"):
            job["status"] = "cancelled" if job["status"] == "running" else "ready"
            if d.get("status") == "running":
                job["note"] = M("note.interrupted")
        if not os.path.isfile(path):
            if job["status"] not in ("done", "skipped"):
                job["status"], job["error"] = "error", M("err.file_gone")
        else:
            try:
                size = os.path.getsize(path)
            except OSError:
                size = job["size"]
            if size != job["size"] or not job["info"]:  # файл подменили: перечитаем параметры
                job["size"], job["info"] = size, None
                if job["status"] not in ("done", "skipped"):
                    job["status"] = "probing"
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
            if job["status"] == "running":  # на всякий случай: не оставляем «вечно в работе»
                job["status"] = "error"
                job["error"] = job["error"] or M("err.no_result")


# ------------------------------------------------------------- Pickers ----

VIDEO_MASK = "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.ts *.m2ts *.m4v *.wmv *.mts"
WINDOW = {"w": None}  # окно программы (pywebview), если запущено в своём окне
_PICK_LOCK = threading.Lock()


def _pick_webview(win, kind):
    import webview
    fd = getattr(webview, "FileDialog", None)
    if kind == "files":
        r = win.create_file_dialog(fd.OPEN if fd else webview.OPEN_DIALOG, allow_multiple=True, file_types=(
            "%s (%s)" % (tr("pick.video"), VIDEO_MASK.replace(" ", ";")), "%s (*.*)" % tr("pick.all")))
    else:
        r = win.create_file_dialog(fd.FOLDER if fd else webview.FOLDER_DIALOG)
    return [str(x) for x in (r or [])]


def _pick_tk(kind):
    """tkinter в отдельном потоке этого же процесса (в exe нельзя запускать sys.executable -c)."""
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
            if kind == "files":
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
    with _PICK_LOCK:  # одно окно выбора за раз
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
    """Свободное место; кэш на 5 с, и без LOCK: сетевой диск не должен тормозить сжатие."""
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
            "quality": QUALITY, "scan": scan_public(scan_ver), "hist_ver": HISTORY["ver"], "version": __version__, "repo": REPO_URL, "donate": DONATE_URL, "window": WINDOW["w"] is not None,
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

    def _tok_ok(self, given):
        return hmac.compare_digest(str(given or "").encode(), TOKEN.encode())

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        if self.path == "/api/ping":  # для второго запуска: «здесь уже работает Framewring»
            return self._send(200, {"app": "Framewring"})
        if self.path == "/" or self.path.startswith("/?"):
            m = re.search(r"[?&]t=([0-9a-f]+)", self.path)
            if not m or not self._tok_ok(m.group(1)):  # страница с ключом — только по ссылке от самой программы
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
        if self.path == "/api/show":  # второй запуск просит показать уже открытое окно
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
        except UserError as e:  # страница покажет на своём языке по ключу, error — запасной текст
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
            return {"added": len(paths), "errors": errs}  # ошибки: строки или {"k","p"}
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
        if path == "/api/quit":  # только для режима в браузере: окна нет, а консоли в exe тоже нет
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
                if not j or j["status"] not in ("error", "cancelled", "ready", "tested"):
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
                JOBS[:] = [j for j in JOBS if j["status"] not in ("done", "skipped")]
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
                if "hist" in b:  # строка истории: задачи в списке может уже не быть
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
.st.done{color:var(--acc2);border-color:var(--acc2)}.st.error{color:var(--err);border-color:var(--err)}
.st.running{color:#fff;background:var(--acc);border-color:var(--acc)}.st.tested{color:var(--warn);border-color:var(--warn)}
.res{margin-top:8px;padding:10px;border-radius:10px;background:#0f1115;border:1px dashed var(--line);font-size:13px}
.res b{color:var(--acc2)}.err{color:var(--err);white-space:pre-wrap;font:12px/1.4 ui-monospace,Consolas,monospace;max-height:160px;overflow:auto;margin-top:8px}
.empty{color:var(--mut);text-align:center;padding:40px 10px;border:1px dashed var(--line);border-radius:12px}
.warnbox{border:1px solid var(--warn);background:#ffb34714;color:var(--warn);padding:12px;border-radius:12px;margin-bottom:14px}
.foot{color:var(--mut);font-size:12px;margin-top:14px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
@media(max-width:1000px){.hrow{grid-template-columns:minmax(120px,1fr) auto!important}.hrow>:nth-child(1),.hrow>:nth-child(4){display:none}.hrow>:nth-child(3){grid-column:1}}.toast{overflow-wrap:anywhere}
.hrow>.row{flex-direction:column;align-items:stretch;gap:4px}.hrow .btn{white-space:nowrap}
.hrow{display:grid;grid-template-columns:88px minmax(160px,1fr) 150px 130px auto;gap:10px;align-items:center;padding:8px 10px;border-bottom:1px solid var(--line)}
.hrow:last-child{border-bottom:0}.hrow .meta{margin:0;overflow-wrap:anywhere}
.don{border-color:#ff6b9a55;color:#ff9abb}.don:hover{border-color:#ff6b9a;background:#ff6b9a14}
.modal{position:fixed;inset:0;background:#000a;display:none;align-items:center;justify-content:center;z-index:50;padding:16px}
.modal.on{display:flex}.mbox{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;max-width:560px;width:100%}
.mbox h3{margin:0 0 4px;font-size:18px}.wal{border:1px solid var(--line);border-radius:12px;padding:12px;margin-top:12px}
.wal b{display:block;margin-bottom:6px}.addr{display:flex;gap:8px;align-items:center}
.addr code{flex:1;background:#0f1115;border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:13px ui-monospace,Consolas,monospace;overflow-wrap:anywhere;user-select:all}
.toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#232836;border:1px solid var(--line);padding:10px 16px;border-radius:10px;display:none;max-width:90%}
.note{color:var(--warn);font-size:12px;margin-top:6px}
.scanlist{max-height:440px;overflow:auto;border:1px solid var(--line);border-radius:10px;margin-top:8px}
.srow{display:grid;grid-template-columns:22px 1fr 86px 120px 150px;gap:10px;align-items:center;padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer}
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
<div class="row" style="align-items:center"><button class="btn sm don" onclick="donate(true)" data-t="donate.btn" data-tt="donate.btn_title"></button><div class="pill" id="ver" data-t="ver.checking"></div></div></div>
<div id="warn"></div>
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
  <div id="jobs"></div>
  <div class="foot"><span><span id="disk"></span> <span id="qinfo" style="margin-left:10px"></span></span><a href="#" onclick="api('/api/clear');return false" style="color:var(--mut)" data-t="btn.clear"></a></div>
 </div>
</div></div></div>
<div class="modal" id="donate" onclick="if(event.target===this)donate(false)"><div class="mbox" role="dialog" data-ta="donate.title">
 <div class="row" style="justify-content:space-between;align-items:flex-start;flex-wrap:nowrap"><div><h3 data-t="donate.title"></h3><div class="meta" data-t="donate.text"></div></div><button class="btn sm" onclick="donate(false)" data-ta="common.close">✕</button></div>
  <p style="margin:14px 0 10px" data-t="donate.ways"></p>
 <button class="btn pri" onclick="openUrl(S.donate)" data-t="donate.open"></button>
 <p class="hint" style="margin:14px 0 0"><span data-t="donate.official"></span> <b id="repoUrl">github.com/remrem23/framewring</b>. <span data-t="donate.official2"></span></p>
</div></div>
<div class="toast" id="toast"></div>
<script>
const T="__TOKEN__";let S=null;
// ---------------- язык: словарь из i18n.py (тот же, что у бэкенда)
const I18N=__I18N__;let LANG="__LANG__";
const LOCS={ru:"ru-RU",en:"en-US",de:"de-DE",fr:"fr-FR",es:"es-ES",pt:"pt-BR",zh:"zh-CN"};const LOC=()=>LOCS[LANG]||"en-US";
const nf=(x,d=0)=>Number(x||0).toLocaleString(LOC(),{minimumFractionDigits:d,maximumFractionDigits:d});
const nfm=(x,m)=>Number(x||0).toLocaleString(LOC(),{maximumFractionDigits:m});
function tr(k,p){let s=(I18N[LANG]||{})[k];if(s==null&&LANG!=="ru")s=I18N.en[k];if(s==null)s=I18N.ru[k];if(s==null)s=k;return p?s.replace(/\{(\w+)\}/g,(m,n)=>n in p?fmtP(p[n]):m):s}
function fmtP(v){return v&&typeof v==="object"?msg(v):typeof v==="number"?nfm(v,1):String(v)}
// сообщение бэкенда: строка (старые записи, сырой текст ffmpeg), {k,p} или список таких
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
// innerHTML только при реальном изменении: иначе каждую секунду пересоздаются кнопки и клик «теряется»
function setHTML(el,h){if(el._h!==h){el.innerHTML=h;el._h=h}}
async function api(p,b){try{const r=await fetch(p,{method:"POST",headers:{"X-Token":T,"Content-Type":"application/json"},body:JSON.stringify(b||{})});const j=await r.json().catch(()=>({}));if(r.status===403){stale();return {}}if(!r.ok)toast(j.msg?msg(j.msg):(j.error||tr("err.generic")));return j}catch(e){toast(tr("err.no_response"));return {}}}
function stale(){document.body.innerHTML='<div style="padding:40px;font-size:16px">Программа была перезапущена или закрыта — эта вкладка устарела. Открой программу заново.<br><br>The program was restarted or closed — this tab is out of date.</div>'}
function toasts(a){a=(a||[]).map(msg).filter(Boolean);if(a.length)toast(a.slice(0,4).join(" · ")+(a.length>4?` (+${a.length-4})`:""))}
// перетаскивание: без этого окно открыло бы само видео вместо программы
["dragover","drop"].forEach(ev=>window.addEventListener(ev,e=>{e.preventDefault();if(ev==="drop"&&!S?.window)toast(tr("drop.browser"))}));
function donate(on){$("donate").classList.toggle("on",on)}
document.addEventListener("keydown",e=>{if(e.key==="Escape")donate(false)});
$("lng").addEventListener("change",e=>setLang(e.target.value));
async function openUrl(u){if(u)await api("/api/url",{url:u})}
function toast(m){const t=$("toast");t.textContent=m;t.style.display="block";clearTimeout(t._h);t._h=setTimeout(()=>t.style.display="none",5000)}
const gb=b=>{const n=Math.abs(b||0),sg=b<0?"−":"";return sg+(n>=1e9?nf(n/1e9,2)+" "+tr("unit.gb"):n>=1e7?nf(n/1e6,0)+" "+tr("unit.mb"):nf(n/1e6,1)+" "+tr("unit.mb"))};
const tm=s=>{if(s==null||!isFinite(s))return"—";s=Math.round(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return h?tr("time.hm",{h:String(h),m:String(m)}):m?tr("time.ms",{m:String(m),s:String(x)}):tr("time.s",{s:String(x)})};
const dur=s=>{s=Math.round(s||0);return`${Math.floor(s/3600)}:${String(Math.floor(s%3600/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`};
const pctS=d=>(d<0?"+":"−")+nf(Math.abs(d),0); // −37 (меньше) / +5 (больше)
const testLabel=tl=>{tl=tl||120;return tl<60?tr("btn.test_sec",{n:String(Math.round(tl))}):tr("btn.test_min",{n:nfm(Math.round(tl/6)/10,1)})};
const presetTitle=k=>I18N.ru["preset."+k+".title"]!=null?tr("preset."+k+".title"):k;
let pending=0,sver=0;
async function setS(k,v){S.settings[k]=v;sver++;pending++;renderSettings();try{await api("/api/settings",{[k]:v})}finally{pending--}}
async function pick(kind){toast(S.window?tr("pick.opening"):tr("pick.opening_browser"));const r=await api("/api/pick",{kind});toasts(r.errors);refresh()}
async function addManual(){const el=$("manual");if(!el.value.trim())return;const v=el.value;el.value="";toast(tr("add.adding"));
 const paths=[...v.matchAll(/"([^"]+)"|([^"\r\n]+)/g)].map(m=>(m[1]||m[2]).trim()).filter(Boolean); // «Копировать как путь» из проводника: "a" "b"
 const r=await api("/api/add",{paths});toasts(r.errors);refresh()}
$("manual").addEventListener("keydown",e=>{if(e.key==="Enter")addManual()});
async function start(mode){const r=await api("/api/start",{mode});if(r.queued===0)toast(S.jobs.some(j=>j.status==="probing")?tr("start.probing"):tr("start.nothing"));refresh()}
async function cancel(){const j=S&&S.jobs.find(x=>x.status==="running");if(j&&j.mode!=="test"&&j.pct>2&&!confirm(tr("stop.confirm",{name:j.name,pct:nf(j.pct,0)})))return;await api("/api/cancel");refresh()}
// ---------------- история
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
  <div class="row" style="flex-wrap:nowrap"><button class="btn sm" title="${esc(tr("btn.open_out_title"))}" onclick="api('/api/open',{hist:${x.idx}})">${esc(tr("btn.open_out"))}</button><button class="btn sm" title="${esc(tr("btn.open_src_title"))}" onclick="api('/api/open',{hist:${x.idx},which:'src'})">${esc(tr("btn.open_src"))}</button></div></div>`}).join(""))}
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
 if(!builtSettings){$("outdir").value=st.outdir||"";["lowprio","nosleep","skip"].forEach(k=>$(k).checked=!!st[k]);builtSettings=true}
}
$("outdir").addEventListener("change",e=>setS("outdir",e.target.value.trim()));
["lowprio","nosleep","skip"].forEach(k=>$(k).addEventListener("change",e=>setS(k,e.target.checked)));
function vmafCls(v){return v>=95?"g":v>=92?"y":"r"}
const phk=j=>j.phase&&j.phase.k||""; // этап работы: ключ (phase.save, phase.save_wait, …)
function jobStatic(j){
 const i=j.info;
 const meta=i?`${i.width}×${i.height} · ${esc(nfm(i.fps,2))} fps · ${esc(i.vcodec.toUpperCase())} · ${esc(nf(i.bitrate/1e6,1))} ${esc(tr("unit.mbps"))} · ${dur(i.duration)} · ${gb(j.size)} · ${esc(tr("job.audio",{list:i.audio.map(a=>`${a.codec} ${a.bitrate?Math.round(a.bitrate/1000)+tr("unit.k"):""}`).join(", ")||tr("job.no_audio")}))}`:gb(j.size);
 let body="";
 if(j.status==="done"||j.status==="skipped"){const d=(1-j.out_size/j.size)*100;const bigger=d<0;
  body=`<div class="res">${j.status==="skipped"?esc(tr("job.skipped_prefix")):""}<b>${gb(j.size)} → ${gb(j.out_size)}</b> (${pctS(d)}%) <button class="btn sm" title="${esc(tr("btn.open_out_title"))}" onclick="api('/api/open',{id:${j.id}})">${esc(tr("btn.open_out"))}</button> <button class="btn sm" title="${esc(tr("btn.open_src_title"))}" onclick="api('/api/open',{id:${j.id},which:'src'})">${esc(tr("btn.open_src"))}</button>${bigger?`<div class="note">${esc(tr("job.bigger"))}</div>`:""}</div>`}
 if(j.test){const x=j.test;const tb=x.ratio>=1;const label=x.preset?`${presetTitle(x.preset)} · ${tr("quality.name."+x.quality)}`:(x.label||"");
  body+=`<div class="res">${esc(tr("test.head",{label:"\u0001"}))
   .replace("\u0001",`<i>${esc(label)}</i>`)}<br>${esc(tr("test.clip",{a:gb(x.ref_size),b:gb(x.test_size),pct:pctS((1-x.ratio)*100)}))} <b>${esc(tr("test.forecast",{size:gb(x.est_size)}))}</b>${esc(tr("test.time",{t:tm(x.est_time)}))}
  ${x.vmaf!=null?`<br>VMAF: <span class="vm ${vmafCls(x.vmaf)}">${esc(nf(x.vmaf,1))}</span> ${esc(tr("test.vmaf_scale"))}`:`<br>${esc(tr("test.eyes"))}`}
  ${tb?`<div class="note">${esc(tr("test.not_smaller"))}</div>`:""}
  <br><button class="btn sm" style="margin-top:6px" onclick="api('/api/open',{id:${j.id},which:'test'})">${esc(tr("test.open"))}</button></div>`}
 const note=msg(j.note),err=msg(j.error);
 if(note)body+=`<div class="note">${esc(note)}</div>`;
 if(err)body+=`<div class="err">${esc(err)}</div>`;
 const rt=(j.status==="error"||j.status==="cancelled")&&j.info?`<button class="btn sm pri" title="${esc(tr("job.retry_title"))}" onclick="retryJob(${j.id})">${esc(tr("job.retry"))}</button>`:"";
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
function render(){
 const c=S.caps;$("ver").textContent=c.ffmpeg?(c.version||tr("ver.found")).replace(/Copyright.*/,"").slice(0,60):tr("ver.missing");
 setHTML($("warn"),!c.ffmpeg||!c.ffprobe?`<div class="warnbox"><b>${esc(tr("warn.ffmpeg_t"))}</b> ${esc(tr("warn.ffmpeg_1"))}<br>Windows: <code>winget install Gyan.FFmpeg</code> · Mac: <code>brew install ffmpeg</code><br>${esc(tr("warn.ffmpeg_2"))}</div>`:c.pagefile_off?`<div class="warnbox"><b>${esc(tr("warn.pf_t"))}</b> ${esc(tr("warn.pf_1"))}<br>Win+R → <code>sysdm.cpl</code> ${esc(tr("warn.pf_2"))}</div>`:"");
 renderSettings();renderJobs();
 $("btnStop").style.display=S.running?"inline-block":"none";
 // во время работы кнопки не блокируем: новые файлы встают в очередь за текущим
 $("btnGo").disabled=$("btnTest").disabled=!c.ffmpeg;
 const q=S.jobs.filter(j=>j.status==="queued");
 const left=q.reduce((a,j)=>a+(j.info?j.info.duration:0),0);
 $("qinfo").textContent=q.length?tr("foot.queue",{n:String(q.length),d:dur(left)}):"";
 $("disk").textContent=S.disk?tr("foot.disk",{size:gb(S.disk.free)}):"";
 document.title=S.running?`${(S.jobs.find(j=>j.status==="running")||{pct:0}).pct.toFixed(0)}% · Framewring`:tr("app.title");
 if(S.version)$("appver").textContent="v"+S.version;
}
// ---------------- поиск тяжёлых видео
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
const B=(s,st)=>"\u0001"+(st||"")+"\u0004"+s+"\u0002"; // жирное внутри переведённой строки: esc() потом развернёт
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
  if(pending||v!==sver)d.settings=S?S.settings:d.settings; // не откатываем только что выбранную настройку
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
    """Страница с ключом доступа, текущим языком и словарём обоих языков (переключение без перезагрузки)."""
    cat = json.dumps(i18n.CATALOG, ensure_ascii=False).replace("</", "<\\/")
    opts = "".join('<option value="%s">%s</option>' % (c, i18n.LANG_NAMES[c]) for c in i18n.LANGS)
    return HTML.replace("__TOKEN__", TOKEN).replace("__LANG__", cur_lang()).replace("__LANGOPTS__", opts) \
        .replace("__I18N__", cat)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # На Windows SO_REUSEADDR позволяет второму процессу сесть на УЖЕ занятый порт: два Жмыха делили
    # 8765, и браузер попадал то в один, то в другой. Берём порт эксклюзивно.
    allow_reuse_address = not IS_WIN

    def server_bind(self):
        if IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def zhmyh_at(port):
    """Отвечает ли на этом порту уже запущенный Framewring."""
    import urllib.request
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:%d/api/ping" % port, timeout=2) as r:
            return json.loads(r.read(200).decode("utf-8", "replace")).get("app") == "Framewring"
    except Exception:
        return False


def ask_show(port):
    """Второй запуск: просим уже работающий экземпляр показать себя (ключ доступа знает только он)."""
    import urllib.request
    try:
        if IS_WIN:
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: разрешаем ему выйти на передний план
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request("http://127.0.0.1:%d/api/show" % port, data=b"{}", method="POST")
        opener.open(req, timeout=3).read()
        return True
    except Exception:
        return False


APP_URL = {"url": None}


def _own_windows():
    """Видимые окна нашего процесса (окно программы pywebview)."""
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
        p = CUR.get("proc")
        if p:
            p.terminate()
    finally:
        os._exit(0)


def _win_msg(text, title, flags):
    """Системное окно сообщения (MessageBoxW) поверх всего; возвращает код кнопки."""
    try:
        return ctypes.windll.user32.MessageBoxW(None, text, title, flags | 0x40000)  # MB_TOPMOST
    except Exception:
        return 0


_MUTEX = []


def _hold_mutex():
    """Именованный мьютекс: по нему установщик понимает, что программа запущена (AppMutex)."""
    if IS_WIN:
        try:
            _MUTEX.append(ctypes.windll.kernel32.CreateMutexW(None, False, "FramewringRunning"))
        except Exception:
            pass


def _setup_log():
    """В сборке без консоли print некуда выводить: пишем в framewring.log в папке данных."""
    if sys.stdout is not None and sys.stderr is not None:
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
    """Полоса заголовка окна в цвет программы: тёмная тема (Windows 10/11), цвет фона, текста и рамки
    (Windows 11). Кнопки, прилипание к краям и изменение размера остаются системными."""
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
    """Своё окно программы на движке Edge (WebView2). False — не вышло, откроем браузер."""
    if "--browser" in sys.argv or not IS_WIN:
        return False
    try:
        import webview
        from webview.platforms import winforms as _wf
        if not _wf._is_chromium():
            _win_msg("Для окна программы нужен компонент Microsoft Edge WebView2 — его нет на этом компьютере.\n\n"
                     "Framewring откроется в браузере. Чтобы было своё окно, установи WebView2 Runtime:\n"
                     "https://developer.microsoft.com/microsoft-edge/webview2/\n\n"
                     "Microsoft Edge WebView2 is missing, so Framewring will open in your browser.",
                     app_name(), 0x40)
            return False
    except Exception as e:
        print(tr("con.window_unavail", e=str(e)))
        return False

    def on_drop(e):  # перетащили файлы или папки в окно
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
    n = load_queue()
    threading.Thread(target=detect_caps, daemon=True).start()
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=queue_saver, daemon=True).start()
    if not srv:
        print(tr("con.no_port"))
        sys.exit(1)
    url = "http://127.0.0.1:%d/?t=%s" % (srv.server_address[1], TOKEN)
    APP_URL["url"] = url
    _hold_mutex()
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
        p = CUR.get("proc")
        if p:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()

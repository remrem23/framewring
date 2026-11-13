"""Run all Framewring tests:  python tests/run_all.py [--ffmpeg-dir DIR] [name ...]

Each test script runs in its own process, in its own temporary work folder (see fwtest.py).
Exit code 0 only if every script passed. No third-party packages are needed (Python standard library + FFmpeg).
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# order: quick ones first
SUITE_TIMEOUT = 900  # seconds per suite
SUITES = ["test_history", "test_compress", "test_replace", "test_control"]


def main():
    args = sys.argv[1:]
    if "--ffmpeg-dir" in args:
        i = args.index("--ffmpeg-dir")
        d = args[i + 1]
        del args[i:i + 2]
        os.environ["PATH"] = os.path.join(d, "bin") + os.pathsep + d + os.pathsep + os.environ.get("PATH", "")
    names = [a if a.startswith("test_") else "test_" + a for a in args] or SUITES
    for n in names:
        if n not in SUITES:
            sys.exit("unknown suite %r, available: %s" % (n, ", ".join(SUITES)))
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit("%s not found in PATH (use --ffmpeg-dir or run packaging/get_ffmpeg.py)" % tool)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    results = []
    for n in names:
        print("=" * 70 + "\n" + n + "\n" + "=" * 70, flush=True)
        t0 = time.time()
        try:
            rc = subprocess.call([sys.executable, os.path.join(HERE, n + ".py")], env=env, cwd=HERE, timeout=SUITE_TIMEOUT)
        except subprocess.TimeoutExpired:
            print("TIMEOUT: %s did not finish in %d s" % (n, SUITE_TIMEOUT), flush=True)
            rc = 124
        results.append((n, rc, time.time() - t0))
    print("=" * 70)
    for n, rc, dt in results:
        print("%-16s %-6s %5.0f s" % (n, "PASS" if rc == 0 else "FAIL", dt))
    bad = [n for n, rc, _ in results if rc]
    print("ALL PASSED" if not bad else "FAILED: " + ", ".join(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

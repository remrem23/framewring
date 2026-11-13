"""Real compression on the CPU through the program's own HTTP API (the same calls the interface makes):
x265 (HEVC) and SVT-AV1, a generated clip. The result must be: status done, the file is smaller than the original,
the duration matches, the codec is the expected one.
This is also the "clean PC" check: the GitHub runner has no video card and no Everything, and none is needed."""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwtest import T  # noqa: E402

t = T("compress")
app = t.start()
check = t.check

# The server runs inside this process on a free port (not 8765 and no program mutex: a running copy of the
# program, if any, is not touched).
srv = app.Server(("127.0.0.1", 0), app.H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
threading.Thread(target=app.worker, daemon=True).start()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(path, body=None):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), headers={"X-Token": app.TOKEN},
                                 data=None if body is None else json.dumps(body).encode("utf-8"))
    with opener.open(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def status():
    return api("/api/status")


def duration(p):
    r = subprocess.run([app.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       stdout=subprocess.PIPE, universal_newlines=True)
    return float(r.stdout.strip())


# the program finishes its capability check on its own (CPU modes are always checked by the encoder list)
for _ in range(120):
    st = status()
    if st["caps"]["checked"]:
        break
    time.sleep(0.5)
caps = st["caps"]["presets"]
print("encoders found:", {k: v["ok"] for k, v in caps.items()})
check("capability check finished", st["caps"]["checked"])
check("x265 and SVT-AV1 are available in this FFmpeg", caps["x265"]["ok"] and caps["av1"]["ok"])

for preset, codec in (("x265", "hevc"), ("av1", "av1")):
    src = t.mk("clip_%s.mp4" % preset, dur=4)
    api("/api/settings", {"preset": preset, "quality": "balanced", "speed": "fast", "skip": False, "outdir": ""})
    api("/api/add", {"paths": [src]})
    api("/api/start", {"mode": "full"})
    t0, job = time.time(), None
    while time.time() - t0 < 300:
        job = next((j for j in status()["jobs"] if os.path.normcase(j["path"]) == os.path.normcase(src)), None)
        if job and job["status"] in ("done", "kept", "error", "cancelled"):
            break
        time.sleep(0.5)
    st_ = job and job["status"]
    check("%s: status is done" % preset, st_ == "done", (st_, job and job.get("error"), job and job.get("note")))
    if st_ != "done":
        continue
    out = job["out_path"]
    check("%s: result file exists" % preset, os.path.isfile(out), out)
    check("%s: result is smaller than the original" % preset, os.path.getsize(out) < os.path.getsize(src),
          (os.path.getsize(src), os.path.getsize(out)))
    d0, d1 = duration(src), duration(out)
    check("%s: duration matches" % preset, abs(d0 - d1) < 0.3, (d0, d1))
    check("%s: video codec is %s" % (preset, codec), app.probe(out)["vcodec"] == codec, app.probe(out)["vcodec"])
    check("%s: the original is untouched" % preset, os.path.isfile(src))
    check("%s: history has the entry" % preset, any(os.path.normcase(h["src"]) == os.path.normcase(src)
                                                    for h in app.HISTORY["items"]))
t.finish()

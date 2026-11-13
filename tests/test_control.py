"""Control checks: false "Kept", Test-mode VMAF, long paths, checksum, audio, import, parallel history writes,
broken entries at startup, .mp4 recovery, custom output folder. CPU mode (x265 / SVT-AV1)."""
import json
import os
import shutil
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwtest import T  # noqa: E402

t = T("control", need_bin=True)
app = t.start()
check, mk, ff, entry, cand, ks, run_replace = t.check, t.mk, t.ff, t.entry, t.cand, t.keys, t.run_replace
V = t.V
compress = t.compress

# 1. false "Kept": a complex start and a static continuation must be compressed, not stopped
fl = os.path.join(V, "frontloaded.mp4")
ff("-f", "lavfi", "-i", "testsrc2=size=960x540:rate=30:duration=5", "-f", "lavfi", "-i", "color=gray:size=960x540:rate=30:duration=25",
   "-filter_complex", "[0:v]noise=alls=40:allf=t+u,format=yuv420p[a];[1:v]format=yuv420p[b];[a][b]concat=n=2:v=1[v]",
   "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", fl)
j = compress(fl, preset="x265", speed="fast")
check("1 front-loaded video is compressed, not falsely Kept", j["status"] == "done", (j["status"], j["size"], j["out_size"]))

# 2. EARLY STOP: an already efficient HEVC must be stopped while it is being encoded (note.no_gain_early, written by the
#    2-second size watcher), not after a full encode (that is note.no_gain). The slow speed keeps the encode running
#    long enough for the watcher on any machine. This used to run on NVENC AV1; here it is x265 and SVT-AV1.
eff = os.path.join(V, "efficient.mp4")
ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=20", "-vf", "noise=alls=12:allf=t+u,format=yuv420p",
   "-c:v", "libx265", "-preset", "ultrafast", "-crf", "30", "-x265-params", "log-level=error", eff)


def note_keys(j):
    n = j["note"] if isinstance(j["note"], list) else [j["note"]]
    return [x["k"] for x in n if isinstance(x, dict)]


for preset, tag in (("x265", "a"), ("av1", "b")):
    j = compress(eff, preset=preset, speed="slow")
    check("2%s %s: efficient HEVC is stopped EARLY (Kept, note.no_gain_early)" % (tag, preset),
          j["status"] == "kept" and "note.no_gain_early" in note_keys(j), (j["status"], note_keys(j)))

# 3. VMAF from a Test run with other settings is not used
v3 = mk("vmaf.mp4"); app.add_path(v3); j3 = app.JOBS[-1]
j3["test"] = {"vmaf": 97.0, "preset": "nvenc_hevc", "quality": "high"}
j3["status"] = "running"
app.do_full(j3, t.settings(preset="x265", quality="compact"))
check("3 Test VMAF from other settings is not used", entry(v3).get("vmaf") is None and "rep.w.no_test" in ks(cand(v3)["warn"]))

# 4. a path of 250+ characters is blocked. The source path is 254 characters, i.e. still below Windows' MAX_PATH (260),
#    so the test does not depend on LongPathsEnabled; the output folder is short, so only the source path is long.
cur = V
while 223 - len(cur) > 2:
    cur = os.path.join(cur, "d" * min(30, 223 - len(cur) - 1))
os.makedirs(cur, exist_ok=True)
lp = os.path.join(cur, "x" * 16 + "_long_video.mp4")
shutil.copy2(mk("lsrc.mp4"), lp)
compress(lp, outdir=os.path.join(V, "o"))
check("4 path > 250 chars is blocked", 250 <= len(app._real_path(lp)) < 260 and "rep.b.long_path" in ks(cand(lp)["block"]),
      len(app._real_path(lp)))

# 5. checksum: a silently changed byte in the compressed file is caught
h5 = mk("hash.mp4"); j5 = compress(h5)
e5 = entry(h5); o5 = e5["out"]
with open(o5, "r+b") as f:
    f.seek(os.path.getsize(o5) // 2); b = f.read(1); f.seek(-1, 1); f.write(bytes([b[0] ^ 1]))
os.utime(o5, (e5["out_sig"][1], e5["out_sig"][1]))  # same time and size - the fingerprint still matches
r = run_replace(h5)
check("5 silent 1-byte change caught by checksum", r["state"] == "error" and r["err"]["k"] == "verify.hash"
      and os.path.exists(h5) and os.path.exists(o5), r["err"])

# 6. shortened audio is caught
a6 = mk("audio.mp4", dur=8); j6 = compress(a6)
e6 = entry(a6); o6 = e6["out"]
bad = o6 + ".tmp.mp4"
ff("-i", o6, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", "atrim=0:3", "-c:a", "aac", bad)
os.replace(bad, o6)
e6["out_sig"] = app.src_sig(o6); e6["out_hash"] = app.file_sha256(o6)
r = run_replace(a6)
check("6 shortened audio caught", r["state"] == "error" and r["err"]["k"] in ("verify.audio_short", "verify.duration"), r["err"])

# 7. history import: its own block reason
f7 = os.path.join(V, "imp.json")
other7 = mk("imp_src.mp4")
json.dump([{"t": 5, "src": other7, "out": o6, "name": "x", "size": 9, "out_size": 1, "out_hash": "z"}], open(f7, "w"))
app.H.route(app.H.__new__(app.H), "/api/hist_import", {"path": f7})
imp = [c for c in app.replace_candidates() if c["key"].startswith("5|")]
check("7 imported entry is blocked with its own message", imp and "rep.b.imported" in ks(imp[0]["block"]))

# 8. parallel history writes - nothing is lost
errs = []


def w1():
    for i in range(150):
        try:
            app.add_history({"t": 1000 + i, "src": "C:/p/%d.mp4" % i, "out": "C:/p/c/%d.mp4" % i, "name": "p"})
        except Exception as e:
            errs.append(e)


def w2():
    k = app._hkey(entry(a6))
    for i in range(150):
        try:
            app._set_hist(k, note_test=i)
        except Exception as e:
            errs.append(e)


t1, t2 = threading.Thread(target=w1), threading.Thread(target=w2); t1.start(); t2.start(); t1.join(); t2.join()
disk = json.load(open(app.HISTORY_FILE, encoding="utf-8"))
mem_p = [h for h in app.HISTORY["items"] if h.get("name") == "p"]
disk_p = [h for h in disk if h.get("name") == "p"]
disk_a6 = next((h for h in disk if os.path.normcase(h.get("src", "")) == os.path.normcase(a6)), {})
check("8 concurrent history writes: no errors, nothing lost", not errs and len(disk) == len(app.HISTORY["items"])
      and len(mem_p) == len(disk_p) == 150 and disk_a6.get("note_test") == 149 and entry(a6).get("note_test") == 149,
      (len(errs), len(disk), len(disk_p), disk_a6.get("note_test")))

# 9. broken queue/history entries do not stop startup
json.dump([{"path": None, "name": "x"}, 5, {"path": a6, "name": "ok", "size": 1, "status": "ready"}], open(str(app.QUEUE_FILE), "w"))
app.JOBS.clear()
n = app.load_queue()
app.HISTORY["items"].append({"t": 9, "src": a6, "out": None, "replace_tmp": "x"})
try:
    app.replace_recover(); rec_ok = True
except Exception as e:
    rec_ok = e
check("9 broken queue/history entries don't stop startup", n == 1 and rec_ok is True, (n, rec_ok))

# 10. .mp4 original: a crash after the final rename -> recovery marks it replaced
m10 = mk("m10.mp4"); compress(m10)
e10 = entry(m10); o10 = e10["out"]
os.remove(m10)            # the original "went to the Recycle Bin"
shutil.copy2(o10, m10)    # the compressed file is already in place of the original, no temp file left
os.utime(m10, (e10["out_sig"][1], e10["out_sig"][1]))
e10["replace_tmp"] = str(app._tmp_for(m10)); e10["replace_copy"] = False
app.replace_recover()
check("10 recovery: .mp4 original replaced but not recorded -> marked replaced", entry(m10).get("replaced"))

# 11. a custom output folder is not removed even when it becomes empty
out_custom = os.path.join(V, "my_out")
c11 = mk("c11.mp4")
compress(c11, outdir=out_custom)
r = run_replace(c11)
check("11 custom output folder is kept after replace", r["state"] == "done" and os.path.isdir(out_custom), r)
t.finish()

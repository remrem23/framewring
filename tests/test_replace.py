"""Replacing originals with compressed files (0.9.3+): 12 scenarios, CPU mode (x265). Synthetic videos only."""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwtest import T  # noqa: E402

t = T("replace", need_bin=True)
app = t.start()
check, mk, entry, cand, keys, run_replace = t.check, t.mk, t.entry, t.cand, t.keys, t.run_replace
V = t.V
compress = t.compress_ok

# 1. plain replace: .mp4 in place, .mkv -> .mp4 next to it; the original goes to the Recycle Bin
t0 = time.time()
a = mk("a.mp4"); compress(a)
r = run_replace(a)
check("1a mp4 replaced in place", r["state"] == "done" and app.probe(a)["vcodec"] == "hevc", r)
check("1a original is in the Recycle Bin", app.in_recycle_bin(a, t0))
b = mk("b.mkv"); compress(b)
r = run_replace(b)
check("1b mkv -> mp4 next to it", r["state"] == "done" and not os.path.exists(b) and os.path.exists(b[:-4] + ".mp4"), r)

# 2. a file bigger than the free space of the Recycle Bin is blocked
bc = app.bin_check(a, 10 ** 15)
check("2 file bigger than Recycle Bin is blocked", bc is not None and bc["k"] == "rep.b.bin_small", bc)
check("2b normal size fits", app.bin_check(a, 10 ** 6) is None, app.bin_check(a, 10 ** 6))

# 3. subst: replacing through a subst drive letter still sends to the Recycle Bin (by the real path)
letter = next((l for l in "WVUTSRQP" if not os.path.exists(l + ":\\")), None)
if letter and os.name == "nt":
    subprocess.run(["subst", letter + ":", V], check=True)
    try:
        mk("s.mp4")
        s_via = letter + ":\\s.mp4"
        compress(s_via)
        check("3 subst path resolves to the real path", os.path.normcase(app._real_path(s_via)).startswith(
            os.path.normcase(V)), app._real_path(s_via))
        r = run_replace(s_via)
        check("3 subst: replaced", r["state"] == "done", r)
    finally:
        subprocess.run(["subst", letter + ":", "/d"])
else:
    check("3 subst (no free drive letter)", False, "no free letter")

# 4. an old history entry without fingerprints is blocked
c4 = mk("c.mp4"); compress(c4)
h = entry(c4); sig_s, sig_o = h["src_sig"], h["out_sig"]
h.pop("src_sig"); h.pop("out_sig")
check("4 old entry without fingerprints is blocked", "rep.b.old_entry" in keys(cand(c4)["block"]), keys(cand(c4)["block"]))
h["src_sig"], h["out_sig"] = sig_s, sig_o

# 5. the compressed file was changed -> blocked
orig_out = open(h["out"], "rb").read()
with open(h["out"], "ab") as f:
    f.write(b"\0" * 1000)
check("5 changed compressed file is blocked", "rep.b.out_changed" in keys(cand(c4)["block"]), keys(cand(c4)["block"]))
open(h["out"], "wb").write(orig_out); os.utime(h["out"], (h["out_sig"][1], h["out_sig"][1]))

# 6. keys are stable: history shifting during a replace does not mix up entries
d = mk("d.mp4"); compress(d)
k = app._hkey(entry(d))
app.HISTORY["items"].insert(0, {"t": 0, "src": os.path.join(V, "zzz.mp4"), "out": os.path.join(V, "zzz2.mp4"),
                                "name": "zzz", "size": 1, "out_size": 1})
app.replace_run([k])
app.HISTORY["items"].insert(0, {"t": -1, "src": os.path.join(V, "yyy.mp4"), "out": os.path.join(V, "yyy2.mp4"),
                                "name": "yyy", "size": 1, "out_size": 1})
while app.REPLACE["running"]:
    time.sleep(0.3)
hd = entry(d)
check("6 history shifted mid-run: the right entry is marked replaced", hd.get("replaced") and not any(
    x.get("replaced") for x in app.HISTORY["items"] if x["name"] in ("zzz", "yyy")))

# 7. video truncated while audio is whole -> verification catches it
e = mk("e.mp4", dur=6); je = compress(e)
out_e = je["out_path"]
bad = out_e + ".bad.mp4"
t.ff("-i", out_e, "-filter_complex", "[0:v]trim=0:2,setpts=PTS-STARTPTS[v]", "-map", "[v]", "-map", "0:a",
     "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", bad)
os.replace(bad, out_e)
he = entry(e); he["out_sig"] = app.src_sig(out_e); he["out_hash"] = app.file_sha256(out_e)
r = run_replace(e)
check("7 truncated video caught by verification", r["state"] == "error" and r["err"]["k"] in ("verify.short", "verify.duration")
      and os.path.exists(e) and os.path.exists(out_e), r["err"])

# 8. a file that is queued/compressing is blocked
f8 = mk("f.mp4"); jf = compress(f8)
jf["status"] = "queued"
check("8 queued/compressing file is blocked", "rep.b.busy" in keys(cand(f8)["block"]))
jf["status"] = "done"

# 9. recovery after an interrupted replace
g = mk("g.mp4"); jg = compress(g)
hg = entry(g); tmp = app._tmp_for(g)
os.rename(hg["out"], str(tmp)); hg["replace_tmp"], hg["replace_copy"] = str(tmp), False
app.replace_recover()
check("9a crash after move, original present -> rolled back", os.path.exists(hg["out"]) and not tmp.exists()
      and not entry(g).get("replace_tmp"))
os.rename(hg["out"], str(tmp)); entry(g)["replace_tmp"], entry(g)["replace_copy"] = str(tmp), False
moved = g + ".was"
os.rename(g, moved)  # "the original went to the Recycle Bin"
app.replace_recover()
check("9b crash after recycling -> finished (new file in place)", os.path.exists(g) and app.probe(g)["vcodec"] == "hevc"
      and entry(g).get("replaced"))
os.remove(moved)

# 10. a leftover temp file of an unfinished replace blocks a new one
h10 = mk("h.mp4"); compress(h10)
open(str(app._tmp_for(h10)), "wb").write(b"x")
check("10 leftover temp file blocks", "rep.b.leftover" in keys(cand(h10)["block"]))
os.remove(str(app._tmp_for(h10)))

# 11. a lost extra video track -> warning
i11 = os.path.join(V, "i.mkv")
t.ff("-f", "lavfi", "-i", "testsrc2=size=854x480:rate=30:duration=4", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=4",
     "-f", "lavfi", "-i", "sine=duration=4", "-map", "0", "-map", "1", "-map", "2", "-c:v", "libx264", "-preset", "ultrafast",
     "-b:v", "10M", "-c:a", "aac", i11)
compress(i11)
check("11 missing extra video track -> warning", "rep.w.lost_video" in keys(cand(i11)["warn"]), keys(cand(i11)["warn"]))

# 12. the target name appears during verification -> rename must not overwrite it
j12 = mk("j.mkv"); compress(j12)
orig_verify = app.verify_output


def slow_verify(out, info, item, *a, **kw):
    open(j12[:-4] + ".mp4", "wb").write(b"FOREIGN")
    return orig_verify(out, info, item, *a, **kw)


app.verify_output = slow_verify
r = run_replace(j12)
app.verify_output = orig_verify
check("12 a file appearing during verify is NOT overwritten", open(j12[:-4] + ".mp4", "rb").read() == b"FOREIGN"
      and os.path.exists(j12) and r["state"] == "error", r["err"])
t.finish()

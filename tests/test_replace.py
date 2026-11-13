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
letter = t.free_letter()
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
t.wait_replace()
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
      and os.path.exists(j12) and r["state"] == "error" and r["err"]["k"] == "rep.b.collision", r["err"])

# ---------------------------------------------------------------- more scenarios ----


def same_bytes(p, data):
    return os.path.isfile(p) and open(p, "rb").read() == data


# 13. the original was edited after compression -> blocked, both files intact
n13 = mk("n13.mp4"); compress(n13)
o13 = entry(n13)["out"]
with open(n13, "ab") as f:
    f.write(b"\0" * 100)
src13, out13 = open(n13, "rb").read(), open(o13, "rb").read()
r = run_replace(n13)
check("13 original edited after compression -> rep.b.src_changed, nothing touched", "rep.b.src_changed" in keys(cand(n13)["block"])
      and r["state"] == "error" and r["err"]["k"] == "rep.b.src_changed" and same_bytes(n13, src13) and same_bytes(o13, out13), r["err"])

# 14. the Recycle Bin step fails -> rolled back: compressed file back in place, original intact
p14 = mk("p14.mp4"); compress(p14)
o14 = entry(p14)["out"]
src14, out14 = open(p14, "rb").read(), open(o14, "rb").read()
orig_recycle = app.recycle
app.recycle = lambda p: False
try:
    r = run_replace(p14)
finally:
    app.recycle = orig_recycle
check("14 Recycle Bin fails -> rolled back, both files intact", r["state"] == "error" and r["err"]["k"] == "rep.err.recycle"
      and same_bytes(p14, src14) and same_bytes(o14, out14) and not app._tmp_for(p14).exists()
      and not entry(p14).get("replace_tmp") and not entry(p14).get("replaced"), r["err"])
check("14b the entry can be replaced afterwards", run_replace(p14)["state"] == "done")

# 15. the default "compressed" folder: kept while it holds other files, removed when it becomes empty
D15 = os.path.join(V, "f15"); os.makedirs(D15)
x15, y15 = os.path.join(D15, "x.mp4"), os.path.join(D15, "y.mp4")
shutil.copy2(mk("x.mp4", dur=3), x15); shutil.copy2(mk("y.mp4", dur=3), y15)
compress(x15); compress(y15)
cdir = os.path.join(D15, "compressed")
r1 = run_replace(x15)
check("15a compressed folder is kept while another result is in it", r1["state"] == "done" and os.path.isdir(cdir)
      and os.listdir(cdir) == ["y.mp4"], os.listdir(cdir) if os.path.isdir(cdir) else None)
r2 = run_replace(y15)
check("15b compressed folder is removed when empty", r2["state"] == "done" and not os.path.exists(cdir), r2)

# 16. a second replace of the same entry and a result that is not smaller
check("16a already replaced entry -> rep.b.replaced", "rep.b.replaced" in keys(cand(a)["block"]), keys(cand(a)["block"]))
k16 = app._hkey(entry(a))
app.replace_run([k16]); t.wait_replace()
check("16b second replace is refused and the file stays", app.REPLACE["items"][k16]["state"] == "error"
      and app.REPLACE["items"][k16]["err"]["k"] == "rep.b.replaced" and app.probe(a)["vcodec"] == "hevc",
      app.REPLACE["items"][k16]["err"])
q16 = mk("q16.mp4", dur=3); compress(q16)
o16 = entry(q16)["out"]
with open(o16, "ab") as f:
    f.write(b"\0" * (os.path.getsize(q16) + 10))  # now bigger than the original (and changed, so also out_changed)
check("16c result not smaller than the original -> rep.b.not_smaller", "rep.b.not_smaller" in keys(cand(q16)["block"]),
      keys(cand(q16)["block"]))

# 17. a batch of three: the middle one fails, the other two are replaced
b1, b2, b3 = (mk("batch%d.mp4" % i, dur=3) for i in (1, 2, 3))
for p in (b1, b2, b3):
    compress(p)
with open(entry(b2)["out"], "ab") as f:
    f.write(b"\0")  # changed after compression
src_b2 = open(b2, "rb").read()
ks3 = [app._hkey(entry(p)) for p in (b1, b2, b3)]
app.replace_run(ks3); t.wait_replace()
st = [app.REPLACE["items"][k]["state"] for k in ks3]
check("17 batch of 3: the failing one does not stop the others", st == ["done", "error", "done"]
      and app.probe(b1)["vcodec"] == "hevc" and app.probe(b3)["vcodec"] == "hevc" and same_bytes(b2, src_b2), st)

# 18. /api/replace with an unknown key -> rep.err.blocked, nothing starts
route = lambda path, body: app.H.route(app.H.__new__(app.H), path, body)  # noqa: E731
try:
    route("/api/replace", {"keys": ["no-such-key|0"]})
    err = None
except app.UserError as e:
    err = e.k
check("18a /api/replace with an unknown key -> rep.err.blocked", err == "rep.err.blocked" and not app.REPLACE["running"], err)
try:
    route("/api/replace", {"keys": []})
    err = None
except app.UserError as e:
    err = e.k
check("18b /api/replace with no keys -> rep.err.none", err == "rep.err.none", err)
t.finish()

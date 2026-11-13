"""History export/import (home folder redirected into the work folder) and a forged-history attack:
imported entries must never make the program touch foreign files."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwtest import T  # noqa: E402

t = T("history")
app = t.start()
check = t.check
home = os.environ["USERPROFILE"]
route = lambda p, b: app.H.route(app.H.__new__(app.H), p, b)  # noqa: E731
app.open_folder = lambda p: None  # do not open Explorer in a test
# The real Documents folder comes from the shell (it may be redirected to OneDrive or another drive and then ignores
# USERPROFILE), so the function is replaced: an export must never go outside the work folder.
app._documents_dir = lambda: Path(home, "Documents")

# --- export / import round trip
app.HISTORY["items"] = [{"t": 1, "src": "C:/a.mp4", "out": "C:/c/a.mp4", "name": "a", "size": 10, "out_size": 4},
                        {"t": 2, "src": "C:/b.mp4", "out": "C:/c/b.mp4", "name": "b", "size": 10, "out_size": 5}]
r = route("/api/hist_export", {})
check("export goes to the (fake) Documents folder", os.path.normcase(os.path.dirname(r["path"])) == os.path.normcase(
    os.path.join(home, "Documents")) and os.path.exists(r["path"]), r["path"])
app.HISTORY["items"] = app.HISTORY["items"][:1]  # "lost" one entry
r2 = route("/api/hist_import", {"path": r["path"]})
check("import restores the lost entry", r2["added"] == 1 and len(app.HISTORY["items"]) == 2, (r2["added"], len(app.HISTORY["items"])))
r3 = route("/api/hist_import", {"path": r["path"]})
check("re-import adds nothing", r3["added"] == 0, r3["added"])
bad = os.path.join(t.work, "bad.json")
open(bad, "w").write('{"x":1}')
try:
    route("/api/hist_import", {"path": bad})
    check("a file that is not a history is rejected", False, "not rejected")
except app.UserError as e:
    check("a file that is not a history is rejected", True, e.k)

# --- attack: replace_tmp pointing at foreign files
W = os.path.join(t.work, "attack")
os.makedirs(W)
precious = os.path.join(W, "precious.mkv"); open(precious, "wb").write(b"PRECIOUS")
other = os.path.join(W, "other_precious.mov"); open(other, "wb").write(b"OTHER")
src_exists = os.path.join(W, "exists.mp4"); open(src_exists, "wb").write(b"SRC")
evil = [{"t": 11, "src": src_exists, "out": os.path.join(W, "o1.mp4"), "name": "a", "size": 3, "out_size": 1,
         "replace_tmp": precious, "replace_copy": True, "src_sig": [3, 0], "out_sig": [1, 0]},
        {"t": 12, "src": os.path.join(W, "gone.mkv"), "out": os.path.join(W, "o2.mp4"), "name": "b", "size": 3,
         "out_size": 1, "replace_tmp": other, "replace_copy": False}]
f = os.path.join(W, "evil.json"); json.dump(evil, open(f, "w"))
app.HISTORY["items"] = []
r = route("/api/hist_import", {"path": f})
check("attack: both entries imported", r["added"] == 2, r["added"])
check("attack: service fields are stripped on import",
      not any(k in h for h in app.HISTORY["items"] for k in ("replace_tmp", "replace_copy", "src_sig", "out_sig")))
# even if the fields got into the history somehow, recovery must not touch foreign paths
for h, e in zip(app.HISTORY["items"], evil):
    h["replace_tmp"], h["replace_copy"] = e["replace_tmp"], e["replace_copy"]
app.replace_recover()
check("attack: precious files are intact", os.path.exists(precious) and os.path.exists(other)
      and open(precious, "rb").read() == b"PRECIOUS" and open(other, "rb").read() == b"OTHER")
check("attack: no file was created from the forged entries", not os.path.exists(os.path.join(W, "gone.mp4")))
# the files exist now, so the only reason left to block is "imported from a foreign history file"
for p in (os.path.join(W, "o1.mp4"), os.path.join(W, "o2.mp4"), os.path.join(W, "gone.mkv")):
    open(p, "wb").write(b"X")
cs = app.replace_candidates()
check("attack: two candidates, both blocked as imported", len(cs) == 2 and all("rep.b.imported" in t.keys(c["block"]) for c in cs),
      [t.keys(c["block"]) for c in cs])
keys = [c["key"] for c in cs]
app.replace_run(keys)
t.wait_replace()
check("attack: a replace of the imported entries fails and touches nothing",
      all(app.REPLACE["items"][k]["state"] == "error" for k in keys) and os.path.exists(precious) and os.path.exists(other)
      and os.path.exists(src_exists) and open(src_exists, "rb").read() == b"SRC",
      [app.REPLACE["items"][k]["state"] for k in keys])
t.finish()

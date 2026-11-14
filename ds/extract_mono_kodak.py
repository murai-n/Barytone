"""Kodak's black-and-white sheets draw their curves as vector paths, so these
come straight out of the PDF. One curve per plot, so the longest chain wins."""
import sys, json
import numpy as np, pdfplumber, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/claude/ds")
from ex import flat, tidy, pick, chain, chain2, U
from extract4 import lin, frags, chain_arr

def one(p, box, xm, ym, min_pts=20):
    """The single curve inside a panel, in data coordinates."""
    # frags() drops the exactly horizontal and vertical segments, so the panel
    # grid cannot be chained into the curve and saw-tooth it.
    polys = [a for a in chain_arr(frags(p, box), tol=8) if a.shape[0] > min_pts]
    assert polys, ("no curve", box)
    a = max(polys, key=lambda z: z[:, 0].max() - z[:, 0].min())
    return dict(zip(("x", "y"), tidy(xm(a[:, 0]), ym(a[:, 1]))))

OUT = {}

# ---- T-MAX 100 (F-4016), page 8 -------------------------------------------
p = pdfplumber.open(U + "7d73e82b-f4016_tmax_100-2018.pdf").pages[7]
ch = one(p, (348, 52, 560, 248),
         lambda c: lin(c, 355.7, -4.0, 539.2, 1.0), lambda c: lin(c, 57.4, 4.0, 242.3, 0.0))
se = one(p, (68, 492, 310, 655),
         lambda c: lin(c, 75.2, 250.0, 195.8, 550.0), lambda c: lin(c, 498.7, 2.0, 650.2, -2.0))
OUT["T-Max 100"] = dict(iso=100, ch=dict(x=ch["x"], d=ch["y"]),
                        sens=dict(wl=se["x"], logS=se["y"]))

# ---- T-MAX 400 (F-4043), page 8; this sheet prints no spectral curve ------
p = pdfplumber.open(U + "fdde754c-f4043_TMax_400-2016.pdf").pages[7]
ch = one(p, (72, 50, 290, 246),
         lambda c: lin(c, 80.1, -4.0, 229.9, 0.0), lambda c: lin(c, 55.7, 4.0, 241.2, 0.0))
OUT["T-Max 400"] = dict(iso=400, ch=dict(x=ch["x"], d=ch["y"]), sens=None)

# ---- TRI-X 400 (F-4017), page 7 -------------------------------------------
p = pdfplumber.open(U + "05858f64-f4017-2016.pdf").pages[6]
ch = one(p, (358, 65, 565, 260),
         lambda c: lin(c, 366.3, -4.0, 550.0, 1.0), lambda c: lin(c, 69.9, 4.0, 254.8, 0.0))
se = one(p, (70, 288, 300, 448),
         lambda c: lin(c, 87.6, 250.0, 147.8, 400.0), lambda c: lin(c, 293.1, 4.0, 442.4, 0.0))
OUT["Tri-X 400"] = dict(iso=400, ch=dict(x=ch["x"], d=ch["y"]),
                        sens=dict(wl=se["x"], logS=se["y"]))

for k, v in OUT.items():
    c = v["ch"]; s = v["sens"]
    print(f"{k:11s} char n={len(c['x']):4d} logE {min(c['x']):.2f}..{max(c['x']):.2f} "
          f"D {min(c['d']):.2f}..{max(c['d']):.2f}   "
          + (f"sens n={len(s['wl'])} wl {min(s['wl']):.0f}..{max(s['wl']):.0f}" if s else "sens: not published"))

json.dump(OUT, open("/home/claude/ds/mono_kodak_raw.json", "w"))
print("wrote", len(OUT), "films")

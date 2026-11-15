"""Digitize the 2026-11 batch of datasheets into ds/new2.json.
Vector paths are read straight out of the PDFs with pdfplumber (ex.py helpers),
so the curves carry the publisher's own geometry rather than a traced guess."""
import sys, json, numpy as np, pdfplumber, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/claude/ds")
from ex import flat, tidy, pick, chain, chain2, sens_extract, U

def lin(v, a, va, b, vb):
    return va + (np.asarray(v) - a) / (b - a) * (vb - va)

def letters(p, xa, ta, xb, tb, keys=("R", "G", "B")):
    out = []
    for w in p.extract_words():
        x = (w["x0"] + w["x1"]) / 2; y = (w["top"] + w["bottom"]) / 2
        if w["text"] in keys and xa <= x <= xb and ta <= y <= tb:
            out.append((w["text"], x, y))
    return out

def classify_by_letters(polys, lets):
    """One-to-one match of R/G/B labels to curves.

    Nearest-neighbour fails where two curves run close together: both labels
    latch onto the same polyline and a third curve is dropped.  The labels are
    stacked in the same vertical order as the curves they name, so ranking both
    by y at the labels' x and zipping gives a stable, one-to-one assignment."""
    lets = sorted(lets, key=lambda t: t[2])          # top label first
    xref = float(np.mean([x for _, x, _ in lets]))
    def yat(a):
        return float(a[int(np.argmin(abs(a[:, 0] - xref))), 1])
    order = sorted(range(len(polys)), key=lambda i: yat(polys[i]))
    assert len(order) >= len(lets), (len(order), len(lets))
    return {lets[k][0]: order[k] for k in range(len(lets))}

OUT = {}

# ================= KODAK PORTRA 160NC / 160VC / 400NC / 400VC (E-190, 2006) =========
# One template across pages 8-11, but the pages do not place it at the same spot:
# the VC pages sit 12 pt right of the NC pages, and pages 9-11 sit 16 pt higher
# than page 8.  Using page 8's anchors on every page put the VC spectral curves
# 30 nm too far to the red (blue layer peaking at 500 nm), which pushed reds and
# skin toward yellow.  Each page is now located by its own tick labels.
PORTRA = [("Portra 160NC", 7, 160), ("Portra 160VC", 8, 160),
          ("Portra 400NC", 9, 400), ("Portra 400VC", 10, 400)]
def portra_offset(p):
    """(dx, dy) of this page's chart block relative to page 8 (index 7), from the
    '250' wavelength label (x) and the top '4.0' density label of the
    characteristic-curve panel (y)."""
    ws = p.extract_words()
    x250 = [(w["x0"] + w["x1"]) / 2 for w in ws if w["text"] == "250" and w["top"] > 400]
    y40 = [(w["top"] + w["bottom"]) / 2 for w in ws if w["text"] == "4.0" and w["x0"] < 80 and w["top"] < 120]
    assert len(x250) == 1 and len(y40) == 1, (x250, y40)
    return x250[0] - 75.3, y40[0] - 92.7
pdf = pdfplumber.open(U + "2e719031-e190-Portra-2006.pdf")
for name, pi, iso in PORTRA:
    p = pdf.pages[pi]; H = p.height; dx, dy = portra_offset(p)
    xm = lambda c: lin(c, 74.5 + dx, -4.0, 258.2 + dx, 1.0)
    ym = lambda c: lin(c, 92.7 + dy, 4.0, 277.6 + dy, 0.0)
    polys = [a for a in chain(pick(p, 70 + dx, 88 + dy, 335 + dx, 285 + dy, minw=80), H) if a.shape[0] > 20]
    lets = letters(p, 70 + dx, 88 + dy, 340 + dx, 287 + dy); cl = classify_by_letters(polys, lets)
    assert set(cl) == {"R", "G", "B"}, (name, len(polys), lets)
    ch = {t: dict(zip(("x", "d"), tidy(xm(polys[i][:, 0]), ym(polys[i][:, 1])))) for t, i in cl.items()}
    sx = lambda c: lin(c, 75.3 + dx, 250.0, 275.8 + dx, 750.0)
    sy = lambda c: lin(c, 336.7 + dy, 4.0, 486.2 + dy, 0.0)
    sens = sens_extract(p, (70 + dx, 330 + dy, 335 + dx, 495 + dy), sx, sy)
    print(f"{name}: page offset dx {dx:+.1f} dy {dy:+.1f}")
    OUT[name] = dict(kind="neg", iso=iso, ch=ch, sens=sens)
    print(f"{name}: ch", {k: len(v["x"]) for k, v in ch.items()},
          "sens", {k: len(v["wl"]) for k, v in sens.items()})

def frags(p, bbox, minpts=3):
    """Curve fragments in a panel, taking both `curves` and `lines`.

    Some sheets draw the straight-line portion of a characteristic curve as
    PDF line segments, so reading only `curves` leaves a hole in the middle of
    the scale.  Axis rules and gridlines are dropped by their exact horizontal
    or vertical direction; a real curve segment is always slanted."""
    xa, ta, xb, tb = bbox; H = p.height; out = []
    for c in p.curves:
        if (xa <= c["x0"] and c["x1"] <= xb and ta <= c["top"] and c["bottom"] <= tb
                and len(c["pts"]) >= minpts and not c.get("fill")):
            out.append(flat(c, H))
    for l in p.lines:
        if not (xa <= l["x0"] and l["x1"] <= xb and ta <= l["top"] and l["bottom"] <= tb):
            continue
        a = np.array([[l["x0"], H - l["y0"]], [l["x1"], H - l["y1"]]], dtype=float)
        dx = a[1, 0] - a[0, 0]; dy = a[1, 1] - a[0, 1]
        if abs(dx) < 0.5 or abs(dy) < 0.5:
            continue
        out.append(a[np.argsort(a[:, 0], kind="stable")])
    return out

def chain_arr(segs, tol=8.0, maxang=45.0):
    """Stitch polyline arrays end-to-end, same rule as ex.chain2 but on arrays."""
    segs = [s[np.argsort(s[:, 0], kind="stable")] if s[0, 0] > s[-1, 0] else s for s in segs]
    segs = sorted(segs, key=lambda s: s[0, 0])
    def ang(v1, v2):
        n1 = np.hypot(*v1); n2 = np.hypot(*v2)
        if n1 < 1e-9 or n2 < 1e-9: return 0.0
        return np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (n1 * n2), -1, 1)))
    chains = []
    for s in segs:
        best = None; bd = tol + 1
        for ch in chains:
            a = ch[-1]
            gap = s[0] - a[-1]; d = float(np.hypot(*gap))
            if d >= bd or s[0, 0] < a[-1, 0] - 0.5: continue
            da = a[-1] - a[max(0, len(a) - 4)]; db = s[min(3, len(s) - 1)] - s[0]
            if d > 1.0 and (ang(da, gap) > maxang or ang(gap, db) > maxang): continue
            if d <= 1.0 or ang(da, db) <= maxang: best = ch; bd = d
        if best is None: chains.append([s])
        else: best.append(s)
    return [np.vstack(c) for c in chains]

def grab(p, name, kind, iso, cbox, cx, cy, sbox, sx, sy, letbox=None):
    """Pull one film's characteristic + spectral-sensitivity curves off a page."""
    H = p.height
    polys = [a for a in chain(pick(p, *cbox, minw=60), H) if a.shape[0] > 20]
    if len(polys) < 3:
        # Some sheets draw each curve as a run of short fragments, with the
        # straight middle section emitted as plain lines; stitch both kinds.
        polys = [a for a in chain_arr(frags(p, cbox), tol=8) if a.shape[0] > 12]
    lb = letbox or (cbox[0], cbox[1], cbox[2] + 6, cbox[3] + 4)
    lets = letters(p, *lb)
    assert set(t for t, _, _ in lets) == {"R", "G", "B"}, (name, "letters", lets)
    assert len(polys) >= 3, (name, "polys", [a.shape[0] for a in polys])
    cl = classify_by_letters(polys, lets)
    ch = {t: dict(zip(("x", "d"), tidy(cx(polys[i][:, 0]), cy(polys[i][:, 1])))) for t, i in cl.items()}
    sens = sens_extract(p, sbox, sx, sy)
    OUT[name] = dict(kind=kind, iso=iso, ch=ch, sens=sens)
    print(f"{name}: ch", {k: len(v['x']) for k, v in ch.items()},
          "sens", {k: len(v['wl']) for k, v in sens.items()})

# ================= KODAK VERICOLOR III (VPS, E-26) =================================
p = pdfplumber.open(U + "e3dcb0dc-e26-Vericolor_III.pdf").pages[3]
grab(p, "Vericolor III", "neg", 160,
     (70, 68, 335, 265), lambda c: lin(c, 75.5, -3.0, 259.5, 1.0), lambda c: lin(c, 72.4, 4.0, 258.1, 0.0),
     (350, 70, 560, 218), lambda c: lin(c, 357.2, 250.0, 550.5, 750.0), lambda c: lin(c, 75.2, 2.0, 211.9, -2.0))

# ================= KODAK ULTRA COLOR 100UC / 400UC (E-4035) ========================
uc = pdfplumber.open(U + "9f1d7e10-e4035-100UC_400UC.pdf")
grab(uc.pages[5], "Ultra Color 100UC", "neg", 100,
     (70, 98, 340, 292), lambda c: lin(c, 82.8, -4.0, 267.4, 1.0), lambda c: lin(c, 102.3, 4.0, 287.7, 0.0),
     (62, 345, 335, 505), lambda c: lin(c, 77.0, 350.0, 201.5, 600.0), lambda c: lin(c, 351.8, 3.0, 500.8, -1.0))
# 400UC page carries two characteristic panels; the left one is the rated EI 400.
grab(uc.pages[6], "Ultra Color 400UC", "neg", 400,
     (80, 78, 345, 272), lambda c: lin(c, 92.6, -4.0, 279.7, 1.0), lambda c: lin(c, 83.4, 4.0, 267.8, 0.0),
     (70, 320, 320, 482), lambda c: lin(c, 83.7, 350.0, 286.2, 750.0), lambda c: lin(c, 327.0, 4.0, 477.2, 0.0))

# ================= KODAK PRO IMAGE 100 (A-009) =====================================
p = pdfplumber.open(U + "4aeb7ea4-446556806-kodak-proimage-100-pdf.pdf").pages[2]
grab(p, "Pro Image 100", "neg", 100,
     (95, 70, 340, 265), lambda c: lin(c, 102.8, -3.0, 287.6, 1.0), lambda c: lin(c, 75.7, 4.0, 260.6, 0.0),
     (355, 72, 575, 234), lambda c: lin(c, 363.4, 250.0, 563.7, 750.0), lambda c: lin(c, 77.1, 4.0, 226.6, 0.0))

# ================= KODAK EKTACHROME 100 Professional / EPN (E-27) ==================
p = pdfplumber.open(U + "011d7302-e27-1.pdf").pages[4]
grab(p, "Ektachrome EPN", "pos", 100,
     (80, 120, 340, 316), lambda c: lin(c, 86.5, -3.0, 270.3, 1.0), lambda c: lin(c, 125.2, 4.0, 310.1, 0.0),
     (355, 48, 575, 210), lambda c: lin(c, 363.3, 250.0, 563.8, 750.0), lambda c: lin(c, 53.7, 3.0, 203.2, -1.0))

# ================= FUJICHROME VELVIA 100 (AF3-202E) ================================
# Layers are told apart by stroke dash pattern, matching the sheet's own legend:
# R solid, G dash-dot, B dashed.
p = pdfplumber.open(U + "252b10b1-films_velvia-100_datasheet_01.pdf").pages[7]
H = p.height
DASH = {"R": "[]", "G": "[8.999, 1.5, 2.5, 1.5]", "B": "[3, 1.5]"}
cbox = (85, 173, 283, 349)       # the plot frame itself, so stray marks stay out
# The sheet's own legend and the exposure/process note sit inside the plot box
# and are drawn with the same dashes as the blue layer, so they are cut out.
NOTE = (188, 172, 285, 208)      # "Exposure / Process / Densitometry" block
LEGEND = (86, 278, 128, 338)     # R / G / B key
def inside(c, r):
    return r[0] <= c["x0"] and c["x1"] <= r[2] and r[1] <= c["top"] and c["bottom"] <= r[3]
bydash = {}
for c in p.curves:
    if not (cbox[0] <= c["x0"] and c["x1"] <= cbox[2] and cbox[1] <= c["top"] and c["bottom"] <= cbox[3]):
        continue
    if len(c["pts"]) < 2 or round(c.get("linewidth", 0), 2) != 1.0:
        continue
    if inside(c, NOTE) or inside(c, LEGEND):
        continue
    if c["x1"] - c["x0"] < 0.3:       # vertical tick or box edge, never a curve
        continue
    bydash.setdefault(str(c.get("dash")[0] if isinstance(c.get("dash"), tuple) else c.get("dash")), []).append(c)
xm = lambda c: lin(c, 107.6, -3.0, 281.8, 1.0)
ym = lambda c: lin(c, 174.2, 4.0, 347.2, 0.0)
ch = {}
for k, dk in DASH.items():
    cc = bydash.get(dk, [])
    assert cc, ("Velvia 100", k, list(bydash))
    polys = [a for a in chain_arr([flat(c, H) for c in cc], tol=10) if a.shape[0] > 5]
    a = np.vstack(sorted(polys, key=lambda a: a[0, 0]))
    ch[k] = dict(zip(("x", "d"), tidy(xm(a[:, 0]), ym(a[:, 1]))))
sens = sens_extract(p, (340, 174, 585, 346),
                    lambda c: lin(c, 347.1, 400.0, 521.8, 700.0),
                    lambda c: lin(c, 205.1, 1.0, 320.4, -1.0))
OUT["Velvia 100"] = dict(kind="pos", iso=100, ch=ch, sens=sens)
print("Velvia 100: ch", {k: len(v["x"]) for k, v in ch.items()},
      "sens", {k: len(v["wl"]) for k, v in sens.items()})

# ================= FUJICOLOR SUPERIA X-TRA 400 (AF3-177E family) ===================
# Black strokes, labelled Blue/Green/Red top to bottom on the sheet.
p = pdfplumber.open(U + "000b998e-films_superia-xtra400_datasheet_01.pdf").pages[5]
H = p.height
xm = lambda c: lin(c, 84.9, -4.0, 280.8, 0.5)
ym = lambda c: lin(c, 104.2, 4.0, 276.1, 0.0)
polys = [a for a in chain_arr(frags(p, (80, 100, 292, 280)), tol=10) if a.shape[0] > 20]
polys = sorted(polys, key=lambda a: a[:, 1].mean())
assert len(polys) >= 3, ("Superia", [a.shape[0] for a in polys])
ch = {k: dict(zip(("x", "d"), tidy(xm(a[:, 0]), ym(a[:, 1])))) for k, a in zip("BGR", polys[:3])}
sens = sens_extract(p, (325, 100, 545, 280),
                    lambda c: lin(c, 350.4, 400.0, 521.9, 700.0),
                    lambda c: lin(c, 161.9, 1.0, 219.1, 0.0))
OUT["Superia X-TRA 400"] = dict(kind="neg", iso=400, ch=ch, sens=sens)
print("Superia X-TRA 400: ch", {k: len(v["x"]) for k, v in ch.items()},
      "sens", {k: len(v["wl"]) for k, v in sens.items()})

json.dump(OUT, open("/home/claude/ds/new2.json", "w"))
print("wrote", len(OUT), "films")

"""Digitize a curve that a datasheet draws as a raster picture.

Ilford's sheets embed their plots as images, so the vector reader in ex.py
finds nothing. This locates the plot frame and its tick marks in the rendered
page, calibrates both axes from the ticks, then follows the ink column by
column."""
import subprocess, tempfile, os
import numpy as np
from PIL import Image

UPLOADS = "/mnt/user-data/uploads/"

def render(pdf, page, dpi=400):
    """Render one 1-based page of a PDF to a greyscale array."""
    with tempfile.TemporaryDirectory() as d:
        pre = os.path.join(d, "p")
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi),
                        "-png", "-gray", UPLOADS + pdf, pre], check=True)
        f = [x for x in os.listdir(d) if x.endswith(".png")][0]
        return np.array(Image.open(os.path.join(d, f)).convert("L"))

def _longest(mask):
    """Length of the longest contiguous True run."""
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        if cur > best: best = cur
    return best

def frame(dark, min_frac=0.85):
    """Plot frame as (left, right, top, bottom) pixel indices.

    Found by longest unbroken ink run, not by ink count: a block of text can
    hold more dark pixels in a row than the frame rule does, but never in one
    continuous line across the plot."""
    runs_c = np.array([_longest(dark[:, x]) for x in range(dark.shape[1])])
    hc = runs_c.max()
    cand_c = np.where(runs_c >= min_frac * hc)[0]
    L, R = int(cand_c.min()), int(cand_c.max())
    runs_r = np.array([_longest(dark[y, L:R + 1]) for y in range(dark.shape[0])])
    wr = runs_r.max()
    cand_r = np.where(runs_r >= min_frac * wr)[0]
    T, B = int(cand_r.min()), int(cand_r.max())
    return L, R, T, B

def _runs(hits, min_len=1):
    out = []; cur = None
    for i, v in enumerate(hits):
        if v and cur is None: cur = i
        if not v and cur is not None:
            if i - cur >= min_len: out.append(cur + (i - 1 - cur) // 2)
            cur = None
    if cur is not None and len(hits) - cur >= min_len: out.append(cur + (len(hits) - 1 - cur) // 2)
    return out

def ticks(dark, frame_box, axis, depth=18, thresh=8):
    """Tick-mark centres just outside the frame: 'x' below it, 'y' to its right."""
    L, R, T, B = frame_box
    if axis == "x":
        band = dark[B + 2:B + 2 + depth, :]
        # only inside the plot's own span: the axis caption sits beyond it
        return [c for c in _runs(band.sum(axis=0) >= thresh) if L - 5 <= c <= R + 5]
    band = dark[:, R + 2:R + 2 + depth]
    return [r for r in _runs(band.sum(axis=1) >= thresh) if T - 25 <= r <= B + 25]

def fit(px, vals):
    """Least-squares pixel -> value map over every tick, not just the ends."""
    px = np.asarray(px, float); vals = np.asarray(vals, float)
    assert len(px) == len(vals), (len(px), len(vals))
    b, a = np.polyfit(px, vals, 1)
    err = float(np.abs(a + b * px - vals).max())
    return (lambda c: a + b * np.asarray(c, float)), err

def column_runs(dark, frame_box, x, inset, max_frac):
    """Ink runs in one column, with frame rules and leader lines dropped.

    A run taller than max_frac of the plot is a rule or a pointer line, never
    a curve crossing a single column."""
    L, R, T, B = frame_box
    lo = T + inset + 1; hi = B - inset
    col = dark[lo:hi, x]
    limit = max_frac * (hi - lo)
    out = []; cur = None
    for i, v in enumerate(list(col) + [False]):
        if v and cur is None: cur = i
        if not v and cur is not None:
            if (i - cur) <= limit: out.append((lo + (cur + i - 1) / 2.0, i - cur))
            cur = None
    return out

def follow(dark, frame_box, inset=8, max_frac=0.55, pick="longest"):
    """Centre of the ink in each column.

    pick "longest" takes the tallest surviving run; "lowest" takes the one
    nearest the bottom of the plot, which isolates the lower of two curves
    drawn in the same frame."""
    L, R, T, B = frame_box
    xs, ys = [], []
    for x in range(L + inset + 1, R - inset):
        runs = column_runs(dark, frame_box, x, inset, max_frac)
        if not runs: continue
        y = (max(runs, key=lambda r: r[0])[0] if pick == "lowest"
             else max(runs, key=lambda r: r[1])[0])
        xs.append(x); ys.append(y)
    return np.array(xs, float), np.array(ys, float)

def follow_continuous(dark, frame_box, inset=8, max_frac=0.55, seed_px=None, jump=12.0, max_miss=25):
    """Track one curve through a plot that holds more than one.

    Seeded at a column where only the wanted curve is drawn, then walked out
    in both directions: each step takes the run nearest the last position, so
    a crossing does not hand the trace over to its neighbour."""
    L, R, T, B = frame_box
    lo, hi = L + inset + 1, R - inset
    seed = int(seed_px) if seed_px is not None else (lo + hi) // 2
    seed = min(max(seed, lo), hi - 1)
    got = {}
    for direction in (1, -1):
        last = None; miss = 0
        x = seed
        while lo <= x < hi:
            runs = column_runs(dark, frame_box, x, inset, max_frac)
            took = False
            if runs:
                if last is None:
                    y = max(runs, key=lambda r: r[1])[0]; took = True
                else:
                    y, d = min(((r[0], abs(r[0] - last)) for r in runs), key=lambda t: t[1])
                    took = d <= jump   # a gap is bridged, but never by relaxing what counts as the same curve
                if took:
                    last = y; got[x] = y
            miss = 0 if took else miss + 1
            if miss > max_miss: break
            x += direction
    xs = sorted(got)
    return np.array(xs, float), np.array([got[x] for x in xs], float)

def curve(pdf, page, crop, xvals, yvals, dpi=400, thresh=128, tick_depth=18,
          mode="longest", seed_nm=None, grid=False):
    """Digitize one plot. crop is (y0,y1,x0,x1) as fractions of the page.

    mode "continuous" tracks a single curve through a plot that draws more
    than one, seeded at `seed_nm` on the x axis where only it is present."""
    a = render(pdf, page, dpi)
    h, w = a.shape
    y0, y1, x0, x1 = crop
    sub = a[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]
    dark = sub < thresh
    fb = frame(dark)
    tx = ticks(dark, fb, "x", tick_depth); ty = ticks(dark, fb, "y", tick_depth)
    if grid: dark = degrid(dark, fb)
    assert len(tx) == len(xvals), ("x ticks", len(tx), tx, xvals)
    assert len(ty) == len(yvals), ("y ticks", len(ty), ty, yvals)
    fx, ex = fit(tx, xvals); fy, ey = fit(ty, yvals)
    if mode == "continuous":
        slope, intercept = np.polyfit(np.asarray(tx, float), np.asarray(xvals, float), 1)
        px, py = follow_continuous(dark, fb, seed_px=(seed_nm - intercept) / slope)
    else:
        px, py = follow(dark, fb, pick=mode)
    return dict(x=fx(px).tolist(), y=fy(py).tolist(), frame=fb,
                tick_err=(round(ex, 3), round(ey, 4)), n=len(px))

def despike(x, y, win=41, tol=0.08):
    """Drop points that jump away from the local trend.

    Where two curves share a frame, the unwanted one can dip across the one
    being read, and a pointer line can spike it; both are narrow against a
    rolling median of the curve itself."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    n = len(y); half = win // 2
    keep = np.ones(n, bool)
    for i in range(n):
        lo = max(0, i - half); hi = min(n, i + half + 1)
        if abs(y[i] - float(np.median(y[lo:hi]))) > tol: keep[i] = False
    return x[keep], y[keep]

def degrid(dark, frame_box, frac=0.45):
    """Erase the plot's internal grid before following a curve.

    A gridline runs the full width or height of the frame; the curve never
    does. Clearing them stops a flat part of the curve from being confused
    with the rule it is sitting on."""
    L, R, T, B = frame_box
    out = dark.copy()
    w = R - L; h = B - T
    for y in range(T, B + 1):
        if _longest(dark[y, L:R + 1]) >= frac * w: out[y, L:R + 1] = False
    for x in range(L, R + 1):
        if _longest(dark[T:B + 1, x]) >= frac * h: out[T:B + 1, x] = False
    return out

def monotonic_trim(x, y, drop=0.05):
    """Cut a characteristic curve where it stops rising.

    Density never falls as exposure grows, so the first real fall marks the
    end of the plotted line; past it the tracer is only seeing furniture."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    peak = -1e9; end = len(y)
    for i, v in enumerate(y):
        if v > peak: peak = v
        elif peak - v > drop: end = i; break
    return x[:end], y[:end]

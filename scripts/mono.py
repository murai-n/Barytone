"""Black-and-white rendering: scene -> filter -> film -> printing paper -> grey.

The colour path carries three dye layers through to a colour print. A
monochrome film has one silver image, so the chain collapses to a single
channel. What makes one stock differ from another is (a) how its spectral
sensitivity weighs colours into that one channel and (b) the shape of its
characteristic curve; the paper then supplies contrast (its grade), Dmax and
image tone.

A contrast filter belongs before the film, not after: it changes the spectrum
the emulsion integrates, which is exactly why it can darken a blue sky without
touching skin. That is why these are baked per film-and-filter rather than
applied afterwards.
"""
import json
import numpy as np
import os
import spec3 as M          # scene side only; the colour films are not needed here

WL = M.WL                      # 380..730 nm, 10 nm steps
GRAY = M.GRAY

FILMS = json.load(open(os.path.join(M.ROOT, "ds/mono_films.json")))
PAPERS = json.load(open(os.path.join(M.ROOT, "ds/mono_papers.json")))

def _isotonic(y):
    """Least-squares non-decreasing fit (pool adjacent violators)."""
    v = []; w = []
    for t in np.asarray(y, float):
        v.append(t); w.append(1.0)
        while len(v) > 1 and v[-2] > v[-1]:
            tot = w[-2] + w[-1]; v[-2] = (v[-2] * w[-2] + v[-1] * w[-1]) / tot; w[-2] = tot; v.pop(); w.pop()
    return np.repeat(v, np.asarray(w, int))

CURVE_STEP = 0.005             # log-exposure grid of a cleaned curve
CURVE_SMOOTH = 0.03            # Gaussian sigma in log exposure: below the traces' line width
STRAY = 0.02                   # density off the curve beyond which a traced point is not the curve

def _longest_rising(d, tol):
    """Indices of the longest subsequence where each point is at least the one
    before it minus tol (a longest-increasing-subsequence with slack)."""
    n = len(d); best = np.ones(n, int); prev = -np.ones(n, int)
    for j in range(1, n):
        ok = np.nonzero(d[:j] <= d[j] + tol)[0]
        if len(ok):
            i = ok[np.argmax(best[ok])]
            if best[i] + 1 > best[j]: best[j] = best[i] + 1; prev[j] = i
    j = int(np.argmax(best)); out = []
    while j >= 0: out.append(j); j = prev[j]
    return np.array(out[::-1])

def clean_curve(x0, d0):
    """A traced D-logE curve, cleaned: even grid, isotonic fit, light smoothing.

    Traces wobble and, on raster sheets, come in pixel-row steps. A running
    maximum turns every dip and step into a flat run, which prints as a band of
    one grey (MGIV RC had one at D 0.8, in the mid-tones). The isotonic fit is
    the closest rising curve to the trace; smoothing a rising curve with a
    positive kernel keeps it rising; a ramp of 1e-4 per logE keeps it strictly so."""
    x0 = np.asarray(x0, float); d0 = np.asarray(d0, float)
    # stray ink: a label or a frame line picked up instead of the curve sits off
    # the curve by more than the trace's own wobble. Keep the longest run of
    # points that rises within that wobble; the rest is not the curve.
    # (RC Cooltone had a label in its toe, MGIV RC a mark on its shoulder.)
    keep = _longest_rising(d0, STRAY)
    x0, d0 = x0[keep], d0[keep]
    x = np.arange(x0[0], x0[-1] + 1e-9, CURVE_STEP)
    d = _isotonic(np.interp(x, x0, d0))
    n = int(np.ceil(4 * CURVE_SMOOTH / CURVE_STEP))
    k = np.exp(-0.5 * (np.arange(-n, n + 1) * CURVE_STEP / CURVE_SMOOTH) ** 2); k /= k.sum()
    d = np.convolve(np.pad(d, n, mode="edge"), k, mode="valid")
    return x, d + 1e-4 * (x - x[0])

# Stretches of a traced paper curve that are not the curve, by log exposure on
# the trace's own axis. RC Cooltone's single-curve chart has a frame edge at
# its start and a label sitting across the toe (D 0.15), with the curve itself
# hidden behind the label up to D 1.0; left in, the label reads as a flat step
# that eats part of the ISO range and makes every grade far too hard.
STRAY_X = {"RC Cooltone": [(2.0, 2.225), (2.44, 2.62)]}
# MGIV FB's sheet draws its single curve broken (only verticals survive in the
# PDF), so its trace came off the six-grade family chart and stitches parts of
# different grades together: too hard at grade 00, shadows that never sink.
# The fibre papers take the curve shape of MGIV RC (same Multigrade IV
# emulsion) and keep their own ISO ranges per grade.
SHAPE_FROM = {"MGIV FB": "MGIV RC", "FB Warmtone": "MGIV RC"}

_SHAPES = {}
def paper_shape(paper):
    if paper not in _SHAPES:
        src = SHAPE_FROM.get(paper, paper)
        if src != paper: _SHAPES[paper] = paper_shape(src); return _SHAPES[paper]
        sh = PAPERS[paper]["shape"]; x = np.asarray(sh["x"], float); d = np.asarray(sh["d"], float)
        keep = np.ones(len(x), bool)
        for lo, hi in STRAY_X.get(paper, []): keep &= ~((x >= lo) & (x <= hi))
        _SHAPES[paper] = clean_curve(x[keep], d[keep])
    return _SHAPES[paper]

# Stretches of a traced film curve that are not the curve. FP4 Plus: past the
# end of its shoulder (D 1.87, x 4.14) the trace runs along the "2.0" tick of
# the density scale, which read as a jump to D 2.0 six stops over grey.
FILM_STRAY_X = {"FP4 Plus": [(4.15, 9.0)]}

_CH = {}
def film_curve(film):
    """The film's characteristic curve, cleaned the same way as the papers."""
    if film not in _CH:
        c = FILMS[film]["ch"]; x = np.asarray(c["x"], float); d = np.asarray(c["d"], float)
        keep = np.ones(len(x), bool)
        for lo, hi in FILM_STRAY_X.get(film, []): keep &= ~((x >= lo) & (x <= hi))
        _CH[film] = clean_curve(x[keep], d[keep])
    return _CH[film]

# ---------------------------------------------------------------- filters
def _edge(wl, cut, width, rising=True):
    """Smooth transmittance edge; `width` is the 10-90% span in nm."""
    t = 1.0 / (1.0 + np.exp(-(wl - cut) * (4.4 / max(width, 1e-6))))
    return t if rising else 1.0 - t

def _filters():
    """Idealised Wratten-equivalent transmittances.

    Measured curves for these are not in the film datasheets, so each is an
    ideal cut-on of the published nominal edge. The ranking and rough strength
    are right; the exact shoulder of a real gelatin filter is not reproduced."""
    f = {"none": np.ones_like(WL, float)}
    f["yellow"] = _edge(WL, 480.0, 40.0)                       # Wratten 8 / K2
    f["orange"] = _edge(WL, 545.0, 40.0)                       # Wratten 21
    f["red"] = _edge(WL, 595.0, 35.0)                          # Wratten 25
    f["green"] = _edge(WL, 490.0, 35.0) * _edge(WL, 600.0, 40.0, rising=False)  # Wratten 58
    return f

FILTERS = _filters()
FILTER_IDS = ["none", "yellow", "orange", "red", "green"]

# ---------------------------------------------------------------- film
def kernel(film, filt="none"):
    """One spectral weighting: the film's sensitivity seen through a filter."""
    s = FILMS[film]["sens"]
    k = np.where((WL >= s["wl"][0]) & (WL <= s["wl"][-1]),
                 10 ** np.interp(WL, s["wl"], s["logS"]), 0.0)
    k = k * M.D65S * FILTERS[filt]
    tot = k.sum()
    assert tot > 0, (film, filt)
    return k / tot

_WHITE = M.spectra(M.D65W)

def exposure(film, xyz, filt="none"):
    """Relative exposure on the film, 1.0 at a white that reflects everything."""
    k = kernel(film, filt)
    return np.maximum(M.spectra(xyz) @ k / float(np.ravel(_WHITE @ k)[0]), 1e-7)

def speed_point(film):
    """log exposure giving 0.1 above base density — the ISO speed criterion."""
    x, d = film_curve(film)
    return float(np.interp(d[0] + 0.10, d, x))

def neg_density(film, H):
    """Negative density for a relative exposure, placed at the box speed.

    Ilford prints its curves against relative log exposure and Kodak against
    absolute, so both are anchored through the film's own speed point instead
    of the printed axis."""
    x, d = film_curve(film)
    lo, hi = x[0], x[-1]
    # a metered mid-grey sits about 10x above the speed point on the curve
    pos = speed_point(film) + 1.0 + np.log10(np.asarray(H, float) / GRAY)
    return np.interp(np.clip(pos, lo, hi), x, d)

# ---------------------------------------------------------------- paper
def paper_curve(paper, grade):
    """Density against log printing exposure for one grade.

    The sheets publish one set of curves but a table of ISO ranges, so the
    traced shape is stretched along log exposure until its range matches the
    grade's published R. That keeps every grade tied to Ilford's own numbers."""
    p = PAPERS[paper]
    i = p["grades"].index(grade)
    R = p["iso_range"][i] / 100.0
    x, d = paper_shape(paper)
    dmin, dmax = float(d.min()), float(d.max())
    # ISO 6846 measures the range between these two densities
    lo = float(np.interp(dmin + 0.04, d, x))
    hi = float(np.interp(dmax - 0.10, d, x))
    span = max(hi - lo, 1e-6)
    xs = (x - lo) / span * R                 # 0 at the toe point, R at the shoulder
    return xs, d



def print_density(paper, grade, logE):
    xs, d = paper_curve(paper, grade)
    return np.interp(np.clip(logE, xs[0], xs[-1]), xs, d)

# ---------------------------------------------------------------- tone
# Paper colour, CIELAB a*, b* (D65): the base where there is no silver, the
# image where the silver is dense. Ilford states these only in words, quoted
# below; the numbers are stand-ins sized to read as the words say on screen.
TONE = {
    # "MULTIGRADE IV RC has a bright base tint. The image colour remains cool-to-neutral"
    "MGIV RC":     dict(base=(0.0, -1.5), image=(-0.3, -1.0)),
    # "a cool-of-neutral image tone on a cool white base"
    "RC Cooltone": dict(base=(0.0, -2.5), image=(-0.8, -4.0)),
    # fibre base, no colour stated: a plain fibre white, neutral image
    "MGIV FB":     dict(base=(0.0, 0.8), image=(0.0, 0.0)),
    # "a warm black image tone on a warm white base"
    "FB Warmtone": dict(base=(0.5, 4.0), image=(1.5, 7.0)),
}

def tone_xyz(Y, paper, Dp):
    """Print colour from its lightness and the paper's density.

    The base tint shows where the paper is bare; as silver builds up the colour
    turns to the image tone. The mix follows how much light the silver itself
    absorbs (1 - 10^-(D - Dmin)): half way at D 0.3 above the base, 0.8 at a
    printed mid-grey, all image tone in the blacks."""
    t = TONE[paper]; dmin = float(paper_curve(paper, "2")[1][0])
    s = 1.0 - 10.0 ** (-np.clip(np.asarray(Dp, float) - dmin, 0, None))
    a = t["base"][0] * (1 - s) + t["image"][0] * s
    b = t["base"][1] * (1 - s) + t["image"][1] * s
    Y = np.clip(np.asarray(Y, float), 0, None)
    fy = np.where(Y > 216 / 24389, np.cbrt(Y), (24389 / 27 * Y + 16) / 116)
    fx = fy + a / 500.0; fz = fy - b / 200.0
    inv = lambda f: np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) / (24389 / 27))
    W = M.D65W
    return np.stack([inv(fx) * W[0], Y, inv(fz) * W[2]], axis=-1)

# ---------------------------------------------------------------- full chain
VIEW_FLARE = 0.003             # print surface reflection under viewing light
MID_L = 50.0                   # a metered mid-grey prints at this L*

def render(film, xyz, paper="MGIV RC", grade="2", filt="none", view_flare=VIEW_FLARE):
    """Scene XYZ (D65) -> print XYZ. The only colour left is the paper's tone."""
    H = exposure(film, xyz, filt)
    Dn = neg_density(film, H)
    # the enlarger is set from the negative, so densities are read against the
    # density a mid-grey itself produces
    ref = float(np.ravel(neg_density(film, np.array([GRAY])))[0])
    logE = (ref - Dn) + _mid_offset(paper, grade)
    Dp = print_density(paper, grade, logE)
    Y = 10.0 ** (-Dp)
    Y = (Y + view_flare) / (1.0 + view_flare)
    return tone_xyz(Y, paper, Dp)

def _mid_offset(paper, grade):
    """Print exposure: the log exposure at which a metered mid-grey lands.

    Set so mid-grey prints at L* 50 (with the surface reflection), as a test
    strip would be judged. Centring the negative on the grade's ISO range
    instead (R/2) printed mid-grey at L* 28-37, a stop dark, and left the
    whites of the soft grades grey (L* 69 at grade 00). With this anchor the
    whites of grade 2 sit at L* 94-96, still short of paper white."""
    xs, d = paper_curve(paper, grade)
    Y = ((MID_L + 16) / 116) ** 3
    Dt = -np.log10(Y * (1 + VIEW_FLARE) - VIEW_FLARE)
    assert d[0] < Dt < d[-1], (paper, grade, Dt)
    return float(np.interp(Dt, d, xs))

# ---------------------------------------------------------------- ICC / style split
# The kit splits the chain where the darkroom does: the ICC is the negative
# (film + filter), a style is the print (paper + grade). The ICC writes the
# negative's density relative to mid-grey into the value Capture One's curves
# work on (linear light ** 1/ENC), so a paper-grade style is an ordinary curve
# of that value and every paper works on every film.
ENC = 1.8                      # Capture One curve domain, as in styles.py
NEG_SPAN = 2.4                 # density across the whole curve domain 0..1
V_MID = GRAY ** (1.0 / ENC)    # mid-grey keeps its place (L* 50)
FILTER_LABEL = {"none": "フィルターなし", "yellow": "黄（Y2 相当）", "orange": "橙（O2 相当）",
                "red": "赤（R2 相当）", "green": "緑（G 相当）"}

def neg_rel(film, xyz, filt="none"):
    """Negative density relative to the density of a metered mid-grey.
    Positive = thinner than mid-grey (a shadow)."""
    H = exposure(film, xyz, filt)
    ref = float(np.ravel(neg_density(film, np.array([GRAY])))[0])
    return ref - neg_density(film, H)

def icc_value(u):
    """Relative negative density -> curve-domain value written by the ICC."""
    return np.clip(V_MID - np.asarray(u, float) / NEG_SPAN, 0.0, 1.0)

def icc_xyz(film, xyz, filt="none"):
    """Scene XYZ (D65) -> what the film ICC hands to Capture One: a neutral grey."""
    Y = icc_value(neg_rel(film, xyz, filt)) ** ENC
    return np.asarray(Y, float)[..., None] * M.D65W

def print_from_value(v, paper="MGIV RC", grade="2", view_flare=VIEW_FLARE):
    """The paper-grade style's job: ICC value -> print XYZ. Inverts icc_value
    exactly, so icc_xyz followed by this equals render()."""
    u = (V_MID - np.asarray(v, float)) * NEG_SPAN
    Dp = print_density(paper, grade, u + _mid_offset(paper, grade))
    Y = (10.0 ** (-Dp) + view_flare) / (1.0 + view_flare)
    return tone_xyz(Y, paper, Dp)

# ids used in file names: maker letter + short name, like the colour films
ALIAS = {"HP5 Plus": "IHP5", "FP4 Plus": "IFP4", "Delta 100": "ID100", "Delta 400": "ID400",
         "Pan F Plus": "IPANF", "SFX 200": "ISFX200", "T-Max 100": "KTM100", "T-Max 400": "KTM400",
         "Tri-X 400": "KTX400"}
FILTER_ID = {"none": "base", "yellow": "Y", "orange": "O", "red": "R", "green": "G"}

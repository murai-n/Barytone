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
import model3 as M

WL = M.WL                      # 380..730 nm, 10 nm steps
GRAY = M.GRAY

FILMS = json.load(open("/home/claude/ds/mono_films.json"))
PAPERS = json.load(open("/home/claude/ds/mono_papers.json"))

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
    c = FILMS[film]["ch"]
    x = np.asarray(c["x"], float); d = np.asarray(c["d"], float)
    return float(np.interp(min(d) + 0.10, d, x))

def neg_density(film, H):
    """Negative density for a relative exposure, placed at the box speed.

    Ilford prints its curves against relative log exposure and Kodak against
    absolute, so both are anchored through the film's own speed point instead
    of the printed axis."""
    c = FILMS[film]["ch"]
    x = np.asarray(c["x"], float); d = np.asarray(c["d"], float)
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
    x = np.asarray(p["shape"]["x"], float); d = np.asarray(p["shape"]["d"], float)
    dmin, dmax = float(d.min()), float(d.max())
    # ISO 6846 measures the range between these two densities
    lo = float(np.interp(dmin + 0.04, d, x))
    hi = float(np.interp(dmax - 0.10, d, x))
    span = max(hi - lo, 1e-6)
    xs = (x - lo) / span * R                 # 0 at the toe point, R at the shoulder
    d = np.maximum.accumulate(d)             # the traced line wobbles; density only rises
    return xs, d

def print_density(paper, grade, logE):
    xs, d = paper_curve(paper, grade)
    return np.interp(np.clip(logE, xs[0], xs[-1]), xs, d)

# ---------------------------------------------------------------- tone
TONE_XY = {"neutral": (0.0, 0.0), "warm": (0.016, 0.010), "cool": (-0.012, -0.006)}

def tone_xyz(Y, tone):
    """Paper image tone as a small chromaticity offset from D65.

    Ilford describes warm and cool papers in words, not numbers, so the shift
    is a modest documented stand-in, strongest in the mid-tones where image
    silver dominates and vanishing at paper white."""
    dx, dy = TONE_XY[tone]
    w = 4.0 * np.clip(Y, 0, 1) * (1.0 - np.clip(Y, 0, 1))      # peaks at mid grey
    x0, y0 = 0.3127, 0.3290
    xx = x0 + dx * w; yy = y0 + dy * w
    X = Y * xx / yy; Z = Y * (1 - xx - yy) / yy
    return np.stack([X, Y, Z], axis=-1)

# ---------------------------------------------------------------- full chain
def render(film, xyz, paper="MGIV RC", grade="2", filt="none", view_flare=0.003):
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
    return tone_xyz(Y, PAPERS[paper]["tone"])

def _mid_offset(paper, grade):
    """Centre the negative's density range on the grade's own range.

    This is how a grade is chosen in the darkroom: pick the paper whose ISO
    range matches the negative, which lands mid-grey mid-scale and keeps both
    ends inside the paper rather than blocking up or blowing out."""
    i = PAPERS[paper]["grades"].index(grade)
    return PAPERS[paper]["iso_range"][i] / 100.0 / 2.0

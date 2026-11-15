"""Black-and-white paper styles: 4 papers x grades 00-5 = 28 .costyle files.

The film ICC hands Capture One the negative (mono.icc_xyz); each style here is
the print: one layer whose R, G, B curves are mono.print_from_value() for one
paper and grade. They are camera-independent and work on every mono film.

Curve points. A hard grade is steep in the curve domain (slope 12 at grade 5)
and the paper saturates at both ends, so fixed 16 points cannot follow it.
Points are placed adaptively, at most 16 (Capture One reads no more than 16
points per curve: every style it accepts uses 16, and the earlier 20-40 point
B&W curves had no effect at all), until both a straight-line and a natural
cubic reading of them are within 0.6/255 of the target. Capture One's exact
interpolator is not published, so both are held to the tolerance. Before
fitting, the target is rounded with a Gaussian (sigma 0.004) at the two clip
corners; a spline through a hard corner rings. Any drop of the cubic below its
own running maximum is held under 0.3/255 by adding points where it happens.

    python3 scripts/styles_mono.py [OUTDIR]      (default /home/claude/presets)"""
import os, sys, uuid, numpy as np
from scipy.interpolate import CubicSpline
from scipy.ndimage import gaussian_filter1d
import mono, spec3 as S

PAPER_ID = {"MGIV RC": "IMR", "RC Cooltone": "ICT", "MGIV FB": "IMF", "FB Warmtone": "IFW"}
FOLDER = "3 Paper/B&W"
V = np.linspace(0, 1, 2001); DV = V[1] - V[0]
TOL = 0.6 / 255; MAXBACK = 0.3 / 255; MAXBACK_16 = 0.5 / 255; NMAX = 16; ROUND = 0.004   # Capture One reads at most 16 points per curve (every working style uses 16)
CH = ("GradationCurveRed", "GradationCurveGreen", "GradationCurveBlue")

def target(paper, grade):
    """Curve-domain output per channel, on the V grid (exact, before rounding)."""
    lin = np.clip(mono.print_from_value(V, paper, grade) @ S.M_XYZ_SRGB.T, 0, 1)
    return lin ** (1.0 / mono.ENC)

def _back(cs): return float((np.maximum.accumulate(cs) - cs).max())

def _fit_once(T, rnd):
    T = gaussian_filter1d(T, rnd / DV, mode="nearest")
    idx = [0, len(V) - 1]
    while len(idx) < NMAX:
        xs = V[idx]; cs = CubicSpline(xs, T[idx], bc_type="natural")(V)
        e = np.maximum(np.abs(np.interp(V, xs, T[idx]) - T), np.abs(cs - T))
        if e.max() < TOL and _back(cs) < MAXBACK: break
        n = int(np.argmax(np.maximum.accumulate(cs) - cs)) if e.max() < TOL else int(np.argmax(e))
        free = [k for k in (n, n + 1, n - 1, n + 2, n - 2) if 0 <= k < len(V) and k not in idx]
        if not free: break
        idx = sorted(idx + [free[0]])
    cs = CubicSpline(V[idx], T[idx], bc_type="natural")(V)
    return idx, T, _back(cs)

ROUNDS = (0.004, 0.006, 0.009, 0.013, 0.018, 0.025, 0.035)

def fit(T):
    """Indices into V of the control points for one channel (at most NMAX).

    With only 16 points a cubic through a hard clip corner rings; the corner is
    rounded a little more each try until the cubic stops running backwards."""
    for rnd in ROUNDS:
        idx, Ts, back = _fit_once(T, rnd)
        if back < MAXBACK_16: break
    return idx, Ts

def curves(paper, grade):
    """{key: [(x, y), ...]} for one paper and grade."""
    T = target(paper, grade); out = {}
    neutral = not any(any(v) for v in mono.TONE[paper].values())
    for c, k in enumerate(CH):
        if neutral and c != 1: continue
        idx, Ts = fit(T[:, c])
        out[k] = [(float(V[i]), float(np.clip(Ts[i], 0, 1))) for i in idx]
    if neutral: out[CH[0]] = out[CH[2]] = out[CH[1]]       # a neutral paper keeps grey grey
    return out

def curve_str(pts): return ";".join(f"{x:.6f},{y:.6f}" for x, y in pts)

def style_xml(name, cv):
    E = lambda k, v: f'\t\t\t<E K="{k}" V="{v}" />'
    layer = "\n".join(['\t\t<LD>', '\t\t\t<LA>', E("Clarity", "0"), E("DehazeAmount", "0"), E("Enabled", "1"),
        E("GradationCurveBlue", curve_str(cv[CH[2]])), E("GradationCurveGreen", curve_str(cv[CH[1]])),
        E("GradationCurveRed", curve_str(cv[CH[0]])), E("Name", name), E("Opacity", "100"), '\t\t\t</LA>',
        '\t\t\t<MD>', '\t\t\t\t<E K="Density" V="1" />', '\t\t\t\t<E K="MaskType" V="1" />', '\t\t\t</MD>', '\t\t</LD>'])
    # SL carries no base characteristics, so applying it never touches the film ICC (as the colour papers)
    return "\n".join(['<?xml version="1.0"?>', '<SL Engine="1300">', f'\t<E K="Name" V="{name}" />',
        '\t<E K="StyleSource" V="Styles" />', f'\t<E K="UUID" V="{str(uuid.uuid4()).upper()}" />', '</SL>',
        '<LDS>', layer, '</LDS>', ''])

def style_name(paper, grade): return f"Paper {PAPER_ID[paper]} grade {grade}"

def apply(cv, v, cubic=True):
    """What the style does to an ICC value v (curve domain), per channel -> linear sRGB."""
    o = []
    for k in CH:
        x, y = np.array(cv[k]).T
        o.append(CubicSpline(x, y, bc_type="natural")(v) if cubic else np.interp(v, x, y))
    return np.clip(np.stack(o, -1), 0, 1) ** mono.ENC

def main(out="/home/claude/presets"):
    d = os.path.join(out, FOLDER); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    # check: every film, scene colours through ICC + style vs the whole chain
    rng = np.random.default_rng(5)
    X = colour_pts = rng.uniform(0, 1, (300, 3)) ** 2.2 @ S.M_SRGB_XYZ.T
    lab = lambda XYZ: __import__("colour").XYZ_to_Lab(np.clip(XYZ, 1e-7, None), __import__("colour").XYZ_to_xy(S.D65W))
    rows = []
    for p in mono.PAPERS:
        for g in mono.PAPERS[p]["grades"]:
            cv = curves(p, g); name = style_name(p, g)
            open(os.path.join(d, name + ".costyle"), "w").write(style_xml(name, cv))
            worst = 0.0
            for f in mono.FILMS:
                v = mono.icc_xyz(f, X)[:, 1] ** (1 / mono.ENC)
                ref = lab(mono.render(f, X, p, g))
                for cub in (True, False):
                    got = lab(apply(cv, v, cub) @ S.M_SRGB_XYZ.T)
                    worst = max(worst, float(np.sqrt(((got - ref) ** 2).sum(-1)).max()))
            rows.append((name, max(len(c) for c in cv.values()), worst))
    for n, k, w in rows: print(f"{n:24s} {k:2d} points   ICC+style vs model: max dE76 {w:.2f}")
    print(len(rows), "styles in", d)
    return rows

if __name__ == "__main__":
    main(*sys.argv[1:])

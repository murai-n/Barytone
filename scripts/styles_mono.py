"""Black-and-white paper styles: 4 papers x grades 00-5 = 28 .costyle files.

Capture One applies style curves *before* the ICC. The film ICC writes the
deepened MGIV RC grade-3 print (mono.icc_xyz); each style here maps encoded
camera/scene values so that, after that ICC, neutrals land on the chosen
paper and grade. The curves are camera-independent and work on every mono film
(built from the mean of all stocks' neutral responses).

Curve points. Capture One reads at most 16 points per curve. Points are placed
adaptively until both a straight-line and a natural cubic reading of them are
within 0.6/255 of the target. Capture One's exact interpolator is not
published, so both are held to the tolerance. Slope is capped at CAP (the kit
ceiling that keeps sharpening halos in check). Before fitting, the target is
rounded with a Gaussian at hard corners; a spline through a hard corner rings.

    python3 scripts/styles_mono.py [OUTDIR]      (default kit/)"""
import os, sys, uuid, numpy as np
from scipy.interpolate import CubicSpline
from scipy.ndimage import gaussian_filter1d
import mono, spec3 as S

PAPER_ID = {"MGIV RC": "IMR", "RC Cooltone": "ICT", "MGIV FB": "IMF", "FB Warmtone": "IFW"}
FOLDER = "3 Paper/B&W"
V = np.linspace(0, 1, 2001); DV = V[1] - V[0]
TOL = 0.6 / 255; MAXBACK = 0.3 / 255; MAXBACK_16 = 0.5 / 255; NMAX = 16; ROUND = 0.004
CAP = 2.4                      # max |dS/dz| in the curve domain (matches the prior kit ceiling)
CH = ("GradationCurveRed", "GradationCurveGreen", "GradationCurveBlue")

def _cap_slope(S, mid=None):
    """Limit the slope of S outwards from mid-grey to CAP."""
    S = np.array(S, float)
    if mid is None: mid = float(0.18 ** (1 / mono.ENC))
    i0 = int(np.argmin(np.abs(V - mid)))
    out = S.copy()
    for i in range(i0 + 1, len(V)):
        out[i] = min(out[i], out[i - 1] + CAP * DV)
    for i in range(i0 - 1, -1, -1):
        out[i] = max(out[i], out[i + 1] - CAP * DV)
    return np.clip(out, 0, 1)

def target(paper, grade):
    """Curve-first style output on the V grid (encoded scene -> encoded ICC input).

    For each film, A(z) is the ICC's encoded response to a neutral of encoded
    value z, and W(z) is the wanted encoded print on this paper and grade.
    The style S satisfies A(S(z)) = W(z) on the mean of all films, so after
    the ICC the neutrals match the kit print. Grade 3 on MGIV RC is identity."""
    As, Ws = [], []
    for f in mono.FILMS:
        xyz = (V ** mono.ENC)[:, None] * S.D65W
        As.append(mono.icc_xyz(f, xyz)[:, 1] ** (1 / mono.ENC))
        Ws.append(np.clip(mono.render(f, xyz, paper, grade)[:, 1], 0, 1) ** (1 / mono.ENC))
    A = np.mean(As, 0); W = np.mean(Ws, 0)
    A = np.maximum.accumulate(np.maximum(A, 0))
    # keep A strictly increasing for a stable inverse
    for i in range(1, len(A)):
        if A[i] <= A[i - 1]: A[i] = A[i - 1] + 1e-9
    sty = np.interp(W, A, V)
    if paper == mono.ANCHOR_PAPER and grade == mono.ANCHOR_GRADE:
        sty = V.copy()
    sty = _cap_slope(np.clip(sty, 0, 1))
    return np.repeat(sty[:, None], 3, 1)

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
    """Indices into V of the control points for one channel (at most NMAX)."""
    for rnd in ROUNDS:
        idx, Ts, back = _fit_once(T, rnd)
        if back < MAXBACK_16: break
    return idx, Ts

def curves(paper, grade):
    """{key: [(x, y), ...]} for one paper and grade."""
    if paper == mono.ANCHOR_PAPER and grade == mono.ANCHOR_GRADE:
        pts = [(0.0, 0.0), (1.0, 1.0)]          # ICC already is this print
        return {k: pts for k in CH}
    T = target(paper, grade); out = {}
    # lightness only; Capture One drops colour on a grey-only ICC
    idx, Ts = fit(T[:, 1])
    pts = [(float(V[i]), float(np.clip(Ts[i], 0, 1))) for i in idx]
    for k in CH: out[k] = pts
    return out

def curve_str(pts): return ";".join(f"{x:.6f},{y:.6f}" for x, y in pts)

def style_xml(name, cv):
    E = lambda k, v: f'\t\t\t<E K="{k}" V="{v}" />'
    layer = "\n".join(['\t\t<LD>', '\t\t\t<LA>', E("Clarity", "0"), E("DehazeAmount", "0"), E("Enabled", "1"),
        E("GradationCurveBlue", curve_str(cv[CH[2]])), E("GradationCurveGreen", curve_str(cv[CH[1]])),
        E("GradationCurveRed", curve_str(cv[CH[0]])), E("Name", name), E("Opacity", "100"), '\t\t\t</LA>',
        '\t\t\t<MD>', '\t\t\t\t<E K="Density" V="1" />', '\t\t\t\t<E K="MaskType" V="1" />', '\t\t\t</MD>', '\t\t</LD>'])
    return "\n".join(['<?xml version="1.0"?>', '<SL Engine="1300">', f'\t<E K="Name" V="{name}" />',
        '\t<E K="StyleSource" V="Styles" />', f'\t<E K="UUID" V="{str(uuid.uuid4()).upper()}" />', '</SL>',
        '<LDS>', layer, '</LDS>', ''])

def style_name(paper, grade): return f"Paper {PAPER_ID[paper]} grade {grade}"

def apply(cv, v, cubic=True):
    """What the style does to an encoded value v (per channel) -> encoded out."""
    o = []
    for k in CH:
        x, y = np.array(cv[k]).T
        o.append(CubicSpline(x, y, bc_type="natural")(v) if cubic else np.interp(v, x, y))
    return np.clip(np.stack(o, -1), 0, 1)

def main(out=None):
    if out is None: out = os.path.join(S.ROOT, "kit")
    d = os.path.join(out, FOLDER); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".costyle"): os.remove(os.path.join(d, f))
    # check: curve-first (style then ICC) vs the whole-chain model, neutrals
    # Z = linear scene Y; encoded input to the style is Z^(1/ENC)
    Z = np.array([1e-6, 0.05, 0.1, 0.18, 0.3, 0.5, 0.7, 0.9, 1.0])
    lab = lambda XYZ: __import__("colour").XYZ_to_Lab(np.clip(XYZ, 1e-7, None), __import__("colour").XYZ_to_xy(S.D65W))
    rows = []
    for p in mono.PAPERS:
        for g in mono.PAPERS[p]["grades"]:
            cv = curves(p, g); name = style_name(p, g)
            open(os.path.join(d, name + ".costyle"), "w").write(style_xml(name, cv))
            worst = 0.0
            for f in mono.FILMS:
                for s in Z:
                    xyz = np.array([[s * S.D65W[0], s, s * S.D65W[2]]])
                    want = lab(mono.render(f, xyz, p, g))[0, 0]
                    for cub in (True, False):
                        z_in = s ** (1 / mono.ENC)
                        z2 = float(apply(cv, np.array([z_in]), cub)[0, 1])
                        s2 = max(z2, 0.0) ** mono.ENC
                        xyz2 = np.array([[s2 * S.D65W[0], s2, s2 * S.D65W[2]]])
                        got = lab(mono.icc_xyz(f, xyz2))[0, 0]
                        worst = max(worst, abs(got - want))
            rows.append((name, max(len(c) for c in cv.values()), worst))
    for n, k, w in rows: print(f"{n:24s} {k:2d} points   style->ICC vs model: max |dL*| {w:.2f}")
    print(len(rows), "styles in", d)
    return rows

if __name__ == "__main__":
    main(*sys.argv[1:])

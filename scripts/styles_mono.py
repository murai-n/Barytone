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
    """Curve-domain output, the print's lightness only (grey), on the V grid.

    The paper's colour is not in the curves: Capture One treats an image whose
    ICC gives only greys as monochrome and drops any colour a curve adds, so
    the colour goes into the B&W tool's split toning instead (split_tone)."""
    Y = np.clip(mono.print_from_value(V, paper, grade)[:, 1], 0, 1)
    return np.repeat((Y ** (1.0 / mono.ENC))[:, None], 3, 1)

# Split toning (Capture One's B&W tool): shadows take the paper's image tone,
# highlights its base tint. Hue and saturation are those of the target colour in
# sRGB (HSV) at L* 30 and 88; SAT_GAIN scales Capture One's saturation to taste
# (its scale against real chroma is not published; tune it on screen).
SAT_GAIN = 1.0
def split_tone(paper):
    import colorsys, colour
    t = mono.TONE[paper]; xy = colour.XYZ_to_xy(S.D65W)
    def hs(L, ab):
        rgb = np.clip(colour.XYZ_to_sRGB(colour.Lab_to_XYZ([L, ab[0], ab[1]], xy)), 0, 1)
        h, sat, _ = colorsys.rgb_to_hsv(*rgb)
        return (round(h * 360, 1), round(min(sat * 100 * SAT_GAIN, 100), 1)) if sat > 1e-3 else (0.0, 0.0)
    return dict(dark=hs(30, t["image"]), light=hs(88, t["base"]))

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
    neutral = True        # curves carry lightness only; colour is split toning
    for c, k in enumerate(CH):
        if neutral and c != 1: continue
        idx, Ts = fit(T[:, c])
        out[k] = [(float(V[i]), float(np.clip(Ts[i], 0, 1))) for i in idx]
    if neutral: out[CH[0]] = out[CH[2]] = out[CH[1]]       # a neutral paper keeps grey grey
    return out

def curve_str(pts): return ";".join(f"{x:.6f},{y:.6f}" for x, y in pts)

def style_xml(name, cv, st=None):
    E = lambda k, v: f'\t\t\t<E K="{k}" V="{v}" />'
    layer = "\n".join(['\t\t<LD>', '\t\t\t<LA>', E("Clarity", "0"), E("DehazeAmount", "0"), E("Enabled", "1"),
        E("GradationCurveBlue", curve_str(cv[CH[2]])), E("GradationCurveGreen", curve_str(cv[CH[1]])),
        E("GradationCurveRed", curve_str(cv[CH[0]])), E("Name", name), E("Opacity", "100"), '\t\t\t</LA>',
        '\t\t\t<MD>', '\t\t\t\t<E K="Density" V="1" />', '\t\t\t\t<E K="MaskType" V="1" />', '\t\t\t</MD>', '\t\t</LD>'])
    # SL carries no base characteristics, so applying it never touches the film ICC (as the colour papers)
    bw = [] if st is None else [f'\t<E K="BwDarkHue" V="{st["dark"][0]}" />', f'\t<E K="BwDarkSaturation" V="{st["dark"][1]}" />',
        '\t<E K="BwEnabled" V="1" />', f'\t<E K="BwLightHue" V="{st["light"][0]}" />', f'\t<E K="BwLightSaturation" V="{st["light"][1]}" />']
    return "\n".join(['<?xml version="1.0"?>', '<SL Engine="1300">'] + bw + [f'\t<E K="Name" V="{name}" />',
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
            open(os.path.join(d, name + ".costyle"), "w").write(style_xml(name, cv))   # pure black: colour is a Toning style
            worst = 0.0
            for f in mono.FILMS:
                v = mono.icc_xyz(f, X)[:, 1] ** (1 / mono.ENC)
                ref = lab(mono.render(f, X, p, g)); ref[:, 1:] = 0        # lightness only: colour is split toning
                for cub in (True, False):
                    got = lab(apply(cv, v, cub) @ S.M_SRGB_XYZ.T); got[:, 1:] = 0
                    worst = max(worst, float(np.sqrt(((got - ref) ** 2).sum(-1)).max()))
            rows.append((name, max(len(c) for c in cv.values()), worst))
    for n, k, w in rows: print(f"{n:24s} {k:2d} points   ICC+style vs model: max dL* {w:.2f}")
    print(len(rows), "styles in", d)
    write_toning(out); write_detail(out)
    return rows

# Toning: the paper's colour on its own, so a Paper style alone gives a pure black.
# Capture One drops colour that layers add to a monochrome image, so toning cannot be
# a layer with an opacity; it is the B&W tool's split toning, in strength steps.
TONE_FOLDER = "3 Paper/B&W Toning"; TONE_STEPS = (25, 50, 100)
def _sl(name, rows):
    return "\n".join(['<?xml version="1.0"?>', '<SL Engine="1300">'] + rows + [f'\t<E K="Name" V="{name}" />',
        '\t<E K="StyleSource" V="Styles" />', f'\t<E K="UUID" V="{str(uuid.uuid4()).upper()}" />', '</SL>', ''])
def write_toning(out):
    d = os.path.join(out, TONE_FOLDER); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    n = 0
    for p in mono.PAPERS:
        st = split_tone(p)
        if st["dark"][1] == 0 and st["light"][1] < 2: continue          # a neutral paper has nothing to tone
        for k in TONE_STEPS:
            name = f"Tone {PAPER_ID[p]} {k}%"; f = k / 100.0
            open(os.path.join(d, name + ".costyle"), "w").write(_sl(name, [
                f'\t<E K="BwDarkHue" V="{st["dark"][0]}" />', f'\t<E K="BwDarkSaturation" V="{round(st["dark"][1] * f, 1)}" />',
                '\t<E K="BwEnabled" V="1" />', f'\t<E K="BwLightHue" V="{st["light"][0]}" />',
                f'\t<E K="BwLightSaturation" V="{round(st["light"][1] * f, 1)}" />'])); n += 1
    open(os.path.join(d, "Tone off.costyle"), "w").write(_sl("Tone off", [
        '\t<E K="BwDarkSaturation" V="0" />', '\t<E K="BwLightSaturation" V="0" />'])); n += 1
    print(n, "toning styles in", d)

# Detail: sharpening off. Capture One sharpens before the paper curves; film has no
# digital sharpening. Only the amount is set; radius, threshold and halo stay the user's.
DETAIL_FOLDER = "5 Detail"
def write_detail(out):
    d = os.path.join(out, DETAIL_FOLDER); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "Sharpening off.costyle"), "w").write(_sl("Sharpening off", ['\t<E K="UsmAmount" V="0" />']))
    print("1 detail style in", d)

if __name__ == "__main__":
    main(*sys.argv[1:])

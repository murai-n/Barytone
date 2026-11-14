"""Film model v3
 - scene colour -> spectral reflectance by Jakob & Hanika 2019 (Rec.2020 gamut table)
 - reversal films: Status-A densities unmixed into C/M/Y dye amounts, slide rendered
   spectrally (dye transmittance x D50 viewing light -> CIE XYZ)
 - negative films: as v2 (ideal print), but layer exposures from the new spectra
All colour I/O is CIE XYZ relative to D65 white (Y=1)."""
import sys, json, numpy as np, colour, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/claude/scripts")
import model, model2
from model2 import ALL, KIND, ISO

GRAY = 0.18
shape = colour.SpectralShape(380, 730, 10)
WL = shape.wavelengths
_al = lambda sd: sd.copy().align(shape).values
CMF = colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(shape).values
D65S = _al(colour.SDS_ILLUMINANTS["D65"]); D50S = _al(colour.SDS_ILLUMINANTS["D50"])
SRGB = colour.RGB_COLOURSPACES["sRGB"]
M_SRGB_XYZ = SRGB.matrix_RGB_to_XYZ; M_XYZ_SRGB = SRGB.matrix_XYZ_to_RGB
D65W = colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"])
DY = json.load(open("/home/claude/m3/dyes.json"))
CAST = {k: np.array(v) for k, v in json.load(open("/home/claude/m3/tungsten_cast.json")).items()}  # tungsten films: uncorrected-daylight blue, magnitude from the film's own spectral sensitivity
def _target_white(film):
    g = CAST.get(film)
    if g is None: return D65W
    W = (g @ M_SRGB_XYZ.T); return W / W[1]   # neutral seen through the uncorrected tungsten balance (a blue white)
BRAD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
def cat(src, dst):
    s = BRAD @ src; d = BRAD @ dst; return np.linalg.inv(BRAD) @ np.diag(d / s) @ BRAD

# ---------- spectral upsampling: Otsu et al. 2018, with soft cluster boundaries ----------
OT = json.load(open("/home/claude/m3/otsu2018.json"))
OB = np.array(OT["basis"]); OM = np.array(OT["means"]); OS = np.array(OT["selector"])
_W = D65S[:, None] * CMF / (D65S @ CMF[:, 1])            # (36,3) reflectance -> XYZ
OMINV = np.array([np.linalg.inv(OB[c] @ _W) for c in range(len(OB))])   # XYZ = mu + w @ (B@W)
OXMU = OM @ _W
BLEND = 0.02
def leaf_weights(xy):
    n = len(xy); w = np.zeros((n, len(OB)))
    def walk(row, acc):
        origin, direction, lo, hi = OS[row]; t = np.clip((xy[:, int(direction)] - origin) / BLEND + 0.5, 0, 1)
        for idx, wt in ((int(lo), acc * (1 - t)), (int(hi), acc * t)):
            if idx < 0: walk(-idx, wt)
            else: w[:, idx] += wt
    walk(0, np.ones(n)); return w
M_XYZ_2020 = np.linalg.inv(colour.RGB_COLOURSPACES["ITU-R BT.2020"].matrix_RGB_to_XYZ)
NORM_MAX = 0.35
def spectra(xyz):
    """XYZ (D65, Y rel.) -> spectra (n,36).  Otsu 2018, blended across clusters, and made
    homogeneous in exposure: each colour is upsampled at a fixed level (max Rec.2020 channel
    = NORM_MAX) and scaled back, so changing exposure never changes a colour's spectral shape."""
    xyz = np.atleast_2d(np.asarray(xyz, float))
    sc = np.maximum((xyz @ M_XYZ_2020.T).max(1), 1e-9) / NORM_MAX
    return _spectra_raw(xyz / sc[:, None]) * sc[:, None]
def _spectra_raw(xyz):
    s = xyz.sum(1, keepdims=True)
    xy = np.where(s > 1e-9, xyz[:, :2] / np.maximum(s, 1e-9), np.array([[0.3127, 0.3290]]))
    lw = leaf_weights(xy); out = np.zeros((len(xyz), len(WL)))
    for c in range(len(OB)):
        sel = lw[:, c] > 0
        if not sel.any(): continue
        w = (xyz[sel] - OXMU[c]) @ OMINV[c]
        out[sel] += lw[sel, c:c + 1] * (w @ OB[c] + OM[c])
    return np.maximum(out, 0)

# ---------- per-film layer kernels ----------
def kernels(film):
    K = np.zeros((3, len(WL)))
    for i, layer in enumerate(("red", "green", "blue")):
        s = model.sp[film]["sens"][layer]
        K[i] = np.where((WL >= s["wl"][0]) & (WL <= s["wl"][-1]), 10 ** np.interp(WL, s["wl"], s["logS"]), 0.0) * D65S
        K[i] /= K[i].sum()
    return K
KER = {f: kernels(f) for f in ALL}
_WHITE = spectra(D65W)  # spectrum of neutral white
HW = {f: (_WHITE @ KER[f].T)[0] for f in ALL}
def exposures(film, xyz):
    return np.maximum(spectra(xyz) @ KER[film].T / HW[film], 1e-7)

# ---------- negative films (ideal print, as v2) ----------
def neg_render(film, H, deep, k):
    ref = model.res[film]["ref"]; z = np.zeros_like(H); zn = np.zeros_like(H); z0 = np.zeros(3)
    xn = ref + np.log10(H).mean(-1) - np.log10(GRAY)
    for i, ch in enumerate("RGB"):
        c = model.res[film]["ch"][ch]; g = model.summ[film][ch]["gamma"]; dref = model.summ[film][ch]["dref"]
        x = np.clip(ref + np.log10(H[:, i] / GRAY), c["x"][0], c["x"][-1])
        z[:, i] = (np.interp(x, c["x"], c["d"]) - dref) / g
        zn[:, i] = (np.interp(np.clip(xn, c["x"][0], c["x"][-1]), c["x"], c["d"]) - dref) / g
        z0[i] = (c["d"][0] - dref) / g
    dev = z - zn; dm = dev.mean(-1, keepdims=True); z = zn + dm + (1 + k) * (dev - dm)
    P = GRAY * 10 ** z
    if deep:
        P0 = GRAY * 10 ** z0; w = np.clip((GRAY - P) / (GRAY - P0), 0, 1) ** 2; P = P - P0 * w
    return np.clip(P, 0, 1) @ M_SRGB_XYZ.T

# ---------- reversal films: unmixing + spectral slide ----------
STATUS_A = {"R": 615.0, "G": 545.0, "B": 440.0}; SA_SIGMA = 30 / 2.3548
SA = np.array([np.exp(-0.5 * ((WL - STATUS_A[c]) / SA_SIGMA) ** 2) for c in "RGB"]); SA /= SA.sum(1, keepdims=True)
def dye_matrix(film):
    d = DY["films"][film]; w = np.array(DY["wl"])
    return np.array([np.interp(WL, w, d[k]) for k in ("cyan", "magenta", "yellow")])  # (3,36) C,M,Y
def status_a(a, E):
    T = 10 ** (-(a @ E)); return -np.log10(np.maximum(T @ SA.T, 1e-12))
XYZ_D50W = D50S @ CMF / (D50S @ CMF[:, 1])
def slide_xyz_raw_E(E, a):
    T = 10 ** (-(np.atleast_2d(a) @ E)); return (T * D50S) @ CMF / (D50S @ CMF[:, 1])
def unmix(film):
    """Dye amounts along the neutral scale.  Assumes the published neutral scale is visually
    neutral under D50 at equal Status-A densities; R/G/B differences in the published curves are
    added back as deviations through a narrow-band Status-A approximation."""
    E = dye_matrix(film); ch = model.res[film]["ch"]
    lo = max(ch[c]["x"][0] for c in "RGB"); hi = min(ch[c]["x"][-1] for c in "RGB")
    xg = np.linspace(lo, hi, 400); Dm = np.stack([np.interp(xg, ch[c]["x"], ch[c]["d"]) for c in "RGB"], 1)
    Dbar = Dm.mean(1)
    A0 = SA @ E.T
    a = np.outer(Dbar, np.linalg.solve(A0, np.ones(3)))
    target = np.outer(10 ** (-Dbar), XYZ_D50W)
    for _ in range(40):  # Newton: XYZ of the slide == neutral of visual density Dbar
        f = np.log(slide_xyz_raw_E(E, a)) - np.log(target)
        J = np.zeros((len(xg), 3, 3)); eps = 1e-5
        for k in range(3):
            da = np.zeros(3); da[k] = eps; J[:, :, k] = (np.log(slide_xyz_raw_E(E, a + da)) - np.log(slide_xyz_raw_E(E, a))) / eps
        a = a - np.linalg.solve(J, f[:, :, None])[:, :, 0]
    resid = np.abs(np.log(slide_xyz_raw_E(E, a)) - np.log(target)).max()
    a = a + (Dm - Dbar[:, None]) @ np.linalg.inv(A0).T
    return dict(x=xg, a=a, E=E, resid=resid)
UNMIX = {f: unmix(f) for f in ALL if KIND[f] == "pos"}
def slide_xyz_raw(film, a):
    E = UNMIX[film]["E"]; T = 10 ** (-(a @ E))
    return (T * D50S) @ CMF / (D50S @ CMF[:, 1])
POSNORM = {}
for f in UNMIX:
    u = UNMIX[f]; ref = model.res[f]["ref"]
    ag = np.array([np.interp(ref, u["x"], u["a"][:, k]) for k in range(3)])
    Xg = slide_xyz_raw(f, ag[None])[0]
    Xw = slide_xyz_raw(f, u["a"][-1][None])[0]          # clear film (Dmin) = white of the lightbox view
    POSNORM[f] = cat(Xg / Xg[1], D65W) * (1.0 / Xw[1])   # grey stays neutral, its lightness comes from the data
def pos_render(film, H, k):
    u = UNMIX[film]; ref = model.res[film]["ref"]
    x = np.clip(ref + np.log10(H / GRAY), u["x"][0], u["x"][-1])  # layer order R,G,B -> dyes C,M,Y
    a = np.stack([np.interp(x[:, i], u["x"], u["a"][:, i]) for i in range(3)], 1)
    xn = np.clip(ref + np.log10(H).mean(-1) - np.log10(GRAY), u["x"][0], u["x"][-1])
    an = np.stack([np.interp(xn, u["x"], u["a"][:, i]) for i in range(3)], 1)
    dev = a - an; dm = dev.mean(-1, keepdims=True); a = an + dm + (1 + k) * (dev - dm)
    return slide_xyz_raw(film, a) @ POSNORM[film].T

def render(film, xyz, variant):
    H = exposures(film, xyz)
    if KIND[film] == "neg": return neg_render(film, H, variant["deep"], variant["k"])
    return pos_render(film, H, variant["k"])

K3 = json.load(open("/home/claude/m3/k3.json"))
def variants(film):
    if KIND[film] == "neg":
        k = K3["fuji_neg"] if film == "Pro 400H" else K3["kodak_neg"]
        return [dict(id="print1", paper="endura", deep=False, k=k), dict(id="print2", paper="crystal", deep=False, k=k),
                dict(id="deepblack", deep=True, k=k), dict(id="faded", deep=False, k=k)]
    return [dict(id="standard", deep=False, k=K3["slide"]), dict(id="vivid", deep=False, k=K3["slide_vivid"])]

# ======================= v4: negative -> print on colour paper =======================
PAPERS_RAW = json.load(open("/home/claude/paper/papers.json"))
def _resample_dye(wl, d):
    wl = np.asarray(wl, float); d = np.asarray(d, float); v = np.interp(WL, wl, d)
    hi = wl.max(); t = WL > hi
    if t.any(): v[t] = d[-1]
    return np.clip(v, 0, None) / max(np.max(v), 1e-9)
def unmix_curves(ch, E, n=400):
    lo = max(ch[c]["x"][0] for c in "RGB"); hi = min(ch[c]["x"][-1] for c in "RGB")
    xg = np.linspace(lo, hi, n); Dm = np.stack([np.interp(xg, ch[c]["x"], ch[c]["d"]) for c in "RGB"], 1)
    Dbar = Dm.mean(1); A0 = SA @ E.T
    a = np.outer(Dbar, np.linalg.solve(A0, np.ones(3))); target = np.outer(10 ** (-Dbar), XYZ_D50W)
    for _ in range(40):
        f = np.log(slide_xyz_raw_E(E, a)) - np.log(target)
        J = np.zeros((len(xg), 3, 3)); eps = 1e-5
        for k in range(3):
            da = np.zeros(3); da[k] = eps; J[:, :, k] = (np.log(slide_xyz_raw_E(E, a + da)) - np.log(slide_xyz_raw_E(E, a))) / eps
        a = a - np.linalg.solve(J, f[:, :, None])[:, :, 0]
    a = a + (Dm - Dbar[:, None]) @ np.linalg.inv(A0).T
    return dict(x=xg, a=a, E=E, D=Dm)
PAPERS = {}
# Crystal Archive has no published characteristic curve; its shape comes from FUJIFLEX (a laser-exposed
# display material), so only that product's shared R/G curve is used, for all three layers.
PAPERS_RAW["crystal"]["ch"]["B"] = PAPERS_RAW["crystal"]["ch"]["G"]
for pid, p in PAPERS_RAW.items():
    E = np.array([_resample_dye(p["dyes"][k]["wl"], p["dyes"][k]["d"]) for k in ("cyan", "magenta", "yellow")])
    u = unmix_curves(p["ch"], E)
    u["name"] = p["name"]; PAPERS[pid] = u
PRINT_AIM = {pid: np.log10(1 / GRAY) + u["D"][0].mean() for pid, u in PAPERS.items()}  # mid-grey prints at 18% of paper white
for pid, u in PAPERS.items():
    Xw = slide_xyz_raw_E(u["E"], u["a"][0][None])[0]        # paper white (lowest exposure)
    ag = np.array([np.interp(np.interp(PRINT_AIM[pid], u["D"][:, i], u["x"]), u["x"], u["a"][:, i]) for i in range(3)])
    Xg = slide_xyz_raw_E(u["E"], ag[None])[0]               # the printed mid-grey
    u["white_cat"] = cat(Xg / Xg[1], D65W) / Xw[1]          # grey looks neutral; paper white -> Y=1
PRINT_BAL = {}
def print_balance(film, pid):
    """printer light per channel so the film's mid-grey prints to PRINT_AIM on all three layers"""
    key = (film, pid)
    if key in PRINT_BAL: return PRINT_BAL[key]
    u = PAPERS[pid]; ref = model.res[film]["ref"]; b = np.zeros(3)
    for i, c in enumerate("RGB"):
        Dn = np.interp(ref, model.res[film]["ch"][c]["x"], model.res[film]["ch"][c]["d"])
        xp = np.interp(PRINT_AIM[pid], u["D"][:, i], u["x"])  # paper log-exposure giving the aim density
        b[i] = xp + Dn
    PRINT_BAL[key] = b; return b
def neg_densities(film, H, k):
    ref = model.res[film]["ref"]; xn = ref + np.log10(H).mean(-1) - np.log10(GRAY); D = np.zeros_like(H); Dn = np.zeros_like(H)
    for i, c in enumerate("RGB"):
        cc = model.res[film]["ch"][c]; lo, hi = cc["x"][0], cc["x"][-1]
        D[:, i] = np.interp(np.clip(ref + np.log10(H[:, i] / GRAY), lo, hi), cc["x"], cc["d"])
        Dn[:, i] = np.interp(np.clip(xn, lo, hi), cc["x"], cc["d"])
    dev = D - Dn; dm = dev.mean(-1, keepdims=True)
    D = Dn + dm + (1 + k) * (dev - dm)
    # printing-density correction: Status M slopes are matched to the green layer, so a neutral
    # scale prints neutral (film and paper are designed as a system; Status M only approximates
    # what the paper sees).  Curve shapes (toe, shoulder, crossovers) are kept.
    g = np.array([model.summ[film][c]["gamma"] for c in "RGB"]); dref = np.array([model.summ[film][c]["dref"] for c in "RGB"])
    return dref + (D - dref) * (g[1] / g)
CAM_FLARE = 0.01     # camera veiling glare, as a fraction of mid-grey exposure
VIEW_FLARE = 0.003   # print surface reflection, as a fraction of paper white
SYSTEM_GAMMA = 1.5   # target neg x paper contrast; the data alone gives ~2.0
def paper_gamma(pid):
    u = PAPERS[pid]; Dg = u["D"][:, 1]; i0 = np.argmin(abs(Dg - 0.5)); i1 = np.argmin(abs(Dg - 1.5))
    return (Dg[i1] - Dg[i0]) / (u["x"][i1] - u["x"][i0])
def print_scale(film, pid, g=None):
    return (SYSTEM_GAMMA if g is None else g) / (model.summ[film]["G"]["gamma"] * paper_gamma(pid))
PRINT_CAL = 0.9      # lab gray-balance: fraction of the neutral-scale cast removed end-to-end (0 = mid-grey only, 1 = fully neutral)
CAL_ON = False       # enabled after the per-paper calibration LUTs are built (see end of file)
def print_render(film, H, pid, k, g=None):
    u = PAPERS[pid]; b = print_balance(film, pid)
    dref = np.array([model.summ[film][c]["dref"] for c in "RGB"])
    D = dref + (neg_densities(film, H + CAM_FLARE * GRAY, k) - dref) * print_scale(film, pid, g)
    Lp = np.clip(b[None, :] - D, u["x"][0], u["x"][-1])
    a = np.stack([np.interp(Lp[:, i], u["x"], u["a"][:, i]) for i in range(3)], 1)
    X = slide_xyz_raw_E(u["E"], a) @ u["white_cat"].T
    if CAL_ON and PRINT_CAL and "calib" in u:            # pull neutrals to neutral across the whole tonal scale
        P = np.clip(X @ M_XYZ_SRGB.T, 0, None); gr, tg = u["calib"]
        for i in range(3):
            corr = np.interp(P[:, i], gr[i], tg[i])
            P[:, i] = P[:, i] + PRINT_CAL * (corr - P[:, i])
        X = P @ M_SRGB_XYZ.T
    return (X + VIEW_FLARE * D65W) / (1 + VIEW_FLARE)

_render_v3 = render
def render(film, xyz, variant):
    if variant.get("paper"):
        return print_render(film, exposures(film, xyz), variant["paper"], variant["k"], variant.get("gamma"))
    return _render_v3(film, xyz, variant)


# ---------- viewing conditions (CAM16, J M h preserved: keeps the Hunt effect of a bright viewer) ----------
M16 = np.array([[0.401288, 0.650173, -0.051461], [-0.250268, 1.204414, 0.045854], [-0.002079, 0.048952, 0.953127]])
M16I = np.linalg.inv(M16)
SURROUND_AVG = (1.0, 0.69, 1.0)          # F, c, Nc
VIEW_SRC = {"print": 32.0, "slide": 254.0}  # adapting luminance cd/m2: print under 500 lx (ISO 3664 P2), transparency viewer 1270 cd/m2 (T1)
VIEW_DST = 20.0                            # display, ~100 cd/m2 white
YB = 20.0
def cam_cond(LA):
    F, c, Nc = SURROUND_AVG; W = D65W * 100
    k = 1 / (5 * LA + 1); FL = 0.2 * k**4 * (5 * LA) + 0.1 * (1 - k**4)**2 * (5 * LA)**(1 / 3)
    n = YB / W[1]; z = 1.48 + np.sqrt(n); Nbb = 0.725 * n**-0.2
    RGBw = M16 @ W; DR = W[1] / RGBw
    def fa(x): q = (FL * np.abs(x) / 100)**0.42; return 400 * np.sign(x) * q / (q + 27.13) + 0.1
    Rw = fa(DR * RGBw); Aw = (2 * Rw[0] + Rw[1] + 0.05 * Rw[2] - 0.305) * Nbb
    return dict(FL=FL, n=n, z=z, Nbb=Nbb, DR=DR, Aw=Aw, c=c, Nc=Nc, fa=fa)
def cam_fwd(X, P):
    R = P["fa"]((np.atleast_2d(X) * 100 @ M16.T) * P["DR"])
    a = R[:, 0] - 12 * R[:, 1] / 11 + R[:, 2] / 11; b = (R[:, 0] + R[:, 1] - 2 * R[:, 2]) / 9; h = np.arctan2(b, a)
    et = 0.25 * (np.cos(h + 2) + 3.8); A = (2 * R[:, 0] + R[:, 1] + 0.05 * R[:, 2] - 0.305) * P["Nbb"]
    J = 100 * np.clip(A / P["Aw"], 0, None)**(P["c"] * P["z"])
    t = (50000 / 13 * P["Nc"] * P["Nbb"] * et * np.hypot(a, b)) / (R[:, 0] + R[:, 1] + 21 / 20 * R[:, 2])
    C = t**0.9 * np.sqrt(J / 100) * (1.64 - 0.29**P["n"])**0.73
    return J, C * P["FL"]**0.25, h
def cam_inv(J, Mc, h, P):
    C = Mc / P["FL"]**0.25; Js = np.maximum(J, 1e-9)
    t = (C / (np.sqrt(Js / 100) * (1.64 - 0.29**P["n"])**0.73))**(1 / 0.9)
    et = 0.25 * (np.cos(h + 2) + 3.8); A = P["Aw"] * (Js / 100)**(1 / (P["c"] * P["z"]))
    p2 = A / P["Nbb"] + 0.305; p3 = 21 / 20; sh, ch = np.sin(h), np.cos(h)
    a = np.zeros_like(J); b = np.zeros_like(J); nz = t > 1e-12
    p1 = np.where(nz, 50000 / 13 * P["Nc"] * P["Nbb"] * et / np.where(nz, t, 1), 0)
    big = np.abs(sh) >= np.abs(ch)
    with np.errstate(divide="ignore", invalid="ignore"):
        bb = p2 * (2 + p3) * (460 / 1403) / (p1 / sh + (2 + p3) * (220 / 1403) * (ch / sh) - 27 / 1403 + p3 * (6300 / 1403))
        aa = p2 * (2 + p3) * (460 / 1403) / (p1 / ch + (2 + p3) * (220 / 1403) - (27 / 1403 - p3 * (6300 / 1403)) * (sh / ch))
    a = np.where(nz, np.where(big, bb * ch / sh, aa), 0); b = np.where(nz, np.where(big, bb, aa * sh / ch), 0)
    R = np.stack([(460 * p2 + 451 * a + 288 * b) / 1403, (460 * p2 - 891 * a - 261 * b) / 1403, (460 * p2 - 220 * a - 6300 * b) / 1403], 1) - 0.1
    Rc = np.sign(R) * 100 / P["FL"] * (27.13 * np.abs(R) / (400 - np.abs(R)))**(1 / 0.42)
    return (Rc / P["DR"]) @ M16I.T / 100
_CAMP = {}
def view_adapt(X, kind):
    if kind not in _CAMP: _CAMP[kind] = (cam_cond(VIEW_SRC[kind]), cam_cond(VIEW_DST))
    ps, pd = _CAMP[kind]; J, Mc, h = cam_fwd(np.clip(X, 1e-7, None), ps); return cam_inv(J, Mc, h, pd)
_render_core = render
def render(film, xyz, variant):
    X = _render_core(film, xyz, variant)
    if variant.get("paper"): return view_adapt(X, "print")
    if KIND[film] != "neg": return view_adapt(X, "slide")
    return X

# ---------- "base" variant: a pre-development profile ----------
# Tone along the neutral axis is returned to the input (full latitude, no crushed toe), greys are kept
# neutral at every level, and what remains is the film's colour signature: hue shifts, saturation and
# relative lightness of colours, all from the data.
BRAD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
BRADI = np.linalg.inv(BRAD)
BASE_EV = np.linspace(-12, 4, 1025)
_BASE = {}
PB_GAMMA = 1.5   # paper colour is extracted at the same contrast as the print tone curve
def _core_color(film, X, k, paper=None):
    if paper: return _render_core(film, X, dict(paper=paper, deep=False, k=k, gamma=PB_GAMMA))
    if KIND[film] == "neg": return _render_core(film, X, dict(deep=False, k=k))
    return _render_core(film, X, dict(k=k))
def base_table(film, k, paper=None):
    key = (film, k, paper)
    if key in _BASE: return _BASE[key]
    Yin = GRAY * 2 ** BASE_EV
    Xo = _core_color(film, np.outer(Yin, D65W), k, paper)
    Yo = np.maximum.accumulate(np.maximum(Xo[:, 1], 1e-9)) * (1 + 1e-9 * np.arange(len(Yin)))  # strictly increasing
    lms = Xo @ BRAD.T / Xo[:, 1:2]; lmsw = BRAD @ _target_white(film)
    r = lmsw[None, :] / lms
    sl = np.gradient(np.log10(np.maximum(Xo[:, 1], 1e-12)), np.log10(Yin))   # film's own tonal slope at each level
    w = np.clip((sl - 0.15) / 0.35, 0, 1)        # where the film stops recording (flat toe / shoulder) fall back to the input
    t = dict(logYo=np.log10(Yo), logYin=np.log10(Yin), r=r, w=w)
    _BASE[key] = t; return t
def base_render(film, xyz, k, paper=None):
    t = base_table(film, k, paper); Xo = _core_color(film, xyz, k, paper)
    ly = np.log10(np.maximum(Xo[:, 1], 1e-9)); ly = np.clip(ly, t["logYo"][0], t["logYo"][-1])
    yin = 10 ** np.interp(ly, t["logYo"], t["logYin"])
    r = np.stack([np.interp(ly, t["logYo"], t["r"][:, i]) for i in range(3)], 1)
    out = ((Xo @ BRAD.T) * r @ BRADI.T) * (yin / np.maximum(Xo[:, 1], 1e-9))[:, None]
    w = np.interp(np.log10(np.maximum(xyz[:, 1], 1e-12)), t["logYin"], t["w"])[:, None]
    fb = base_render(film, xyz, k) if paper else xyz   # outside the paper'"'"'s range: the negative'"'"'s base, then the input
    return w * out + (1 - w) * fb
_render_full = render
def render(film, xyz, variant):
    if variant.get("base"): return base_render(film, np.atleast_2d(xyz), variant["k"], variant.get("bpaper"))
    return _render_full(film, xyz, variant)
BASE_K = 0.0   # ICCs carry data only; the interimage effect (not in the datasheets) is a separate, adjustable style
def variants(film):
    return [dict(id="base", base=True, k=BASE_K)]   # one ICC per film: the exposure step only
# ---- per-paper gray-balance calibration LUTs (mimic a lab calibrating the whole tonal scale neutral) ----
_CAL_FILM = "Portra 400"
_CAL_Y = np.geomspace(0.002, 1.1, 96)
for pid, u in PAPERS.items():
    Xr = _render_core(_CAL_FILM, np.outer(_CAL_Y, D65W), dict(paper=pid, deep=False, k=0.0, gamma=PB_GAMMA))
    P = np.clip(Xr @ M_XYZ_SRGB.T, 0, None); gY = (P @ M_SRGB_XYZ.T[1])[:, None]  # per-level neutral target = own luminance
    gr = []; tg = []
    for i in range(3):
        xs = P[:, i]; ys = gY[:, 0]
        o = np.argsort(xs); xs, ys = xs[o], ys[o]
        xu, iu = np.unique(np.round(xs, 7), return_index=True)
        gr.append(xu); tg.append(np.maximum.accumulate(ys[iu]))
    u["calib"] = (gr, tg)
CAL_ON = True

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
    POSNORM[f] = cat(Xg / Xg[1], D65W) * (GRAY / Xg[1])
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
VIEW_FLARE = 0.006   # print surface reflection, as a fraction of paper white
SYSTEM_GAMMA = 1.7   # target neg x paper contrast (typical optical print); the data alone gives ~2.0
def paper_gamma(pid):
    u = PAPERS[pid]; Dg = u["D"][:, 1]; i0 = np.argmin(abs(Dg - 0.5)); i1 = np.argmin(abs(Dg - 1.5))
    return (Dg[i1] - Dg[i0]) / (u["x"][i1] - u["x"][i0])
def print_scale(film, pid):
    return SYSTEM_GAMMA / (model.summ[film]["G"]["gamma"] * paper_gamma(pid))
def print_render(film, H, pid, k):
    u = PAPERS[pid]; b = print_balance(film, pid)
    dref = np.array([model.summ[film][c]["dref"] for c in "RGB"])
    D = dref + (neg_densities(film, H + CAM_FLARE * GRAY, k) - dref) * print_scale(film, pid)
    Lp = np.clip(b[None, :] - D, u["x"][0], u["x"][-1])
    a = np.stack([np.interp(Lp[:, i], u["x"], u["a"][:, i]) for i in range(3)], 1)
    X = slide_xyz_raw_E(u["E"], a) @ u["white_cat"].T
    return (X + VIEW_FLARE * D65W) / (1 + VIEW_FLARE)

_render_v3 = render
def render(film, xyz, variant):
    if variant.get("paper"):
        return print_render(film, exposures(film, xyz), variant["paper"], variant["k"])
    return _render_v3(film, xyz, variant)

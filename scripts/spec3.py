"""Spectral core shared by the colour model and the monochrome path.

This is the scene-side half of model3 (wavelength grid, D65, Otsu 2018
upsampling) without the colour films' datasheet data, so the monochrome path
can run on its own. The formulas are model3's, line for line; model3 keeps its
own copy so the colour pipeline is untouched."""
import json, os, numpy as np, colour, warnings
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAY = 0.18
shape = colour.SpectralShape(380, 730, 10)
WL = shape.wavelengths
_al = lambda sd: sd.copy().align(shape).values
CMF = colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(shape).values
D65S = _al(colour.SDS_ILLUMINANTS["D65"])
SRGB = colour.RGB_COLOURSPACES["sRGB"]
M_SRGB_XYZ = SRGB.matrix_RGB_to_XYZ; M_XYZ_SRGB = SRGB.matrix_XYZ_to_RGB
D65W = colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"])

OT = json.load(open(os.path.join(ROOT, "m3/otsu2018.json")))
OB = np.array(OT["basis"]); OM = np.array(OT["means"]); OS = np.array(OT["selector"])
_W = D65S[:, None] * CMF / (D65S @ CMF[:, 1])
OMINV = np.array([np.linalg.inv(OB[c] @ _W) for c in range(len(OB))])
OXMU = OM @ _W
BLEND = 0.02
M_XYZ_2020 = np.linalg.inv(colour.RGB_COLOURSPACES["ITU-R BT.2020"].matrix_RGB_to_XYZ)
NORM_MAX = 0.35

def leaf_weights(xy):
    n = len(xy); w = np.zeros((n, len(OB)))
    def walk(row, acc):
        origin, direction, lo, hi = OS[row]; t = np.clip((xy[:, int(direction)] - origin) / BLEND + 0.5, 0, 1)
        for idx, wt in ((int(lo), acc * (1 - t)), (int(hi), acc * t)):
            if idx < 0: walk(-idx, wt)
            else: w[:, idx] += wt
    walk(0, np.ones(n)); return w

def spectra(xyz):
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

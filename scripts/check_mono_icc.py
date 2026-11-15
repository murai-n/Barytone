"""Check baked black-and-white ICCs through LittleCMS (what an app really does).

    python3 scripts/check_mono_icc.py BASE.icm ICCDIR

For each profile: output is neutral, a grey ramp only rises, mid-grey keeps
L* 50 and the shadows/highlights stay inside the encoding. Then the profile
is decoded, the paper style's curve (MGIV RC grade 2) applied, and the
result compared with mono.render() for the whole chain (print-dev, in 8-bit
levels; must stay under 3)."""
import sys, os, io, numpy as np, colour
from PIL import Image, ImageCms
import mono, spec3 as S

base, d = sys.argv[1], sys.argv[2]
cam = os.path.basename(base).split("-")[0]
srgb = ImageCms.createProfile("sRGB")
def through(path, enc8):
    t = ImageCms.buildTransform(ImageCms.ImageCmsProfile(path), srgb, "RGB", "RGB", renderingIntent=1, flags=0x0004)   # cmsFLAGS_NOWHITEONWHITEFIXUP: LittleCMS would force device white onto paper white
    return np.asarray(ImageCms.applyTransform(Image.fromarray(enc8[None]), t))[0].astype(float)
rng = np.random.default_rng(3)
chart = rng.integers(0, 256, (400, 3)).astype(np.uint8)
ramp = np.stack([np.arange(256)] * 3, -1).astype(np.uint8)
lin = lambda e: colour.models.eotf_sRGB(e / 255.0)
# scene colours for the filter check (sRGB 8-bit): clear sky, red brick, foliage
SCENE = {"空": [86, 140, 200], "赤レンガ": [160, 70, 50], "葉": [70, 110, 50]}
sc = np.array(list(SCENE.values()), np.uint8)
bad = 0; rows = []
for f, a in mono.ALIAS.items():
    for fl, fid in mono.FILTER_ID.items():
        p = os.path.join(d, f"{cam}-Film {a} {fid}.icm")
        o = through(p, chart); spread = (o.max(1) - o.min(1)).max()
        r = through(p, ramp)[:, 1]; mono_ok = bool(np.all(np.diff(r) >= 0))
        mid = through(p, np.array([[118, 118, 118]], np.uint8))[0, 1]
        L = colour.XYZ_to_Lab(lin(np.array([mid]))[:, None] * S.D65W)[0, 0]
        # whole chain: ICC (LittleCMS) -> paper curve, vs the direct model
        v = lin(through(p, sc)[:, 1]) ** (1 / mono.ENC)
        got = colour.XYZ_to_sRGB(mono.print_from_value(v), apply_cctf_encoding=True)[:, 1] * 255
        X = lin(sc.astype(float)) @ S.M_SRGB_XYZ.T
        ref = colour.XYZ_to_sRGB(mono.render(f, X, filt=fl), apply_cctf_encoding=True)[:, 1] * 255
        dev = np.abs(got - ref).max()
        # the ICC's own error in the curve domain (reported), and what it does to the
        # print at grade 2 (tested): a 33-node grid cannot follow the film exactly
        verr = np.abs(v - mono.icc_xyz(f, X, fl)[:, 1] ** (1 / mono.ENC)).max()
        ok = spread <= 1 and mono_ok and abs(L - 50) < 1.0 and r[0] > 0 and r[-1] < 255 and dev < 3.0
        bad += not ok
        rows.append((f, fl, spread, mono_ok, L, r[0], r[-1], verr, dev, np.round(got).astype(int)))
print(f"{'film':11s} {'filter':7s} neutral ramp  L*mid  black white  icc-err  print-dev  " + " ".join(SCENE))
for f, fl, sp, mo, L, b0, w0, ve, dev, g in rows:
    print(f"{f:11s} {fl:7s} {sp:5.0f}  {'ok' if mo else 'NG':4s} {L:6.2f} {b0:5.0f} {w0:5.0f}  {ve:7.4f}  {dev:8.2f}   " + " ".join(f"{x:4d}" for x in g))
print("FAILED" if bad else "all ok", f"({len(rows)} profiles, {bad} failed)")
sys.exit(1 if bad else 0)

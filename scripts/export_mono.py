"""Add the black-and-white films to the baking tool's data (films.json).

The colour entries are produced by export4.py, which needs the colour
pipeline's working data. This script only touches the "mono" entries, so it
can be re-run on its own: it drops any existing mono films and appends fresh
ones built from ds/mono_films.json through mono.py.

Each mono film carries, per filter, the spectral kernel already divided by
the response to white, so the browser computes exposure as one dot product
with the upsampled spectrum and needs nothing else from mono.py."""
import json, os, numpy as np
import mono, spec3 as S

ROOT = S.ROOT
TARGETS = [os.path.join(ROOT, "bake3/src/films.json"), os.path.join(ROOT, "m3/films3.json")]
DESC = {
    "HP5 Plus": "Ilford の高感度定番。粘りのある中間調",
    "FP4 Plus": "中庸な感度の古典的な乳剤。素直な階調",
    "Delta 100": "Ilford のコアシェル乳剤。シャープで硬め",
    "Delta 400": "高感度のコアシェル乳剤",
    "Pan F Plus": "超低感度・微粒子。締まったコントラスト",
    "SFX 200": "赤外寄りの増感。赤が明るく空が暗い（可視域まで）",
    "T-Max 100": "Kodak の T-GRAIN。長い直線部",
    "T-Max 400": "T-GRAIN の高感度版（分光感度は 100 から借用）",
    "Tri-X 400": "Kodak の高感度定番。肩の柔らかい階調",
}
ORDER = ["HP5 Plus", "FP4 Plus", "Delta 100", "Delta 400", "Pan F Plus", "SFX 200", "T-Max 100", "T-Max 400", "Tri-X 400"]
assert set(ORDER) == set(mono.FILMS), set(ORDER) ^ set(mono.FILMS)

def entry(f):
    F = mono.FILMS[f]; c = F["ch"]
    variants = []
    for fl in mono.FILTER_IDS:
        k = mono.kernel(f, fl)
        k = k / float(np.ravel(mono._WHITE @ k)[0])          # H = spectrum . k, 1.0 at white
        variants.append(dict(id=mono.FILTER_ID[fl], filt=fl, label=mono.FILTER_LABEL[fl],
                             mk=[float(v) for v in k], base=False, bpaper=None))
    return dict(name=mono.ALIAS[f], id=mono.ALIAS[f], full=f, desc=DESC[f], iso=f"ISO {F['iso']}", kind="mono",
                x=[float(v) for v in mono.film_curve(f)[0]], d=[float(v) for v in mono.film_curve(f)[1]],
                sp=mono.speed_point(f), ref=float(np.ravel(mono.neg_density(f, np.array([mono.GRAY])))[0]),
                variants=variants)

# The tool's previews show a mono film printed, not the flat negative the ICC
# holds: ICC value -> print Y on this paper and grade (a neutral paper).
PREVIEW_PAPER, PREVIEW_GRADE = "MGIV RC", "2"
_pv = np.linspace(0, 1, 257)
PREVIEW = dict(paper=PREVIEW_PAPER, grade=PREVIEW_GRADE, label="MGIV RC 2号",
               v=[float(x) for x in _pv],
               rgb=np.clip(mono.print_from_value(_pv, PREVIEW_PAPER, PREVIEW_GRADE) @ S.M_XYZ_SRGB.T, 0, 1).tolist())   # linear sRGB, paper tint included

def main():
    films = [entry(f) for f in ORDER]
    for t in TARGETS:
        d = json.load(open(t))
        d["films"] = [e for e in d["films"] if e.get("kind") != "mono"] + films
        d["MONO"] = dict(ENC=mono.ENC, NEG_SPAN=mono.NEG_SPAN, V_MID=mono.V_MID, METER_LOG=mono.METER_LOG, preview=PREVIEW)
        json.dump(d, open(t, "w"))
    # reference renderings for the JS engine test
    rng = np.random.default_rng(7)
    pts = np.vstack([rng.uniform(0, 1, (200, 3)), np.eye(3), np.outer([0.001, 0.02, 0.18, 0.5, 1.0], [1, 1, 1])])
    pts = pts @ S.M_SRGB_XYZ.T
    ref = {e["id"] + "|" + v["id"]: mono.icc_xyz(e["full"], pts, v["filt"]).tolist() for e in films for v in e["variants"]}
    json.dump(dict(pts=pts.tolist(), ref=ref), open(os.path.join(ROOT, "m3/ref_mono.json"), "w"))
    print("mono export ok:", len(films), "films,", sum(len(e["variants"]) for e in films), "profiles")

if __name__ == "__main__":
    main()

"""Re-import Portra 160NC/160VC/400NC/400VC (Kodak E-190, 2006) after the
per-page axis fix in ds/extract4.py, and patch the film entries in place.

The full colour build (model3.py) needs intermediate data that is not in the
repository, so this script redoes only the steps that depend on the corrected
numbers, with the same formulas as model2.py / model3.py / export4.py:
  - layer kernels K   (model3.kernels / HW, export4)
  - ref, g, dref      (model2: 10/S, speed-point rule, straight-line fit)
  - print balance     (densities moved by a constant: bal moves with them)
The neutral-axis tables (bases) and the Develop curves are unchanged: a
uniform shift of the published curve is cancelled by ref/dref, and a grey's
layer exposures do not depend on K.  check_portra_e190.js verifies that.

usage: python3 scripts/fix_portra_e190.py <portra_e190.json from extract4>"""
import sys, os, json, numpy as np, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec3 as S

ROOT = S.ROOT
# Portra VC: the sheet's curves give the same colour as NC once the base ICC
# normalises tone, so VC is NC data plus a baked chroma boost (engine saturate()).
SAT = {"KP160VC": 1.15, "KP400VC": 1.15}
IDS = {"Portra 160NC": "KP160NC", "Portra 160VC": "KP160VC",
       "Portra 400NC": "KP400NC", "Portra 400VC": "KP400VC"}

def kernel(sens):
    K = np.zeros((3, len(S.WL)))
    for i, layer in enumerate(("red", "green", "blue")):
        s = sens[layer]
        K[i] = np.where((S.WL >= s["wl"][0]) & (S.WL <= s["wl"][-1]),
                        10 ** np.interp(S.WL, s["wl"], s["logS"]), 0.0) * S.D65S
        K[i] /= K[i].sum()
    hw = (S.spectra(S.D65W[None]) @ K.T)[0]
    return K / hw[:, None]

def tone(v):
    ch = v["ch"]; iso = v["iso"]; ref = float(np.log10(10 / iso))
    h = [np.interp(min(ch[k]["d"]) + 0.15, ch[k]["d"], ch[k]["x"]) for k in "RGB"]
    Sp = float(np.sqrt(2) / np.sqrt(10 ** h[1] * 10 ** max(h)))
    if abs(np.log2(Sp / iso)) > 0.5: ref = float(np.log10(10 / Sp))
    g, dref = [], []
    for k in "RGB":
        x, d = np.array(ch[k]["x"]), np.array(ch[k]["d"])
        xs = np.linspace(ref - 0.3, min(ref + 1.5, x[-1]), 60)
        g.append(float(np.polyfit(xs, np.interp(xs, x, d), 1)[0]))
        dref.append(float(np.interp(ref, x, d)))
    return ref, g, dref

def main(src):
    new = json.load(open(src))
    p1 = os.path.join(ROOT, "ds/new1.json"); n1 = json.load(open(p1))
    for f in IDS: n1[f] = new[f]
    json.dump(n1, open(p1, "w"))
    for p in ("bake3/src/films.json", "m3/films3.json"):
        p = os.path.join(ROOT, p); d = json.load(open(p))
        for e in d["films"]:
            f = next((k for k, v in IDS.items() if v == e["id"]), None)
            if f is None: continue
            v = new[f]; ref, g, dref = tone(v)
            K = kernel(v["sens"])
            dD = float(np.mean(np.array(dref) - np.array(e["dref"])))
            print(f"{e['id']}: ref {e['ref']:.4f} -> {ref:.4f}  dref shift {dD:+.3f}  "
                  f"K change {np.abs(K - np.array(e['K'])).max():.4f}")
            e["K"] = K.tolist(); e["ref"] = ref; e["g"] = g; e["pg"] = g; e["dref"] = dref
            e["ch"] = {k: dict(x=list(map(float, v["ch"][k]["x"])), d=list(map(float, v["ch"][k]["d"]))) for k in "RGB"}
            if e["id"] in SAT: e["sat"] = SAT[e["id"]]
            e["bal"] = {pid: [b + dD for b in bal] for pid, bal in e["bal"].items()}
        json.dump(d, open(p, "w"))
        print("wrote", p)

if __name__ == "__main__":
    main(*sys.argv[1:])

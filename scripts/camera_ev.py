"""Per-camera exposure offset for the Film styles, derived from Capture One's
film curves (.fcrv).

Capture One places a metered grey low in the raw rendering and lifts it with
its default curve (Film Standard). The kit uses Linear Response so the film
model sees the scene as it is, and that lift is lost; for a Nikon Z5 it is
about 1.25 EV. The offset is read off each camera's own curves:

    x_grey : Film Standard(gain_FS * x_grey) = 0.18      (grey as C1 shows it)
    offset = log2(0.18 / Linear Response(gain_LR * x_grey))

Curve coordinates are taken as linear light (the reading that matches the
~1.5 EV measured on a Nikon; a gamma-1.8 reading would give 2.6 EV). The gain
field is taken as an exposure factor applied before the curve (Fuji and
Phase One curves carry 1.418 = +0.5 EV on Film Standard but 1.0 on Linear
Response).

The .fcrv files are Phase One's and are only read, never stored here; this
script writes the derived numbers to ds/camera_ev.json.

    python3 scripts/camera_ev.py /path/to/FilmCurves"""
import json, os, struct, sys, collections
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "ds/camera_ev.json")

def parse(path):
    """Observed layout (II little / MM big endian): magic, u32 version, curve A,
    u32 flag, 2 x (u32 len + text), u32 kind, f32 gain, 3 x u32, curve B,
    curve C. A curve is u32 n, then n x (u32 x, u32 y) as fractions of 2^32 - 1.
    Older versions (2, 4, 5) differ and are skipped."""
    b = open(path, "rb").read()
    e = {b"II": "<", b"MM": ">"}.get(b[:2])
    if not e: raise ValueError("magic")
    u = lambda o: struct.unpack_from(e + "I", b, o)[0]
    def curve(o):
        n = u(o); o += 4
        return np.array([(u(o + 8*i) / 4294967295.0, u(o + 8*i + 4) / 4294967295.0) for i in range(n)]), o + 8*n
    if u(2) != 6: raise ValueError("version %d" % u(2))
    A, o = curve(6); o += 4; names = []
    for _ in range(2):
        L = u(o); o += 4; names.append(b[o:o+L].decode("utf-8", "replace")); o += L
    kind, gain = struct.unpack_from(e + "If", b, o); o += 20
    B, o = curve(o); C, o = curve(o)
    if o != len(b): raise ValueError("length")
    return dict(A=A, gain=float(gain), names=names)

def main(folder):
    curves = collections.defaultdict(dict); skipped = 0
    for f in os.listdir(folder):
        if not f.lower().endswith(".fcrv") or "-" not in f: continue
        cam, _, name = f[:-5].partition("-")
        if name not in ("Film Standard", "Linear Response"): continue
        try: curves[cam][name] = parse(os.path.join(folder, f))
        except ValueError: skipped += 1
    ev = {}
    for cam, c in sorted(curves.items()):
        if len(c) < 2: continue
        fs, lr = c["Film Standard"], c["Linear Response"]
        x = np.interp(0.18, fs["A"][:, 1], fs["A"][:, 0]) / fs["gain"]
        y = np.interp(lr["gain"] * x, lr["A"][:, 0], lr["A"][:, 1])
        ev[cam] = round(float(np.log2(0.18 / y)), 2)
    vals = np.array(list(ev.values()))
    out = dict(source="Capture One 23 film curves: Film Standard vs Linear Response, curve A, linear-light reading",
               default=round(float(np.median(vals)), 2), ev=ev)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=0, sort_keys=True)
    print(f"{len(ev)} cameras -> {OUT}; median {np.median(vals):+.2f} EV, range {vals.min():+.2f}..{vals.max():+.2f}; skipped {skipped} old-format files")
    for k in ("NikonZ5", "NikonD750", "NikonZ6", "SonyILCE-7M4", "CanonEOSR5", "FujiXT4", "FujiXT5", "LeicaQ2", "PhaseOneIQ4150"):
        if k in ev: print(f"  {k:16s} {ev[k]:+.2f}")

if __name__ == "__main__":
    main(sys.argv[1])

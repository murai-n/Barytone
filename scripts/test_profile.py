"""Write a stand-in camera profile for testing the bake path.

The real base is a Capture One camera profile (RGB -> Lab, mft2 A2B0), which
is the user's and is not in the repository. This one has the same layout,
33-node grid and 1025-entry input tables, and maps sRGB-encoded input to
CIE Lab (D50). Good enough to exercise reading, baking and LittleCMS decoding.

    python3 scripts/test_profile.py OUT.icm"""
import sys, struct, numpy as np, colour

def tag_desc(text):
    t = text.encode("ascii") + b"\0"
    return b"desc" + b"\0" * 4 + struct.pack(">I", len(t)) + t + b"\0" * (4 + 4 + 2 + 1 + 67)

def tag_xyz(X):
    return b"XYZ " + b"\0" * 4 + b"".join(struct.pack(">i", int(round(v * 65536))) for v in X)

def tag_text(text):
    return b"text" + b"\0" * 4 + text.encode("ascii") + b"\0"

def tag_mft2(g=33, nin=1025, nout=2):
    D50 = np.array([0.9642, 1.0, 0.8249]); d50xy = colour.XYZ_to_xy(D50)
    s = np.linspace(0, 1, g)
    R, G, B = np.meshgrid(s, s, s, indexing="ij")          # r slowest, as ICC orders it
    enc = np.stack([R, G, B], -1).reshape(-1, 3)
    lin = colour.models.eotf_sRGB(enc)
    XYZ = lin @ colour.RGB_COLOURSPACES["sRGB"].matrix_RGB_to_XYZ.T
    XYZ = colour.adaptation.chromatic_adaptation_VonKries(XYZ, colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]), D50, transform="Bradford")
    Lab = colour.XYZ_to_Lab(XYZ, d50xy)
    e = np.clip(np.round(np.stack([Lab[:, 0] / 100 * 65280, (Lab[:, 1] + 128) * 256, (Lab[:, 2] + 128) * 256], -1)), 0, 65535).astype(">u2")
    head = b"mft2" + b"\0" * 4 + bytes([3, 3, g, 0])
    mat = b"".join(struct.pack(">i", v) for v in (65536, 0, 0, 0, 65536, 0, 0, 0, 65536))
    tabs = struct.pack(">HH", nin, nout)
    intab = np.tile(np.round(np.linspace(0, 65535, nin)), 3).astype(">u2").tobytes()
    outtab = np.tile(np.round(np.linspace(0, 65535, nout)), 3).astype(">u2").tobytes()
    return head + mat + tabs + intab + e.tobytes() + outtab

def profile(name="TestCam-Generic_Neutral"):
    tags = [(b"desc", tag_desc(name)), (b"cprt", tag_text("test profile, no rights")),
            (b"wtpt", tag_xyz([0.9642, 1.0, 0.8249])), (b"A2B0", tag_mft2())]
    off = 128 + 4 + 12 * len(tags); table = b""; body = b""
    for sig, data in tags:
        pad = (-len(data)) % 4
        table += sig + struct.pack(">II", off + len(body), len(data)); body += data + b"\0" * pad
    size = off + len(body)
    hdr = struct.pack(">I", size) + b"lcms" + bytes([2, 0x10, 0, 0]) + b"scnr" + b"RGB " + b"Lab "
    hdr += b"\0" * 12 + b"acsp" + b"APPL" + b"\0" * 4 + b"\0" * 8 + b"\0" * 8 + struct.pack(">I", 0)
    hdr += b"".join(struct.pack(">i", int(round(v * 65536))) for v in (0.9642, 1.0, 0.8249)) + b"test"
    hdr += b"\0" * (128 - len(hdr))
    return hdr + struct.pack(">I", len(tags)) + table + body

if __name__ == "__main__":
    open(sys.argv[1], "wb").write(profile())

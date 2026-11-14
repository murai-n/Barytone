import sys; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour
from model2 import *
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
XYZ=colour.xyY_to_XYZ(np.array(list(cc.data.values())))
D65=colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"])
XYZ=colour.adaptation.chromatic_adaptation_VonKries(XYZ,colour.xy_to_XYZ(cc.illuminant),D65)
cs=colour.RGB_COLOURSPACES["sRGB"]; lin=(XYZ@cs.matrix_XYZ_to_RGB.T); 
def lab(l): return colour.XYZ_to_Lab(l@cs.matrix_RGB_to_XYZ.T,colour.XYZ_to_xy(D65))
L0=lab(lin[:18]); C0=np.hypot(L0[:,1],L0[:,2]); h0=np.degrees(np.arctan2(L0[:,2],L0[:,1]))
def stats(film,k):
    out=render_lin(film,lin,k=k); L=lab(out[:18]); C=np.hypot(L[:,1],L[:,2]); h=np.degrees(np.arctan2(L[:,2],L[:,1])); dh=(h-h0+180)%360-180
    g=lab(out[18:]); return C.mean()/C0.mean(), np.abs(dh).mean(), g[:,0].round(0).tolist(), float((out<=0).any(-1).sum()+ (out>=1).any(-1).sum())
print("input gray patches L*:",lab(lin[18:])[:,0].round(0).tolist())
for f in ALL:
    for k in (0.0,0.361):
        s=stats(f,k); print(f"{f:16s} k={k:.3f} chroma {s[0]:.3f} hue-shift {s[1]:.1f}deg clipped-patches {int(s[3])} grays L* {s[2]}")

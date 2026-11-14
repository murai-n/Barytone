import sys, numpy as np, colour
sys.path.insert(0,"/home/claude/scripts"); import model
from model import *
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
XYZ=colour.xyY_to_XYZ(np.array(list(cc.data.values())))
D65=colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"])
XYZ=colour.adaptation.chromatic_adaptation_VonKries(XYZ,colour.xy_to_XYZ(cc.illuminant),D65)
cs=colour.RGB_COLOURSPACES["sRGB"]; lin=(XYZ@cs.matrix_XYZ_to_RGB.T)[:18]
def lab(l): return colour.XYZ_to_Lab(l@cs.matrix_RGB_to_XYZ.T,colour.XYZ_to_xy(D65))
L0=lab(lin); C0=np.hypot(L0[:,1],L0[:,2]); h0=np.degrees(np.arctan2(L0[:,2],L0[:,1]))
def stats(film,k):
    L=lab(film_linear(film,lin,deep_black=True,k=k)); C=np.hypot(L[:,1],L[:,2]); h=np.degrees(np.arctan2(L[:,2],L[:,1])); dh=(h-h0+180)%360-180
    return C.mean()/C0.mean(), np.abs(dh).mean(), np.abs(L[:,0]-L0[:,0]).mean()
lo,hi=0.0,2.0
for _ in range(40):
    mid=(lo+hi)/2
    if stats("Portra 400",mid)[0]<1: lo=mid
    else: hi=mid
k=round((lo+hi)/2,3); print("k =",k)
for film in ORDER:
    a=stats(film,0); b=stats(film,k); print(f"{film:10s} chroma ratio {a[0]:.3f} -> {b[0]:.3f} | mean hue shift {a[1]:.1f} -> {b[1]:.1f} deg | mean dL {a[2]:.1f} -> {b[2]:.1f}")
open("/home/claude/work/k.txt","w").write(str(k))

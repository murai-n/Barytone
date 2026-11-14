import sys; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, warnings; warnings.filterwarnings("ignore")
import model3 as M
import model, model2
sds=colour.SDS_COLOURCHECKERS["ColorChecker N Ohta"]
RT=np.array([sd.copy().align(M.shape).values for sd in sds.values()])[:18]
XT=(RT*M.D65S)@M.CMF/(M.D65S@M.CMF[:,1])
for f in M.ALL:
    Ht=RT@M.KER[f].T/M.HW[f]; print(f"{f:16s} upsampling error vs measured spectra: {np.abs(np.log2(M.exposures(f,XT)/Ht)).mean():.3f} stops")
# white & gray neutrality of H
for f in M.ALL: print(f"{f:16s} H(white)",np.round(M.exposures(f,M.D65W[None])[0],4))
for f,u in M.UNMIX.items(): print(f"{f:16s} unmix residual {u['resid']:.4f}  dye amounts at ref:",np.round([np.interp(model.res[f]['ref'],u['x'],u['a'][:,k]) for k in range(3)],3))
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
XYZ=colour.adaptation.chromatic_adaptation_VonKries(colour.xyY_to_XYZ(np.array(list(cc.data.values()))),colour.xy_to_XYZ(cc.illuminant),M.D65W)
d65xy=colour.XYZ_to_xy(M.D65W)
def lab(X): return colour.XYZ_to_Lab(X,d65xy)
L0=lab(XYZ[:18]); C0=np.hypot(L0[:,1],L0[:,2]); h0=np.degrees(np.arctan2(L0[:,2],L0[:,1]))
def stats(X):
    L=lab(X); C=np.hypot(L[:,1],L[:,2]); h=np.degrees(np.arctan2(L[:,2],L[:,1])); dh=(h-h0+180)%360-180
    return C.mean()/C0.mean(), np.abs(dh).mean()
lin_in=XYZ@M.M_XYZ_SRGB.T
print("\nfilm             variant    v2 chroma  v3 chroma   v2 hue  v3 hue   v3 grays a*,b* (6 patches)")
for f in M.ALL:
    for v in M.variants(f):
        old=model.film_linear(f,lin_in,deep_black=v["deep"],k=v["k"])@M.M_SRGB_XYZ.T
        new=M.render(f,XYZ,v)
        so=stats(old[:18]); sn=stats(new[:18]); g=lab(new[18:])
        print(f"{f:16s} {v['id']:10s} {so[0]:.3f}      {sn[0]:.3f}      {so[1]:4.1f}    {sn[1]:4.1f}   "," ".join("%+.1f,%+.1f"%(a,b) for a,b in g[:,1:]))
# per-patch hue/chroma for Velvia vs Provia standard
names=list(cc.data.keys())[:18]
pv=lab(M.render("Provia 100F",XYZ,M.variants("Provia 100F")[0]))[:18]; vv=lab(M.render("Velvia 50",XYZ,M.variants("Velvia 50")[0]))[:18]
print("\npatch            C*in  Provia  Velvia | h_in  Provia Velvia")
for i,n in enumerate(names):
    ci=C0[i]; cp=np.hypot(*pv[i,1:]); cv=np.hypot(*vv[i,1:])
    hp=np.degrees(np.arctan2(pv[i,2],pv[i,1])); hv=np.degrees(np.arctan2(vv[i,2],vv[i,1]))
    print(f"{n[:15]:15s} {ci:5.1f} {cp:6.1f} {cv:6.1f}  | {h0[i]:5.0f} {hp:6.0f} {hv:6.0f}")
# wide-gamut sweep: saturated Rec2020 hues at L~50: old vs new continuity
hues=np.linspace(0,1,24,endpoint=False)
import matplotlib.colors as mc
rgb2020=mc.hsv_to_rgb(np.stack([hues,np.full(24,0.95),np.full(24,0.6)],1))
X=rgb2020@colour.RGB_COLOURSPACES['ITU-R BT.2020'].matrix_RGB_to_XYZ.T
lin=X@M.M_XYZ_SRGB.T
print("\nRec.2020 saturated sweep, fraction outside sRGB:",np.mean((lin<0).any(1)))
for f in ("Portra 400","Velvia 50"):
    v=M.variants(f)[0]
    o=lab(model.film_linear(f,lin,deep_black=v["deep"],k=v["k"])@M.M_SRGB_XYZ.T); n=lab(M.render(f,X,v))
    print(f,"v2 L* range %.0f..%.0f, C* %.0f..%.0f | v3 L* %.0f..%.0f, C* %.0f..%.0f"%(o[:,0].min(),o[:,0].max(),np.hypot(o[:,1],o[:,2]).min(),np.hypot(o[:,1],o[:,2]).max(),n[:,0].min(),n[:,0].max(),np.hypot(n[:,1],n[:,2]).min(),np.hypot(n[:,1],n[:,2]).max()))

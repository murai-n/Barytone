import sys; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, warnings; warnings.filterwarnings("ignore")
import model3 as M
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
XYZ=colour.adaptation.chromatic_adaptation_VonKries(colour.xyY_to_XYZ(np.array(list(cc.data.values()))),colour.xy_to_XYZ(cc.illuminant),M.D65W)
d65=colour.XYZ_to_xy(M.D65W); L0=colour.XYZ_to_Lab(XYZ,d65); C0=np.hypot(L0[:18,1],L0[:18,2]); h0=np.degrees(np.arctan2(L0[:18,2],L0[:18,1]))
for pid,u in M.PAPERS.items(): print(pid,u["name"],"| paper Dmin (R,G,B):",np.round(u["D"][0],3),"Dmax:",np.round(u["D"][-1],2))
print("\nfilm         paper    k     chroma  hue   grays L* (in: 95 81 67 51 36 21)        grays a*,b*")
for f in [x for x in M.ALL if M.KIND[x]=="neg"]:
    for pid in M.PAPERS:
        for k in (0.0,):
            o=M.render(f,XYZ,dict(paper=pid,k=k)); L=colour.XYZ_to_Lab(o,d65); C=np.hypot(L[:18,1],L[:18,2]); h=np.degrees(np.arctan2(L[:18,2],L[:18,1]))
            print(f"{f:12s} {pid:8s} {k:.2f}  {C.mean()/C0.mean():.3f}  {np.abs((h-h0+180)%360-180).mean():4.1f}  {' '.join('%3.0f'%v for v in L[18:,0])}   {' '.join('%+.1f,%+.1f'%(p,q) for p,q in L[18:,1:])}")

import sys, json; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, warnings; warnings.filterwarnings("ignore")
import model3 as M
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
XYZ=colour.adaptation.chromatic_adaptation_VonKries(colour.xyY_to_XYZ(np.array(list(cc.data.values()))),colour.xy_to_XYZ(cc.illuminant),M.D65W)[:18]
d65xy=colour.XYZ_to_xy(M.D65W); L0=colour.XYZ_to_Lab(XYZ,d65xy); C0=np.hypot(L0[:,1],L0[:,2]).mean()
def chroma(f,v): L=colour.XYZ_to_Lab(M.render(f,XYZ,v),d65xy); return np.hypot(L[:,1],L[:,2]).mean()/C0
def solve(f,deep):
    lo,hi=-0.5,2.0
    for _ in range(40):
        k=(lo+hi)/2
        if chroma(f,dict(deep=deep,k=k))<1: lo=k
        else: hi=k
    return round((lo+hi)/2,3)
K=dict(kodak_neg=solve("Portra 400",True),fuji_neg=solve("Pro 400H",True),slide=solve("Provia 100F",False))
K["slide_vivid"]=round(K["slide"]+0.361,3)
print(K); json.dump(K,open("/home/claude/m3/k3.json","w"))

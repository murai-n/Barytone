import sys; sys.path.insert(0,"/home/claude/scripts")
import json, numpy as np
from scipy.signal import savgol_filter
import model
from model import *
F2=json.load(open("/home/claude/work2/films2.json"))
NEW=["Pro 400H","Provia 100F","Velvia 50","Ektachrome E100"]
KIND={f:"neg" for f in ORDER}; ISO={"Portra 160":160,"Portra 400":400,"Ektar 100":100}
K_FILM={}
for f in NEW:
    v=F2[f]; KIND[f]=v["kind"]; ISO[f]=v["iso"]; ch={}
    for k in "RGB":
        x=np.array(v["ch"][k]["x"]); d=np.array(v["ch"][k]["d"])
        if f in ("Velvia 50","Provia 100F"): d=savgol_filter(d,41,3)
        if v["kind"]=="pos":   # enforce monotone decreasing, flat extrapolation
            d=np.minimum.accumulate(d)
        ch[k]=dict(x=x.tolist(),d=d.tolist())
    model.sp[f]=dict(sens={k:v["sens"][k] for k in ("blue","green","red")})
    if v["kind"]=="neg":
        ref=float(np.log10(14.4/v["iso"])); model.res[f]=dict(ref=ref,ch=ch); model.summ[f]={}
        for k in "RGB":
            xs=np.linspace(ref-0.3,min(ref+1.5,ch[k]["x"][-1]),60); g=float(np.polyfit(xs,np.interp(xs,ch[k]["x"],ch[k]["d"]),1)[0])
            model.summ[f][k]=dict(gamma=g,dref=float(np.interp(ref,ch[k]["x"],ch[k]["d"])),dmin=float(min(ch[k]["d"])))
    else:
        ref=float(np.log10(10/v["iso"]))   # ISO 2240: mid-tone exposure H_m = 10/S (same basis as the negatives)
        model.res[f]=dict(ref=ref,ch=ch); model.summ[f]={k:dict(gamma=-1.0,dref=float(np.interp(ref,ch[k]["x"],ch[k]["d"])),dmin=float(min(ch[k]["d"]))) for k in "RGB"}
ALL=ORDER+NEW
def render_lin(film,lin,variant="deepblack",k=None):
    kk=K_FILM.get(film,model.INTERIMAGE_K) if k is None else k
    return film_linear(film,lin,deep_black=(variant=="deepblack" and KIND[film]=="neg"),k=kk)
if __name__=="__main__":
    for f in NEW:
        r=model.res[f]["ref"]; s=model.summ[f]; iso=ISO[f]
        print(f"{f:16s} {KIND[f]} ref logH {r:.3f}  (10/S: {np.log10(10/iso):.3f}, 8/S: {np.log10(8/iso):.3f}, 14.4/S: {np.log10(14.4/iso):.3f})  gamma/dref:",{k:(round(s[k]['gamma'],3),round(s[k]['dref'],2),round(s[k]['dmin'],2)) for k in 'RGB'})
        if KIND[f]=="pos":
            c=model.res[f]["ch"]["G"]; xs=np.linspace(r-0.3,r+0.3,30); print("    mid-tone slope (G) %.2f ; D at ref-2 stops %.2f, ref+2 stops %.2f, Dmax %.2f"%(-np.polyfit(xs,np.interp(xs,c["x"],c["d"]),1)[0],np.interp(r-0.602,c["x"],c["d"]),np.interp(r+0.602,c["x"],c["d"]),max(c["d"])))
        print("    matrix diag",np.round(np.diag(matrix(f)),3))

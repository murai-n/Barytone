import json, csv, numpy as np, pdfplumber
OUT="/home/claude/out/"
F={
 "Portra 160": dict(path="/mnt/user-data/uploads/a874eeb8-e4051.pdf", sx=(73.8,274.2), sy=(348.0,499.6), syr=(3.0,-1.0), dx=(355.1,539.5), dy=(101.2,285.5)),
 "Portra 400": dict(path="/mnt/user-data/uploads/4dfc4cff-e4050_Kodak_Portra_400.pdf", sx=(76.2,276.7), sy=(343.1,494.6), syr=(4.0,0.0), dx=(357.1,541.8), dy=(103.7,288.1)),
 "Ektar 100":  dict(path="/mnt/user-data/uploads/a31aa11d-e4046.pdf", sx=(74.2,274.7), sy=(356.6,508.0), syr=(3.0,0.0), dx=(357.5,541.8), dy=(106.0,290.4)),
}
def flat(c,H):
    out=[];cur=None
    for seg in c["path"]:
        cmd=seg[0];pts=seg[1:]
        if cmd in("m","l"): cur=pts[-1]; out.append(cur)
        elif cmd=="c":
            p0=np.array(cur);p1,p2,p3=[np.array(p) for p in pts]
            for t in np.linspace(0,1,13)[1:]: out.append(tuple((1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t**2*p2+t**3*p3))
            cur=tuple(p3)
    a=np.array(out); ref=np.array(c["pts"])
    if abs(a[0,1]-ref[0,1])>1: a[:,1]=H-a[:,1]
    return a
res={}
for film,f in F.items():
    pg=pdfplumber.open(f["path"]).pages[3]
    sens=[c for c in pg.curves if 40<c["x0"] and c["x1"]<310 and 300<c["top"] and c["bottom"]<520 and len(c["pts"])>3 and c["height"]>40]
    sens.sort(key=lambda c:c["x1"]); assert len(sens)==3,(film,len(sens))
    S={}
    for name,c in zip(("blue","green","red"),sens):
        a=flat(c,pg.height)
        wl=250+(a[:,0]-f["sx"][0])/(f["sx"][1]-f["sx"][0])*500
        ls=f["syr"][0]+(a[:,1]-f["sy"][0])/(f["sy"][1]-f["sy"][0])*(f["syr"][1]-f["syr"][0])
        mono=np.all(np.diff(wl)>-0.5) or np.all(np.diff(wl)<0.5)
        o=np.argsort(wl); S[name]=dict(wl=wl[o].tolist(),logS=ls[o].tolist())
        print(film,name,"wl %.0f-%.0f logS max %.2f at %.0f nm"%(wl.min(),wl.max(),ls.max(),wl[np.argmax(ls)]),"monotone-x",mono)
    dye=[c for c in pg.curves if 310<c["x0"] and c["x1"]<600 and 90<c["top"] and c["bottom"]<300 and len(c["pts"])>15]
    dye.sort(key=lambda c:c["top"]); assert len(dye)==2
    Dy={}
    for name,c in zip(("midscale_neutral","dmin"),dye):
        a=flat(c,pg.height)
        wl=400+(a[:,0]-f["dx"][0])/(f["dx"][1]-f["dx"][0])*300
        d=2.5-(a[:,1]-f["dy"][0])/(f["dy"][1]-f["dy"][0])*2.5
        o=np.argsort(wl); Dy[name]=dict(wl=wl[o].tolist(),d=d[o].tolist())
        print(film,name,"wl %.0f-%.0f D %.2f-%.2f"%(wl.min(),wl.max(),d.min(),d.max()))
    res[film]=dict(sens=S,dye=Dy)
json.dump(res,open("/home/claude/work/spectral.json","w"))
with open(OUT+"spectral_sensitivity.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["film","wavelength_nm","logS_blue_layer","logS_green_layer","logS_red_layer"])
    for film in F:
        for wl in range(380,701,5):
            row=[film,wl]
            for n in ("blue","green","red"):
                s=res[film]["sens"][n]; row.append(round(float(np.interp(wl,s["wl"],s["logS"])),3) if s["wl"][0]<=wl<=s["wl"][-1] else "")
            w.writerow(row)
with open(OUT+"spectral_dye_density.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["film","wavelength_nm","D_midscale_neutral","D_min"])
    for film in F:
        for wl in range(400,701,5):
            row=[film,wl]
            for n in ("midscale_neutral","dmin"):
                s=res[film]["dye"][n]; row.append(round(float(np.interp(wl,s["wl"],s["d"])),3) if s["wl"][0]-1<=wl<=s["wl"][-1]+1 else "")
            w.writerow(row)

import sys, json, pdfplumber, numpy as np
FILMS = {
 "Portra 400": dict(path="/mnt/user-data/uploads/4dfc4cff-e4050_Kodak_Portra_400.pdf", fx=(81.2,265.6), xr=(-4,1), fy=(102.9,287.4), ref=-1.44),
 "Portra 160": dict(path="/mnt/user-data/uploads/a874eeb8-e4051.pdf", fx=(81.4,266.0), xr=(-4,1), fy=(102.1,286.6), ref=-1.051),
 "Ektar 100":  dict(path="/mnt/user-data/uploads/a31aa11d-e4046.pdf", fx=(81.2,265.7), xr=(-3,2), fy=(107.9,292.4), ref=-0.84),
}
def flatten(c, H):
    path = c.get("path")
    out=[]
    if path:
        cur=None
        for seg in path:
            cmd=seg[0]; pts=seg[1:]
            if cmd in ("m","l"):
                cur=pts[-1]; out.append(cur)
            elif cmd=="c":
                p0=np.array(cur); p1,p2,p3=[np.array(p) for p in pts]
                for t in np.linspace(0,1,21)[1:]:
                    out.append(tuple((1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t**2*p2+t**3*p3))
                cur=tuple(p3)
        return out, "bezier"
    return c["pts"], "pts"
res={}
for name,f in FILMS.items():
    pg=pdfplumber.open(f["path"]).pages[3]
    cs=[c for c in pg.curves if c["x1"]<310 and c["bottom"]<300 and c["top"]>90 and len(c["pts"])>5]
    cs.sort(key=lambda c:c["top"])
    assert len(cs)==3, len(cs)
    film={}
    for ch,c in zip("BGR",cs):
        pts,mode=flatten(c, pg.height)
        pts=np.array(pts)
        # detect y convention: compare with c["pts"] (top-based)
        ref=np.array(c["pts"])
        if abs(pts[0,1]-ref[0,1])>1: pts[:,1]=pg.height-pts[:,1]
        x=f["xr"][0]+(pts[:,0]-f["fx"][0])/(f["fx"][1]-f["fx"][0])*(f["xr"][1]-f["xr"][0])
        d=4.0-(pts[:,1]-f["fy"][0])/(f["fy"][1]-f["fy"][0])*4.0
        o=np.argsort(x); x=x[o]; d=d[o]
        ux,idx=np.unique(np.round(x,5),return_index=True)
        film[ch]=dict(x=ux.tolist(), d=d[idx].tolist())
        print(name,ch,mode,len(ux),"logH %.2f..%.2f D %.2f..%.2f"%(ux[0],ux[-1],d[idx][0],d[idx][-1]))
    res[name]=dict(ref=f["ref"],ch=film)
json.dump(res,open(sys.argv[1],"w"))

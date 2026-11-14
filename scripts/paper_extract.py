import json, numpy as np, pdfplumber
from PIL import Image
from scipy import ndimage as ndi
from scipy.signal import savgol_filter
U="/mnt/user-data/uploads/"
def lin(v,a,va,b,vb): return va+(np.asarray(v,float)-a)/(b-a)*(vb-va)
def flat(c,H,n=16):
    out=[];cur=None
    for seg in c["path"]:
        cmd=seg[0];pts=seg[1:]
        if cmd in("m","l"): cur=pts[-1]; out.append(cur)
        elif cmd=="c":
            p0=np.array(cur);p1,p2,p3=[np.array(p) for p in pts]
            for t in np.linspace(0,1,n+1)[1:]: out.append(tuple((1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t**2*p2+t**3*p3))
            cur=tuple(p3)
    a=np.array(out); ref=np.array(c["pts"])
    if abs(a[0,1]-ref[0,1])>1: a[:,1]=H-a[:,1]
    return a
def tidy(x,y):
    o=np.argsort(x); x=np.asarray(x)[o]; y=np.asarray(y)[o]; u,i=np.unique(np.round(x,4),return_index=True); return u, y[i]
out={}
# ---------- Kodak Endura Premier (vector)
pdf=pdfplumber.open(U+"9f48819f-premier-paper_technical-data_1983285.pdf"); p4,p5=pdf.pages[3],pdf.pages[4]
cs=sorted([c for c in p4.curves if 364<c["x0"] and c["x1"]<550 and 72<c["top"] and c["bottom"]<258 and len(c["pts"])>=10],key=lambda c:c["top"]); assert len(cs)==3
ch={}
for k,c in zip("RGB",cs):
    a=flat(c,p4.height); x,d=tidy(lin(a[:,0],364.7,-3.0,549.2,0.0),lin(a[:,1],257.2,0.0,72.5,3.0)); ch[k]=dict(x=x.tolist(),d=d.tolist())
    print("Endura",k,"logH %.2f..%.2f D %.2f..%.2f"%(x[0],x[-1],d.min(),d.max()))
dy=[c for c in p5.curves if 76<c["x0"] and c["x1"]<262 and 86<c["top"] and c["bottom"]<272 and len(c["pts"])>=20]; assert len(dy)==3
dyes={}
for c in dy:
    a=flat(c,p5.height); wl,d=tidy(lin(a[:,0],76.8,400,261.3,700),lin(a[:,1],270.9,0.0,86.6,2.5))
    nm="yellow" if wl[np.argmax(d)]<500 else ("magenta" if wl[np.argmax(d)]<600 else "cyan"); dyes[nm]=dict(wl=wl.tolist(),d=d.tolist())
    print("Endura dye",nm,"peak %.2f at %.0f"%(d.max(),wl[np.argmax(d)]))
out["endura"]=dict(ch=ch,dyes=dyes,name="Kodak Endura Premier")
# ---------- Fujicolor Crystal Archive Type CA dyes (colour raster)
a=np.asarray(Image.open("img/ca-004.png").convert("RGB")).astype(int); R,G,B=a[...,0],a[...,1],a[...,2]
masks={"yellow":(R>200)&(G>200)&(B<120),"magenta":(R>180)&(G<90)&(B>180),"cyan":(R<120)&(G>190)&(B>190)}
xs=lin(np.arange(a.shape[1]),231.5,500,586.5,700); dyes={}
for k,m in masks.items():
    m=ndi.binary_opening(m,np.ones((2,2))); px=[];pd=[];prev=None
    for j in range(a.shape[1]):
        r=np.where(m[60:455,j])[0]+60
        if 401<=xs[j]<=748 and len(r)>=2:
            sp=np.split(r,np.where(np.diff(r)>3)[0]+1); cands=[s.mean() for s in sp if len(s)>=2]
            if not cands: continue
            y=cands[0] if prev is None else min(cands,key=lambda q:abs(q-prev)); prev=y; px.append(xs[j]); pd.append(float(lin(y,449,0.0,129,1.0)))
    w=np.arange(401,748,1.0); v=ndi.uniform_filter1d(np.interp(w,px,pd),5,mode="nearest"); dyes[k]=dict(wl=w.tolist(),d=v.tolist())
    print("CA dye",k,"wl %.0f..%.0f peak %.2f at %.0f"%(px[0],px[-1],v.max(),w[v.argmax()]))
# ---------- FUJIFLEX characteristic curves (black raster, relative log H)
g=np.asarray(Image.open("img/flex_char.png").convert("L")).astype(int); m=ndi.binary_opening(g<120,np.ones((3,3)))
m[:,:110]=False; m[:,950:]=False; m[:20,:]=False; m[765:,:]=False; m[:150,100:600]=False; m[560:770,110:300]=False
xg=lambda c: (c-484.0)/(94.6/0.5); dg=lambda r: lin(r,769.5,0.0,13.5,4.0)
up=[];lo=[]
for c in range(300,700):
    r=np.where(m[:,c])[0]
    if len(r)==0: continue
    sp=np.split(r,np.where(np.diff(r)>2)[0]+1); runs=[(s.mean(),len(s)) for s in sp]
    runs=[q for q in runs if q[1]>=2]
    if not runs: continue
    top=min(runs)[0]; bot=max(runs)[0]
    up.append((xg(c),dg(top))); lo.append((xg(c),dg(bot)))
up=np.array(up); lo=np.array(lo)
xx=np.arange(up[:,0].min(),up[:,0].max(),0.01)
dU=savgol_filter(np.interp(xx,up[:,0],up[:,1]),31,3); dL=savgol_filter(np.interp(xx,lo[:,0],lo[:,1]),31,3)
dU=np.maximum.accumulate(dU); dL=np.maximum.accumulate(np.minimum(dL,dU))
print("FLEX RG D %.2f..%.2f  B D %.2f..%.2f over relative logH %.2f..%.2f"%(dU.min(),dU.max(),dL.min(),dL.max(),xx[0],xx[-1]))
out["crystal"]=dict(ch=dict(R=dict(x=xx.tolist(),d=dU.tolist()),G=dict(x=xx.tolist(),d=dU.tolist()),B=dict(x=xx.tolist(),d=dL.tolist())),dyes=dyes,name="Fujicolor Crystal Archive (dyes: Type CA, curve shape: FUJIFLEX)")
json.dump(out,open("/home/claude/paper/papers.json","w"))

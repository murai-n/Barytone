import json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
def lin(v,a,va,b,vb): return va+(np.asarray(v,float)-a)/(b-a)*(vb-va)
out={}
# ---- Provia (colour raster)
a=np.asarray(Image.open("provia_dye.png").convert("RGB")).astype(int); R,G,B=a[...,0],a[...,1],a[...,2]
masks={"yellow":(R>200)&(G>190)&(B<120),"magenta":(R>170)&(G<90)&(B>80)&(B<200),"cyan":(R<120)&(G>140)&(B>190)}
xs=lin(np.arange(a.shape[1]),217.5,400,1206,700); ds=lin(np.arange(a.shape[0]),172,1.0,511,0.5)
dbg=np.stack([a.mean(-1)]*3,-1).astype(np.uint8)
prov={}
for k,m in masks.items():
    m=ndi.binary_opening(m,np.ones((2,2)))
    px=[];pd=[]
    for j in range(a.shape[1]):
        r=np.where(m[:,j])[0]
        if 383<=xs[j]<=718 and len(r)>=2:
            # if multiple runs, take the one closest to previous
            sp=np.split(r,np.where(np.diff(r)>3)[0]+1); cands=[s.mean() for s in sp]
            y=cands[0] if not pd else min(cands,key=lambda c:abs(c-pdrow)); pdrow=y
            px.append(xs[j]); pd.append(float(lin(y,172,1.0,511,0.5))); dbg[int(y)-2:int(y)+3,j]=(255,0,0)
    w=np.arange(385,716,1.0); v=ndi.uniform_filter1d(np.interp(w,px,pd),5,mode="nearest")
    prov[k]=dict(wl=w.tolist(),d=v.tolist()); print("provia",k,"wl %.0f..%.0f peak %.3f at %.0f"%(px[0],px[-1],v.max(),w[v.argmax()]),"at 440/545/610:",np.round(np.interp([440,545,610],w,v),3))
Image.fromarray(dbg).resize((a.shape[1]//2,a.shape[0]//2)).save("dbg_provia_dye.png")
out["Provia 100F"]=prov
# ---- Velvia (black raster): tracking
g=np.asarray(Image.open("velvia_dye.png").convert("L")).astype(int); m=ndi.binary_opening(g<120,np.ones((5,5)))
m[:20,:]=False; m[805:,:]=False; m[:,:134]=False; m[:,1209:]=False
m[40:150,600:1100]=False  # legend text
def runs(col):
    r=np.where(col)[0]
    if len(r)==0: return []
    sp=np.where(np.diff(r)>1)[0]; st=np.r_[r[0],r[sp+1]]; en=np.r_[r[sp],r[-1]]; return [((s+e)/2,e-s+1) for s,e in zip(st,en)]
def track(c0,y0,step,tol=6,maxgap=40):
    pts=[(c0,y0)]; gap=0; c=c0+step
    while 134<=c<1209 and gap<=maxgap:
        rs=runs(m[:,c]); k=min(len(pts),22)
        if len(pts)>=4:
            pc=np.array([p[0] for p in pts[-k:]]); py=np.array([p[1] for p in pts[-k:]]); sl=np.polyfit(pc,py,1)[0]
        else: sl=0
        pred=pts[-1][1]+sl*(c-pts[-1][0]); best=min(rs,key=lambda r:abs(r[0]-pred)) if rs else None
        if best and best[1]>11 and abs(best[0]-pred)<=best[1]: pts.append((c,pred)); gap=0
        elif best and abs(best[0]-pred)<=tol+abs(sl)*1.5: pts.append((c,best[0])); gap=0
        else: gap+=1
        c+=step
    return pts
wx=lambda w:int(round(lin(w,400,191,700,1152.5)))
vel={}; dbg=np.stack([g]*3,-1).astype(np.uint8)
for k,w0,col in (("yellow",449,(255,170,0)),("magenta",545,(220,0,140)),("cyan",660,(0,150,255))):
    rs=[r for r in runs(m[:,wx(w0)]) if r[0]<260]; assert rs,(k,runs(m[:,wx(w0)]))
    pts=track(wx(w0),rs[0][0],-1)[::-1]+track(wx(w0),rs[0][0],+1)[1:]
    for c,y in pts: dbg[int(y)-2:int(y)+3,c]=col
    wl=lin([p[0] for p in pts],191,400,1152.5,700); d=lin([p[1] for p in pts],171.5,1.0,811.5,0.0)
    w=np.arange(385,716,1.0); v=np.interp(w,wl,d,left=np.nan,right=np.nan)
    print("velvia",k,"tracked wl %.0f..%.0f"%(wl.min(),wl.max()))
    vel[k]=dict(wl=w.tolist(),d=v.tolist(),tracked=[float(wl.min()),float(wl.max())])
Image.fromarray(dbg).resize((g.shape[1]//2,g.shape[0]//2)).save("dbg_velvia_dye.png")
json.dump(dict(prov=out,vel=vel),open("/home/claude/work2/dyes_raw.json","w"))

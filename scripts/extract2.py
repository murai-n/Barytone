import sys, json, numpy as np, pdfplumber
from PIL import Image
from scipy import ndimage as ndi
U="/mnt/user-data/uploads/"; S=400/72
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
def lin(v,a,va,b,vb): return va+(np.asarray(v)-a)/(b-a)*(vb-va)
def tidy(x,y):
    o=np.argsort(x,kind="stable"); x=np.asarray(x)[o]; y=np.asarray(y)[o]; ux,i=np.unique(np.round(x,4),return_index=True); return ux.tolist(), y[i].tolist()
def pick(pg,xa,ta,xb,tb,minw=25,minpts=3,dash=None):
    r=[c for c in pg.curves if xa<=c["x0"] and c["x1"]<=xb and ta<=c["top"] and c["bottom"]<=tb and len(c["pts"])>=minpts and c["width"]>minw and c["height"]>20 and not c.get("fill")]
    return r
out={}
# ---------- E100 (vector)
pdf=pdfplumber.open(U+"f4627662-e4000_ektachrome_100.pdf"); p3,p4=pdf.pages[2],pdf.pages[3]
cs=sorted(pick(p3,370,360,560,545),key=lambda c:c["top"]); assert len(cs)==3
ch={}
for name,c in zip("BGR",cs):
    a=flat(c,p3.height); ch[name]=dict(zip(("x","d"),tidy(lin(a[:,0],368.7,-3.0,553.9,1.0),lin(a[:,1],358.6,4.0,543.0,0.0))))
ss=sorted(pick(p4,70,105,280,260,minpts=50),key=lambda c:c["x1"]); assert len(ss)==3
sens={}
for name,c in zip(("blue","green","red"),ss):
    a=flat(c,p4.height); sens[name]=dict(zip(("wl","logS"),tidy(lin(a[:,0],74.3,250,274.9,750),lin(a[:,1],107.0,2.0,258.5,-2.0))))
dy=pick(p4,70,345,275,505,minpts=30); dyes={}
for c in dy:
    a=flat(c,p4.height); wl=lin(a[:,0],70.6,400,271.1,700); d=lin(a[:,1],349.7,1.4,501.1,0.0); pk=wl[np.argmax(d)]
    nm="neutral_sum" if d.min()>0.5 else ("yellow" if pk<500 else "magenta" if pk<600 else "cyan"); dyes[nm]=dict(zip(("wl","d"),tidy(wl,d)))
out["Ektachrome E100"]=dict(kind="pos",iso=100,ch=ch,sens=sens,dyes=dyes)
# ---------- Pro 400H (vector, outlined text -> manual axes)
pg=pdfplumber.open(U+"5fcba9a4-films_pro-400h_datasheet_01.pdf").pages[7]
cs=sorted(pick(pg,78,105,286,250,minw=100),key=lambda c:c["top"]); assert len(cs)==3,len(cs)
ch={}
for name,c in zip("BGR",cs):
    a=flat(c,pg.height); ch[name]=dict(zip(("x","d"),tidy(lin(a[:,0],78.6,-4.0,285.5,1.0),lin(a[:,1],105.0,3.5,249.6,0.0))))
ss=pick(pg,336,104,516,259,minw=30); sens={}
for c in ss:
    a=flat(c,pg.height); wl=lin(a[:,0],346.9,400,504.5,700); ls=lin(a[:,1],155.8,1.0,207.0,0.0)
    nm="cyan4th" if c.get("dash") and c["dash"][0] else ("blue" if wl.max()<530 else "green" if wl.max()<610 else "red"); sens[nm]=dict(zip(("wl","logS"),tidy(wl,ls)))
out["Pro 400H"]=dict(kind="neg",iso=400,ch=ch,sens=sens)
# ---------- Provia 100F: sens vector, char raster (colour)
pg=pdfplumber.open(U+"6abf16f9-films_provia-100f_datasheet_01.pdf").pages[5]
ss=sorted(pick(pg,338,172,539,349,minw=40),key=lambda c:c["x1"]); assert len(ss)==3,len(ss)
sens={}
for name,c in zip(("blue","green","red"),ss):
    a=flat(c,pg.height); sens[name]=dict(zip(("wl","logS"),tidy(lin(a[:,0],349.6,400,527.9,700),lin(a[:,1],203.7,1.0,322.5,-1.0))))
im=np.asarray(Image.open("pv400-6.png").convert("RGB")).astype(int)[int(162*S):int(375*S),int(53*S):int(294*S)]
R,G,B=im[...,0],im[...,1],im[...,2]
cls={"R":(R>170)&(G<110)&(B<110),"G":(G>110)&(R<90)&(B<140)&(G>B+25),"B":(B>95)&(R<110)&(G<110)&(B>R+40)}
cols=np.arange(im.shape[1]); xs=lin(cols,169.0,-3.5,1290.0,1.0); rows=np.arange(im.shape[0]); ds=lin(rows,53.0,4.0,1046.5,0.0)
tr={}
for k,m in cls.items():
    m=m.copy(); m[(ds[:,None]<2.0)&(xs[None,:]<-2.3)]=False   # legend
    px,pd=[],[]
    for j in cols:
        r=np.where(m[:,j])[0]
        if len(r)>=3: px.append(xs[j]); pd.append(float(np.median(ds[r])))
    tr[k]=(np.array(px),np.array(pd)); print("provia",k,len(px),"x %.2f..%.2f"%(px[0],px[-1]),"D %.2f..%.2f"%(max(pd),min(pd)))
ch={}
gx=np.arange(-3.35,0.851,0.01)
red=np.interp(gx,*tr["R"])
for k in "RGB":
    x,d=tr[k]
    if k=="R": v=red
    else:
        v=np.interp(gx,x,d); hi=x.max(); v=np.where(gx<=hi,v,red)
        # blend last 0.1 into red to avoid step
        w=np.clip((hi-gx)/0.1,0,1); v=np.where(gx<=hi,w*v+(1-w)*red,red)
    v=ndi.uniform_filter1d(v,7,mode="nearest"); ch[k]=dict(x=gx.round(3).tolist(),d=v.tolist())
out["Provia 100F"]=dict(kind="pos",iso=100,ch=ch,sens=sens)
# ---------- Velvia 50: all raster (black)
full=np.asarray(Image.open("vv400-8.png").convert("L")).astype(int)
def runs(col):
    r=np.where(col)[0]; 
    if len(r)==0: return []
    sp=np.where(np.diff(r)>1)[0]; st=np.r_[r[0],r[sp+1]]; en=np.r_[r[sp],r[-1]]; return [((a+b)/2,b-a+1) for a,b in zip(st,en)]
DBG={}
def track(mask,c0,y0,step,tol=28,maxgap=70):
    pts=[(c0,y0)]; gap=0; c=c0+step
    while 0<=c<mask.shape[1] and gap<=maxgap:
        rs=runs(mask[:,c])
        if len(pts)>=6:
            k=min(len(pts),8); pc=np.array([p[0] for p in pts[-k:]]); py=np.array([p[1] for p in pts[-k:]]); sl=np.polyfit(pc,py,1)[0] if np.ptp(pc)>0 else 0
        else: sl=0
        pred=pts[-1][1]+sl*(c-pts[-1][0])
        best=min(rs,key=lambda r:abs(r[0]-pred)) if rs else None
        if best and abs(best[0]-pred)<=tol+abs(sl)*2: pts.append((c,best[0])); gap=0
        else: gap+=1
        c+=step
    return pts
def thick(box,k=6):
    x0,t0,x1,t1=box; im=full[int(t0*S):int(t1*S),int(x0*S):int(x1*S)]; return ndi.binary_opening(im<128,structure=np.ones((k,k)))
def overlay(box,tracks,fn):
    x0,t0,x1,t1=box; im=np.stack([full[int(t0*S):int(t1*S),int(x0*S):int(x1*S)]]*3,-1).astype(np.uint8).copy()
    for col,pts in zip(((255,0,0),(0,170,0),(0,0,255)),tracks):
        for c,y in pts: im[max(0,int(y)-2):int(y)+3,max(0,int(c)-1):int(c)+2]=col
    Image.fromarray(im).resize((im.shape[1]*2//3,im.shape[0]*2//3)).save(fn)
m=thick((60,105,287,309),3); cx=lambda x: int(round(lin(x,-3.0,149.0,1.5,1251.5))); 
m[int(lin(1.2,4.0,27.5,0.0,1009.0)):,:cx(-2.2)]=False; m[:int(lin(2.2,4.0,27.5,0.0,1009.0)),cx(-1.2):]=False; m[:34,:]=False; m[1000:,:]=False; m[:,:156]=False; m[:,1244:]=False
rowD=lambda r: lin(r,27.5,4.0,1009.0,0.0); colX=lambda c: lin(c,149.0,-3.0,1251.5,1.5)
seed=[r for r in runs(m[:,cx(-2.75)]) if 3.2<rowD(r[0])<3.45]; assert len(seed)==1,seed
rp=track(m,cx(-2.75),seed[0][0],+1,tol=12,maxgap=40)+track(m,cx(-2.75),seed[0][0],-1,tol=8,maxgap=10)[1:]
rx,rd=tidy(colX([p[0] for p in rp]),rowD(np.array([p[1] for p in rp]))); rx=np.array(rx); rd=np.array(rd)
two=[];one=[]
for c in range(cx(-2.83),cx(-1.72)):
    x=colX(c); rr=np.interp(x,rx,rd)
    cand=[rowD(r[0]) for r in runs(m[:,c]) if rowD(r[0])>rr+0.05 and r[1]<=14 and abs(rowD(r[0])-3.5)>0.015 and rowD(r[0])<3.9]
    if len(cand)==2: two.append((x,max(cand),min(cand)))
    elif len(cand)==1: one.append((x,cand[0]))
two=np.array(two); one=np.array(one); print("velvia shadows: two-run cols",len(two),"one-run cols",len(one))
pg_=np.polyfit(two[:,0],two[:,1],4); pb_=np.polyfit(two[:,0],two[:,2],4)
for it in range(2):
    dg=np.abs(np.polyval(pg_,one[:,0])-one[:,1]); db=np.abs(np.polyval(pb_,one[:,0])-one[:,1]); isg=dg<db
    gxs=np.r_[two[:,0],one[isg,0]]; gds=np.r_[two[:,1],one[isg,1]]; bxs=np.r_[two[:,0],one[~isg,0]]; bds=np.r_[two[:,2],one[~isg,1]]
    pg_=np.polyfit(gxs,gds,5); pb_=np.polyfit(bxs,bds,5)
gx=np.arange(-2.8,1.101,0.01); red=np.interp(gx,rx,rd); ch={}; TR=[[],[],[]]
for i,(name,pf,xm) in enumerate((("G",pg_,gxs.max()),("B",pb_,bxs.max()),("R",None,None))):
    if pf is None: v=red
    else:
        v=np.polyval(pf,gx); w=np.clip((xm-gx)/0.08,0,1); v=np.where(gx<=xm,np.maximum(w*v+(1-w)*red,red),red)
    v=ndi.uniform_filter1d(v,9,mode="nearest"); ch[name]=dict(x=gx.round(3).tolist(),d=v.tolist())
    TR[i]=[(lin(x,-3.0,149.0,1.5,1251.5),lin(d,4.0,27.5,0.0,1009.0)) for x,d in zip(gx,v)]
    print("velvia",name,"D(-2.8) %.2f D(-2.0) %.2f D(-1.0) %.2f D(0) %.2f D(1.0) %.2f"%tuple(np.interp([-2.8,-2.0,-1.0,0,1.0],gx,v)))
overlay((60,105,287,309),TR,"dbg_velvia_char.png")
ms=thick((312,105,533,308),5); ms[:42,:]=False; ms[988:,:]=False; ms[:,:137]=False; ms[:,1206:]=False; TS=[]; wx=lambda w: int(round(lin(w,400,191.0,700,1155.5))); sens={}
for name,w0,lo,hi in (("blue",430,380,496),("green",552,484,594),("red",648,577,694)):
    rs=runs(ms[:,wx(w0)]); rs=[r for r in rs if 300<r[0]<700]; assert len(rs)==1,(name,rs)
    sub=ms.copy(); sub[:,:wx(lo)]=False; sub[:,wx(hi):]=False
    pts=track(sub,wx(w0),rs[0][0],+1,tol=30,maxgap=4)+track(sub,wx(w0),rs[0][0],-1,tol=30,maxgap=4)[1:]; TS.append(pts)
    wl=lin([p[0] for p in pts],191.0,400,1155.5,700); ls=lin([p[1] for p in pts],353.0,1.0,674.5,0.0); wl,ls=tidy(wl,ls)
    keep=[i for i,w in enumerate(wl) if {"blue":(380,492),"green":(493,590),"red":(593,694)}[name][0]<=w<={"blue":(380,492),"green":(493,590),"red":(593,694)}[name][1]]; wl=[wl[i] for i in keep]; ls=[ls[i] for i in keep]
    sens[name]=dict(wl=wl,logS=ndi.uniform_filter1d(np.array(ls),5,mode="nearest").tolist()); print("velvia sens",name,"wl %.0f..%.0f logS max %.2f min %.2f"%(wl[0],wl[-1],max(ls),min(ls)))
overlay((312,105,533,308),TS,"dbg_velvia_sens.png")
out["Velvia 50"]=dict(kind="pos",iso=50,ch=ch,sens=sens)
json.dump(out,open("/home/claude/work2/films2.json","w"))
for f,v in out.items():
    print("==",f,v["kind"])
    for k in "RGB": c=v["ch"][k]; print("  ",k,"logH %.2f..%.2f  D %.2f..%.2f"%(c["x"][0],c["x"][-1],max(c["d"]),min(c["d"])))
    for k,s in v["sens"].items(): print("   sens",k,"wl %.0f..%.0f peak %.2f at %.0f"%(s["wl"][0],s["wl"][-1],max(s["logS"]),s["wl"][int(np.argmax(s["logS"]))]))

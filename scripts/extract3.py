import sys, json, re, numpy as np, pdfplumber, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0,"/home/claude/scripts")
from PIL import Image
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
    o=np.argsort(x,kind="stable"); x=np.asarray(x)[o]; y=np.asarray(y)[o]; ux,i=np.unique(np.round(x,4),return_index=True); return ux.tolist(), np.asarray(y)[i].tolist()
U="/mnt/user-data/uploads/"
def words(pg):
    return [(w["text"],w["x0"]+w["width"]/2,(w["top"]+w["bottom"])/2) for w in pg.extract_words() if re.fullmatch(r"-?\d+\.?\d*",w["text"])]
def axis(pg,vals,xr,yr,horiz):
    """fit px->value from tick words whose |value| matches vals (sign may be lost in the PDF)"""
    cand=[(float(t),x,y) for t,x,y in words(pg) if xr[0]<=x<=xr[1] and yr[0]<=y<=yr[1] and any(abs(abs(float(t))-abs(v))<1e-9 for v in vals)]
    # ticks of one axis share the same cross coordinate: keep the largest such group
    import collections
    g=collections.defaultdict(list)
    for t,x,y in cand: g[round((y if horiz else x)/4)].append((t,x,y))
    cand=max(g.values(),key=len)
    pos=sorted(x if horiz else y for _,x,y in cand)
    assert len(pos)==len(vals), (len(pos),vals,cand)
    vv=sorted(vals) if horiz else sorted(vals,reverse=True)   # x grows right, y grows down
    A=np.polyfit(pos,vv,1)
    r=np.abs(np.polyval(A,pos)-np.array(vv)).max(); assert r<abs(A[0])*6, (r,A)
    return lambda p: np.polyval(A,p)
def paths(pg,x0,t0,x1,t1,minw=25,minh=12):
    return [c for c in pg.curves if x0<=c["x0"] and c["x1"]<=x1 and t0<=c["top"] and c["bottom"]<=t1 and not c.get("fill") and (c["x1"]-c["x0"])>minw and (c["bottom"]-c["top"])>minh]
def frags(pg,x0,t0,x1,t1):
    return [c for c in pg.curves if x0<=c["x0"] and c["x1"]<=x1 and t0<=c["top"] and c["bottom"]<=t1 and not c.get("fill")]
def chain(cs,H,eps=3.0):
    """join dash fragments into curves by endpoint proximity"""
    segs=[flat(c,H) for c in cs]; segs=[s for s in segs if len(s)>=2]
    merged=True
    while merged:
        merged=False
        for i in range(len(segs)):
            if merged: break
            for j in range(i+1,len(segs)):
                a,b=segs[i],segs[j]; best=None
                for af,bf in ((0,0),(0,1),(1,0),(1,1)):
                    pa=a[0] if af==0 else a[-1]; pb=b[0] if bf==0 else b[-1]
                    d=np.hypot(pa[0]-pb[0],pa[1]-pb[1])
                    if d<eps and (best is None or d<best[0]): best=(d,af,bf)
                if best:
                    _,af,bf=best
                    if (min(a[:,0].max(),b[:,0].max())-max(a[:,0].min(),b[:,0].min()))>4: continue   # big x overlap: different curves
                    aa=a if af==1 else a[::-1]; bb=b if bf==0 else b[::-1]
                    segs[i]=np.vstack([aa,bb]); del segs[j]; merged=True; break
    return sorted(segs,key=lambda s:-len(s))
def grid(pg,x0,t0,x1,t1):
    ln=[l for l in pg.lines if x0<=l["x0"] and l["x1"]<=x1 and t0<=l["top"] and l["bottom"]<=t1]
    vx=sorted({round(l["x0"],1) for l in ln if abs(l["x0"]-l["x1"])<0.5}); hy=sorted({round(l["top"],1) for l in ln if abs(l["top"]-l["bottom"])<0.5})
    return vx,hy
def monorun(a):
    dx=np.sign(np.diff(a[:,0])); best=(0,0); i=0
    while i<len(dx):
        j=i
        while j<len(dx) and (dx[j]==dx[i] or dx[j]==0): j+=1
        if j-i>best[1]-best[0]: best=(i,j)
        i=j
    return a[best[0]:best[1]+2]
def sens_xy(c,H,fx,fy):
    a=monorun(flat(c,H)); return dict(zip(("wl","logS"),tidy(fx(a[:,0]),fy(a[:,1]))))
def xy(c,H,fx,fy):
    a=flat(c,H); return dict(zip(("x","d"),tidy(fx(a[:,0]),fy(a[:,1]))))
def xy_seg(s,fx,fy): return dict(zip(("x","d"),tidy(fx(s[:,0]),fy(s[:,1]))))
out={}; DYE={}
# ================= Portra 800 (E-4040, p3) =================
pg=pdfplumber.open(U+"704fec0a-e4040_portra_800-2016.pdf").pages[3]; H=pg.height
fx=axis(pg,[-4,-3,-2,-1,0,1],(70,280),(255,275),True); fy=axis(pg,[4,3,2,1,0],(58,85),(60,270),False)
cs=sorted(paths(pg,85,95,285,260),key=lambda c:c["top"]); assert len(cs)==3,len(cs)
ch=dict(zip("BGR",[xy(c,H,fx,fy) for c in cs]))
sx=axis(pg,[250,300,350,400,450,500,550,600,650,700,750],(340,560),(465,482),True); sy=axis(pg,[4,3,2,1,0],(330,352),(305,470),False)
ss=sorted(paths(pg,390,345,545,467),key=lambda c:c["x0"]+c["x1"]); assert len(ss)==3,len(ss)
sens={n:sens_xy(c,H,sx,sy) for n,c in zip(("blue","green","red"),ss)}
out["Portra 800"]=dict(kind="neg",iso=800,ch=ch,sens=sens)
# ================= Gold 200 (E-7022, p3) =================
pg=pdfplumber.open(U+"3b199048-E7022_Gold_200-2016.pdf").pages[3]; H=pg.height
fx=axis(pg,[-3,-2,-1,0,1],(70,280),(288,302),True); fy=axis(pg,[4,3,2,1,0],(55,80),(90,295),False)
cs=sorted(paths(pg,75,150,285,285),key=lambda c:c["top"]); assert len(cs)==3,len(cs)
ch=dict(zip("BGR",[xy(c,H,fx,fy) for c in cs]))
sx=axis(pg,[250,300,350,400,450,500,550,600,650,700,750],(65,290),(498,515),True); sy=axis(pg,[4,3,2,1,0],(52,78),(335,505),False)
segs=chain(frags(pg,80,345,300,500),H)
segs=[s for s in segs if (s[:,0].max()-s[:,0].min())>30]
blue=min(segs,key=lambda s:s[:,0].min()); red=max(segs,key=lambda s:s[:,0].max())
green=max([s for s in segs if s is not blue and s is not red],key=len)
segs=[blue,green,red]
sens={n:dict(zip(("wl","logS"),tidy(sx(s[:,0]),sy(s[:,1])))) for n,s in zip(("blue","green","red"),segs)}
out["Gold 200"]=dict(kind="neg",iso=200,ch=ch,sens=sens)
# ================= Vision3 500T (H-1-5219, p3) =================
pg=pdfplumber.open(U+"171866e4-VISION3-500T-Color-Negative-Film-7219-TECHNICAL-DATA.pdf").pages[3]; H=pg.height
fx=axis(pg,[-4,-3,-2,-1,0,1],(340,560),(108,125),True); fy=axis(pg,[3,2,1,0],(335,355),(115,310),False)
fs=axis(pg,list(range(-8,9)),(340,560),(303,320),True)   # camera stops
cs=sorted(paths(pg,350,115,545,300),key=lambda c:c["top"]); assert len(cs)==3,len(cs)
ch=dict(zip("BGR",[xy(c,H,fx,fy) for c in cs]))
# ref: log H where camera stop = 0
import numpy.polynomial.polynomial as P
xs=np.linspace(350,545,200); stop=fs(xs); x0=np.interp(0,stop,xs); ref500=float(fx(x0))
sx=axis(pg,[250,300,350,400,450,500,550,600,650,700,750],(340,570),(668,688),True); sy=axis(pg,[4,3,2,1,0],(330,355),(505,672),False)
ss=sorted(paths(pg,395,540,560,660),key=lambda c:c["x0"]+c["x1"]); assert len(ss)==3,len(ss)
sens={n:sens_xy(c,H,sx,sy) for n,c in zip(("blue","green","red"),ss)}
out["Vision3 500T"]=dict(kind="neg",iso=500,ch=ch,sens=sens,ref=ref500)
print("Vision3 camera-stop-0 ref logH = %.3f  (10/500 would be %.3f)"%(ref500,np.log10(10/500)))
# ================= Pro 800Z (AF3-177E, p7) =================
pg=pdfplumber.open(U+"7034ba9e-c42dcf4b-110d-ec14-a166-0230ca909e47.pdf").pages[7]; H=pg.height
vx,hy=grid(pg,60,90,310,345)
fx=lambda p: lin(p,99.5,-3.5,265.3,0.5); fy=lambda p: lin(p,126.6,3.0,229.9,0.5)
cs=sorted(paths(pg,60,95,310,345,minh=8),key=lambda c:c["top"]); assert len(cs)==3,(len(cs))
ch=dict(zip("BGR",[xy(c,H,fx,fy) for c in cs]))
vx2,hy2=grid(pg,324,90,565,350)
assert len(vx2)>=4, vx2
sxl=[v for v in vx2 if v>335]; d=np.diff(sxl); 
sx=lambda p: lin(p,sxl[0],400,sxl[-1],400+100*(len(sxl)-1)) if len(sxl)==4 else lin(p,sxl[0],400,sxl[3],700)
dh=np.median(np.diff(hy2))
sy=lambda p,h0=hy2[0],dh=dh: (h0-np.asarray(p))/dh   # 1.0 log per gridline, arbitrary offset
ss=sorted(paths(pg,330,95,520,345,minh=8),key=lambda c:c["top"]-c["bottom"])[:3]   # tallest three: the dashed 4th-layer arc is short
ss=sorted(ss,key=lambda c:c["x0"]+c["x1"])
assert len(ss)==3
print("PZ sens picks:",[("%.0f-%.0f -> %.0f-%.0fnm"%(c["x0"],c["x1"],sx(c["x0"]),sx(c["x1"]))) for c in ss[:3]])
sens={n:sens_xy(c,H,sx,sy) for n,c in zip(("blue","green","red"),ss[:3])}
out["Pro 800Z"]=dict(kind="neg",iso=800,ch=ch,sens=sens)
print("PZ sens x gridlines:",sxl," y gridline pitch %.1f"%dh)
# ================= Pro 160NS (JP, p7) =================
pg=pdfplumber.open(U+"16ee3e09-datasheet_pro160ns_01.pdf").pages[7]; H=pg.height
fx=lambda p: lin(p,110.7,-3.5,266.1,0.0); fy=axis(pg,[4,3.5,3,2.5,2,1.5,1,0.5,0],(70,95),(110,300),False)
cs=sorted(paths(pg,85,105,300,300,minh=8),key=lambda c:c["top"]); assert len(cs)==3,len(cs)
ch=dict(zip("BGR",[xy(c,H,fx,fy) for c in cs]))
sx=axis(pg,[400,500,600,700],(330,540),(290,305),True)
vx3,hy3=grid(pg,315,130,548,310); dh=np.median(np.diff(hy3)); sy=lambda p,h0=hy3[0],dh=dh:(h0-np.asarray(p))/dh
ss=[c for c in paths(pg,325,130,520,300,minh=60)]   # the 4th (cyan) layer is the small dashed arc; keep the three tall layers
ss=sorted(ss,key=lambda c:c["x0"]+c["x1"]); assert len(ss)==3,len(ss)
sens={n:sens_xy(c,H,sx,sy) for n,c in zip(("blue","green","red"),ss)}
out["Pro 160NS"]=dict(kind="neg",iso=160,ch=ch,sens=sens)
print("NS sens y gridline pitch %.1f (lines %s)"%(dh,hy3[:6]))
json.dump(out,open("/home/claude/work3/films3_new_part1.json","w"))
print("part1 ok:",list(out))

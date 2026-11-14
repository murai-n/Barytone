import sys, json, numpy as np, pdfplumber, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0,"/home/claude/ds"); from ex import flat, tidy, pick, chain, chain2, sens_extract, U
def lin(v,a,va,b,vb): return va+(np.asarray(v)-a)/(b-a)*(vb-va)
def letters(p,xa,ta,xb,tb,keys=("R","G","B")):
    out=[]
    for w in p.extract_words():
        x=(w["x0"]+w["x1"])/2; y=(w["top"]+w["bottom"])/2
        if w["text"] in keys and xa<=x<=xb and ta<=y<=tb: out.append((w["text"],x,y))
    return out
def classify_by_letters(polys,lets):
    """polys: list of (N,2) page-coord arrays; assign nearest poly to each letter"""
    res={}
    for t,x,y in lets:
        best=None;bd=1e9
        for i,a in enumerate(polys):
            j=np.argmin(abs(a[:,0]-x)); d=np.hypot(a[j,0]-x,a[j,1]-y)
            if d<bd: bd=d; best=i
        res.setdefault(t,(best,bd))
    return {t:v[0] for t,v in res.items()}
def sens_classify(polys,xmap):
    out={}
    for a in polys:
        wl=xmap(a[:,0]); mx=wl.max()
        nm="blue" if mx<540 else "green" if mx<615 else "red"
        if nm in out: out[nm+"2"]=a
        else: out[nm]=a
    return out
OUT={}
# ---------------- Gold 200 ----------------
pdf=pdfplumber.open(U+"3b199048-E7022_Gold_200-2016.pdf"); p=pdf.pages[3]; H=p.height
xm=lambda c: lin(c,81.6,-3.0,265.3,1.0); ym=lambda c: lin(c,98.2,4.0,283.1,0.0)
polys=[a for a in chain(pick(p,70,95,330,290,minw=80),H) if a.shape[0]>20]
lets=letters(p,70,95,335,292); cl=classify_by_letters(polys,lets)
assert len(polys)>=3 and set(cl)=={"R","G","B"}, (len(polys),cl,lets)
ch={t:dict(zip(("x","d"),tidy(xm(polys[i][:,0]),ym(polys[i][:,1])))) for t,i in cl.items()}
sx=lambda c: lin(c,75.5,250.0,276.0,750.0); sy=lambda c: lin(c,345.0,4.0,494.5,0.0)
sens=sens_extract(p,(70,335,335,502),sx,sy)
OUT["Gold 200"]=dict(kind="neg",iso=200,ch=ch,sens=sens)
print("gold200: ch pts",{k:len(v["x"]) for k,v in ch.items()},"sens",{k:len(v["wl"]) for k,v in sens.items()})
# ---------------- Portra 800 ----------------
pdf=pdfplumber.open(U+"704fec0a-e4040_portra_800-2016.pdf"); p=pdf.pages[3]; H=p.height
xm=lambda c: lin(c,81.8,-4.0,266.1,1.0); ym=lambda c: lin(c,73.1,4.0,254.8,0.0)
polys=[a for a in chain(pick(p,66,70,335,258,minw=80),H) if a.shape[0]>20]
lets=letters(p,66,70,340,260); cl=classify_by_letters(polys,lets)
assert set(cl)=={"R","G","B"}, (len(polys),lets)
ch={t:dict(zip(("x","d"),tidy(xm(polys[i][:,0]),ym(polys[i][:,1])))) for t,i in cl.items()}
sx=lambda c: lin(c,350.9,250.0,551.3,750.0); sy=lambda c: lin(c,311.6,4.0,461.1,0.0)
sens=sens_extract(p,(340,305,560,468),sx,sy)
OUT["Portra 800"]=dict(kind="neg",iso=800,ch=ch,sens=sens)
print("portra800: ch pts",{k:len(v["x"]) for k,v in ch.items()},"sens",{k:len(v["wl"]) for k,v in sens.items()})
json.dump(OUT,open("/home/claude/ds/new1.json","w"))
# ---------------- Vision3 500T: camera-stops axis anchors mid-grey ----------------
pdf=pdfplumber.open(U+"171866e4-VISION3-500T-Color-Negative-Film-7219-TECHNICAL-DATA.pdf"); p=pdf.pages[3]; H=p.height
import math
REF=math.log10(10/500.0)
xm=lambda c: lin(c,352.3,REF-8*0.30103,538.6,REF+8*0.30103); ym=lambda c: lin(c,120.3,3.0,303.0,0.0)
polys=[a for a in chain2(pick(p,345,115,560,308,minw=30,minpts=3),H,tol=8) if a.shape[0]>25]
lets=letters(p,345,115,565,310); cl=classify_by_letters(polys,lets)
assert set(cl)=={"R","G","B"}, (len(polys),lets,[a.shape for a in polys])
ch={t:dict(zip(("x","d"),tidy(xm(polys[i][:,0]),ym(polys[i][:,1])))) for t,i in cl.items()}
sx=lambda c: lin(c,353.3,250.0,553.8,750.0); sy=lambda c: lin(c,519.7,4.0,669.2,0.0)
sens=sens_extract(p,(340,510,565,676),sx,sy)
OUT["Vision3 500T"]=dict(kind="neg",iso=500,ch=ch,sens=sens)
print("v500t: ch pts",{k:len(v["x"]) for k,v in ch.items()},"sens",{k:(len(v["wl"]),round(min(v["wl"])),round(max(v["wl"]))) for k,v in sens.items()})
# ---------------- Kodachrome 25 / 64 / 200 ----------------
pdf=pdfplumber.open(U+"b1cfeea7-e55-2009_06.pdf")
KPAGES={"Kodachrome 25":(2,25,dict(cx=((86.5,-2.0),(270.8,2.0)),cy=((132.2,4.0),(317.1,0.0)),dx=((368.5,400.0),(552.8,700.0)),dy=((187.1,1.0),(315.5,0.0)),sx=((87.3,250.0),(287.8,750.0)),sy=((399.6,2.0),(551.1,-2.0)))),
        "Kodachrome 64":(3,64,dict(cx=((72.0,-3.0),(257.0,1.0)),cy=((164.0,3.0),(302.8,0.0)),dx=((350.9,400.0),(535.2,700.0)),dy=None,sx=((75.3,250.0),(275.8,750.0)),sy=((387.0,2.0),(538.5,-2.0)))),
        "Kodachrome 200":(4,200,dict(cx=((84.0,-3.0),(269.0,1.0)),cy=((164.0,3.0),(302.8,0.0)),dx=((362.9,400.0),(547.2,700.0)),dy=((176.6,1.0),(305.0,0.0)),sx=((87.3,250.0),(287.8,750.0)),sy=((387.0,2.0),(538.5,-2.0))))}
for name,(pi,iso,A) in KPAGES.items():
    p=pdf.pages[pi]; H=p.height
    L=lambda k: (lambda c,a=A[k]: lin(c,a[0][0],a[0][1],a[1][0],a[1][1]))
    xm,ym=L("cx"),L("cy")
    x0=A["cx"][0][0]-14; x1=A["cx"][1][0]+30; y0=A["cy"][0][0]-35; y1=A["cy"][1][0]+12
    polys=[a for a in chain2(pick(p,x0,y0,x1+20,y1,minw=10,minpts=3),H,tol=8) if a.shape[0]>25]
    lets=letters(p,x0,y0,x1+25,y1); cl=classify_by_letters(polys,lets)
    assert set(cl)>={"R","G","B"}, (name,len(polys),lets)
    ch={t:dict(zip(("x","d"),tidy(xm(polys[i][:,0]),ym(polys[i][:,1])))) for t,i in cl.items() if t in "RGB"}
    sens=sens_extract(p,(A["sx"][0][0]-14,A["sy"][0][0]-16,A["sx"][1][0]+18,A["sy"][1][0]+14),L("sx"),L("sy"),tol=10)
    # dye density: classify by peak
    if A["dy"] is None:
        A2=dict(A); A2["dy"]=((176.6,1.0),(305.0,0.0))   # p3 y labels missing; pages 3 and 4 share the same grid (x tick rows match)
        dyem,dyey=(lambda c,a=A2["dx"]: lin(c,a[0][0],a[0][1],a[1][0],a[1][1])),(lambda c,a=A2["dy"]: lin(c,a[0][0],a[0][1],a[1][0],a[1][1]))
    else:
        dyem,dyey=L("dx"),L("dy")
    dx0=A["dx"][0][0]-14; dx1=A["dx"][1][0]+25
    dpolys=[a for a in chain2(pick(p,dx0,120,dx1,330,minw=10,minpts=3),H,tol=9) if a.shape[0]>20]
    dyes={}
    for a in dpolys:
        wl=dyem(a[:,0]); d=dyey(a[:,1])
        if max(d)<0.25: continue
        pk=wl[int(np.argmax(d))]
        nm="neutral" if min(d)>0.4 else ("yellow" if pk<500 else "magenta" if pk<600 else "cyan")
        if nm in dyes and nm!="neutral": continue
        dyes[nm]=dict(zip(("wl","d"),tidy(wl,d)))
    assert {"yellow","magenta","cyan"}<=set(dyes), (name,{k:len(v["wl"]) for k,v in dyes.items()},len(dpolys))
    OUT[name]=dict(kind="pos",iso=iso,ch=ch,sens=sens,dyes={k:v for k,v in dyes.items() if k!="neutral"})
    print(f"{name}: ch",{k:len(v['x']) for k,v in ch.items()},"sens",{k:(len(v['wl']),round(min(v['wl'])),round(max(v['wl']))) for k,v in sens.items()},"dyes",list(dyes))
json.dump(OUT,open("/home/claude/ds/new1.json","w"))
# ---------------- Astia 100F (colour-coded strokes) ----------------
pdf=pdfplumber.open(U+"aa3bceb6-astia_100f_datasheet.pdf"); p=pdf.pages[7]; H=p.height
import collections
def bycolor(bb,tol=10):
    cs=[c for c in p.curves if bb[0]<=c["x0"] and c["x1"]<=bb[2] and bb[1]<=c["top"] and c["bottom"]<=bb[3] and len(c["pts"])>=3]
    g=collections.defaultdict(list)
    for c in cs:
        col=c.get("stroking_color"); col=tuple(round(v,2) for v in col) if isinstance(col,(list,tuple)) else col
        g[col].append(c)
    out={}
    for col,cc in g.items():
        polys=[a for a in chain2(cc,H,tol=tol) if a.shape[0]>8 and np.hypot(*(a[0]-a[-1]))>6]   # drop closed shapes (label boxes)
        if polys: out[col]=np.vstack(sorted(polys,key=lambda a:a[0,0]))
    return out
CB=(0.96,0.93,0.0,0.0); CG=(0.93,0.0,1.0,0.0); CR=(0.01,0.96,0.91,0.0)
xm=lambda c: lin(c,103.6,-3.0,278.3,1.0); ym=lambda c: lin(c,194.3,4.0,367.3,0.0)
g=bycolor((80,180,332,372))
ch={k:dict(zip(("x","d"),tidy(xm(g[c][:,0]),ym(g[c][:,1])))) for k,c in (("B",CB),("G",CG),("R",CR))}
sx=lambda c: lin(c,348.4,400.0,526.5,700.0); sy=lambda c: lin(c,222.3,1.0,341.0,-1.0)
g=bycolor((335,180,560,372))
sens={k:dict(zip(("wl","logS"),tidy(sx(g[c][:,0]),sy(g[c][:,1])))) for k,c in (("blue",CB),("green",CG),("red",CR))}
dx=lambda c: lin(c,348.2,400.0,524.8,700.0); dy=lambda c: lin(c,496.4,1.0,614.4,0.0)
g=bycolor((335,450,560,620))
dyes={k:dict(zip(("wl","d"),tidy(dx(g[c][:,0]),dy(g[c][:,1])))) for k,c in (("yellow",(0.0,0.0,1.0,0.0)),("magenta",(0.0,1.0,0.0,0.0)),("cyan",(1.0,0.0,0.0,0.0)))}
OUT["Astia 100F"]=dict(kind="pos",iso=100,ch=ch,sens=sens,dyes=dyes)
print("astia: ch",{k:len(v["x"]) for k,v in ch.items()},"sens",{k:(len(v["wl"]),round(min(v["wl"])),round(max(v["wl"]))) for k,v in sens.items()},"dyes",{k:len(v["wl"]) for k,v in dyes.items()})
# ---------------- Pro 160NS (black strokes; order B,G,R from the top) ----------------
pdf=pdfplumber.open(U+"16ee3e09-datasheet_pro160ns_01.pdf"); p=pdf.pages[7]; H=p.height
xm=lambda c: lin(c,88.7,-4.0,265.6,0.0); ym=lambda c: lin(c,116.7,4.0,290.6,0.0)
cs=[c for c in p.curves if 95<=c["x0"] and c["x1"]<=295 and 110<=c["top"] and c["bottom"]<=296 and len(c["pts"])>=3 and c["width"]>60]
polys=sorted([a for a in chain2(cs,H,tol=12) if a.shape[0]>25],key=lambda a: a[:,1].mean())
assert len(polys)==3, len(polys)
ch={k:dict(zip(("x","d"),tidy(xm(a[:,0]),ym(a[:,1])))) for k,a in zip("BGR",polys)}
sx=lambda c: lin(c,343.7,400.0,520.1,700.0); sy=lambda c: lin(c,176.5,1.0,234.4,0.0)
cs=[c for c in p.curves if 330<=c["x0"] and c["x1"]<=560 and 150<=c["top"] and c["bottom"]<=296 and len(c["pts"])>=3 and not (c.get("dash") and c["dash"][0])]
sens={}
for a in sorted([a for a in chain2(cs,H,tol=12) if a.shape[0]>40],key=lambda a:a[int(np.argmin(a[:,1])),0]):
    sens[["blue","green","red"][len(sens)]]=dict(zip(("wl","logS"),tidy(sx(a[:,0]),sy(a[:,1]))))
assert set(sens)=={"blue","green","red"}, list(sens)
OUT["Pro 160NS"]=dict(kind="neg",iso=160,ch=ch,sens=sens)
print("pro160ns: ch",{k:len(v["x"]) for k,v in ch.items()},"sens",{k:(len(v["wl"]),round(min(v["wl"])),round(max(v["wl"]))) for k,v in sens.items()})
json.dump(OUT,open("/home/claude/ds/new1.json","w"))

# ---------------- Pro 800Z (outlined text; axes from gridlines, 1.0 bracket tip-to-tip) ----------------
pdf=pdfplumber.open(U+"7034ba9e-c42dcf4b-110d-ec14-a166-0230ca909e47.pdf"); p=pdf.pages[7]; H=p.height
xm=lambda c: lin(c,99.5,-3.5,265.3,0.5); ym=lambda c: lin(c,126.6,3.0,229.9,0.5)
cs=[c for c in p.curves if 76<=c["x0"] and c["x1"]<=290 and 100<=c["top"] and c["bottom"]<=255 and len(c["pts"])>=3 and c["width"]>60]
polys=sorted([a for a in chain2(cs,H,tol=12) if a.shape[0]>25],key=lambda a: a[:,1].mean())
assert len(polys)==3, len(polys)
ch={k:dict(zip(("x","d"),tidy(xm(a[:,0]),ym(a[:,1])))) for k,a in zip("BGR",polys)}
sx=lambda c: lin(c,351.0,400.0,508.6,700.0); sy=lambda c: lin(c,155.1,1.0,206.3,0.0)
cs=[c for c in p.curves if 335<=c["x0"] and c["x1"]<=560 and 100<=c["top"] and c["bottom"]<=330 and len(c["pts"])>=3 and c["width"]>8 and not (c.get("dash") and c["dash"][0])]
mains=sorted([a for a in chain2(cs,H,tol=12) if a.shape[0]>40],key=lambda a:-a.shape[0])[:4]
mains=[a for a in mains if a[:,1].min()<190]   # the dashed 4th layer sits low even if dash flags are missing
mains.sort(key=lambda a:a[int(np.argmin(a[:,1])),0])
sens={["blue","green","red"][i]:dict(zip(("wl","logS"),tidy(sx(a[:,0]),sy(a[:,1])))) for i,a in enumerate(mains[:3])}
assert set(sens)=={"blue","green","red"}, list(sens)
OUT["Pro 800Z"]=dict(kind="neg",iso=800,ch=ch,sens=sens)
print("pro800z: ch",{k:len(v["x"]) for k,v in ch.items()},"sens",{k:(len(v["wl"]),round(min(v["wl"])),round(max(v["wl"]))) for k,v in sens.items()})
json.dump(OUT,open("/home/claude/ds/new1.json","w"))

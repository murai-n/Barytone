import sys, json, numpy as np, pdfplumber, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0,"/home/claude/scripts")
import importlib.util as il
spec=il.spec_from_file_location("e3","/home/claude/scripts/extract3.py")
# reuse helpers without re-running: pull the functions by exec of the top block
src=open("/home/claude/scripts/extract3.py").read()
head=src[:src.index("out={}; DYE={}")]
ns={}; exec(head,ns)
axis,paths,flat,tidy,words,frags=ns["axis"],ns["paths"],ns["flat"],ns["tidy"],ns["words"],ns["frags"]
U="/mnt/user-data/uploads/"
out={}
def curve(c,H,fx,fy):
    a=flat(c,H); return dict(zip(("x","d"),tidy(fx(a[:,0]),fy(a[:,1]))))
# ================= Astia 100F (AF3-149E, p7) =================
pg=pdfplumber.open(U+"aa3bceb6-astia_100f_datasheet.pdf").pages[7]; H=pg.height
fx=axis(pg,[-3,-2,-1,0,1],(90,290),(368,382),True)
fy=axis(pg,[4,3.5,3,2.5,2,1.5,1,0.5,0],(64,90),(185,375),False)
cs=paths(pg,80,185,300,370,minh=8); assert len(cs)==3,len(cs)
def ckey(c): return tuple(round(v,2) for v in (c.get("stroking_color") or (0,)*4)[:3])
CMAP={(0.01,0.96,0.91):"R",(0.93,0.0,1.0):"G",(0.96,0.93,0.0):"B"}
def closest(c):
    k=ckey(c); return min(CMAP,key=lambda m:sum((a-b)**2 for a,b in zip(m,k)))
ch={CMAP[closest(c)]:curve(c,H,fx,fy) for c in cs}; assert set(ch)=={"R","G","B"}
sx=axis(pg,[400,500,600,700],(330,545),(368,382),True)
sy=axis(pg,[1,0],(318,340),(200,300),False)
ss=sorted(paths(pg,335,190,540,345,minh=50),key=lambda c:c["x0"]+c["x1"]); assert len(ss)==3,len(ss)
sens={n:ns["sens_xy"](c,H,sx,sy) for n,c in zip(("blue","green","red"),ss)}
dx=axis(pg,[400,500,600,700],(330,545),(615,632),True)
dy=axis(pg,[1,0.5,0],(318,342),(480,630),False)
ds=paths(pg,335,460,545,630,minh=30); assert len(ds)==3,len(ds)
dyes={}
for c in ds:
    a=flat(c,H); wl,d=tidy(dx(a[:,0]),dy(a[:,1])); pk=wl[int(np.argmax(d))]
    dyes["yellow" if pk<500 else "magenta" if pk<600 else "cyan"]=dict(wl=wl,d=d)
assert set(dyes)=={"cyan","magenta","yellow"},set(dyes)
out["Astia 100F"]=dict(kind="pos",iso=100,ch=ch,sens=sens,dyes=dyes)
# ================= Kodachrome 25 / 64 / 200 (E-55, p2-4) =================
pdf=pdfplumber.open(U+"b1cfeea7-e55-2009_06.pdf")
CFG={2:dict(cx=([-2,-1,0,1,2],(60,290),(322,340)),cy=([4,3,2,1,0],(62,88),(125,328)),cr=(90,135,255,318),
            dx=((355,565),(320,338)),dy=((344,370),(140,325)),dr=(362,135,560,322),
            sx=((78,292),(555,572)),sy=((68,86),(395,560)),sr=(110,400,300,560)),
     3:dict(cx=([-3,-2,-1,0,1],(60,280),(302,318)),cy=([4,3,2,1,0],(52,72),(105,305)),cr=(90,105,255,300),
            dx=((340,545),(303,320)),dy=((328,352),(160,310)),dr=(352,115,545,308),
            sx=((66,285),(536,552)),sy=((56,74),(375,545)),sr=(110,410,300,545)),
     4:dict(cx=([-3,-2,-1,0,1],(60,285),(306,322)),cy=([4,3,2,1,0],(62,82),(110,310)),cr=(88,120,255,305),
            dx=((350,560),(307,323)),dy=((340,362),(165,312)),dr=(362,130,555,310),
            sx=((78,296),(540,556)),sy=((68,86),(378,545)),sr=(110,392,300,545))}
for name,iso,pi in (("Kodachrome 25",25,2),("Kodachrome 64",64,3),("Kodachrome 200",200,4)):
    pg=pdf.pages[pi]; H=pg.height; C=CFG[pi]
    fx=axis(pg,*C["cx"],True); fy=axis(pg,C["cy"][0],C["cy"][1],C["cy"][2],False)
    cs=paths(pg,*C["cr"],minh=40); assert len(cs)==3,(name,len(cs))
    cs=sorted(cs,key=lambda c: flat(c,H)[np.argmin(flat(c,H)[:,0]),1])
    ch=dict(zip("RGB",[curve(c,H,fx,fy) for c in cs]))
    dx=axis(pg,[400,500,600,700],C["dx"][0],C["dx"][1],True)
    dyv=axis(pg,[1,0.5,0],C["dy"][0],C["dy"][1],False)
    ds=paths(pg,*C["dr"],minh=25); assert len(ds)==4,(name,len(ds))
    info=[]
    for c in ds:
        a=flat(c,H); wl,d=tidy(dx(a[:,0]),dyv(a[:,1])); wl=np.array(wl); d=np.array(d)
        g=np.interp(np.linspace(430,670,60),wl,d); info.append((g.min()/max(g.max(),1e-6),wl,d))
    info.sort(key=lambda t:-t[0])
    dyes={}
    for _,wl,d in info[1:]:
        pk=wl[int(np.argmax(d))]
        dyes["yellow" if pk<500 else "magenta" if pk<600 else "cyan"]=dict(wl=wl.tolist(),d=d.tolist())
    assert set(dyes)=={"cyan","magenta","yellow"},(name,set(dyes))
    try: sx=axis(pg,[250,300,350,400,450,500,550,600,650,700,750],C["sx"][0],C["sx"][1],True)
    except AssertionError: sx=axis(pg,[250,300,350,400,450,500,550,600,650,700],C["sx"][0],C["sx"][1],True)
    sy=axis(pg,[2,1,0,-1,-2],C["sy"][0],C["sy"][1],False)
    ss=sorted(paths(pg,*C["sr"],minh=50),key=lambda c:c["x0"]+c["x1"]); assert len(ss)==3,(name,len(ss))
    sens={n:ns["sens_xy"](c,H,sx,sy) for n,c in zip(("blue","green","red"),ss)}
    out[name]=dict(kind="pos",iso=iso,ch=ch,sens=sens,dyes=dyes)
json.dump(out,open("/home/claude/work3/films3_new_part2.json","w"))
print("part2 ok:",list(out))

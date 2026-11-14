import sys,io,contextlib,colorsys,uuid; sys.path.insert(0,"/home/claude/scripts")
with contextlib.redirect_stdout(io.StringIO()): import styles as S
from scipy.optimize import least_squares
M=S.M; np=S.np; colour=S.colour
SEG=[("Red",0),("Orange",30),("Yellow",60),("Green",120),("Cyan",180),("Blue",240),("Purple",270),("Magenta",300)]
def hsv_xyz(h,s,v): return (np.array(colorsys.hsv_to_rgb(h/360,s,v))**2.2)@M.M_SRGB_XYZ.T
cent=np.array([np.degrees(np.arctan2(*S.lab(hsv_xyz(h,0.6,0.7)[None])[0,[2,1]]))%360 for _,h in SEG]); order=np.argsort(cent); cs=cent[order]
def weights(h):
    h=h%360; W=np.zeros((len(h),8)); ext=np.concatenate([[cs[-1]-360],cs,[cs[0]+360]]); idx=np.concatenate([[order[-1]],order,[order[0]]])
    j=np.clip(np.searchsorted(ext,h)-1,0,8); t=(h-ext[j])/(ext[j+1]-ext[j])
    np.add.at(W,(np.arange(len(h)),idx[j]),1-t); np.add.at(W,(np.arange(len(h)),idx[j+1]),t); return W
def coloredit(X,p):
    L=S.lab(X); C=np.hypot(L[:,1],L[:,2]); h=np.degrees(np.arctan2(L[:,2],L[:,1])); W=weights(h); p=p.reshape(8,3)
    g=np.clip(C/8,0,1)   # leave near-neutrals alone
    h2=np.radians(h+g*(W@p[:,0])); C2=C*(1+g*(W@p[:,1])/100); L2=L[:,0]+g*(W@p[:,2])
    return colour.Lab_to_XYZ(np.stack([L2,C2*np.cos(h2),C2*np.sin(h2)],1),S.d65)
train=np.array([hsv_xyz(h,s,v) for h in range(0,360,15) for s in (0.3,0.55,0.8) for v in (0.35,0.6,0.85)])
negs=[f for f in M.ALL if M.KIND[f]=="neg"]; PAR={}
for pid,lab in [("endura","KEP"),("crystal","FCA")]:
    pv=dict(base=True,bpaper=pid,k=0.0)
    B=[M.render(f,train,M.variants(f)[0]) for f in negs]; T=[S.lab(M.render(f,train,pv)) for f in negs]
    res=least_squares(lambda p: np.concatenate([(S.lab(coloredit(b,p))-t).ravel() for b,t in zip(B,T)]),np.zeros(24))
    p=res.x.reshape(8,3); PAR[lab]=p
    print(f"Print {lab} paper colour (Color Editor, basic):"); [print(f"  {n:8s} hue {p[i,0]:+5.1f}  sat {p[i,1]:+5.1f}  light {p[i,2]:+5.1f}") for i,(n,_) in enumerate(SEG)]
    # best-guess .costyle encoding (field layout inferred from third-party style files; unverified)
    ent=[]
    for i,(n,h) in enumerate(SEG):
        r,g,b=[255*c for c in colorsys.hsv_to_rgb(h/360,0.85,0.95)]
        ent.append(f"1,1,0,{p[i,0]:.3f},{p[i,1]:.3f},{p[i,2]:.3f},{r:.1f},{g:.1f},{b:.1f},-15,15,-100,0,25,0,0,0,0")
    S.write("3 Print",f"Print {lab} - paper color",{},[("ColorCorrections",";".join(ent))])
    for f in negs:
        a=S.ALIAS[f]; ref=S.lab(M._render_core(f,S.X24,dict(paper=pid,deep=False,k=0.0,gamma=1.5))); b=M.render(f,S.X24,M.variants(f)[0]); cur=S.CUR[f"Print {lab} full"] if f"Print {lab} full" in S.CUR else None
        e0=S.dE(S.lab(S.apply(b,cur)),ref,slice(0,18)); e1=S.dE(S.lab(S.apply(coloredit(b,res.x),cur)),ref,slice(0,18)); e2=S.dE(S.lab(S.apply(M.render(f,S.X24,pv),cur)),ref,slice(0,18))
        e3=S.dE(S.lab(S.apply(S.apply(coloredit(b,res.x),S.CUR[f"Print {lab} tint"]),S.CUR[f"Print {lab} tone"])),ref,slice(0,18)); chn=lambda X: np.hypot(*S.lab(X)[:18,1:].T).mean()
        print(f"  {a}: 3 layers (color+tint+tone) vs model print dE {e3.mean():.1f}/{e3.max():.1f}  chroma vs ICC only: color {chn(coloredit(b,res.x))/chn(b):.2f}, all three {chn(S.apply(S.apply(coloredit(b,res.x),S.CUR[f'Print {lab} tint']),S.CUR[f'Print {lab} tone']))/chn(b):.2f}, model {np.hypot(ref[:18,1],ref[:18,2]).mean()/chn(b):.2f}")
        print(f"  {a}: vs model print  no colour {e0.mean():.1f}/{e0.max():.1f}  | colour editor (simulated) {e1.mean():.1f}/{e1.max():.1f} | old print ICC {e2.mean():.1f}/{e2.max():.1f}")
import json; json.dump({k:v.tolist() for k,v in PAR.items()},open("/home/claude/out3/papercolor.json","w"))
# preview
from PIL import Image, ImageDraw, ImageFont
rows=[("Original",lambda X:X)]
for f in M.ALL:
    a=S.ALIAS[f]; v=M.variants(f)[0]
    rows.append((a+"  1 exposure (ICC)",lambda X,f=f,v=v: M.render(f,X,v)))
    if M.KIND[f]=="neg":
        rows.append((a+"  +2 develop",lambda X,f=f,v=v,a=a: S.apply(M.render(f,X,v),S.CUR[a+" film"])))
        rows.append((a+"  +3 print A",lambda X,f=f,v=v: S.apply(coloredit(M.render(f,X,v),PAR["KEP"].ravel()),S.CUR["Print KEP tone"])))
    else: rows.append((a+"  +2 develop",lambda X,f=f,v=v,a=a: S.apply(S.apply(M.render(f,X,v),S.CUR[a+" color"]),S.CUR[a+" tone"])))
P=26; W=220+24*P; H=len(rows)*(2*P+10)+10
im=Image.new("RGB",(W,H),(245,245,245)); dr=ImageDraw.Draw(im); fnt=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",13)
for r,(lab_,fn) in enumerate(rows):
    y=10+r*(2*P+10); a_=S.srgb(fn(S.X24)); b_=S.srgb(fn(S.ramp)); dr.text((8,y+P-8),lab_,fill=(20,20,20),font=fnt)
    for i in range(24):
        dr.rectangle([220+i*P,y,220+i*P+P-2,y+P-2],fill=tuple(int(c) for c in a_[i])); dr.rectangle([220+i*P,y+P,220+i*P+P-2,y+2*P-2],fill=tuple(int(c) for c in b_[i]))
im.save("/home/claude/out3/preview_v11.png")

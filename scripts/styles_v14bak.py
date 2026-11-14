import sys, uuid, json; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, warnings; warnings.filterwarnings("ignore")
import model3 as M
PV=dict(id="printA",base=True,bpaper="endura",k=0.0)
ENC=1.8; OUT="/home/claude/out3/styles/"
ALIAS=json.load(open("/home/claude/out3/alias.json"))["alias"]
x=np.concatenate([[0,0.02,0.05],np.linspace(0.1,1,10)]); Yin=np.maximum(x,1e-4)**ENC
lum=M.M_SRGB_XYZ[1]
def write(folder,name,curves,extra=()):
    rows="".join(f'\t<E K="{k}" V="{";".join(f"{a:.6f},{min(max(b,0),1):.6f}" for a,b in zip(x,v))}" />\n' for k,v in curves.items())
    rows+="".join(f'\t<E K="{k}" V="{v}" />\n' for k,v in extra)
    open(f"{OUT}{folder}/{name}.costyle","w").write(f'<?xml version="1.0"?>\n<SL Engine="900">\n{rows}\t<E K="Name" V="{name}" />\n\t<E K="UUID" V="{str(uuid.uuid4()).upper()}" />\n</SL>\n')
enc=lambda v: np.clip(v,0,1)**(1/ENC)
CUR={}
def rgbcurves(P,color_only):
    if color_only: P=P*(Yin/np.maximum(P@lum,1e-9))[:,None]
    o=enc(P); o[0]=o[0] if not color_only else 0
    return {"GradationCurveRed":o[:,0],"GradationCurveGreen":o[:,1],"GradationCurveBlue":o[:,2]}
G=np.outer(Yin,M.D65W)
for f in M.ALL:
    a=ALIAS[f]
    if M.KIND[f]=="neg":
        P=M._render_v3(f,G,dict(deep=False,k=0.0))@M.M_XYZ_SRGB.T
        CUR[a+" color"]=rgbcurves(P,True); write("2 Develop",f"Develop {a} - color",CUR[a+" color"])
        CUR[a+" film"]=rgbcurves(P,False); write("2 Develop",f"Develop {a} - color + film black",CUR[a+" film"])
    else:
        P=M._render_v3(f,G,dict(k=0.0))@M.M_XYZ_SRGB.T
        CUR[a+" color"]=rgbcurves(P,True); write("2 Develop",f"Develop {a} - color",CUR[a+" color"])
        Y=M._render_core(f,G,dict(k=0.0))[:,1]; CUR[a+" tone"]={"GradationCurveY":enc(Y)}; write("2 Develop",f"Develop {a} - slide tone",CUR[a+" tone"])
for pid,lab in [("endura","A"),("crystal","B")]:
    X=M._render_core("Portra 400",G,dict(paper=pid,deep=False,k=0.0,gamma=1.5)); P=X@M.M_XYZ_SRGB.T
    CUR["Print "+lab+" tone"]={"GradationCurveY":enc(X[:,1])}; write("3 Print",f"Print {lab} - tone",CUR["Print "+lab+" tone"])
    CUR["Print "+lab+" full"]=rgbcurves(P,False); write("3 Print",f"Print {lab} - tone + paper tint",CUR["Print "+lab+" full"])
    CUR["Print "+lab+" tint"]=rgbcurves(P,True); write("3 Print",f"Print {lab} - paper tint",CUR["Print "+lab+" tint"])
for s in (15,30): write("2 Develop",f"Develop - coupler +{s}",{},[("Saturation",str(s))])
# ---- simulate ICC + styles and compare with the full model
def apply(X,c):
    P=np.clip(X@M.M_XYZ_SRGB.T,0,None)
    if "GradationCurveY" in c:
        Y=np.maximum(P@lum,1e-9); P=P*((np.interp(enc(Y),x,c["GradationCurveY"])**ENC)/Y)[:,None]
    else:
        P=np.stack([np.interp(enc(P[:,i]),x,c[k])**ENC for i,k in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue"))],1)
    return P@M.M_SRGB_XYZ.T
d65=colour.XYZ_to_xy(M.D65W); lab=lambda X: colour.XYZ_to_Lab(np.clip(X,1e-6,None),d65)
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
X24=colour.adaptation.chromatic_adaptation_VonKries(colour.xyY_to_XYZ(np.array(list(cc.data.values()))),colour.xy_to_XYZ(cc.illuminant),M.D65W)
L0=lab(X24); C0=np.hypot(L0[:18,1],L0[:18,2]).mean(); dE=lambda a,b,s=slice(0,24): colour.delta_E(a[s],b[s],method="CIE 2000")
print("film      ICC chroma | ICC+Develop(film) vs model negative: dE mean/max | ICC printA + Print A full vs model print: dE mean/max")
R={}
for f in M.ALL:
    a=ALIAS[f]; b=M.render(f,X24,M.variants(f)[0]); R[a]=lab(b); line=f"{a:7s} {np.hypot(R[a][:18,1],R[a][:18,2]).mean()/C0:.2f}"
    if M.KIND[f]=="neg":
        e=dE(lab(apply(b,CUR[a+" film"])),lab(M._render_v3(f,X24,dict(deep=False,k=0.0)))); line+=f" | {e.mean():.1f}/{e.max():.1f}"
        pa=M.render(f,X24,PV); e=dE(lab(apply(pa,CUR["Print A full"])),lab(M._render_core(f,X24,dict(paper="endura",deep=False,k=0.0,gamma=1.5)))); line+=f" | {e.mean():.1f}/{e.max():.1f}"
        g=dE(lab(apply(b,CUR[a+" color"])),R[a],slice(18,24)); line+=f" | color style moves greys by dE {g.mean():.1f}, dL {abs(lab(apply(b,CUR[a+' color']))[18:,0]-R[a][18:,0]).max():.2f}"
    else:
        e=dE(lab(apply(apply(b,CUR[a+" color"]),CUR[a+" tone"])),lab(M._render_core(f,X24,dict(k=0.0)))); line+=f" | slide: {e.mean():.1f}/{e.max():.1f}"
    print(line)
names=list(R); print("film-film dE (ICC only):"," ".join(f"{p}-{q}:{dE(R[p],R[q],slice(0,18)).mean():.1f}" for i,p in enumerate(names) for q in names[i+1:] if (p[0]==q[0] or 1) and i<4 and names.index(q)<4))
from PIL import Image, ImageDraw, ImageFont
ramp=np.outer(0.18*2**np.linspace(-6,2.4,24),M.D65W)
def srgb(X): return (np.clip(colour.XYZ_to_sRGB(np.clip(X,0,None),apply_cctf_encoding=True),0,1)*255).astype(np.uint8)
rows=[("Original",lambda X:X)]
for f in M.ALL:
    a=ALIAS[f]; vs=M.variants(f)
    rows.append((a+"  1 exposure (ICC)",lambda X,f=f,vs=vs: M.render(f,X,vs[0])))
    if M.KIND[f]=="neg":
        rows.append((a+"  +2 develop",lambda X,f=f,vs=vs,a=a: apply(M.render(f,X,vs[0]),CUR[a+" film"])))
        rows.append((a+"  +3 print A",lambda X,f=f,vs=vs: apply(M.render(f,X,PV),CUR["Print A full"])))
    else:
        rows.append((a+"  +2 develop",lambda X,f=f,vs=vs,a=a: apply(apply(M.render(f,X,vs[0]),CUR[a+" color"]),CUR[a+" tone"])))
P=26; W=220+24*P; H=len(rows)*(2*P+10)+10
im=Image.new("RGB",(W,H),(245,245,245)); dr=ImageDraw.Draw(im); fnt=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",13)
for r,(lab_,fn) in enumerate(rows):
    y=10+r*(2*P+10); a_=srgb(fn(X24)); b_=srgb(fn(ramp)); dr.text((8,y+P-8),lab_,fill=(20,20,20),font=fnt)
    for i in range(24):
        dr.rectangle([220+i*P,y,220+i*P+P-2,y+P-2],fill=tuple(int(c) for c in a_[i])); dr.rectangle([220+i*P,y+P,220+i*P+P-2,y+2*P-2],fill=tuple(int(c) for c in b_[i]))
im.save("/home/claude/out3/preview_v10.png")

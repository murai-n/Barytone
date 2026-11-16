import sys, uuid, json; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, warnings; warnings.filterwarnings("ignore")
import model3 as M
PV=dict(id="printA",base=True,bpaper="endura",k=0.0)
ENC=1.8; OUT="/home/claude/out3/styles/"
ALIAS=json.load(open("/home/claude/out3/alias.json"))["alias"]
x=np.array([0,.03,.06,.09,.12,.16,.2,.25,.3,.4,.5,.6,.7,.8,.9,1.0]); Yin=np.maximum(x,1e-4)**ENC
XD=np.linspace(0,1,2001); YD=np.maximum(XD,1e-4)**ENC; SMIN=0.3; X0=0.35
def toe(od,smin=None):
    smin=SMIN if smin is None else smin
    """keep a minimum slope below X0 so deep shadows stay separated (the paper's own toe is flat there)"""
    s=np.maximum(np.gradient(od,XD),0); s2=np.where(XD<X0,(s**3+smin**3)**(1/3),s); i0=np.searchsorted(XD,X0)
    c=np.cumsum((s2[:i0+1][::-1])[:-1]*(XD[1]-XD[0]))[::-1]
    if c[0]>od[i0]-0.004: c=c*(od[i0]-0.004)/c[0]     # never run into zero: keeps the curve strictly rising down to black
    o=od.copy(); o[:i0]=od[i0]-c
    return np.clip(o,0,1)
def shoulder(od,smin=None,X1=0.8):
    """mirror of toe(): keep a minimum slope near white so flat tops cannot make the spline dip"""
    smin=SMIN if smin is None else smin
    sl=np.maximum(np.gradient(od,XD),0); s2=np.where(XD>X1,(sl**3+smin**3)**(1/3),sl); i1=np.searchsorted(XD,X1)
    c=np.cumsum(s2[i1:-1]*(XD[1]-XD[0]))
    top=1.0-0.004
    if od[i1]+c[-1]>top: c=c*max(top-od[i1],1e-4)/c[-1]
    o=od.copy(); o[i1+1:]=od[i1]+c
    return np.clip(np.maximum.accumulate(o),0,1)
from scipy.ndimage import gaussian_filter1d as _g1d
def toe2(od,smin):
    """dark and bright slope floors, plus a light rounding of kinks so the control-point spline cannot overshoot"""
    o=shoulder(toe(od,smin),smin)
    return np.clip(np.maximum.accumulate(_g1d(o,8,mode="nearest")),0,1)
def samp(od): return np.interp(x,XD,od)
GD=np.outer(YD,M.D65W)
MONO_MIN=0.06   # smallest dark-end slope that keeps the curve rising once Capture One splines it through the control points
GD=np.outer(YD,M.D65W)
lum=M.M_SRGB_XYZ[1]
SLIDE_GAMMA=1.2/1.5   # slides are made for a dark-surround light box (system gamma ~1.5); a dim-surround display wants ~1.2
SLIDE_FLARE=0.001     # viewing-flare floor (linear): the darkest the slide's own Dmax is shown
SLIDE_KNEE_EV=1.5     # above mid-grey + this, lift so sensor saturation reaches clear film (engine.js slideTone)
def slide_view(Y, x=None):
    """Film Dmax is the darkest point: subtract it, then compress (T^P), then leave a 0.1% flare floor.
    Above mid-grey + SLIDE_KNEE_EV the curve is lifted so x=1 maps to clear film. The browser tool
    computes the same curve in engine.js slideTone(); films.json "slide" comes from there.
    x, if given, is the curve-domain input (gamma 1.8) for each row of Y; default is the styles grid."""
    Y=np.clip(Y,1e-7,None); lo=Y.min()
    o=SLIDE_FLARE+(1-SLIDE_FLARE)*(np.clip((Y-lo)/(1-lo),0,None))**SLIDE_GAMMA
    if x is None: x=XD  # encoded scene levels on the styles grid
    x=np.asarray(x,float); xk=(0.18*2**SLIDE_KNEE_EV)**(1/ENC); y1=float(o[-1])
    t=np.clip((x-xk)/max(1-xk,1e-9),0,1); w=t*t*(3-2*t)
    return np.where(x<=xk, o, np.minimum(1, o+(1-y1)*w))
FADED_FLARE=0.012   # print surface reflection for the faded paper variant (normal uses M.VIEW_FLARE)
CURVE_KEYS=("GradationCurve","GradationCurveRed","GradationCurveGreen","GradationCurveBlue","GradationCurveY")
IDENTITY="0.000000,0.000000;1.000000,1.000000"
def write(folder,name,curves,extra=()):
    """every real Capture One style carries all five curve keys; a missing one is left undefined, so
    unused channels are written as an explicit identity curve"""
    got={k:";".join(f"{a:.6f},{min(max(b,0),1):.6f}" for a,b in zip(x,v)) for k,v in curves.items()}
    rows="".join(f'\t<E K="{k}" V="{got.get(k,IDENTITY)}" />\n' for k in CURVE_KEYS)
    rows+="".join(f'\t<E K="{k}" V="{v}" />\n' for k,v in extra)
    open(f"{OUT}{folder}/{name}.costyle","w").write(f'<?xml version="1.0"?>\n<SL Engine="900">\n{rows}\t<E K="Name" V="{name}" />\n\t<E K="UUID" V="{str(uuid.uuid4()).upper()}" />\n</SL>\n')
enc=lambda v: np.clip(v,0,1)**(1/ENC)
CUR={}
def rgbcurves(P,color_only):
    """P on the full YD grid"""
    if color_only:
        Yl=np.maximum(P@lum,1e-9); P=YD[:,None]*(1+(P/Yl[:,None]-1)*np.minimum(1,Yl/YD)[:,None])
    o=enc(P)
    return {k:samp(toe2(np.maximum.accumulate(o[:,i]),MONO_MIN)) for i,k in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue"))}
G=np.outer(Yin,M.D65W)
for f in M.ALL:
    a=ALIAS[f]
    if M.KIND[f]=="neg":
        P=np.clip(M._render_v3(f,GD,dict(deep=False,k=0.0))@M.M_XYZ_SRGB.T,0,None)
        CUR[a+" color"]=rgbcurves(P,True); write("2 Develop",f"Develop {a} - color",CUR[a+" color"])
        Pd=np.clip(M._render_v3(f,GD,dict(deep=False,k=0.0))@M.M_XYZ_SRGB.T,0,1)
        CUR[a+" film"]={kk:samp(toe2(np.maximum.accumulate(enc(Pd[:,i])),MONO_MIN)) for i,kk in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue"))}; write("2 Develop",f"Develop {a} - color + film black",CUR[a+" film"])
    else:
        P=np.clip(M._render_v3(f,GD,dict(k=0.0))@M.M_XYZ_SRGB.T,0,None)
        CUR[a+" color"]=rgbcurves(P,True); write("2 Develop",f"Develop {a} - color",CUR[a+" color"])
        Y=slide_view(M._render_core(f,GD,dict(k=0.0))[:,1]); CUR[a+" tone"]={"GradationCurve":samp(toe(enc(Y),MONO_MIN))}; write("2 Develop",f"Develop {a} - slide tone",CUR[a+" tone"])
        write("2 Develop",f"Develop {a} - slide tone (luma, background only)",{"GradationCurve":samp(toe2(np.maximum.accumulate(enc(Y)),MONO_MIN))})
_VF0=M.VIEW_FLARE
for pid,lab,pg,nf in [("endura","KEP",1.5,_VF0),("crystal","FCA",1.5,_VF0),("fujiflex","FFX",1.5,_VF0),("metallic","KEM",1.5,_VF0),("ultra","KUE",1.5,_VF0),("portra","KPE",1.5,_VF0),("supra","KSE",1.5,_VF0),("ilfochrome","ILF",1.9,0.0015)]:
    # pg = print system gamma: Ilfochrome (silver-dye-bleach) is markedly contrastier than RA-4, so a higher value.
    # nf = normal-variant surface reflection: Ilfochrome's glossy polyester base reflects less, so a deeper black.
    M.VIEW_FLARE=nf
    X=M._render_core("Portra 400",GD,dict(paper=pid,deep=False,k=0.0,gamma=pg)); P=np.clip(X@M.M_XYZ_SRGB.T,0,None)
    od=enc(X[:,1]); o2=toe(od); P2=P*((o2**ENC)/np.maximum(X[:,1],1e-9))[:,None]; Pt=P*(YD/np.maximum(P@lum,1e-9))[:,None]
    CUR["Print "+lab+" tone"]={"GradationCurve":samp(o2)}; write("3 Print",f"Print {lab} - tone",CUR["Print "+lab+" tone"])
    write("3 Print",f"Print {lab} - tone (luma, background only)",{"GradationCurveY":samp(o2)})
    CUR["Print "+lab+" full"]={k:samp(enc(P2[:,i])) for i,k in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue"))}; write("3 Print",f"Print {lab} - tone + paper tint",CUR["Print "+lab+" full"])
    t={k:samp(enc(Pt[:,i])) for i,k in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue"))}
    for k in t: t[k][0]=0
    CUR["Print "+lab+" tint"]=t; write("3 Print",f"Print {lab} - paper tint",t)
    # paper tint variants on the model's own calibration basis.
    #  full  = the model's gray-balanced print (default PRINT_CAL) -> tiny residual
    #  partial = only half the lab calibration, so half of the paper's native cast remains (for character)
    for cal,suf in ((M.PRINT_CAL,"full"),(0.5,"partial")):
        old=M.PRINT_CAL; M.PRINT_CAL=cal
        Pc=np.clip(M._render_core("Portra 400",GD,dict(paper=pid,deep=False,k=0.0,gamma=pg))@M.M_XYZ_SRGB.T,0,None)
        M.PRINT_CAL=old
        Ptc=Pc*(YD/np.maximum(Pc@lum,1e-9))[:,None]
        tc={k:samp(enc(Ptc[:,i])) for i,k in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue"))}
        for k in tc: tc[k][0]=0
        CUR[f"Print {lab} tint {suf}"]=tc; write("3 Print",f"Print {lab} - paper tint ({suf} cal)",tc)
    # faded = stronger print surface reflection (glossy print under less ideal light): lifted black, same calibration
    oldvf=M.VIEW_FLARE; M.VIEW_FLARE=FADED_FLARE
    Xf=M._render_core("Portra 400",GD,dict(paper=pid,deep=False,k=0.0,gamma=pg)); M.VIEW_FLARE=oldvf
    of=toe(enc(Xf[:,1])); write("3 Print",f"Print {lab} - tone (faded)",{"GradationCurve":samp(of)})
    Pf=np.clip(Xf@M.M_XYZ_SRGB.T,0,None); Pf=Pf*(YD/np.maximum(Pf@lum,1e-9))[:,None]
    tf={k:samp(enc(Pf[:,i])) for i,k in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue"))}
    for k in tf: tf[k][0]=0
    write("3 Print",f"Print {lab} - paper tint (faded)",tf)
    TOE=(od,o2) if lab=="KEP" else globals().get("TOE")
M.VIEW_FLARE=_VF0
for s in (15,30,40,50): write("2 Develop",f"Develop - coupler +{s}",{},[("Saturation",str(s))])
# ---- simulate ICC + styles and compare with the full model
def apply(X,c):
    P=np.clip(X@M.M_XYZ_SRGB.T,0,None)
    if "GradationCurveY" in c:
        Y=np.maximum(P@lum,1e-9); P=P*((np.interp(enc(Y),x,c["GradationCurveY"])**ENC)/Y)[:,None]
    elif "GradationCurve" in c:
        P=np.stack([np.interp(enc(P[:,i]),x,c["GradationCurve"])**ENC for i in range(3)],1)
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
        pa=M.render(f,X24,PV); e=dE(lab(apply(pa,CUR["Print KEP full"])),lab(M._render_core(f,X24,dict(paper="endura",deep=False,k=0.0,gamma=1.5)))); line+=f" | {e.mean():.1f}/{e.max():.1f}"
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
        rows.append((a+"  +3 print KEP",lambda X,f=f,vs=vs: apply(M.render(f,X,PV),CUR["Print KEP full"])))
    else:
        rows.append((a+"  +2 develop",lambda X,f=f,vs=vs,a=a: apply(apply(M.render(f,X,vs[0]),CUR[a+" color"]),CUR[a+" tone"])))
P=26; W=220+24*P; H=len(rows)*(2*P+10)+10
im=Image.new("RGB",(W,H),(245,245,245)); dr=ImageDraw.Draw(im); fnt=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",13)
for r,(lab_,fn) in enumerate(rows):
    y=10+r*(2*P+10); a_=srgb(fn(X24)); b_=srgb(fn(ramp)); dr.text((8,y+P-8),lab_,fill=(20,20,20),font=fnt)
    for i in range(24):
        dr.rectangle([220+i*P,y,220+i*P+P-2,y+P-2],fill=tuple(int(c) for c in a_[i])); dr.rectangle([220+i*P,y+P,220+i*P+P-2,y+2*P-2],fill=tuple(int(c) for c in b_[i]))
im.save("/home/claude/out3/preview_v10.png")

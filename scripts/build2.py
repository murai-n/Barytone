import sys; sys.path.insert(0,"/home/claude/scripts")
import csv, io, struct, json, numpy as np, colour
import model, model2
from model2 import *
from PIL import Image, ImageCms
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.rcParams["font.family"]="IPAGothic"
OUT="/home/claude/out2/"; INK="#0b0b0b"; SEC="#52514e"; MUT="#898781"; GRID="#e1e0d9"; AX="#c3c2b7"; SURF="#fcfcfb"
COL={"R":"#e34948","G":"#008300","B":"#2a78d6","red":"#e34948","green":"#008300","blue":"#2a78d6"}; DASH={"R":(0,(2,2)),"G":(0,(6,2)),"B":"solid","red":(0,(2,2)),"green":(0,(6,2)),"blue":"solid"}
slug={"Pro 400H":"Pro400H","Provia 100F":"Provia100F","Velvia 50":"Velvia50","Ektachrome E100":"EktachromeE100"}
cs=colour.RGB_COLOURSPACES["sRGB"]; D65=colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"])
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
XYZ=colour.adaptation.chromatic_adaptation_VonKries(colour.xyY_to_XYZ(np.array(list(cc.data.values()))),colour.xy_to_XYZ(cc.illuminant),D65)
cclin=XYZ@cs.matrix_XYZ_to_RGB.T
def lab(l): return colour.XYZ_to_Lab(l@cs.matrix_RGB_to_XYZ.T,colour.XYZ_to_xy(D65))
def chroma(film,k):
    L0=lab(cclin[:18]); L=lab(render_lin(film,cclin[:18],k=k)); return np.hypot(L[:,1],L[:,2]).mean()/np.hypot(L0[:,1],L0[:,2]).mean()
lo,hi=0.0,1.0
for _ in range(40):
    mid=(lo+hi)/2
    if chroma("Pro 400H",mid)<1: lo=mid
    else: hi=mid
K_FILM["Pro 400H"]=round((lo+hi)/2,3); print("Pro 400H k =",K_FILM["Pro 400H"])
VAR={f:([("deepblack",None),("faded",None)] if KIND[f]=="neg" else [("standard",0.0),("vivid",model.INTERIMAGE_K)]) for f in NEW}
def rend(film,tag,k,lin): return render_lin(film,lin,variant=tag,k=k)
def cube(path,film,tag,k,n=33):
    g=np.linspace(0,1,n); B,G,R=np.meshgrid(g,g,g,indexing="ij"); rgb=np.stack([R,G,B],-1).reshape(-1,3); o=oetf(rend(film,tag,k,eotf(rgb)))
    with open(path,"w") as f:
        f.write(f'TITLE "{film} model ({tag})"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n')
        for r in o: f.write("%.6f %.6f %.6f\n"%tuple(r))
print("== neutral ramp (8-bit in -> out), chroma ratio")
vs=np.array([0,16,32,64,118,128,192,224,255])/255
for f in NEW:
    for tag,k in VAR[f]:
        p=OUT+f"luts/{slug[f].lower()}_{tag}.cube"; cube(p,f,tag,k); lut=read_cube(p)
        o=apply_cube(lut,np.stack([vs]*3,-1)); t=np.linspace(0,1,1024); ramp=apply_cube(lut,np.stack([t]*3,-1))
        kk=K_FILM.get(f,model.INTERIMAGE_K) if k is None else k
        print(f"{f:16s} {tag:9s}",[tuple(int(round(v*255)) for v in r) for r in o],"min step %.5f"%np.diff(ramp,axis=0).min(),"chroma %.2f"%chroma(f,kk))
# ---- ICC
SRC="/mnt/user-data/uploads/ebfcaeec-NikonZ5-Nikon_-_Neutral.icm"; b=open(SRC,"rb").read()
n=struct.unpack(">I",b[128:132])[0]; tags={b[132+12*i:136+12*i]:struct.unpack(">II",b[136+12*i:144+12*i]) for i in range(n)}
off,sz=tags[b"A2B0"]; ni,no,g=b[off+8],b[off+9],b[off+10]; nin,nout=struct.unpack(">HH",b[off+48:off+52]); c0=off+52+ni*nin*2; cl=g**3*no*2
clut=np.frombuffer(b[c0:c0+cl],">u2").astype(float).reshape(g,g,g,3); Lab=np.stack([clut[...,0]/65280*100,clut[...,1]/256-128,clut[...,2]/256-128],-1)
D50=np.array([0.9642,1.0,0.8249]); d50xy=colour.XYZ_to_xy(D50)
def lab_to_lin(L): return colour.adaptation.chromatic_adaptation_VonKries(colour.Lab_to_XYZ(L,d50xy),D50,D65,transform="Bradford")@cs.matrix_XYZ_to_RGB.T
def lin_to_lab(l): return colour.XYZ_to_Lab(colour.adaptation.chromatic_adaptation_VonKries(l@cs.matrix_RGB_to_XYZ.T,D65,D50,transform="Bradford"),d50xy)
def enc(L): return np.clip(np.round(np.stack([L[...,0]/100*65280,(L[...,1]+128)*256,(L[...,2]+128)*256],-1)),0,65535).astype(">u2")
assert bytes(b[:c0]+enc(Lab).tobytes()+b[c0+cl:])==b
baselin=lab_to_lin(Lab); srgb=ImageCms.createProfile("sRGB"); ramp8=np.stack([np.linspace(0,255,9).round()]*3,-1).astype(np.uint8)[None]
def through(pb,arr): return np.asarray(ImageCms.applyTransform(Image.fromarray(arr),ImageCms.buildTransform(ImageCms.ImageCmsProfile(io.BytesIO(pb)),srgb,"RGB","RGB",renderingIntent=1)))[0]
print("== ICC neutral ramp via lcms; base:",through(b,ramp8).tolist())
for f in NEW:
    for tag,k in VAR[f]:
        o=rend(f,tag,k,baselin.reshape(-1,3)).reshape(baselin.shape); nb=b[:c0]+enc(lin_to_lab(o)).tobytes()+b[c0+cl:]; assert len(nb)==len(b)
        name=f"NikonZ5-Film {slug[f]} {tag}.icm"; open(OUT+"icc/"+name,"wb").write(nb); print(" ",name,through(nb,ramp8).tolist())
# ---- preview
patches=np.clip(oetf(np.clip(cclin,0,1)),0,1).reshape(4,6,3)
def chart():
    ps=60; img=np.zeros((6*ps,6*ps,3))
    for r in range(4):
        for c in range(6): img[r*ps:(r+1)*ps,c*ps:(c+1)*ps]=patches[r,c]
    img[4*ps:5*ps]=np.linspace(0,1,6*ps)[None,:,None]; h=np.linspace(0,1,6*ps,endpoint=False)
    img[5*ps:]=matplotlib.colors.hsv_to_rgb(np.stack([h,np.full_like(h,0.75),np.full_like(h,0.85)],-1))[None]; return img
src=chart(); fig,axs=plt.subplots(2,5,figsize=(16.5,7.6),facecolor=SURF)
for r in range(2):
    for c,name in enumerate(["元画像（sRGB）"]+NEW):
        ax=axs[r,c]; ax.axis("off")
        if c==0:
            if r==0: ax.imshow(src,interpolation="nearest"); ax.set_title(name,fontsize=12,color=INK,loc="left")
            continue
        tag=VAR[name][r][0]; ax.imshow(np.clip(apply_cube(read_cube(OUT+f"luts/{slug[name].lower()}_{tag}.cube"),src),0,1),interpolation="nearest"); ax.set_title(f"{name}  {tag}",fontsize=12,color=INK,loc="left")
fig.suptitle("LUT適用プレビュー（追加4銘柄）　上からカラーチェッカー、グレー階調、色相スイープ",x=0.01,ha="left",fontsize=11,color=SEC)
fig.tight_layout(rect=(0,0,1,0.95),h_pad=2.5); fig.savefig(OUT+"preview_new_films.png",dpi=120,facecolor=SURF); plt.close(fig)
# ---- curves chart
fig,axs=plt.subplots(2,4,figsize=(15.5,7.4),facecolor=SURF)
for j,f in enumerate(NEW):
    ax=axs[0,j]; ref=model.res[f]["ref"]
    for ch in "BGR":
        c=model.res[f]["ch"][ch]; xs=(np.array(c["x"])-ref)/0.30103; ax.plot(xs,c["d"],color=COL[ch],lw=2,ls=DASH[ch],solid_capstyle="round")
    ax.axvline(0,color=AX,lw=1); ax.set_title(f+("（ネガ）" if KIND[f]=="neg" else "（ポジ）"),fontsize=13,color=INK,loc="left",pad=10)
    ax.set_xlim(-7.5,7.5); ax.set_ylim(0,4.0); ax.set_xticks(range(-6,7,2)); ax.set_xlabel("中間グレーからの段数（EV）",fontsize=10,color=SEC)
    ax=axs[1,j]
    for layer,lab_ in (("blue","B"),("green","G"),("red","R")):
        s=model.sp[f]["sens"][layer]; y=np.array(s["logS"])-max(s["logS"]); ax.plot(s["wl"],y,color=COL[layer],lw=2,ls=DASH[layer])
        ax.annotate(lab_,(s["wl"][int(np.argmax(s["logS"]))],0),xytext=(0,5),textcoords="offset points",ha="center",fontsize=10,color=SEC)
    if "cyan4th" in F2[f]["sens"]:
        s=F2[f]["sens"]["cyan4th"]; top=max(F2[f]["sens"]["green"]["logS"]); ax.plot(s["wl"],np.array(s["logS"])-top,color="#898781",lw=2,ls=(0,(1,2))); ax.annotate("第4層",(s["wl"][len(s["wl"])//2],s["logS"][len(s["wl"])//2]-top),xytext=(0,6),textcoords="offset points",ha="center",fontsize=9.5,color=SEC)
    ax.set_ylim(-2.2,0.3); ax.set_xlim(370,710); ax.set_xlabel("波長（nm）",fontsize=10,color=SEC)
for ax in axs.ravel():
    ax.set_facecolor(SURF); ax.grid(axis="y",color=GRID,lw=1); ax.set_axisbelow(True); ax.tick_params(colors=MUT,length=0,labelsize=9.5)
    for s_ in ("top","right","left"): ax.spines[s_].set_visible(False)
    ax.spines["bottom"].set_color(AX)
axs[0,0].set_ylabel("濃度",fontsize=10,color=SEC); axs[1,0].set_ylabel("相対log感度（各層のピーク = 0）",fontsize=10,color=SEC)
from matplotlib.lines import Line2D
fig.legend([Line2D([],[],color=COL[c],lw=2,ls=DASH[c]) for c in "BGR"],["B（青感層）","G（緑感層）","R（赤感層）"],loc="upper right",ncol=3,frameon=False,fontsize=10,labelcolor=SEC,bbox_to_anchor=(0.99,1.0))
fig.suptitle("特性曲線（上段）と分光感度（下段）　追加4銘柄、データシートから抽出",x=0.01,ha="left",fontsize=12,color=INK)
fig.tight_layout(rect=(0,0,1,0.95)); fig.savefig(OUT+"curves_new_films.png",dpi=140,facecolor=SURF)
# ---- CSV
with open(OUT+"characteristic_curves_new_films.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["film","type","log_H","stops_from_mid_gray","D_red","D_green","D_blue"])
    for f in NEW:
        ch=model.res[f]["ch"]; lo=max(ch[c]["x"][0] for c in "RGB"); hi=min(ch[c]["x"][-1] for c in "RGB")
        for x in np.round(np.arange(-3.6,1.2001,0.05),2):
            if lo<=x<=hi: w.writerow([f,KIND[f],x,round((x-model.res[f]["ref"])/0.30103,2)]+[round(float(np.interp(x,ch[c]["x"],ch[c]["d"])),3) for c in "RGB"])
with open(OUT+"spectral_sensitivity_new_films.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["film","wavelength_nm","logS_blue_layer","logS_green_layer","logS_red_layer","logS_4th_layer"])
    for f in NEW:
        for wl_ in range(380,701,5):
            row=[f,wl_]
            for nme in ("blue","green","red","cyan4th"):
                s=F2[f]["sens"].get(nme); row.append(round(float(np.interp(wl_,s["wl"],s["logS"])),3) if s and s["wl"][0]<=wl_<=s["wl"][-1] else "")
            w.writerow(row)
with open(OUT+"e100_spectral_dye_density.csv","w",newline="") as fh:
    w=csv.writer(fh); d=F2["Ektachrome E100"]["dyes"]; ks=[k for k in ("yellow","magenta","cyan","neutral_sum") if k in d]; w.writerow(["wavelength_nm"]+ks)
    for wl_ in range(400,701,5): w.writerow([wl_]+[round(float(np.interp(wl_,d[k]["wl"],d[k]["d"])),3) if d[k]["wl"][0]-1<=wl_<=d[k]["wl"][-1]+1 else "" for k in ks])
with open(OUT+"film_parameters.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["film","type","iso","ref_logH","gamma_R","gamma_G","gamma_B","interimage_k"])
    for f in ALL: w.writerow([f,KIND[f],ISO[f],round(model.res[f]["ref"],3)]+[round(model.summ[f][c]["gamma"],3) for c in "RGB"]+[K_FILM.get(f,model.INTERIMAGE_K) if KIND[f]=="neg" else "0 / %.3f"%model.INTERIMAGE_K])
json.dump(K_FILM,open("/home/claude/work2/kfilm.json","w"))

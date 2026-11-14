import sys, csv, json, numpy as np, colour
sys.path.insert(0,"/home/claude/scripts")
from model import *
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.rcParams["font.family"]="IPAGothic"
OUT="/home/claude/out/"; INK="#0b0b0b"; SEC="#52514e"; MUT="#898781"; GRID="#e1e0d9"; AX="#c3c2b7"; SURF="#fcfcfb"
COL={"red":"#e34948","green":"#008300","blue":"#2a78d6"}; DASH={"red":(0,(2,2)),"green":(0,(6,2)),"blue":"solid"}
slug={"Portra 160":"portra160","Portra 400":"portra400","Ektar 100":"ektar100"}
# LUTs
for film in ORDER:
    write_cube(OUT+f"luts/{slug[film]}_deepblack.cube",film,deep_black=True,title=f"{film} model (deep black)")
    write_cube(OUT+f"luts/{slug[film]}_faded.cube",film,deep_black=False,title=f"{film} model (faded toe)")
# verification
print("== neutral axis (8bit) deepblack / faded")
vs=np.array([0,16,32,64,118,128,192,255])/255
for film in ORDER:
    for tag in ("deepblack","faded"):
        lut=read_cube(OUT+f"luts/{slug[film]}_{tag}.cube")
        o=apply_cube(lut,np.stack([vs]*3,-1)); direct=film_render(film,np.stack([vs]*3,-1),deep_black=(tag=="deepblack"))
        ramp=apply_cube(lut,np.stack([np.linspace(0,1,256)]*3,-1))
        print(f"{film:10s} {tag:9s}",[tuple(int(round(v*255)) for v in r) for r in o],"mono",bool(np.all(np.diff(ramp,axis=0)>=-1e-6)),"interp-err %.4f"%np.abs(o-direct).max())
# saturation check on primaries
print("== sRGB primaries/secondaries at 50% through LUT")
test=np.array([[.6,.2,.2],[.2,.6,.2],[.2,.2,.6],[.6,.6,.2],[.2,.6,.6],[.6,.2,.6]])
for film in ORDER:
    lut=read_cube(OUT+f"luts/{slug[film]}_deepblack.cube"); print(film,(apply_cube(lut,test)*255).round().astype(int).tolist())
# preview
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
xyY=np.array(list(cc.data.values())); XYZ=colour.xyY_to_XYZ(xyY)
XYZ=colour.adaptation.chromatic_adaptation_VonKries(XYZ,colour.xy_to_XYZ(cc.illuminant),colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]))
patches=np.clip(colour.XYZ_to_sRGB(XYZ),0,1).reshape(4,6,3)
def chart():
    ps=60; img=np.zeros((4*ps+2*ps,6*ps,3))
    for r in range(4):
        for c in range(6): img[r*ps:(r+1)*ps,c*ps:(c+1)*ps]=patches[r,c]
    img[4*ps:5*ps]=np.linspace(0,1,6*ps)[None,:,None]
    h=np.linspace(0,1,6*ps,endpoint=False); hsv=np.stack([h,np.full_like(h,0.75),np.full_like(h,0.85)],-1)
    img[5*ps:]=matplotlib.colors.hsv_to_rgb(hsv)[None]
    return img
src=chart()
for tag,title in (("deepblack","黒を締めた版（deepblack）"),("faded","フィルムの足をそのまま残した版（faded）")):
    fig,axs=plt.subplots(1,4,figsize=(14,4.4),facecolor=SURF)
    for ax,name in zip(axs,["元画像（sRGB）"]+ORDER):
        im=src if name.startswith("元") else apply_cube(read_cube(OUT+f"luts/{slug[name]}_{tag}.cube"),src)
        ax.imshow(np.clip(im,0,1),interpolation="nearest"); ax.set_title(name,fontsize=12,color=INK,loc="left"); ax.axis("off")
    fig.suptitle(f"LUT適用プレビュー：{title}　上からカラーチェッカー、グレー階調、色相スイープ",x=0.01,ha="left",fontsize=11,color=SEC)
    fig.tight_layout(rect=(0,0,1,0.93)); fig.savefig(OUT+f"preview_{tag}.png",dpi=130,facecolor=SURF); plt.close(fig)
# spectral chart
fig,axs=plt.subplots(2,3,figsize=(13,7.2),facecolor=SURF,sharex="row",sharey="row")
for j,film in enumerate(ORDER):
    ax=axs[0,j]; ax.set_facecolor(SURF)
    for layer,lab in (("blue","B"),("green","G"),("red","R")):
        s=sp[film]["sens"][layer]; y=np.array(s["logS"])-max(s["logS"])
        ax.plot(s["wl"],y,color=COL[layer],lw=2,ls=DASH[layer])
        k=int(np.argmax(s["logS"])); ax.annotate(lab,(s["wl"][k],0),xytext=(0,5),textcoords="offset points",ha="center",fontsize=10,color=SEC)
    ax.set_title(film,fontsize=13,color=INK,loc="left",pad=14); ax.set_ylim(-2.2,0.25); ax.set_xlim(370,710)
    ax=axs[1,j]; ax.set_facecolor(SURF); d=sp[film]["dye"]
    ax.plot(d["midscale_neutral"]["wl"],d["midscale_neutral"]["d"],color="#52514e",lw=2); ax.plot(d["dmin"]["wl"],d["dmin"]["d"],color="#898781",lw=2,ls=(0,(5,2)))
    ax.annotate("中間グレー",(560,np.interp(560,d["midscale_neutral"]["wl"],d["midscale_neutral"]["d"])),xytext=(0,8),textcoords="offset points",fontsize=9.5,color=SEC)
    ax.annotate("Dmin（未露光部）",(615,np.interp(615,d["dmin"]["wl"],d["dmin"]["d"])),xytext=(0,8),textcoords="offset points",fontsize=9.5,color=SEC)
    ax.set_ylim(0,2.3); ax.set_xlabel("波長（nm）",fontsize=10,color=SEC)
for ax in axs.ravel():
    ax.grid(axis="y",color=GRID,lw=1); ax.set_axisbelow(True); ax.tick_params(colors=MUT,length=0,labelsize=9.5)
    for s in ("top","right","left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AX)
axs[0,0].set_ylabel("相対log感度（各層のピーク = 0）",fontsize=10,color=SEC); axs[1,0].set_ylabel("分光濃度",fontsize=10,color=SEC)
fig.suptitle("分光感度（上段）と分光色素濃度（下段）　Kodakデータシート 2025年1月版から抽出",x=0.01,ha="left",fontsize=12,color=INK)
fig.tight_layout(rect=(0,0,1,0.95)); fig.savefig(OUT+"spectral_curves_comparison.png",dpi=150,facecolor=SURF)
# matrices + Z5 curve
with open(OUT+"film_layer_matrices.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["film","layer","from_sRGB_R","from_sRGB_G","from_sRGB_B"])
    for film in ORDER:
        for n,row in zip(("red_layer","green_layer","blue_layer"),matrix(film)): w.writerow([film,n]+[round(float(v),4) for v in row])
vin=np.array([0,8,16,24,32,40,48,64,80,96,128,160,192,224,255])
with open(OUT+"z5_picture_control_tone_curve.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["film","variant","input","output"])
    for film in ORDER:
        for tag in ("deepblack","faded"):
            o=film_render(film,np.stack([vin/255]*3,-1),deep_black=(tag=="deepblack"),use_matrix=False)
            for v,r in zip(vin,o): w.writerow([film,tag,int(v),int(round(float(r@[0.2126,0.7152,0.0722])*255))])

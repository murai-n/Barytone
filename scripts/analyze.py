import json, sys, csv, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
res=json.load(open("/home/claude/work/curves.json")); OUT="/home/claude/out/"
jp=[f.name for f in font_manager.fontManager.ttflist if any(k in f.name for k in ("Noto Sans CJK","IPAGothic","IPAexGothic","TakaoGothic","Noto Sans JP"))]
print("jp fonts", sorted(set(jp))[:3])
if jp: plt.rcParams["font.family"]=jp[0]
COL={"R":"#e34948","G":"#008300","B":"#2a78d6"}; DASH={"R":(0,(2,2)),"G":(0,(6,2)),"B":"solid"}
INK="#0b0b0b"; SEC="#52514e"; MUT="#898781"; GRID="#e1e0d9"; AX="#c3c2b7"; SURF="#fcfcfb"
order=["Portra 160","Portra 400","Ektar 100"]
def D(film,ch,x): c=res[film]["ch"][ch]; return np.interp(x,c["x"],c["d"])
# 1. CSV of curves
grid=np.round(np.arange(-3.5,1.2001,0.05),2)
with open(OUT+"characteristic_curves.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["film","log_H","stops_from_ref","D_red","D_green","D_blue"])
    for film in order:
        lo=max(res[film]["ch"][c]["x"][0] for c in "RGB"); hi=min(res[film]["ch"][c]["x"][-1] for c in "RGB")
        for x in grid:
            if lo<=x<=hi: w.writerow([film,x,round((x-res[film]["ref"])/0.30103,2)]+[round(float(D(film,c,x)),3) for c in "RGB"])
# 2. gamma
summ={}
print("film        ref    ch  Dmin  D@ref gamma(ref-0.3..ref+1.5)  gamma_lo(ref-0.3..+0.6) gamma_hi(+0.6..+1.5)")
for film in order:
    ref=res[film]["ref"]; summ[film]={}
    for ch in "RGB":
        hi=min(ref+1.5,res[film]["ch"][ch]["x"][-1])
        def g(a,b):
            xs=np.linspace(a,b,60); return float(np.polyfit(xs,D(film,ch,xs),1)[0])
        s=dict(dmin=float(min(res[film]["ch"][ch]["d"])),dref=float(D(film,ch,ref)),gamma=g(ref-0.3,hi),glo=g(ref-0.3,ref+0.6),ghi=g(ref+0.6,hi))
        summ[film][ch]=s
        print(f"{film:11s} {ref:6.2f} {ch}  {s['dmin']:.2f}  {s['dref']:.2f}  {s['gamma']:.3f}   {s['glo']:.3f}   {s['ghi']:.3f}")
json.dump(summ,open("/home/claude/work/summary.json","w"),indent=1)
# 3. chart: small multiples, x = stops from reference
fig,axs=plt.subplots(1,3,figsize=(13,4.6),sharey=True,facecolor=SURF)
for ax,film in zip(axs,order):
    ref=res[film]["ref"]; ax.set_facecolor(SURF)
    for ch in "BGR":
        c=res[film]["ch"][ch]; xs=(np.array(c["x"])-ref)/0.30103
        ax.plot(xs,c["d"],color=COL[ch],lw=2,ls=DASH[ch],solid_capstyle="round")
        ax.annotate(f"{ch}  γ {summ[film][ch]['gamma']:.2f}",(xs[-1],c["d"][-1]),xytext=(6,0),textcoords="offset points",ha="left",va="center",fontsize=9.5,color=SEC)
    ax.axvline(0,color=AX,lw=1); ax.text(0.15,0.08,"基準露光\n(Log H Ref)",fontsize=8.5,color=MUT,va="bottom")
    ax.set_title(film,fontsize=13,color=INK,loc="left",pad=10)
    ax.set_xlim(-7.5,10.8); ax.set_ylim(0,3.3); ax.set_xticks(range(-6,7,2))
    ax.grid(axis="y",color=GRID,lw=1); ax.set_axisbelow(True)
    for s in ("top","right","left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AX); ax.tick_params(colors=MUT,length=0,labelsize=9.5)
    ax.set_xlabel("基準露光からの段数（EV）",fontsize=10,color=SEC)
axs[0].set_ylabel("濃度（Status M）",fontsize=10,color=SEC)
from matplotlib.lines import Line2D
fig.legend([Line2D([],[],color=COL[c],lw=2,ls=DASH[c]) for c in "BGR"],["B（青感層）","G（緑感層）","R（赤感層）"],loc="upper right",ncol=3,frameon=False,fontsize=10,labelcolor=SEC,bbox_to_anchor=(0.99,1.0))
fig.suptitle("特性曲線の比較（Kodakデータシート 2025年1月版から抽出）",x=0.01,ha="left",fontsize=12,color=INK,y=0.99)
fig.tight_layout(rect=(0,0,1,0.94)); fig.savefig(OUT+"characteristic_curves_comparison.png",dpi=160,facecolor=SURF)
# 4. Capture One curve points
ENC=2.2; GRAY=0.18
vin=[0,16,24,32,48,64,96,128,160,192,224,255]
for tag,perch in (("captureone_rgb_curves.csv",True),("captureone_rgb_curves_statusM_raw.csv",False)):
    rows=[]
    for film in order:
        ref=res[film]["ref"]
        for v in vin:
            L=max((v/255)**ENC,1e-6); x=ref+np.log10(L/GRAY)
            out=[]
            for ch in "RGB":
                gp=1.0/summ[film][ch if perch else "G"]["gamma"]
                c=res[film]["ch"][ch]; xx=min(max(x,c["x"][0]),c["x"][-1])
                P=GRAY*10**(gp*(D(film,ch,xx)-summ[film][ch]["dref"]))
                out.append(int(round(255*min(P,1.0)**(1/ENC))))
            rows.append([film,v]+out)
    with open(OUT+tag,"w",newline="") as f:
        w=csv.writer(f); w.writerow(["film","input","R_output","G_output","B_output"]); w.writerows(rows)
    print(tag)
    for r in rows: print(r)

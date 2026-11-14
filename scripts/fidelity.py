import sys; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, json, warnings; warnings.filterwarnings("ignore")
import model3 as M, model, model2
d65=colour.XYZ_to_xy(M.D65W); G=M.GRAY
negs=[f for f in M.ALL if M.KIND[f]=="neg"]; poss=[f for f in M.ALL if M.KIND[f]!="neg"]
print("== 0. data ranges"); 
for f in M.ALL:
    s=model.sp[f]["sens"]; c=model.res[f]["ch"]; ref=model.res[f]["ref"]
    print(f"{f:16s} sens wl "+" ".join(f"{k[0]}:{s[k]['wl'][0]:.0f}-{s[k]['wl'][-1]:.0f}" for k in ("blue","green","red"))+f" | curve EV {(max(c[k]['x'][0] for k in 'RGB')-ref)/0.30103:+.1f}..{(min(c[k]['x'][-1] for k in 'RGB')-ref)/0.30103:+.1f}  ref {ref:.3f}")
print("dye keys", {f:list(M.DY['films'][f].keys()) for f in M.DY['films']})
print("== 1. ISO speed recomputed from digitised curves (checks the log H axis)")
for f in negs:
    c=model.res[f]["ch"]; h=[]
    for k in "RGB":
        x=np.array(c[k]["x"]); d=np.array(c[k]["d"]); h.append(np.interp(d.min()+0.15,d,x))
    Hm=np.sqrt(10**h[1]*10**max(h)); print(f"{f:16s} ISO(5800) {np.sqrt(2)/Hm:6.0f}  box {M.ISO[f]}  -> {np.log2(np.sqrt(2)/Hm/M.ISO[f]):+.2f} stop")
for f in poss:
    c=model.res[f]["ch"]; x=np.array(c["G"]["x"]); d=np.mean([np.interp(x,c[k]["x"],c[k]["d"]) for k in "RGB"],0)
    dmin=d.min(); Ht=np.interp(-(dmin+0.2),-d,x); Hs=np.interp(-(dmin+2.0),-d,x); Hm=np.sqrt(10**Ht*10**Hs)
    print(f"{f:16s} ISO(2240) {10/Hm:6.0f}  box {M.ISO[f]}  -> {np.log2(10/Hm/M.ISO[f]):+.2f} stop   Dmin {dmin:.2f} Dmax {d.max():.2f}")
print("== 2. smoothing applied to traced curves (raw vs used)")
for f in model2.NEW:
    v=model2.F2[f]
    print(f"{f:16s} "+" ".join(f"{k}: max {np.abs(np.array(v['ch'][k]['d'])-np.array(model.res[f]['ch'][k]['d'])).max():.3f} rms {np.sqrt(np.mean((np.array(v['ch'][k]['d'])-np.array(model.res[f]['ch'][k]['d']))**2)):.3f}" for k in "RGB"))
print("== 3. characteristic curve recovered from model output (fade / slide, neutral scale)")
ev=np.linspace(-9,6,600); Xg=np.outer(G*2**ev,M.D65W)
for f in negs:
    P=M.render(f,Xg,dict(deep=False,k=M.BASE_K))@M.M_XYZ_SRGB.T; ref=model.res[f]["ref"]; out=[]
    for i,k in enumerate("RGB"):
        c=model.res[f]["ch"][k]; s=model.summ[f][k]; x=ref+np.log10(2**ev)
        ok=(x>=c["x"][0])&(x<=c["x"][-1])&(P[:,i]<0.999)&(P[:,i]>1e-6)
        Dm=s["dref"]+s["gamma"]*np.log10(P[ok,i]/G); Dd=np.interp(x[ok],c["x"],c["d"])
        out.append(f"{k}: max err {abs(Dm-Dd).max():.4f} (EV {ev[ok].min():+.1f}..{ev[ok].max():+.1f})")
    print(f"{f:16s} "+"  ".join(out))
for f in poss:
    u=M.UNMIX[f]; ref=model.res[f]["ref"]; x=ref+np.log10(2**ev); ok=(x>=u["x"][0])&(x<=u["x"][-1])
    X=M._render_v3(f,Xg[ok],dict(k=0.3)); Dvis=-np.log10(X[:,1])
    c=model.res[f]["ch"]; Dbar=np.mean([np.interp(x[ok],c[k]["x"],c[k]["d"]) for k in "RGB"],0); Dbar0=Dbar-Dbar.min()
    sa=M.status_a(u["a"],u["E"]); Dm=np.stack([np.interp(u["x"],c[k]["x"],c[k]["d"]) for k in "RGB"],1)
    print(f"{f:16s} visual density vs mean curve (above Dmin): max err {abs(Dvis-Dbar0).max():.3f} | Status A of rebuilt dyes vs chart: max {abs(sa-Dm).max():.3f} rms {np.sqrt(((sa-Dm)**2).mean()):.3f} per ch max {np.abs(sa-Dm).max(0).round(3)}")
print("== 4. paper curves: Status A of rebuilt dyes vs chart")
for pid,u in M.PAPERS.items():
    sa=M.status_a(u["a"],u["E"]); print(f"{pid:8s} max {abs(sa-u['D']).max():.3f} rms {np.sqrt(((sa-u['D'])**2).mean()):.3f} per ch {np.abs(sa-u['D']).max(0).round(3)}  Dmin {u['D'][0].round(2)} Dmax {u['D'][-1].round(2)}  gamma {M.paper_gamma(pid):.2f}")
for f in negs: print(f"{f:16s} neg gamma RGB {[round(model.summ[f][k]['gamma'],3) for k in 'RGB']}  native system gamma (endura) {model.summ[f]['G']['gamma']*M.paper_gamma('endura'):.2f}  scale used: printA/B base {M.print_scale(f,'endura',M.PB_GAMMA):.2f}/{M.print_scale(f,'crystal',M.PB_GAMMA):.2f}")
print("== 5. spectral sensitivity: layer exposures of measured ColorChecker spectra, true vs model (stops)")
fine=colour.SpectralShape(300,800,1); wf=fine.wavelengths
d65f=colour.SDS_ILLUMINANTS["D65"].copy().align(fine).values; cmff=colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(fine).values
sds=colour.SDS_COLOURCHECKERS["ColorChecker N Ohta"]; R=np.array([sd.copy().interpolate(colour.SpectralShape(380,780,1)).extrapolate(fine).values for sd in sds.values()]); R=np.clip(R,0,1)
XYZ=(R*d65f)@cmff/(d65f@cmff[:,1])
for f in M.ALL:
    T=np.zeros((24,3))
    for i,layer in enumerate(("red","green","blue")):
        s=model.sp[f]["sens"][layer]; S=np.where((wf>=s["wl"][0])&(wf<=s["wl"][-1]),10**np.interp(wf,s["wl"],s["logS"]),0.0)*d65f
        T[:,i]=R@S/S.sum()
    Hm=M.exposures(f,XYZ); e=np.log2(Hm/T)
    # grid-only error: true spectra on the model's 10 nm grid
    Rg=np.array([np.interp(M.WL,wf,r) for r in R]); Hg=Rg@M.KER[f].T; eg=np.log2(Hg/T)
    print(f"{f:16s} total: mean|e| {abs(e[:18]).mean():.3f} max {abs(e[:18]).max():.2f} (R {abs(e[:18,0]).mean():.3f} G {abs(e[:18,1]).mean():.3f} B {abs(e[:18,2]).mean():.3f}) greys max {abs(e[18:]).max():.3f} | 10nm grid + range only: mean {abs(eg[:18]).mean():.3f} max {abs(eg[:18]).max():.2f}")
print("== 6. what the base variant removes (dE2000 base vs fade/slide core, 18 colour patches) and non-data parameters")
cc=colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
X24=colour.adaptation.chromatic_adaptation_VonKries(colour.xyY_to_XYZ(np.array(list(cc.data.values()))),colour.xy_to_XYZ(cc.illuminant),M.D65W)
lab=lambda X: colour.XYZ_to_Lab(X,d65)
for f in M.ALL:
    vs=M.variants(f); b=lab(M.render(f,X24,vs[0])); o=lab(M.render(f,X24,vs[-1])); k0=lab(M.render(f,X24,dict(base=True,k=0.0)))
    de=colour.delta_E(b[:18],o[:18],method="CIE 2000"); dab=np.hypot(b[:18,1]-o[:18,1],b[:18,2]-o[:18,2])
    print(f"{f:16s} base vs {vs[-1]['id']}: dE00 mean {de.mean():.1f} (ab-only {dab.mean():.1f}, dL {abs(b[:18,0]-o[:18,0]).mean():.1f}) | interimage k=0.36 vs 0: dE00 {colour.delta_E(b[:18],k0[:18],method='CIE 2000').mean():.1f}, chroma x{np.hypot(b[:18,1],b[:18,2]).mean()/np.hypot(k0[:18,1],k0[:18,2]).mean():.2f}")

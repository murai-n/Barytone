"""slide tone for a monitor: CAM16 from a dark-surround light box (LA 254) to a dim-surround display (LA 20), then black point mapped to display black"""
import sys; sys.path.insert(0,"/home/claude/scripts")
import numpy as np
import styles as S, model3 as M
DARK=(0.8,0.525,0.8); DIM=(0.9,0.59,0.9)
BLACK_LSTAR=3.0; YT=BLACK_LSTAR/903.3
def cond(LA,sur):
    old=M.SURROUND_AVG; M.SURROUND_AVG=sur; p=M.cam_cond(LA); M.SURROUND_AVG=old; return p
PS,PD=cond(M.VIEW_SRC["slide"],DARK),cond(M.VIEW_DST,DIM)
def viewed(Y):
    X=np.outer(np.clip(Y,1e-7,None),M.D65W); J,Mc,h=M.cam_fwd(X,PS); return M.cam_inv(J,Mc,h,PD)[:,1]
def bpc(Y):
    lo,hi=Y.min(),Y.max(); return YT+(Y-lo)*(hi-YT)/(hi-lo)
OUT="/home/claude/slideview/"
res={}
for f,a in S.ALIAS.items():
    if M.KIND.get(f)!="pos": continue
    Y=M._render_core(f,S.GD,dict(k=0.0))[:,1]
    Yv=bpc(viewed(Y))
    raw=S.samp(S.toe(S.enc(Y),S.MONO_MIN)); new=S.samp(S.toe(S.enc(Yv),S.MONO_MIN))
    res[a]=(raw,new)
    S.OUT=OUT; S.write("2 Develop",f"Develop {a} - slide tone (viewed)",{"GradationCurve":new})
np.save(OUT+"res.npy",res,allow_pickle=True)
for a,(r,n) in res.items():
    print(a," ".join(f"{x:.2f}:{p:.3f}>{q:.3f}" for x,p,q in zip(S.x,r,n) if x in (0,.06,.12,.16,.2,.3,.385,.5,.7,1.0)))
# variant B: classic surround rule (dark-surround slides are made for system gamma ~1.5, a dim-surround display wants ~1.2):
# luminance raised to 1.2/1.5 = 0.8, white (clear film) fixed, then the same black mapping
P=1.2/1.5
for f,a in S.ALIAS.items():
    if M.KIND.get(f)!="pos": continue
    Y=M._render_core(f,S.GD,dict(k=0.0))[:,1]
    Yb=bpc(np.clip(Y,1e-7,None)**P); nb=S.samp(S.toe(S.enc(Yb),S.MONO_MIN))
    S.write("2 Develop",f"Develop {a} - slide tone (gamma 0.8)",{"GradationCurve":nb})
    r,n=res[a]; print("B",a," ".join(f"{x:.2f}:{p:.3f}/{q:.3f}/{w:.3f}" for x,p,q,w in zip(S.x,r,n,nb) if x in (0,.06,.12,.16,.2,.3,.5,.7,1.0)))

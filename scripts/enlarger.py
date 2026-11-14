"""Enlarger dichroic filters: a Y/M/C filter removes its complementary light from the printing lamp
(Y cuts blue, M cuts green, C cuts red).  1 unit = 0.01 density.  Printing time is re-timed so mid-grey
keeps its lightness, as a printer does after changing filtration, leaving a pure colour move.
The result is written as per-channel curves to lay over the print tone."""
import sys,io,contextlib; sys.path.insert(0,"/home/claude/scripts")
with contextlib.redirect_stdout(io.StringIO()): import styles as S
import numpy as np
from scipy.optimize import brentq
from scipy.interpolate import CubicSpline
M=S.M; F="Portra 400"; mid=np.argmin(abs(S.YD-0.18)); UNIT=10
def printed(pid,filt=(0,0,0),t=0.0):
    b0=M.print_balance(F,pid).copy(); M.PRINT_BAL[(F,pid)]=b0-np.array(filt,float)/100.0+t
    X=M._render_core(F,S.GD,dict(paper=pid,deep=False,k=0.0,gamma=1.5)); M.PRINT_BAL[(F,pid)]=b0; return X
def retimed(pid,filt):
    base=printed(pid)[mid,1]
    return printed(pid,filt,brentq(lambda t: printed(pid,filt,t)[mid,1]-base,-1.0,1.0,xtol=1e-7))
srgb=lambda X: S.enc(np.clip(X@M.M_XYZ_SRGB.T,0,None))
def mapping(xs,ys):
    """printed value -> filtered value.  Outside the print's own range the curve runs straight to
    (0,0) and (1,1): no flat run, and no slope break big enough to make Capture One's spline dip."""
    xs=np.clip(xs,0,1); ys=np.clip(ys,0,1)
    X=np.concatenate([[0.0],xs,[1.0]]); Y=np.concatenate([[0.0],ys,[1.0]])
    k=np.argsort(X); return np.interp(S.XD,X[k],Y[k])

if __name__=="__main__":
    out={}
    for pid,lab in (("endura","KEP"),("crystal","FCA"),("fujiflex","FFX"),("metallic","KEM"),("ultra","KUE"),("portra","KPE"),("supra","KSE")):
        b=srgb(printed(pid))
        for ch,i in (("Y",2),("M",1),("C",0)):
            for sgn in (+1,-1):
                f=np.zeros(3); f[i]=sgn*UNIT
                a=srgb(retimed(pid,tuple(f)))
                cur={}
                for j,k in enumerate(("GradationCurveRed","GradationCurveGreen","GradationCurveBlue")):
                    cur[k]=S.samp(S.toe(np.maximum.accumulate(mapping(b[:,j],a[:,j])),S.MONO_MIN))
                nm=f"Print {lab} - filter {sgn*UNIT:+d}{ch}"
                S.write("3 Print",nm,cur); out[nm]=cur
    bad=[n for n,c in out.items() for v in c.values() if not (np.diff(CubicSpline(S.x,v)(np.linspace(0,1,3001)))>=-1e-9).all()]
    print(len(out),"filter styles written | curves that dip:",bad or "none")

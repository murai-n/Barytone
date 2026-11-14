import time, numpy as np, colour, warnings
warnings.filterwarnings("ignore")
from colour.recovery import find_coefficients_Jakob2019
shape=colour.SpectralShape(380,780,5)
cmfs=colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(shape)
d65=colour.SDS_ILLUMINANTS["D65"].copy().align(shape)
cs=colour.RGB_COLOURSPACES["ITU-R BT.2020"]
import sys
N=33; t0=time.time(); FACE=int(sys.argv[1])
tab=np.zeros((3,N,N,3)); err=np.zeros((3,N,N))
g=np.linspace(0,1,N)
for face in [FACE]:
    others=[i for i in range(3) if i!=face]
    prev=None
    for i,u in enumerate(g):
        for j,v in enumerate(g):
            rgb=np.zeros(3); rgb[face]=1.0; rgb[others[0]]=u; rgb[others[1]]=v
            XYZ=colour.RGB_to_XYZ(rgb,cs,illuminant=cs.whitepoint) if False else rgb@cs.matrix_RGB_to_XYZ.T
            coef,e=find_coefficients_Jakob2019(XYZ,cmfs,d65,coefficients_0=prev if prev is not None else np.zeros(3),max_error=1e-4)
            tab[face,i,j]=coef; err[face,i,j]=e; prev=coef
        prev=tab[face,i,0]
    print("face",face,"done %.0fs"%(time.time()-t0),"max err %.4f median %.5f"%(err[face].max(),np.median(err[face])),flush=True)
np.save(f"/home/claude/m3/jk_face{FACE}.npy",tab[FACE]); np.save(f"/home/claude/m3/jk_err{FACE}.npy",err[FACE])

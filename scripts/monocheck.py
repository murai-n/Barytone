import sys, numpy as np
sys.path.insert(0,"/home/claude/scripts"); from model import *
for f in ("portra160_faded","ektar100_deepblack","ektar100_faded","portra400_deepblack"):
    lut=read_cube(f"/home/claude/out/luts/{f}.cube"); t=np.linspace(0,1,1024); r=apply_cube(lut,np.stack([t]*3,-1)); d=np.diff(r,axis=0)
    i=np.unravel_index(np.argmin(d),d.shape); print(f,"worst step %.5f (8bit %.2f) at input %.3f ch %d"%(d.min(),d.min()*255,t[i[0]],i[1]), "direct-model min step %.6f"%np.diff(film_render("Ektar 100" if "ektar" in f else "Portra 160" if "160" in f else "Portra 400",np.stack([t]*3,-1),deep_black="deep" in f),axis=0).min())

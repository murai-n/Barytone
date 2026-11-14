import sys,io,contextlib,colorsys; sys.path.insert(0,"/home/claude/scripts")
with contextlib.redirect_stdout(io.StringIO()): import styles as S
from scipy.optimize import least_squares
M=S.M; np=S.np; colour=S.colour
SEG=[("Red",0),("Orange",30),("Yellow",60),("Green",120),("Cyan",180),("Blue",240),("Purple",270),("Magenta",300)]
def hsv_xyz(h,s,v): return (np.array(colorsys.hsv_to_rgb(h/360,s,v))**2.2)@M.M_SRGB_XYZ.T
cent=np.array([np.degrees(np.arctan2(*S.lab(hsv_xyz(h,0.6,0.7)[None])[0,[2,1]]))%360 for _,h in SEG]); order=np.argsort(cent); cs=cent[order]
def weights(h):
    h=h%360; W=np.zeros((len(h),8)); ext=np.concatenate([[cs[-1]-360],cs,[cs[0]+360]]); idx=np.concatenate([[order[-1]],order,[order[0]]])
    j=np.clip(np.searchsorted(ext,h)-1,0,8); t=(h-ext[j])/(ext[j+1]-ext[j])
    np.add.at(W,(np.arange(len(h)),idx[j]),1-t); np.add.at(W,(np.arange(len(h)),idx[j+1]),t); return W
def coloredit(X,p):
    L=S.lab(X); C=np.hypot(L[:,1],L[:,2]); h=np.degrees(np.arctan2(L[:,2],L[:,1])); W=weights(h); p=p.reshape(8,3)
    g=np.clip(C/8,0,1)
    h2=np.radians(h+g*(W@p[:,0])); C2=C*(1+g*(W@p[:,1])/100); L2=L[:,0]+g*(W@p[:,2])
    return colour.Lab_to_XYZ(np.stack([L2,C2*np.cos(h2),C2*np.sin(h2)],1),S.d65)
train=np.array([hsv_xyz(h,s,v) for h in range(0,360,15) for s in (0.3,0.55,0.8) for v in (0.35,0.6,0.85)])
negs=[f for f in M.ALL if M.KIND[f]=="neg"]
pid,lab="ilfochrome","ILF"; pv=dict(base=True,bpaper=pid,k=0.0)
B=[M.render(f,train,M.variants(f)[0]) for f in negs]; T=[S.lab(M.render(f,train,pv)) for f in negs]
res=least_squares(lambda p: np.concatenate([(S.lab(coloredit(b,p))-t).ravel() for b,t in zip(B,T)]),np.zeros(24))
p=res.x.reshape(8,3)
print("Ilfochrome paper colour (Color Editor):")
for i,(n,_) in enumerate(SEG): print(f"  {n:8s} hue {p[i,0]:+5.1f}  sat {p[i,1]:+5.1f}  light {p[i,2]:+5.1f}")
ent=[]
for i,(n,h) in enumerate(SEG):
    r,g,b=[255*c for c in colorsys.hsv_to_rgb(h/360,0.85,0.95)]
    ent.append(f"1,1,0,{p[i,0]:.3f},{p[i,1]:.3f},{p[i,2]:.3f},{r:.1f},{g:.1f},{b:.1f},-15,15,-100,0,25,0,0,0,0")
S.write("3 Print","Print ILF - paper color (optional)",{},[("ColorCorrections",";".join(ent))])
print("wrote Print ILF - paper color (optional).costyle")

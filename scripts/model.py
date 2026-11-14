import json, numpy as np, colour
res=json.load(open("/home/claude/work/curves.json")); sp=json.load(open("/home/claude/work/spectral.json")); summ=json.load(open("/home/claude/work/summary.json"))
ORDER=["Portra 160","Portra 400","Ektar 100"]; GRAY=0.18
wl=np.arange(380,781,5.0)
basis=colour.recovery.MSDS_BASIS_FUNCTIONS_sRGB_MALLETT2019.copy().align(colour.SpectralShape(380,780,5)).values  # (81,3) r,g,b
d65=colour.SDS_ILLUMINANTS["D65"].copy().align(colour.SpectralShape(380,780,5)).values
def matrix(film):
    M=np.zeros((3,3))
    for i,layer in enumerate(("red","green","blue")):
        s=sp[film]["sens"][layer]; S=np.where((wl>=s["wl"][0])&(wl<=s["wl"][-1]),10**np.interp(wl,s["wl"],s["logS"]),0.0)
        for k in range(3): M[i,k]=np.sum(basis[:,k]*d65*S)
        M[i]/=M[i].sum()
    return M
def eotf(v): v=np.asarray(v,float); return np.where(v<=0.04045,v/12.92,((v+0.055)/1.055)**2.4)
def oetf(l): l=np.clip(l,0,1); return np.where(l<=0.0031308,l*12.92,1.055*l**(1/2.4)-0.055)
def film_render(film,rgb_enc,deep_black=True,use_matrix=True):
    """rgb_enc: (...,3) sRGB-encoded 0..1 -> sRGB-encoded 0..1"""
    return oetf(film_linear(film,eotf(rgb_enc),deep_black,use_matrix))
INTERIMAGE_K=0.361
def film_linear(film,lin,deep_black=True,use_matrix=True,k=None):
    """linear sRGB (may exceed 0..1) -> linear sRGB 0..1.  k = interimage strength (log-domain colour separation boost)"""
    k=INTERIMAGE_K if k is None else k
    lin=np.asarray(lin,float); M=matrix(film) if use_matrix else np.eye(3)
    H=np.clip(lin@M.T,1e-7,None); ref=res[film]["ref"]; z=np.zeros_like(H); zn=np.zeros_like(H); z0=np.zeros(3)
    xn=ref+np.log10(H).mean(-1)-np.log10(GRAY)   # neutral of the same overall exposure
    for i,ch in enumerate("RGB"):
        c=res[film]["ch"][ch]; g=summ[film][ch]["gamma"]; dref=summ[film][ch]["dref"]
        x=np.clip(ref+np.log10(H[...,i]/GRAY),c["x"][0],c["x"][-1])
        z[...,i]=(np.interp(x,c["x"],c["d"])-dref)/g; zn[...,i]=(np.interp(np.clip(xn,c["x"][0],c["x"][-1]),c["x"],c["d"])-dref)/g; z0[i]=(c["d"][0]-dref)/g
    dev=z-zn; dm=dev.mean(-1,keepdims=True); z=zn+dm+(1+k)*(dev-dm)   # neutrals (dev=0) are untouched: published curves already include interimage
    P=GRAY*10**z
    if deep_black:
        P0=GRAY*10**z0; w=np.clip((GRAY-P)/(GRAY-P0),0,1)**2; P=P-P0*w
    return np.clip(P,0,1)
def write_cube(path,film,n=33,title=None,**kw):
    g=np.linspace(0,1,n); B,G,R=np.meshgrid(g,g,g,indexing="ij")  # R fastest
    rgb=np.stack([R,G,B],-1).reshape(-1,3); o=film_render(film,rgb,**kw)
    with open(path,"w") as f:
        f.write(f'TITLE "{title or film}"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n')
        for r in o: f.write("%.6f %.6f %.6f\n"%tuple(r))
def read_cube(path):
    n=None; data=[]
    for line in open(path):
        t=line.split()
        if not t: continue
        if t[0]=="LUT_3D_SIZE": n=int(t[1])
        elif t[0][0] in "0123456789.-": data.append([float(v) for v in t])
    return np.array(data).reshape(n,n,n,3)  # [b,g,r]
def apply_cube(lut,img):
    n=lut.shape[0]; p=np.clip(img,0,1)*(n-1); i0=np.clip(np.floor(p).astype(int),0,n-2); f=p-i0
    out=np.zeros_like(img)
    for dr in (0,1):
        for dg in (0,1):
            for db in (0,1):
                w=(f[...,0] if dr else 1-f[...,0])*(f[...,1] if dg else 1-f[...,1])*(f[...,2] if db else 1-f[...,2])
                out+=w[...,None]*lut[i0[...,2]+db,i0[...,1]+dg,i0[...,0]+dr]
    return out
if __name__=="__main__":
    np.set_printoptions(precision=3,suppress=True)
    for film in ORDER:
        print(film,"\n",matrix(film))

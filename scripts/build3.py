import sys, io, struct, json, csv; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, warnings; warnings.filterwarnings("ignore")
import model3 as M, model
from PIL import Image, ImageCms
OUT="/home/claude/out3/"
ALIAS={"Portra 160": "KP160", "Portra 400": "KP400", "Ektar 100": "KE100", "Pro 400H": "FP400H", "Provia 100F": "FPR100", "Velvia 50": "FV50", "Ektachrome E100": "KEC100", "Gold 200": "KG200", "Portra 800": "KP800", "Vision3 500T": "KV500T", "Kodachrome 25": "KK25", "Kodachrome 64": "KK64", "Kodachrome 200": "KK200", "Astia 100F": "FA100", "Pro 160NS": "FP160NS", "Pro 800Z": "FP800Z", "Ektachrome 64T": "KET64", "Ektachrome 160T": "KET160", "Fujichrome 64T II": "FT64", "Portra 160NC": "KP160NC", "Portra 160VC": "KP160VC", "Portra 400NC": "KP400NC", "Portra 400VC": "KP400VC", "Vericolor III": "KVPS", "Ultra Color 100UC": "KUC100", "Ultra Color 400UC": "KUC400", "Pro Image 100": "KPI100", "Ektachrome EPN": "KEPN", "Velvia 100": "FV100", "Superia X-TRA 400": "FSX400"}
def eotf(v): v=np.asarray(v,float); return np.where(v<=0.04045,v/12.92,((v+0.055)/1.055)**2.4)
def oetf(l): l=np.clip(l,0,1); return np.where(l<=0.0031308,l*12.92,1.055*l**(1/2.4)-0.055)
def srgb_render(f,v,enc):
    X=eotf(enc)@M.M_SRGB_XYZ.T; return oetf(M.render(f,X,v)@M.M_XYZ_SRGB.T)
# ---- LUTs
n=33; g=np.linspace(0,1,n); B,G,R=np.meshgrid(g,g,g,indexing="ij"); grid=np.stack([R,G,B],-1).reshape(-1,3)
for f in M.ALL:
    for v in M.variants(f):
        o=srgb_render(f,v,grid)
        with open(OUT+f"luts/{ALIAS[f]}_{v['id']}.cube","w") as fh:
            fh.write(f'TITLE "{ALIAS[f]} {v["id"]} (film model v3)"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n')
            for r in o: fh.write("%.6f %.6f %.6f\n"%tuple(r))
        ramp=srgb_render(f,v,np.stack([np.linspace(0,1,1024)]*3,-1))
        print(f"{ALIAS[f]:16s} {v['id']:9s} gray ramp monotone {bool(np.all(np.diff(ramp,axis=0)>=-1e-4))}  min step {np.diff(ramp,axis=0).min():.5f}  118->{np.round(srgb_render(f,v,np.full((1,3),118/255))[0]*255).astype(int)}")
# ---- ICC (Z5 base)
SRC="/mnt/user-data/uploads/ebfcaeec-NikonZ5-Nikon_-_Neutral.icm"; b=open(SRC,"rb").read()
nt=struct.unpack(">I",b[128:132])[0]; tags={b[132+12*i:136+12*i]:struct.unpack(">II",b[136+12*i:144+12*i]) for i in range(nt)}
off,sz=tags[b"A2B0"]; ni,no,gg=b[off+8],b[off+9],b[off+10]; nin,nout=struct.unpack(">HH",b[off+48:off+52]); c0=off+52+ni*nin*2; cl=gg**3*no*2
clut=np.frombuffer(b[c0:c0+cl],">u2").astype(float).reshape(-1,3)
Lab=np.stack([clut[:,0]/65280*100,clut[:,1]/256-128,clut[:,2]/256-128],-1)
D50=np.array([0.9642,1.0,0.8249]); d50xy=colour.XYZ_to_xy(D50)
A50_65=M.cat(D50,M.D65W); A65_50=M.cat(M.D65W,D50)
X65=colour.Lab_to_XYZ(Lab,d50xy)@A50_65.T
def enc(L): return np.clip(np.round(np.stack([L[...,0]/100*65280,(L[...,1]+128)*256,(L[...,2]+128)*256],-1)),0,65535).astype(">u2")
srgb=ImageCms.createProfile("sRGB"); ramp8=np.stack([np.linspace(0,255,9).round()]*3,-1).astype(np.uint8)[None]
def through(pb,arr): return np.asarray(ImageCms.applyTransform(Image.fromarray(arr),ImageCms.buildTransform(ImageCms.ImageCmsProfile(io.BytesIO(pb)),srgb,"RGB","RGB",renderingIntent=1)))[0]
for f in M.ALL:
    for v in M.variants(f):
        Xo=M.render(f,X65,v); Lo=colour.XYZ_to_Lab(Xo@A65_50.T,d50xy)
        nb=b[:c0]+enc(Lo).tobytes()+b[c0+cl:]
        name=f"NikonZ5-Film {ALIAS[f]} {v['id']}"; open(OUT+"icc/"+name+".icm","wb").write(nb)
        print(" ICC",name,through(nb,ramp8)[:,1].tolist())
json.dump(dict(alias=ALIAS),open(OUT+"alias.json","w"))

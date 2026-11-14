import sys, struct, numpy as np, colour, io
sys.path.insert(0,"/home/claude/scripts")
from model import *
from PIL import Image, ImageCms
SRC="/mnt/user-data/uploads/ebfcaeec-NikonZ5-Nikon_-_Neutral.icm"; OUT="/home/claude/out/icc/"
b=open(SRC,"rb").read()
n=struct.unpack(">I",b[128:132])[0]; tags={b[132+12*i:136+12*i]:struct.unpack(">II",b[136+12*i:144+12*i]) for i in range(n)}
off,sz=tags[b"A2B0"]; assert b[off:off+4]==b"mft2"
ni,no,g=b[off+8],b[off+9],b[off+10]; nin,nout=struct.unpack(">HH",b[off+48:off+52])
c0=off+52+ni*nin*2; cl=g**3*no*2; assert c0+cl+no*nout*2<=off+sz
clut=np.frombuffer(b[c0:c0+cl],">u2").astype(float).reshape(g,g,g,3)   # [r,g,b] r slowest
intab=np.frombuffer(b[off+52:c0],">u2").reshape(3,nin); outtab=np.frombuffer(b[c0+cl:c0+cl+no*nout*2],">u2").reshape(3,nout)
print("grid",g,"inTab first/last",intab[:,0],intab[:,-1],"mid",intab[:,nin//2],"outTab",outtab.tolist())
Lab=np.stack([clut[...,0]/65280*100, clut[...,1]/256-128, clut[...,2]/256-128],-1)
print("black node",Lab[0,0,0].round(2),"white node",Lab[-1,-1,-1].round(2),"mid gray node",Lab[16,16,16].round(2),"red node",Lab[-1,0,0].round(1))
D50=np.array([0.9642,1.0,0.8249]); D65=colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"])
cs=colour.RGB_COLOURSPACES["sRGB"]; d50xy=colour.XYZ_to_xy(D50)
def lab_to_lin(Lab):
    XYZ=colour.Lab_to_XYZ(Lab,d50xy); XYZ=colour.adaptation.chromatic_adaptation_VonKries(XYZ,D50,D65,transform="Bradford"); return XYZ@cs.matrix_XYZ_to_RGB.T
def lin_to_lab(lin):
    XYZ=lin@cs.matrix_RGB_to_XYZ.T; XYZ=colour.adaptation.chromatic_adaptation_VonKries(XYZ,D65,D50,transform="Bradford"); return colour.XYZ_to_Lab(XYZ,d50xy)
def encode(Lab):
    e=np.stack([Lab[...,0]/100*65280,(Lab[...,1]+128)*256,(Lab[...,2]+128)*256],-1); return np.clip(np.round(e),0,65535).astype(">u2")
# round-trip checks
assert bytes(b[:c0]+encode(Lab).tobytes()+b[c0+cl:])==b, "identity rebuild mismatch"
lin=lab_to_lin(Lab); print("out-of-sRGB nodes: %.1f%%"%(100*np.mean((lin<-1e-4).any(-1)|(lin>1+1e-4).any(-1))), "roundtrip Lab err", np.abs(lin_to_lab(lin)-Lab).max().round(5))
slug={"Portra 160":"Portra160","Portra 400":"Portra400","Ektar 100":"Ektar100"}
srgb=ImageCms.createProfile("sRGB")
ramp=np.stack([np.linspace(0,255,9).round()]*3,-1).astype(np.uint8)[None]
cols=np.array([[[150,110,100],[110,150,105],[100,115,150],[180,120,90],[120,120,60],[90,130,140]]],np.uint8)
def through(pbytes,arr):
    t=ImageCms.buildTransform(ImageCms.ImageCmsProfile(io.BytesIO(pbytes)),srgb,"RGB","RGB",renderingIntent=1)
    return np.asarray(ImageCms.applyTransform(Image.fromarray(arr),t))[0]
print("base  neutral ramp ->sRGB",through(b,ramp).tolist()); print("base  colours",through(b,cols).tolist())
for film in ORDER:
    for tag,db in (("deepblack",True),("faded",False)):
        out=film_linear(film,lin.reshape(-1,3),deep_black=db).reshape(lin.shape)
        nb=b[:c0]+encode(lin_to_lab(out)).tobytes()+b[c0+cl:]
        assert len(nb)==len(b)
        name=f"NikonZ5-Film {slug[film]} {tag}.icm"; open(OUT+name,"wb").write(nb)
        p=ImageCms.ImageCmsProfile(io.BytesIO(nb)); 
        print(name,p.profile.device_class,p.profile.connection_space.strip(),"ramp",through(nb,ramp).tolist(),"\n   colours",through(nb,cols).tolist())

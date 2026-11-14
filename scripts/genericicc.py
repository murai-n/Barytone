"""Build generic ICC profiles (one per film) from the Nikon Z5 base camera profile.
Same rendering pipeline as camera-specific (build3.py): read the original Z5 CLUT,
convert Lab->XYZ(D65), apply film model, convert back to Lab(D50), write into a
self-contained ICC. The only difference from camera-specific is that this produces
a fresh ICC file (no dependency on the original .icm being installed).
"""
import sys,struct,os; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, colour, model3 as M
OUT="/home/claude/out3/generic_icc/"; os.makedirs(OUT,exist_ok=True)
ALIAS=__import__("json").load(open("/home/claude/out3/alias.json"))["alias"]

# ---- Read original Nikon Z5 camera profile CLUT ----
SRC="/mnt/user-data/uploads/ebfcaeec-NikonZ5-Nikon_-_Neutral.icm"
b=open(SRC,"rb").read()
nt=struct.unpack(">I",b[128:132])[0]
tags={b[132+12*i:136+12*i]:struct.unpack(">II",b[136+12*i:144+12*i]) for i in range(nt)}
off,sz=tags[b"A2B0"]; ni,no,g=b[off+8],b[off+9],b[off+10]
nin,nout=struct.unpack(">HH",b[off+48:off+52])
c0=off+52+ni*nin*2; cl=g**3*no*2
clut_raw=np.frombuffer(b[c0:c0+cl],">u2").astype(float).reshape(-1,3)

# Decode CLUT to Lab(D50)
Lab0=np.stack([clut_raw[:,0]/65280*100, clut_raw[:,1]/256-128, clut_raw[:,2]/256-128],-1)

# Lab(D50) -> XYZ(D65)
D50=np.array([0.9642,1.0,0.8249]); d50xy=colour.XYZ_to_xy(D50)
A50_65=M.cat(D50,M.D65W); A65_50=M.cat(M.D65W,D50)
X65=colour.Lab_to_XYZ(Lab0,d50xy)@A50_65.T

N=g  # same grid size as original (33)

# ---- ICC building helpers ----
def s15(x): return struct.pack(">i",int(round(x*65536)))
def xyznum(v): return s15(v[0])+s15(v[1])+s15(v[2])
def desc_tag(s):
    a=s.encode("ascii")+b"\x00"
    body=b"desc"+b"\x00"*4+struct.pack(">I",len(a))+a+struct.pack(">II",0,0)+struct.pack(">H",0)+bytes([0])+b"\x00"*67
    return body
def text_tag(s): return b"text"+b"\x00"*4+s.encode("ascii")+b"\x00"
def xyz_tag(v): return b"XYZ "+b"\x00"*4+xyznum(v)
def enc_lab(Lab):
    L=np.clip(Lab[:,0]/100*65280,0,65535)
    a=np.clip((Lab[:,1]+128)*256,0,65535)
    b2=np.clip((Lab[:,2]+128)*256,0,65535)
    return np.stack([L,a,b2],1).round().astype(">u2")
def a2b0(clut_u16):
    h=b"mft2"+b"\x00"*4+bytes([3,3,N,0])
    mat=b"".join(s15(x) for x in (1,0,0,0,1,0,0,0,1))
    tbl=struct.pack(">HH",nin,nout)
    # Copy input/output tables from original profile for identical interpolation
    intab=np.frombuffer(b[off+52:c0],">u2").tobytes()
    clutb=clut_u16.tobytes()
    outtab=np.frombuffer(b[c0+cl:c0+cl+no*nout*2],">u2").tobytes()
    return h+mat+tbl+intab+clutb+outtab

def build(film):
    # Apply film model: XYZ(D65) -> film render -> XYZ(D65) -> Lab(D50)
    Xo=M.render(film,X65,dict(id="base",base=True,k=0.0))
    Lo=colour.XYZ_to_Lab(Xo@A65_50.T,d50xy)
    clut_u16=enc_lab(Lo)

    desc=f"Film {ALIAS[film]} (generic, Nikon Z5)"
    tags_d={b"desc":desc_tag(desc),b"cprt":text_tag("Film emulation kit"),
            b"wtpt":xyz_tag(D50),b"A2B0":a2b0(clut_u16)}
    order=[b"desc",b"cprt",b"wtpt",b"A2B0"]
    n=len(order); tbl=struct.pack(">I",n); hoff=128+4+12*n; datab=b""; ents=b""
    for t in order:
        d=tags_d[t]; d+=b"\x00"*((4-len(d)%4)%4)
        ents+=t+struct.pack(">II",hoff+len(datab),len(tags_d[t])); datab+=d
    body=tbl+ents+datab
    size=128+len(body)
    hdr=struct.pack(">I",size)+b"\x00"*4+struct.pack(">I",0x02400000)+b"scnr"+b"RGB "+b"Lab "
    hdr+=b"\x00"*12  # date
    hdr+=b"acsp"+b"\x00"*4+b"\x00"*4+b"\x00"*4  # platform, flags, manufacturer
    hdr+=b"\x00"*12  # model (4) + attributes (8)
    hdr+=struct.pack(">I",0)   # rendering intent = perceptual
    hdr+=xyznum(D50)           # PCS illuminant
    hdr+=b"\x00"*4             # creator
    hdr+=b"\x00"*(128-len(hdr))
    open(OUT+f"Film {ALIAS[film]} generic.icc","wb").write(hdr+body)

for f in M.ALL: build(f)
print("generic ICCs:",len(os.listdir(OUT)),"→",OUT)

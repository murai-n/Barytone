import sys, struct
b=open(sys.argv[1],"rb").read()
print("size",len(b),"hdr size",struct.unpack(">I",b[:4])[0],"cmm",b[4:8],"ver",b[8:12].hex(),"class",b[12:16],"cs",b[16:20],"pcs",b[20:24],"plat",b[40:44],"intent",struct.unpack(">I",b[64:68])[0],"illum",[x/65536 for x in struct.unpack(">3i",b[68:80])],"creator",b[80:84])
n=struct.unpack(">I",b[128:132])[0]
for i in range(n):
    sig,off,sz=struct.unpack(">4sII",b[132+12*i:144+12*i]); t=b[off:off+4]
    extra=""
    if t in (b"mft2",b"mft1"):
        ni,no,g=b[off+8],b[off+9],b[off+10]; mat=[x/65536 for x in struct.unpack(">9i",b[off+12:off+48])]; extra=f"in {ni} out {no} grid {g} matrix {[round(m,4) for m in mat]}"
        if t==b"mft2": extra+=f" inTab {struct.unpack('>H',b[off+48:off+50])[0]} outTab {struct.unpack('>H',b[off+50:off+52])[0]}"
    elif t==b"XYZ ": extra=str([round(x/65536,4) for x in struct.unpack(">3i",b[off+8:off+20])])
    elif t in(b"desc",b"text"): extra=repr(b[off+8:off+80])
    elif t==b"mluc": extra=repr(b[off+8:off+120])
    elif t==b"curv": c=struct.unpack(">I",b[off+8:off+12])[0]; extra=f"count {c}"+(f" gamma {struct.unpack('>H',b[off+12:off+14])[0]/256}" if c==1 else "")
    elif t==b"mAB ": extra=f"in {b[off+8]} out {b[off+9]} offs {struct.unpack('>5I',b[off+12:off+32])}"
    print(sig,off,sz,t,extra)

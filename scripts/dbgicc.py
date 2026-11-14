import sys, io, struct, numpy as np
from PIL import Image, ImageCms
p="/home/claude/out2/icc/NikonZ5-Film Provia100F standard.icm"; b=open(p,"rb").read()
n=struct.unpack(">I",b[128:132])[0]; tags={b[132+12*i:136+12*i]:struct.unpack(">II",b[136+12*i:144+12*i]) for i in range(n)}
off,sz=tags[b"A2B0"]; g=b[off+10]; nin,nout=struct.unpack(">HH",b[off+48:off+52]); c0=off+52+3*nin*2
cl=np.frombuffer(b[c0:c0+g**3*6],">u2").reshape(g,g,g,3).astype(float)
for idx in ((32,32,32),(31,31,31),(30,30,30),(28,28,28)): print(idx,"L %.1f a %.1f b %.1f"%(cl[idx][0]/65280*100,cl[idx][1]/256-128,cl[idx][2]/256-128))
intab=np.frombuffer(b[off+52:c0],">u2").reshape(3,nin); print("input table at 224/255, 240/255, 250/255, 1.0:",[int(intab[0][int(round(v*(nin-1)))]) for v in (224/255,240/255,250/255,1.0)])
srgb=ImageCms.createProfile("sRGB")
arr=np.stack([np.array([224,236,244,250,253,254,255],np.uint8)]*3,-1)[None]
for intent in (0,1,3):
    t=ImageCms.buildTransform(ImageCms.ImageCmsProfile(io.BytesIO(b)),srgb,"RGB","RGB",renderingIntent=intent); print("intent",intent,np.asarray(ImageCms.applyTransform(Image.fromarray(arr),t))[0][:,1].tolist())

import sys, numpy as np
from PIL import Image
S=400/72
def crop(png,x0,t0,x1,t1):
    im=np.asarray(Image.open(png).convert("RGB")).astype(int); return im[int(t0*S):int(t1*S),int(x0*S):int(x1*S)], (x0,t0)
def lines(mask,axis,frac):
    f=mask.mean(axis=axis); idx=np.where(f>frac)[0]; groups=[]
    for i in idx:
        if groups and i-groups[-1][-1]<=2: groups[-1].append(i)
        else: groups.append([i])
    return [(round(float(np.mean(g)),1),len(g)) for g in groups]
for name,png,box in (("provia_char","pv400-6.png",(53,162,294,375)),("velvia_char","vv400-8.png",(60,105,287,309)),("velvia_sens","vv400-8.png",(312,105,533,308))):
    im,_=crop(png,*box); dark=(im.sum(-1)<240)
    print(name,im.shape)
    print("  vertical lines (col px, width):",lines(dark,0,0.45))
    print("  horizontal lines (row px, width):",lines(dark,1,0.45))

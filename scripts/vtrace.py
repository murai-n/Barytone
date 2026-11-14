import json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
def lin(v,a,va,b,vb): return va+(np.asarray(v,float)-a)/(b-a)*(vb-va)
g=np.asarray(Image.open("velvia_dye.png").convert("L")).astype(int)
m=ndi.binary_opening(g<120,np.ones((4,4)))
m[:20,:]=False; m[806:,:]=False; m[:,:132]=False; m[:,1210:]=False; m[40:150,600:1100]=False
sk=skeletonize(m)
H,W=sk.shape
def nbrs(p):
    y,x=p; out=[]
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            if (dy or dx) and 0<=y+dy<H and 0<=x+dx<W and sk[y+dy,x+dx]: out.append((y+dy,x+dx))
    return out
def trace(start,direction,maxlen=4000,look=25):
    path=[start]; visited={start}; d=np.array(direction,float); d/=np.linalg.norm(d)
    cur=start; sgn=1 if direction[1]>0 else -1
    for _ in range(maxlen):
        cand=[q for q in nbrs(cur) if q not in visited and (q[1]-cur[1])*sgn>=0 and np.dot(np.array(q)-np.array(cur),d)>-0.2]
        if not cand:
            # jump gap: search ahead along direction up to 12 px for skeleton pixel
            found=None
            for step in range(2,14):
                for off in range(-3,4):
                    q=(int(round(cur[0]+d[0]*step+off*(-d[1]))),int(round(cur[1]+d[1]*step+off*d[0])))
                    if 0<=q[0]<H and 0<=q[1]<W and sk[q] and q not in visited and (q[1]-cur[1])*sgn>0: found=q; break
                if found: break
            if not found: break
            cand=[found]
        # pick candidate best aligned with direction
        best=max(cand,key=lambda q: np.dot(np.array(q)-np.array(cur),d)/np.linalg.norm(np.array(q)-np.array(cur)))
        path.append(best); visited.add(best)
        for q in cand: visited.add(q) if q!=best and len(cand)>2 else None
        cur=best
        if len(path)>look:
            v=np.array(path[-1])-np.array(path[-look]); n=np.linalg.norm(v)
            if n>0: d=0.5*d+0.5*v/n; d/=np.linalg.norm(d)
    return path
wx=lambda w:lin(w,400,191,700,1152.5)
res={}; dbg=np.stack([g]*3,-1).astype(np.uint8)
for k,w0,col in (("yellow",449,(255,150,0)),("magenta",545,(220,0,140)),("cyan",660,(0,140,255))):
    c=int(round(wx(w0))); ys=np.where(sk[:300,c-3:c+4].any(1))[0]; y=int(ys[0])
    xs_=np.where(sk[y,c-3:c+4])[0]; st=(y,c-3+int(xs_[0]))
    left=trace(st,(0,-1)); right=trace(st,(0,1))
    path=left[::-1]+right[1:]
    for (yy,xx) in path: dbg[max(0,yy-2):yy+3,max(0,xx-1):xx+2]=col
    wl=lin([p[1] for p in path],191,400,1152.5,700); d=lin([p[0] for p in path],171.5,1.0,811.5,0.0)
    o=np.argsort(wl); wl=wl[o]; d=d[o]; u,i=np.unique(np.round(wl,1),return_index=True)
    w=np.arange(385,716,1.0); v=ndi.uniform_filter1d(np.interp(w,u,d[i]),5,mode="nearest")
    res[k]=dict(wl=w.tolist(),d=v.tolist()); print(k,"wl %.0f..%.0f peak %.3f@%.0f"%(u[0],u[-1],v.max(),w[v.argmax()]),"at 440/545/610:",np.round(np.interp([440,545,610],w,v),3))
Image.fromarray(dbg).resize((W//2,H//2)).save("dbg_velvia_dye.png")
d=json.load(open("/home/claude/work2/dyes_raw.json")); d["vel"]=res; json.dump(d,open("/home/claude/work2/dyes_raw.json","w"))

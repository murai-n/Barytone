import json, re, numpy as np, pdfplumber, warnings; warnings.filterwarnings("ignore")
U="/mnt/user-data/uploads/"
def flat(c,H,n=16):
    out=[];cur=None
    for seg in c["path"]:
        cmd=seg[0];pts=seg[1:]
        if cmd in("m","l"): cur=pts[-1]; out.append(cur)
        elif cmd=="c":
            p0=np.array(cur);p1,p2,p3=[np.array(p) for p in pts]
            for t in np.linspace(0,1,n+1)[1:]: out.append(tuple((1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t**2*p2+t**3*p3))
            cur=tuple(p3)
    a=np.array(out); ref=np.array(c["pts"])
    if abs(a[0,1]-ref[0,1])>1: a[:,1]=H-a[:,1]
    return a
def tidy(x,y):
    o=np.argsort(x,kind="stable"); x=np.asarray(x)[o]; y=np.asarray(y)[o]
    ux,i=np.unique(np.round(x,4),return_index=True); return ux.tolist(), np.asarray(y)[i].tolist()
NUM=re.compile(r"^[–\-−]?\d+\.?\d*$")
def words(p):
    out=[]
    for w in p.extract_words():
        t=w["text"].replace("–","-").replace("−","-")
        if NUM.match(t): out.append((float(t),(w["x0"]+w["x1"])/2,(w["top"]+w["bottom"])/2))
    return out
def axis(ws,vals,fixed_lo,fixed_hi,var_lo,var_hi,horiz,signs=None):
    """fit value -> coordinate from tick labels. horiz: ticks share a top band (x-axis)."""
    pts=[]
    for i,v in enumerate(vals):
        cand=[(x if horiz else y) for t,x,y in ws if abs(t)==abs(v) and fixed_lo<=(y if horiz else x)<=fixed_hi and var_lo<=(x if horiz else y)<=var_hi]
        s=(signs[i] if signs else None)
        for t,x,y in ws:
            pass
        if len(cand)==1: pts.append((v,cand[0]))
        elif len(cand)>1 and signs is None and v>=0: pass
    vs=np.array([p[0] for p in pts]); cs=np.array([p[1] for p in pts])
    assert len(pts)>=2, (vals,pts)
    b,a=np.polyfit(vs,cs,1)
    err=abs(a+b*vs-cs).max()
    return (lambda c: (np.asarray(c)-a)/b), len(pts), err
def pick(pg,xa,ta,xb,tb,minw=25,minh=15,minpts=3):
    return [c for c in pg.curves if xa<=c["x0"] and c["x1"]<=xb and ta<=c["top"] and c["bottom"]<=tb and len(c["pts"])>=minpts and c["width"]>minw and c["height"]>minh and not c.get("fill")]
def chain(cs,H,tol=3.0):
    """merge curve fragments into polylines by endpoint proximity"""
    segs=[flat(c,H) for c in cs]
    out=[]
    while segs:
        a=segs.pop(0)
        changed=True
        while changed:
            changed=False
            for i,b in enumerate(segs):
                for flip in (False,True):
                    bb=b[::-1] if flip else b
                    if np.hypot(*(a[-1]-bb[0]))<tol: a=np.vstack([a,bb]); segs.pop(i); changed=True; break
                    if np.hypot(*(bb[-1]-a[0]))<tol: a=np.vstack([bb,a]); segs.pop(i); changed=True; break
                if changed: break
        out.append(a)
    return out
def dedupe(cs):
    seen=set(); out=[]
    for c in cs:
        k=(round(c["x0"],1),round(c["top"],1),round(c["x1"],1),round(c["bottom"],1),len(c["pts"]))
        if k not in seen: seen.add(k); out.append(c)
    return out
def chain2(cs,H,tol=3.0,maxang=45.0):
    """chain fragments, bridging dash gaps only when the direction carries straight on"""
    import numpy as _np
    segs=[flat(c,H) for c in dedupe(cs)]
    segs=[s[_np.argsort(s[:,0],kind="stable")] if s[0,0]>s[-1,0] else s for s in segs]
    segs.sort(key=lambda s: s[0,0])
    def ang(v1,v2):
        n1=_np.hypot(*v1); n2=_np.hypot(*v2)
        if n1<1e-9 or n2<1e-9: return 0.0
        return _np.degrees(_np.arccos(_np.clip(_np.dot(v1,v2)/(n1*n2),-1,1)))
    chains=[]
    for s in segs:
        best=None; bd=tol+1
        for ch in chains:
            a=ch[-1]
            gap=s[0]-a[-1]; d=_np.hypot(*gap)
            if d>=bd or s[0,0]<a[-1,0]-0.5: continue
            da=a[-1]-a[max(0,len(a)-4)]; db=s[min(3,len(s)-1)]-s[0]
            if d>1.0 and (ang(da,gap)>maxang or ang(gap,db)>maxang): continue
            if d<=1.0 or (ang(da,db)<=maxang): best=ch; bd=d
        if best is None: chains.append([s])
        else: best.append(s)
    return [_np.vstack(c) for c in chains]
def sens_extract(p,bbox,xm,ym,tol=14,maxang=40,nmain=3,minpts=18,exclude=None):

    cs=pick(p,*bbox,minw=1,minh=0,minpts=4)
    if exclude: cs=[c for c in cs if not exclude(c)]
    import numpy as _np
    polys=[a for a in chain2(cs,p.height,tol=tol,maxang=maxang) if a.shape[0]>8]
    polys.sort(key=lambda a:-a.shape[0])
    main=polys[:nmain]; rest=[a for a in polys[nmain:] if a.shape[0]>=8]
    for a in rest:
        d=[min(_np.hypot(*(m[0]-a[-1])),_np.hypot(*(m[-1]-a[0]))) for m in main]
        i=int(_np.argmin(d))
        if d[i]<25: main[i]=_np.vstack([a,main[i]]) if a[0,0]<main[i][0,0] else _np.vstack([main[i],a])
    main=[a for a in main if a.shape[0]>=minpts]
    pk=[xm(a[:,0])[int(_np.argmin(a[:,1]))] for a in main]   # top of page = highest logS
    order=_np.argsort(pk); names=["blue","green","red"][:len(main)]
    return {names[j]:dict(zip(("wl","logS"),tidy(xm(main[order[j]][:,0]),ym(main[order[j]][:,1])))) for j in range(len(main))}

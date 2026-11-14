import sys, pdfplumber
path,pn,xa,ta,xb,tb=sys.argv[1],int(sys.argv[2]),*map(float,sys.argv[3:7]); mp=int(sys.argv[7]) if len(sys.argv)>7 else 4
pg=pdfplumber.open(path).pages[pn-1]
ws=[w for w in pg.extract_words() if xa<=w["x0"] and w["x1"]<=xb and ta<=w["top"] and w["bottom"]<=tb]
print("nums:",[(w["text"],round((w["x0"]+w["x1"])/2,1),round((w["top"]+w["bottom"])/2,1)) for w in ws if any(ch.isdigit() for ch in w["text"]) and len(w["text"])<7])
print("labels:",[(w["text"],round(w["x0"]),round(w["top"])) for w in ws if not any(ch.isdigit() for ch in w["text"])][:30])
print("rects:",[(round(r["x0"],1),round(r["top"],1),round(r["x1"],1),round(r["bottom"],1)) for r in pg.rects if xa<=r["x0"] and r["x1"]<=xb and ta<=r["top"] and r["bottom"]<=tb and r["width"]>60 and r["height"]>60])
L=[l for l in pg.lines if xa<=l["x0"] and l["x1"]<=xb and ta<=l["top"] and l["bottom"]<=tb]
print("long lines:",sorted(set((round(l["x0"],1),round(l["top"],1),round(l["x1"],1),round(l["bottom"],1)) for l in L if l["width"]>60 or l["height"]>60))[:40])
print("short ticks x:",sorted(set(round(l["x0"],1) for l in L if l["width"]<0.5 and l["height"]<10)),"y:",sorted(set(round(l["top"],1) for l in L if l["height"]<0.5 and l["width"]<10)))
for c in pg.curves:
    if xa<=c["x0"] and c["x1"]<=xb and ta<=c["top"] and c["bottom"]<=tb and len(c["pts"])>=mp and (c["width"]>25 or c["height"]>25):
        print(" curve %3d pts x %.1f-%.1f top %.1f-%.1f first (%.1f,%.1f) last (%.1f,%.1f) dash %s lw %s"%(len(c["pts"]),c["x0"],c["x1"],c["top"],c["bottom"],*c["pts"][0],*c["pts"][-1],c.get("dash"),c.get("linewidth")))

import sys, pdfplumber
path,pn=sys.argv[1],int(sys.argv[2]); minpts=int(sys.argv[3]) if len(sys.argv)>3 else 12
pg=pdfplumber.open(path).pages[pn-1]
print("images:",[(round(i["x0"]),round(i["top"]),round(i["x1"]),round(i["bottom"])) for i in pg.images])
print("rects big:",[(round(r["x0"],1),round(r["top"],1),round(r["x1"],1),round(r["bottom"],1)) for r in pg.rects if r["width"]>80 and r["height"]>80][:12])
cs=[c for c in pg.curves if len(c["pts"])>=minpts and c["width"]>40 and c["height"]>15]
print("n wide curves",len(cs))
for c in cs[:60]:
    print(" %3d pts x %.1f-%.1f top %.1f-%.1f lw %s stroke %s fill %s dash %s"%(len(c["pts"]),c["x0"],c["x1"],c["top"],c["bottom"],c.get("linewidth"),c.get("stroking_color"),c.get("fill"),c.get("dash")))

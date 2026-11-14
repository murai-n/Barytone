import sys, pdfplumber
pdf = pdfplumber.open(sys.argv[1]); pg = pdf.pages[3]
print("curves", len(pg.curves), "lines", len(pg.lines), "rects", len(pg.rects), "images", len(pg.images), "chars", len(pg.chars))
for c in pg.curves:
    pts = c.get("pts") or c.get("points")
    if len(pts) > 15:
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        print(len(pts), "x %.1f-%.1f y %.1f-%.1f"%(min(xs),max(xs),min(ys),max(ys)), "lw", c.get("linewidth"), "stroke", c.get("stroking_color"))
for im in pg.images: print("img", im["x0"], im["top"], im["x1"], im["bottom"])

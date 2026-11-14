import sys, pdfplumber
pdf = pdfplumber.open(sys.argv[1]); pg = pdf.pages[3]
def inreg(x0,top,x1,bot): return x1<310 and bot<300 and top>90
print("-- curves")
for c in pg.curves:
    if inreg(c["x0"],c["top"],c["x1"],c["bottom"]):
        pts=c["pts"]; print(len(pts), "x %.1f-%.1f top %.1f-%.1f"%(c["x0"],c["x1"],c["top"],c["bottom"]), "first",[round(v,1) for v in pts[0]],"last",[round(v,1) for v in pts[-1]])
print("-- rects")
for r in pg.rects:
    if inreg(r["x0"],r["top"],r["x1"],r["bottom"]): print("x %.1f-%.1f top %.1f-%.1f"%(r["x0"],r["x1"],r["top"],r["bottom"]))
print("-- lines")
for l in pg.lines:
    if inreg(l["x0"],l["top"],l["x1"],l["bottom"]): print("x %.1f-%.1f top %.1f-%.1f"%(l["x0"],l["x1"],l["top"],l["bottom"]))
print("-- words")
for w in pg.extract_words():
    if w["x1"]<310 and 90<w["top"]<300: print(w["text"], "x %.1f-%.1f top %.1f-%.1f"%(w["x0"],w["x1"],w["top"],w["bottom"]))
print("page h", pg.height)

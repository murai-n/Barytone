import sys, pdfplumber
pg = pdfplumber.open(sys.argv[1]).pages[3]
for name,(xa,xb,ta,tb) in {"SENS":(40,310,300,520),"DYE":(310,600,90,300)}.items():
    print("--",name)
    for c in pg.curves:
        if xa<c["x0"] and c["x1"]<xb and ta<c["top"] and c["bottom"]<tb and len(c["pts"])>3:
            print(" curve",len(c["pts"]),"x %.1f-%.1f top %.1f-%.1f"%(c["x0"],c["x1"],c["top"],c["bottom"]))
    for r in pg.rects:
        if xa<r["x0"] and r["x1"]<xb and ta<r["top"] and r["bottom"]<tb and r["width"]>100 and r["height"]>100: print(" rect x %.1f-%.1f top %.1f-%.1f"%(r["x0"],r["x1"],r["top"],r["bottom"]))
    ls=[l for l in pg.lines if xa<l["x0"] and l["x1"]<xb and ta<l["top"] and l["bottom"]<tb]
    for l in ls:
        if l["width"]>100 or l["height"]>100: print(" line x %.1f-%.1f top %.1f-%.1f"%(l["x0"],l["x1"],l["top"],l["bottom"]))
    ticks=sorted(set(round(l["x0"],1) for l in ls if l["width"]<0.5 and l["height"]<8)); print(" xticks",ticks)
    yt=sorted(set(round(l["top"],1) for l in ls if l["height"]<0.5 and l["width"]<8)); print(" yticks",yt)
    for w in pg.extract_words():
        if xa-25<w["x0"] and w["x1"]<xb+10 and ta-5<w["top"]<tb+15 and w["text"].replace(".","").replace("-","").isdigit(): print("  ",w["text"],"x %.1f top %.1f"%((w["x0"]+w["x1"])/2,(w["top"]+w["bottom"])/2))

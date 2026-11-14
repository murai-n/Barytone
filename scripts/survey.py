import sys, pdfplumber
for path in sys.argv[1:]:
    pdf=pdfplumber.open(path); print("==",path.split("/")[-1],"pages",len(pdf.pages),pdf.pages[0].width,pdf.pages[0].height)
    for i,pg in enumerate(pdf.pages):
        t=(pg.extract_text() or "")
        keys=[k for k in ("Characteristic","CHARACTERISTIC","Spectral","SPECTRAL","特性曲線","分光","Dye","DYE","MTF","Modulation") if k in t]
        big=[c for c in pg.curves if len(c["pts"])>8]
        print(" p%d curves %d (big %d) lines %d images %d chars %d"%(i+1,len(pg.curves),len(big),len(pg.lines),len(pg.images),len(pg.chars)),keys)

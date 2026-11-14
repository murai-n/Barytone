"""Build 2-tier Capture One presets:
   Film <ALIAS>  (Engine 1300): background = ICC(film) + Linear FilmCurve ; one layer = Develop color
   Paper <LAB>   (Engine 900, single layer): tone + paper tint  -> applied 'to new layer'
Camera-specific part is only the 16 Film styles (they carry the camera's ICC); the 7 Paper styles are universal.
"""
import re, os, json, uuid, shutil
STY="/home/claude/out3/styles/"
OUT="/home/claude/presets/"; shutil.rmtree(OUT,ignore_errors=True)
FILM_IND="Film (Camera-specific)"   # per-camera: references the baked NikonZ5 ICC
FILM_GEN="Film (General)"           # generic: references the camera-agnostic ICC (works on any camera)
ICC_IND="ICC (Camera-specific)"; ICC_GEN="ICC (General)"
for d in (FILM_IND,FILM_GEN,"3 Paper","2 Coupler",ICC_IND,ICC_GEN):
    os.makedirs(OUT+d,exist_ok=True)
ALIAS=json.load(open("/home/claude/out3/alias.json"))["alias"]
PAPERS=[("endura","KEP"),("crystal","FCA"),("fujiflex","FFX"),("metallic","KEM"),("ultra","KUE"),("portra","KPE"),("supra","KSE"),("ilfochrome","ILF")]
FILMCURVE="NikonZ5-Linear Response.fcrv"
def uid(): return str(uuid.uuid4()).upper()
def curves(path):
    """return dict key->V string for all Gradation* keys in a single-layer style"""
    t=open(path).read()
    return {k:v for k,v in re.findall(r'<E K="(Gradation\w*)" V="([^"]+)"',t)}
def colorcorr(path):
    m=re.search(r'<E K="ColorCorrections" V="([^"]+)"',open(path).read()); return m.group(1)
def E(k,v): return f'\t\t\t<E K="{k}" V="{v}" />'

# ---------- Film styles (Engine 1300): ICC on background + color layer ----------
# two editions: 個別 = per-camera baked ICC ; 一括 = camera-agnostic generic ICC
def film_style(al,col,icc,name,slide=None):
    layer="\n".join([
        '\t\t<LD>','\t\t\t<LA>',
        E("Clarity","0"),E("DehazeAmount","0"),E("Enabled","1"),
        E("GradationCurveBlue",col["GradationCurveBlue"]),
        E("GradationCurveGreen",col["GradationCurveGreen"]),
        E("GradationCurveRed",col["GradationCurveRed"]),
        f'\t\t\t<E K="Name" V="Develop {al} - color" />',
        '\t\t\t<E K="Opacity" V="100" />','\t\t\t</LA>',
        '\t\t\t<MD>','\t\t\t\t<E K="Density" V="1" />','\t\t\t\t<E K="MaskType" V="1" />','\t\t\t</MD>','\t\t</LD>'])
    if slide:   # positives: light-box viewing tone of the slide, layered above the colour layer
        layer+="\n"+"\n".join([
            '\t\t<LD>','\t\t\t<LA>',
            E("Clarity","0"),E("DehazeAmount","0"),E("Enabled","1"),
            E("GradationCurve",slide),
            f'\t\t\t<E K="Name" V="Develop {al} - slide tone" />',
            '\t\t\t<E K="Opacity" V="100" />','\t\t\t</LA>',
            '\t\t\t<MD>','\t\t\t\t<E K="Density" V="1" />','\t\t\t\t<E K="MaskType" V="1" />','\t\t\t</MD>','\t\t</LD>'])
    return "\n".join([
        '<?xml version="1.0"?>','<SL Engine="1300">',
        f'\t<E K="FilmCurve" V="{FILMCURVE}" />',
        '\t<E K="FilmGrainAmount" V="0" />','\t<E K="FilmGrainDensity" V="0" />',
        '\t<E K="FilmGrainGranularity" V="50" />','\t<E K="FilmGrainType" V="0" />',
        '\t<E K="Highlight" V="1;1;1;1" />',
        f'\t<E K="ICCProfile" V="{icc}" />',
        '\t<E K="Midtone" V="0;0;0;0" />',
        f'\t<E K="Name" V="{name}" />',
        '\t<E K="Shadow" V="0;0;0;0" />','\t<E K="StyleSource" V="Styles" />',
        f'\t<E K="UUID" V="{uid()}" />','</SL>',
        '<LDS>',layer,'</LDS>',''])
for film,al in ALIAS.items():
    col=curves(STY+f"2 Develop/Develop {al} - color.costyle")
    sf=STY+f"2 Develop/Develop {al} - slide tone.costyle"
    slide=curves(sf)["GradationCurve"] if os.path.exists(sf) else None
    # Camera-specific (per-camera baked ICC)
    icm=f"NikonZ5-Film {al} base.icm"
    open(OUT+f"{FILM_IND}/Film {al} (Camera).costyle","w").write(film_style(al,col,icm,f"Film {al} (Camera)",slide))
    src=STY.replace("styles/","")+"icc/"+icm
    if os.path.exists(src): shutil.copy(src,OUT+ICC_IND+"/"+icm)
    # General (generic camera-agnostic ICC)
    gic=f"Film {al} generic.icc"
    open(OUT+f"{FILM_GEN}/Film {al} (General).costyle","w").write(film_style(al,col,gic,f"Film {al} (General)",slide))
    gsrc=f"/home/claude/out3/generic_icc/{gic}"
    if os.path.exists(gsrc): shutil.copy(gsrc,OUT+ICC_GEN+"/"+gic)

# ---------- Paper styles (Engine 1300): two separate layers, tint (bottom) then tone (top) ----------
def rgb_layer(name,c,opacity=100):
    return "\n".join([
        '\t\t<LD>','\t\t\t<LA>',
        E("Clarity","0"),E("DehazeAmount","0"),E("Enabled","1"),
        E("GradationCurveBlue",c["GradationCurveBlue"]),
        E("GradationCurveGreen",c["GradationCurveGreen"]),
        E("GradationCurveRed",c["GradationCurveRed"]),
        f'\t\t\t<E K="Name" V="{name}" />',
        f'\t\t\t<E K="Opacity" V="{opacity}" />','\t\t\t</LA>',
        '\t\t\t<MD>','\t\t\t\t<E K="Density" V="1" />','\t\t\t\t<E K="MaskType" V="1" />','\t\t\t</MD>','\t\t</LD>'])
def tone_layer(name,c,opacity=100):
    return "\n".join([
        '\t\t<LD>','\t\t\t<LA>',
        E("Clarity","0"),E("DehazeAmount","0"),E("Enabled","1"),
        E("GradationCurve",c["GradationCurve"]),   # composite (luma) tone -> layer-safe, no white-out
        f'\t\t\t<E K="Name" V="{name}" />',
        f'\t\t\t<E K="Opacity" V="{opacity}" />','\t\t\t</LA>',
        '\t\t\t<MD>','\t\t\t\t<E K="Density" V="1" />','\t\t\t\t<E K="MaskType" V="1" />','\t\t\t</MD>','\t\t</LD>'])
def color_layer(name,cc,opacity=100):
    return "\n".join([
        '\t\t<LD>','\t\t\t<LA>',
        E("Clarity","0"),E("ColorCorrections",cc),E("Enabled","1"),
        f'\t\t\t<E K="Name" V="{name}" />',
        f'\t\t\t<E K="Opacity" V="{opacity}" />','\t\t\t</LA>',
        '\t\t\t<MD>','\t\t\t\t<E K="Density" V="1" />','\t\t\t\t<E K="MaskType" V="1" />','\t\t\t</MD>','\t\t</LD>'])
for pid,lab in PAPERS:
    pcf=STY+f"3 Print/Print {lab} - paper color (optional).costyle"
    pcol=colorcorr(pcf) if os.path.exists(pcf) else None   # Ilfochrome: azo gamut is wide, no gamut-limiting colour layer
    for suf,tonefile,tintfile in (("normal","tone","paper tint (full cal)"),("faded","tone (faded)","paper tint (faded)")):
        tone=curves(STY+f"3 Print/Print {lab} - {tonefile}.costyle")
        tint=curves(STY+f"3 Print/Print {lab} - {tintfile}.costyle")
        layers="\n".join(([color_layer(f"Print {lab} - paper color",pcol)] if pcol else [])+[
            rgb_layer(f"Print {lab} - paper tint ({suf})",tint),
            tone_layer(f"Print {lab} - tone",tone)])
        xml="\n".join([
            '<?xml version="1.0"?>','<SL Engine="1300">',
            f'\t<E K="Name" V="Paper {lab} ({suf})" />',
            '\t<E K="StyleSource" V="Styles" />',
            f'\t<E K="UUID" V="{uid()}" />','</SL>',
            '<LDS>',layers,'</LDS>',''])   # SL carries no base-characteristics -> applying never touches the film ICC
        open(OUT+f"3 Paper/Paper {lab} ({suf}).costyle","w").write(xml)

# ---------- Coupler (shared, saturation) ----------
for s in (15,30,40,50):
    lay="\n".join(['\t\t<LD>','\t\t\t<LA>',E("Enabled","1"),
        f'\t\t\t<E K="Name" V="Coupler +{s}" />','\t\t\t<E K="Opacity" V="100" />',E("Saturation",str(s)),'\t\t\t</LA>',
        '\t\t\t<MD>','\t\t\t\t<E K="Density" V="1" />','\t\t\t\t<E K="MaskType" V="1" />','\t\t\t</MD>','\t\t</LD>'])
    xml="\n".join(['<?xml version="1.0"?>','<SL Engine="1300">',f'\t<E K="Name" V="Coupler +{s}" />',
        '\t<E K="StyleSource" V="Styles" />',f'\t<E K="UUID" V="{uid()}" />','</SL>','<LDS>',lay,'</LDS>',''])
    open(OUT+f"2 Coupler/Coupler +{s}.costyle","w").write(xml)   # own layer: never touches the curves of the layer it lands on
# ---------- Filter (shared, enlarger YMC): own RGB-curve layer ----------
os.makedirs(OUT+"4 Filter",exist_ok=True)
for fn in sorted(os.listdir(OUT+"4 Filter")): os.remove(OUT+"4 Filter/"+fn)
for nm in ("+10Y","-10Y","+10M","-10M","+10C","-10C"):
    c=curves(STY+f"5 Filter/Filter {nm}.costyle")
    xml="\n".join(['<?xml version="1.0"?>','<SL Engine="1300">',f'\t<E K="Name" V="Filter {nm}" />',
        '\t<E K="StyleSource" V="Styles" />',f'\t<E K="UUID" V="{uid()}" />','</SL>','<LDS>',rgb_layer(f"Filter {nm}",c),'</LDS>',''])
    open(OUT+f"4 Filter/Filter {nm}.costyle","w").write(xml)
print("Film Camera:",len(os.listdir(OUT+FILM_IND)),"| Film General:",len(os.listdir(OUT+FILM_GEN)),"| Paper:",len(os.listdir(OUT+"3 Paper")),"| Coupler:",len(os.listdir(OUT+"2 Coupler")),"| ICC Camera:",len(os.listdir(OUT+ICC_IND)),"| ICC General:",len(os.listdir(OUT+ICC_GEN)))

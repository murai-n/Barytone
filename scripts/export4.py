import sys, json; sys.path.insert(0,"/home/claude/scripts")
import numpy as np, warnings; warnings.filterwarnings("ignore")
import model3 as M, model
ALIAS=json.load(open("/home/claude/out3/alias.json")) if False else None
import importlib, build3
ALIAS=build3.ALIAS
DESC={"Portra 160NC":"旧世代ポートラ。自然で低彩度の発色","Portra 160VC":"旧世代ポートラ。鮮やかめ（NC に彩度 +15%）","Portra 400NC":"旧世代ポートラの高感度。自然な発色","Portra 400VC":"旧世代ポートラの高感度。鮮やかめ（NC に彩度 +15%）","Vericolor III":"古典的なポートレートネガ","Ultra Color 100UC":"高彩度ネガ。くっきりした発色","Ultra Color 400UC":"高彩度ネガの高感度版","Pro Image 100":"暖色寄りで肌がやさしいネガ","Ektachrome EPN":"中性・忠実発色のポジ","Velvia 100":"高彩度ポジ。Velvia 50 より穏やか","Superia X-TRA 400":"大衆ネガの標準的な発色","Portra 160":"やわらかい階調、穏やかな色","Portra 400":"肌色の定番、懐の深いネガ","Ektar 100":"高彩度・微粒子のネガ","Pro 400H":"淡い緑とハイキー向き","Provia 100F":"標準的な発色のポジ","Velvia 50":"高彩度・高コントラストのポジ","Ektachrome E100":"澄んだ青のポジ",
"Gold 200":"暖色寄りの消費者向け定番","Portra 800":"ポートラの高感度版","Vision3 500T":"映画用タングステン、広いラティチュード","Kodachrome 25":"外式ポジの原点、低感度","Kodachrome 64":"外式ポジ、濃い影と締まった発色","Kodachrome 200":"外式ポジの高感度版","Ektachrome 64T":"タングステン用ポジ。昼光では補正なしで青く転ぶ","Ektachrome 160T":"タングステン用ポジ（高感度）。昼光では青く転ぶ","Fujichrome 64T II":"富士のタングステン用ポジ。昼光では青く転ぶ","Astia 100F":"軟調設計のポジ（データ上は高彩度）","Pro 160NS":"スタジオポートレート向けネガ","Pro 800Z":"高感度のプロ用ネガ"}
old=json.load(open("/home/claude/m3/films3.json"))
d={k:v for k,v in old.items() if k!="films"}
ORDER=["Portra 160", "Portra 400", "Portra 800", "Ektar 100", "Gold 200", "Pro Image 100", "Vision3 500T", "Portra 160NC", "Portra 160VC", "Portra 400NC", "Portra 400VC", "Ultra Color 100UC", "Ultra Color 400UC", "Vericolor III", "Pro 160NS", "Pro 400H", "Pro 800Z", "Superia X-TRA 400", "Provia 100F", "Velvia 50", "Velvia 100", "Astia 100F", "Ektachrome E100", "Ektachrome EPN", "Kodachrome 25", "Kodachrome 64", "Kodachrome 200", "Ektachrome 64T", "Ektachrome 160T", "Fujichrome 64T II"]
assert set(ORDER)==set(M.ALL), set(M.ALL)^set(ORDER)
films=[]
for f in ORDER:
    a=ALIAS[f]; kind=M.KIND[f]
    e=dict(name=a,id=a,desc=DESC[f],iso=f"ISO {M.ISO[f]}",kind=kind,
           K=(M.KER[f]/np.asarray(M.HW[f])[:,None]).tolist(),ref=float(model.res[f]["ref"]),
           variants=[dict(id="base",label="撮影",k=0.0,deep=False,base=True,bpaper=None)])
    t=M.base_table(f,0.0)
    e["bases"]={"base":{"logYo":t["logYo"].tolist(),"logYin":t["logYin"].tolist(),"r":t["r"].T.tolist(),"w":t["w"].tolist()}}
    if kind=="neg":
        e["ch"]={k:dict(x=list(map(float,model.res[f]["ch"][k]["x"])),d=list(map(float,model.res[f]["ch"][k]["d"]))) for k in "RGB"}
        g=[float(model.summ[f][k]["gamma"]) for k in "RGB"]; e["g"]=g; e["pg"]=g
        e["dref"]=[float(model.summ[f][k]["dref"]) for k in "RGB"]
        e["bal"]={pid:M.print_balance(f,pid).tolist() for pid in d["papers"]}
        e["pscale"]={pid:float(M.print_scale(f,pid)) for pid in d["papers"]}
        e["pbscale"]={pid:float(M.print_scale(f,pid,M.PB_GAMMA)) for pid in d["papers"]}
    else:
        u=M.UNMIX[f]
        e["ux"]=np.asarray(u["x"]).tolist(); e["ua"]=np.asarray(u["a"]).T.tolist(); e["E"]=np.asarray(u["E"]).tolist()
        e["norm"]=np.asarray(M.POSNORM[f]).tolist()
    if a in ("KP160VC", "KP400VC"): e["sat"] = 1.15   # see fix_portra_e190.py
    films.append(e)

# ---- Develop colour curves, lifted from the built styles so the browser tool
#      can emit the same Engine-1300 combined style without recomputing them ----
import re, os
STY = "/home/claude/out3/styles/2 Develop/"
for e in films:
    f = STY + f"Develop {e['id']} - color.costyle"
    assert os.path.exists(f), f
    cur = dict(re.findall(r'<E K="(GradationCurve(?:Red|Green|Blue))" V="([^"]+)"', open(f).read()))
    assert set(cur) == {"GradationCurveRed", "GradationCurveGreen", "GradationCurveBlue"}, (e['id'], sorted(cur))
    e["dev"] = {"r": cur["GradationCurveRed"], "g": cur["GradationCurveGreen"], "b": cur["GradationCurveBlue"]}
    sf = STY + f"Develop {e['id']} - slide tone.costyle"
    if os.path.exists(sf):
        e["slide"] = re.search(r'<E K="GradationCurve" V="([^"]+)"', open(sf).read()).group(1)
d["films"]=films
json.dump(d,open("/home/claude/m3/films3.json","w")); json.dump(d,open("/home/claude/bake3/src/films.json","w"))
r=json.load(open("/home/claude/m3/ref3.json")); pts=np.array(r["pts"])
r["ref"]={ALIAS[f]+"|base":M.render(f,pts,M.variants(f)[0]).tolist() for f in ORDER}
json.dump(r,open("/home/claude/m3/ref3.json","w"))
print("export ok:",len(films),"films")

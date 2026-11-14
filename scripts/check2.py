import json, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
F=json.load(open("/home/claude/work2/films2.json")); fig,axs=plt.subplots(2,4,figsize=(16,7))
for j,(n,v) in enumerate(F.items()):
    for k,c in zip("RGB",("r","g","b")): axs[0,j].plot(v["ch"][k]["x"],v["ch"][k]["d"],c)
    axs[0,j].set_title(n); axs[0,j].grid(True)
    for k,c in (("red","r"),("green","g"),("blue","b"),("cyan4th","c")):
        if k in v["sens"]: axs[1,j].plot(v["sens"][k]["wl"],v["sens"][k]["logS"],c)
    axs[1,j].grid(True)
fig.tight_layout(); fig.savefig("/home/claude/work2/check2.png",dpi=70)

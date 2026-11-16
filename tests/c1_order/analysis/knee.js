const fs=require("fs");
let src=fs.readFileSync(__dirname+"/../../../bake3/src/engine.js","utf8");
src=src.replace("root.FilmBaker = {","root.FilmBaker = { _pos: posRender, _exp: exposures, _spec: spectrum,");
eval(src);
const FB=globalThis.FilmBaker, C=require(__dirname+"/../../../bake3/src/films.json");
const XS=[0,0.03,0.06,0.09,0.12,0.16,0.2,0.25,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1];
function T(f,s){const W=C.D65W; return FB._pos(C,f,{k:0,deep:false,base:false},FB._exp(f,FB._spec(C,[W[0]*s,W[1]*s,W[2]*s])))[1];}
function curve(f,kneeEV){ // kneeEV relative to grey 0.18; null = current
  const Tb=T(f,1e-6), P=0.8,F=0.001;
  // exposure (relative s) where film reaches 99% of its clear-film transmittance
  let Tmax=T(f,1e4), sD=1; while(T(f,sD)<Tb+0.99*(Tmax-Tb) && sD<1e4) sD*=1.05;
  const sk=0.18*2**kneeEV;
  return XS.map(x=>{let s=Math.max(x**1.8,1e-6);
    if(kneeEV!=null && s>sk){const t=Math.log(s/sk)/Math.log(1/sk); s=sk*Math.exp(t*Math.log(sD/sk));}
    const t=T(f,s); const y=F+(1-F)*Math.max(0,(t-Tb)/(Tmax-Tb))**P; return Math.min(1,y)**(1/1.8);});
}
for(const id of ["FA100","FPR100","FV50","KK64"]){const f=C.films.find(x=>x.id===id);
 const cur=f.slide.split(";").map(p=>+p.split(",")[1]);
 let Tmax=T(f,1e4),sD=1; const Tb=T(f,1e-6); while(T(f,sD)<Tb+0.99*(Tmax-Tb)&&sD<1e4) sD*=1.05;
 console.log(id,"clear film reached at +"+Math.log2(sD/0.18).toFixed(1)+"EV above grey (clip is +2.47)");
 console.log("   x:      "+XS.slice(8).map(v=>v.toFixed(2).padStart(6)).join(""));
 console.log("   now:    "+cur.slice(8).map(v=>v.toFixed(3).padStart(6)).join(""));
 for(const k of [0.5,1.0,1.5]) console.log(("   knee+"+k+"EV").padEnd(10)+curve(f,k).slice(8).map(v=>v.toFixed(3).padStart(6)).join(""));
}
console.log("\n--- lift: y + (1 - y(1)) * smoothstep(knee..clip) ---");
for(const id of ["FA100","FPR100","FV50","KK64"]){const f=C.films.find(x=>x.id===id);
 const cur=f.slide.split(";").map(p=>+p.split(",")[1]);
 console.log(id,"   now:      "+cur.slice(8).map(v=>v.toFixed(3).padStart(6)).join(""));
 for(const k of [0.5,1.0,1.5]){const xk=(0.18*2**k)**(1/1.8);
  const y=XS.map((x,i)=>{if(x<=xk) return cur[i]; const t=(x-xk)/(1-xk), w=t*t*(3-2*t); return cur[i]+(1-cur[15])*w;});
  console.log(("      knee+"+k+"EV").padEnd(19)+y.slice(8).map(v=>v.toFixed(3).padStart(6)).join(""));}
}

const fs=require("fs"); require(__dirname+"/../../../bake3/src/engine.js"); const FB=globalThis.FilmBaker, C=require(__dirname+"/../../../bake3/src/films.json");
const enc=y=>Math.pow(Math.max(y,0),1/1.8), dec=x=>Math.pow(Math.max(x,0),1.8);
const Lstar=Y=>Y>216/24389?116*Math.cbrt(Y)-16:Y*24389/27;
const pc=(file)=>{const s=fs.readFileSync(file,"utf8").match(/K="GradationCurveGreen" V="([^"]+)"/)[1]; return s.split(";").map(p=>p.split(",").map(Number));};
const ip=(x,P)=>{if(x<=P[0][0])return P[0][1]; for(let i=1;i<P.length;i++) if(x<=P[i][0]){const t=(x-P[i-1][0])/(P[i][0]-P[i-1][0]); return P[i-1][1]+t*(P[i][1]-P[i-1][1]);} return P[P.length-1][1];};
const W=C.D65W;
function R(f,x){const Y=Math.max(dec(x),1e-7); return enc(FB.renderXYZ(C,f,f.variants[0],[W[0]*Y,Y,W[2]*Y])[1]);}
const films=process.argv[2].split(","), papers=process.argv[3].split("|");
for(const id of films){const f=C.films.find(x=>x.id===id);
 for(const pf of papers){const P=pc(`${__dirname}/../../../kit/3 Paper/B&W/${pf}.costyle`);
  let row=[];
  for(const ev of [-4,-3,-2,-1,0,1,2]){const x=enc(0.18*2**ev);
   const want=ip(R(f,x),P), got=R(f,ip(x,P));   // designed: curve after ICC; actual: curve before ICC
   row.push(`${ev>=0?"+":""}${ev}EV ${Lstar(dec(want)).toFixed(0)}/${Lstar(dec(got)).toFixed(0)}`);}
  console.log(id.padEnd(6),pf.padEnd(18),row.join("  "));}}

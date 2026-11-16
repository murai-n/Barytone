const fs=require("fs");
let src=fs.readFileSync(__dirname+"/../../../bake3/src/engine.js","utf8");
src=src.replace("root.FilmBaker = {","root.FilmBaker = { _spec: spectrum,"); eval(src);
const FB=globalThis.FilmBaker, C=require(__dirname+"/../../../bake3/src/films.json"), M=C.M_RGB_to_XYZ, W=C.D65W;
const enc=y=>Math.pow(Math.max(y,0),1/1.8), dec=x=>Math.pow(Math.max(x,0),1.8), L=Y=>Y>0.008856?116*Math.cbrt(Y)-16:Y*903.3;
const toX=r=>[0,1,2].map(i=>M[i][0]*r[0]+M[i][1]*r[1]+M[i][2]*r[2]);
const pc=f=>fs.readFileSync(f,"utf8").match(/K="GradationCurveGreen" V="([^"]+)"/)[1].split(";").map(p=>p.split(",").map(Number));
const ip=(x,P)=>{if(x<=P[0][0])return P[0][1]; for(let i=1;i<P.length;i++) if(x<=P[i][0]){const t=(x-P[i-1][0])/(P[i][0]-P[i-1][0]); return P[i-1][1]+t*(P[i][1]-P[i-1][1]);} return P[P.length-1][1];};
function H(f,v,X){const S=FB._spec(C,X),k=v.mk; let h=0; for(let i=0;i<S.length;i++) h+=S[i]*k[i]; return h;}
const Href=(f,v)=>H(f,v,W);  // white normalisation
const sRGB=c=>c.map(v=>{v/=255; return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4);});
const CC=[[115,82,68],[194,150,130],[98,122,157],[87,108,67],[133,128,177],[103,189,170],[214,126,44],[80,91,166],[193,90,99],[94,60,108],[157,188,64],[224,163,46],[56,61,150],[70,148,73],[175,54,60],[231,199,31],[187,86,149],[8,133,161]];
const NM=["dkskin","ltskin","sky","foliage","flower","bluegrn","orange","purpblu","modred","purple","yelgrn","orgyel","blue","green","red","yellow","magenta","cyan"];
const [fid,paper]=process.argv.slice(2);
const f=C.films.find(x=>x.id===fid), P=pc(`${__dirname}/../../../kit/3 Paper/B&W/${paper}.costyle`);
for(const v of f.variants){
 const hw=Href(f,v);
 const Rf=x=>{const Y=Math.max(dec(x),1e-7); return enc(FB.renderXYZ(C,f,v,[W[0]*Y,Y,W[2]*Y])[1]);}; // film tone curve (neutral response of current ICC)
 let errs=[];
 CC.forEach((c,i)=>{const r=sRGB(c);
   const h=H(f,v,toX(r))/hw;                               // film exposure relative to white
   const want=dec(ip(Rf(enc(h)),P));                         // designed: film tone + paper on the film's own exposure
   const rc=r.map(ch=>dec(ip(Rf(enc(ch)),P)));               // new pipeline: curves per channel first...
   const got=H(f,v,toX(rc))/hw;                              // ...then the tone-neutral ICC
   errs.push([NM[i],L(want),L(got)]);});
 const d=errs.map(e=>Math.abs(e[1]-e[2])); const mean=d.reduce((a,b)=>a+b)/d.length;
 const worst=errs.slice().sort((a,b)=>Math.abs(b[1]-b[2])-Math.abs(a[1]-a[2])).slice(0,3).map(e=>`${e[0]} ${e[1].toFixed(0)}→${e[2].toFixed(0)}`).join(", ");
 console.log((v.label||v.id).padEnd(12),"ΔL* mean",mean.toFixed(1)," max",Math.max(...d).toFixed(1)," worst:",worst);
}
console.log("-- current kit (paper curve per channel, then the reference-print ICC) --");
for(const v of f.variants){ const hw=Href(f,v);
 const Rf=x=>{const Y=Math.max(dec(x),1e-7); return enc(FB.renderXYZ(C,f,v,[W[0]*Y,Y,W[2]*Y])[1]);};
 const d=CC.map(c=>{const r=sRGB(c); const h=H(f,v,toX(r))/hw; const want=dec(ip(Rf(enc(h)),P));
   const rc=r.map(ch=>dec(ip(enc(ch),P))); const got=FB.renderXYZ(C,f,v,toX(rc))[1]; return Math.abs(L(want)-L(got));});
 console.log((v.label||v.id).padEnd(12),"ΔL* mean",(d.reduce((a,b)=>a+b)/d.length).toFixed(1)," max",Math.max(...d).toFixed(1));}
console.log("-- luma curve (ratio-preserving, Rec.709 weights), then tone-neutral ICC --");
for(const v of f.variants){ const hw=Href(f,v);
 const Rf=x=>{const Y=Math.max(dec(x),1e-7); return enc(FB.renderXYZ(C,f,v,[W[0]*Y,Y,W[2]*Y])[1]);};
 const d=CC.map(c=>{const r=sRGB(c); const h=H(f,v,toX(r))/hw; const want=dec(ip(Rf(enc(h)),P));
   const l=0.2126*r[0]+0.7152*r[1]+0.0722*r[2]; const s=dec(ip(Rf(enc(l)),P))/l;
   const got=H(f,v,toX(r.map(ch=>Math.min(ch*s,1))))/hw; return Math.abs(L(want)-L(got));});
 console.log((v.label||v.id).padEnd(12),"ΔL* mean",(d.reduce((a,b)=>a+b)/d.length).toFixed(1)," max",Math.max(...d).toFixed(1));}

/* Bake every black-and-white ICC from a camera profile with the browser engine.
   node bake3/bake_mono.js BASE.icm OUTDIR */
const fs = require("fs"), path = require("path");
require("./src/engine.js");
const C = JSON.parse(fs.readFileSync(path.join(__dirname, "src/films.json"), "utf8"));
const FB = globalThis.FilmBaker;
const [src, out] = process.argv.slice(2);
const b = fs.readFileSync(src), buf = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
const cam = path.basename(src).replace(/\.(icc|icm)$/i, "").split("-")[0];
fs.mkdirSync(out, { recursive: true });
let n = 0; const t0 = Date.now();
for (const film of C.films.filter(f => f.kind === "mono")) for (const v of film.variants) {
  const name = `${cam}-Film ${film.id} ${v.id}`;
  fs.writeFileSync(path.join(out, name + ".icm"), FB.bake(C, buf.slice(0), film, v, name)); n++;
}
console.log(`${n} mono profiles in ${out}, avg ${Math.round((Date.now() - t0) / n)} ms`);

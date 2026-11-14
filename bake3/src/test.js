const fs = require("fs");
require("./engine.js");
const C = JSON.parse(fs.readFileSync(__dirname + "/films.json", "utf8"));
const R = JSON.parse(fs.readFileSync("/home/claude/m3/ref3.json", "utf8"));
const FB = globalThis.FilmBaker;
let worst = 0;
for (const film of C.films) for (const v of film.variants) {
  const ref = R.ref[film.id + "|" + v.id]; let w = 0;
  R.pts.forEach((p, i) => { const o = FB.renderXYZ(C, film, v, p); for (let c = 0; c < 3; c++) w = Math.max(w, Math.abs(o[c] - ref[i][c])); });
  worst = Math.max(worst, w);
}
console.log("model max abs diff vs python (XYZ):", worst.toExponential(2));
const src = fs.readFileSync("/mnt/user-data/uploads/ebfcaeec-NikonZ5-Nikon_-_Neutral.icm");
const buf = src.buffer.slice(src.byteOffset, src.byteOffset + src.byteLength);
const info = FB.inspect(buf), a2b = info.luts[0], c0 = a2b.off + 52 + 3 * 1025 * 2, nodes = 33 ** 3;
let t0 = Date.now(), n = 0;
for (const film of C.films) for (const v of film.variants) {
  const name = `NikonZ5-Film ${film.id} ${v.id}`;
  const out = FB.bake(C, buf.slice(0), film, v, name); n++;
  const py = new Uint8Array(fs.readFileSync(`/home/claude/out3/icc/${name}.icm`));
  const dj = new DataView(out.buffer), dp = new DataView(py.buffer, py.byteOffset);
  let maxd = 0, cnt = 0;
  for (let i = 0; i < nodes * 3; i++) { const d = Math.abs(dj.getUint16(c0 + 2 * i) - dp.getUint16(c0 + 2 * i)); if (d > maxd) maxd = d; if (d > 2) cnt++; }
  console.log(`${name.padEnd(40)} max code diff ${maxd}  (>2: ${cnt})`);
}
console.log("avg bake ms:", Math.round((Date.now() - t0) / n));

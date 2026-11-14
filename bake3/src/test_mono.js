/* JS engine vs mono.py: the ICC values for every mono film and filter. */
const fs = require("fs"), path = require("path");
require("./engine.js");
const C = JSON.parse(fs.readFileSync(__dirname + "/films.json", "utf8"));
const R = JSON.parse(fs.readFileSync(path.join(__dirname, "../../m3/ref_mono.json"), "utf8"));
const FB = globalThis.FilmBaker;
let worst = 0, n = 0;
for (const film of C.films.filter(f => f.kind === "mono")) for (const v of film.variants) {
  const ref = R.ref[film.id + "|" + v.id];
  R.pts.forEach((p, i) => { const o = FB.renderXYZ(C, film, v, p); for (let c = 0; c < 3; c++) worst = Math.max(worst, Math.abs(o[c] - ref[i][c])); });
  n++;
}
console.log(`mono: ${n} profiles, max abs diff vs python (XYZ): ${worst.toExponential(2)}`);
process.exit(n === 45 && worst < 1e-6 ? 0 : 1);

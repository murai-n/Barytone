/* Film ICC baker engine — runs in the browser and in Node.
   Reads an RGB→Lab ICC profile (mft2 A2B tags), replaces each colour-table
   node's Lab value with the film model's rendering of it, and returns a new
   profile.  Nothing leaves the viewer's machine. */
(function (root) {
  "use strict";

  /* ---------- small math helpers ---------- */
  function interp(x, xs, ys) {
    var n = xs.length;
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    var lo = 0, hi = n - 1;
    while (hi - lo > 1) { var m = (lo + hi) >> 1; if (xs[m] <= x) lo = m; else hi = m; }
    var t = (x - xs[lo]) / (xs[hi] - xs[lo]);
    return ys[lo] + t * (ys[hi] - ys[lo]);
  }
  function mul3(M, v) {
    return [M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2],
            M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2],
            M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2]];
  }
  function inv3(m) {
    var a = m[0][0], b = m[0][1], c = m[0][2], d = m[1][0], e = m[1][1], f = m[1][2], g = m[2][0], h = m[2][1], i = m[2][2];
    var A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
    var det = a * A + b * B + c * C;
    return [[A / det, -(b * i - c * h) / det, (b * f - c * e) / det],
            [B / det, (a * i - c * g) / det, -(a * f - c * d) / det],
            [C / det, -(a * h - b * g) / det, (a * e - b * d) / det]];
  }
  function matmul(A, B) {
    var R = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++) R[r][c] = A[r][0] * B[0][c] + A[r][1] * B[1][c] + A[r][2] * B[2][c];
    return R;
  }

  /* ---------- colour conversions ---------- */
  var BRADFORD = [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]];
  var D50 = [0.9642, 1.0, 0.8249];
  function cat(fromW, toW) {
    var s = mul3(BRADFORD, fromW), d = mul3(BRADFORD, toW);
    var D = [[d[0] / s[0], 0, 0], [0, d[1] / s[1], 0], [0, 0, d[2] / s[2]]];
    return matmul(inv3(BRADFORD), matmul(D, BRADFORD));
  }
  var E_ = 216 / 24389, K_ = 24389 / 27;
  function labToXYZ50(L, a, b) {
    var fy = (L + 16) / 116, fx = fy + a / 500, fz = fy - b / 200;
    var yr = L > K_ * E_ ? fy * fy * fy : L / K_;
    var fx3 = fx * fx * fx, fz3 = fz * fz * fz;
    return [(fx3 > E_ ? fx3 : (116 * fx - 16) / K_) * D50[0], yr, (fz3 > E_ ? fz3 : (116 * fz - 16) / K_) * D50[2]];
  }
  function xyz50ToLab(X) {
    function f(t) { return t > E_ ? Math.cbrt(t) : (K_ * t + 16) / 116; }
    var fx = f(X[0] / D50[0]), fy = f(X[1]), fz = f(X[2] / D50[2]);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
  }
  var cache = null;
  function prep(C) {
    if (cache && cache.C === C) return cache;
    cache = { C: C, a50to65: cat(D50, C.D65W), a65to50: cat(C.D65W, D50) };
    return cache;
  }

  /* ---------- spectral upsampling (Otsu et al. 2018, blended, exposure-homogeneous) ---------- */
  function leafWeights(O, blend, x, y) {
    var w = new Array(O.B.length).fill(0);
    (function walk(row, acc) {
      var r = O.S[row], v = r[1] === 0 ? x : y, t = Math.min(Math.max((v - r[0]) / blend + 0.5, 0), 1);
      var kids = [[r[2], acc * (1 - t)], [r[3], acc * t]];
      for (var i = 0; i < 2; i++) { var idx = kids[i][0], wt = kids[i][1]; if (wt <= 0) continue; if (idx < 0) walk(-idx, wt); else w[idx] += wt; }
    })(0, 1);
    return w;
  }
  function spectrum(C, xyz) {
    var rgb = mul3(C.M_XYZ_2020, xyz), m = Math.max(rgb[0], rgb[1], rgb[2], 1e-9), sc = m / C.NORM_MAX;
    var X = [xyz[0] / sc, xyz[1] / sc, xyz[2] / sc], s = X[0] + X[1] + X[2];
    var x = s > 1e-9 ? X[0] / s : 0.3127, y = s > 1e-9 ? X[1] / s : 0.3290;
    var O = C.otsu, lw = leafWeights(O, C.BLEND, x, y), n = O.mu[0].length, out = new Float64Array(n);
    for (var c = 0; c < lw.length; c++) {
      if (!(lw[c] > 0)) continue;
      var d0 = X[0] - O.xmu[c][0], d1 = X[1] - O.xmu[c][1], d2 = X[2] - O.xmu[c][2], Mi = O.Minv[c];
      var w0 = d0 * Mi[0][0] + d1 * Mi[1][0] + d2 * Mi[2][0];
      var w1 = d0 * Mi[0][1] + d1 * Mi[1][1] + d2 * Mi[2][1];
      var w2 = d0 * Mi[0][2] + d1 * Mi[1][2] + d2 * Mi[2][2];
      var B = O.B[c], mu = O.mu[c], lwc = lw[c];
      for (var i = 0; i < n; i++) out[i] += lwc * (w0 * B[0][i] + w1 * B[1][i] + w2 * B[2][i] + mu[i]);
    }
    for (i = 0; i < n; i++) out[i] = Math.max(out[i], 0) * sc;
    return out;
  }
  function exposures(film, S) {
    var H = [0, 0, 0];
    for (var k = 0; k < 3; k++) { var K = film.K[k], h = 0; for (var i = 0; i < S.length; i++) h += S[i] * K[i]; H[k] = Math.max(h, 1e-7); }
    return H;
  }

  /* ---------- film models ---------- */
  function negRender(C, film, v, H) {
    var GRAY = C.GRAY, k = v.k, ref = film.ref, keys = ["R", "G", "B"];
    var xn = ref + (Math.log10(H[0]) + Math.log10(H[1]) + Math.log10(H[2])) / 3 - Math.log10(GRAY);
    var z = [0, 0, 0], zn = [0, 0, 0], z0 = [0, 0, 0], i;
    for (i = 0; i < 3; i++) {
      var c = film.ch[keys[i]], xs = c.x, ds = c.d, g = film.g[i], dref = film.dref[i], lo = xs[0], hi = xs[xs.length - 1];
      var x = Math.min(Math.max(ref + Math.log10(H[i] / GRAY), lo), hi);
      z[i] = (interp(x, xs, ds) - dref) / g; zn[i] = (interp(Math.min(Math.max(xn, lo), hi), xs, ds) - dref) / g; z0[i] = (ds[0] - dref) / g;
    }
    var dm = (z[0] - zn[0] + z[1] - zn[1] + z[2] - zn[2]) / 3, P = [0, 0, 0];
    for (i = 0; i < 3; i++) {
      var p = GRAY * Math.pow(10, zn[i] + dm + (1 + k) * (z[i] - zn[i] - dm));
      if (v.deep) { var P0 = GRAY * Math.pow(10, z0[i]), w = Math.min(Math.max((GRAY - p) / (GRAY - P0), 0), 1); p = p - P0 * w * w; }
      P[i] = Math.min(Math.max(p, 0), 1);
    }
    return mul3(C.M_RGB_to_XYZ, P);
  }
  function posRender(C, film, v, H) {
    var GRAY = C.GRAY, k = v.k, ref = film.ref, xs = film.ux, lo = xs[0], hi = xs[xs.length - 1];
    var xn = Math.min(Math.max(ref + (Math.log10(H[0]) + Math.log10(H[1]) + Math.log10(H[2])) / 3 - Math.log10(GRAY), lo), hi);
    var a = [0, 0, 0], an = [0, 0, 0], i;
    for (i = 0; i < 3; i++) {
      a[i] = interp(Math.min(Math.max(ref + Math.log10(H[i] / GRAY), lo), hi), xs, film.ua[i]);
      an[i] = interp(xn, xs, film.ua[i]);
    }
    var dm = (a[0] - an[0] + a[1] - an[1] + a[2] - an[2]) / 3;
    for (i = 0; i < 3; i++) a[i] = an[i] + dm + (1 + k) * (a[i] - an[i] - dm);
    var E = film.E, W = C.W50, X = [0, 0, 0];
    for (var j = 0; j < W.length; j++) {
      var T = Math.pow(10, -(a[0] * E[0][j] + a[1] * E[1][j] + a[2] * E[2][j]));
      X[0] += T * W[j][0]; X[1] += T * W[j][1]; X[2] += T * W[j][2];
    }
    return mul3(film.norm, X);
  }
  function printRender(C, film, v, H) {
    var GRAY = C.GRAY, k = v.k, ref = film.ref, keys = ["R", "G", "B"], P = C.papers[v.paper], b = film.bal[v.paper];
    var ps = v.ps || film.pscale[v.paper];
    H = [H[0] + C.CAM_FLARE * GRAY, H[1] + C.CAM_FLARE * GRAY, H[2] + C.CAM_FLARE * GRAY];
    var xn = ref + (Math.log10(H[0]) + Math.log10(H[1]) + Math.log10(H[2])) / 3 - Math.log10(GRAY);
    var D = [0, 0, 0], Dn = [0, 0, 0], i;
    for (i = 0; i < 3; i++) {
      var c = film.ch[keys[i]], lo = c.x[0], hi = c.x[c.x.length - 1];
      D[i] = interp(Math.min(Math.max(ref + Math.log10(H[i] / GRAY), lo), hi), c.x, c.d);
      Dn[i] = interp(Math.min(Math.max(xn, lo), hi), c.x, c.d);
    }
    var dm = (D[0] - Dn[0] + D[1] - Dn[1] + D[2] - Dn[2]) / 3, a = [0, 0, 0], plo = P.x[0], phi = P.x[P.x.length - 1];
    for (i = 0; i < 3; i++) {
      var Di = Dn[i] + dm + (1 + k) * (D[i] - Dn[i] - dm);
      Di = film.dref[i] + (Di - film.dref[i]) * (film.pg[1] / film.pg[i]) * ps;
      a[i] = interp(Math.min(Math.max(b[i] - Di, plo), phi), P.x, P.a[i]);
    }
    var E = P.E, W = C.W50, X = [0, 0, 0];
    for (var j = 0; j < W.length; j++) {
      var T = Math.pow(10, -(a[0] * E[0][j] + a[1] * E[1][j] + a[2] * E[2][j]));
      X[0] += T * W[j][0]; X[1] += T * W[j][1]; X[2] += T * W[j][2];
    }
    X = mul3(P.cat, X);
    var vf = C.VIEW_FLARE, w = C.D65W;
    return [(X[0] + vf * w[0]) / (1 + vf), (X[1] + vf * w[1]) / (1 + vf), (X[2] + vf * w[2]) / (1 + vf)];
  }
  /* XYZ (D65, Y=1 white) in -> XYZ (D65) out */
  /* ---------- CAM16 viewing-condition transform (J, M, h kept; average surround) ---------- */
  var M16 = [[0.401288, 0.650173, -0.051461], [-0.250268, 1.204414, 0.045854], [-0.002079, 0.048952, 0.953127]], M16I = null, CAMP = {};
  function camCond(C, LA) {
    var W = [C.D65W[0] * 100, C.D65W[1] * 100, C.D65W[2] * 100], F = 1.0, c = 0.69, Nc = 1.0, Yb = C.VIEW.Yb;
    var k = 1 / (5 * LA + 1), k4 = k * k * k * k, FL = 0.2 * k4 * 5 * LA + 0.1 * (1 - k4) * (1 - k4) * Math.cbrt(5 * LA);
    var n = Yb / W[1], z = 1.48 + Math.sqrt(n), Nbb = 0.725 * Math.pow(n, -0.2), RGBw = mul3(M16, W);
    var DR = [W[1] / RGBw[0], W[1] / RGBw[1], W[1] / RGBw[2]];
    var P = { FL: FL, n: n, z: z, Nbb: Nbb, DR: DR, c: c, Nc: Nc };
    var Rw = [0, 1, 2].map(function (i) { return camFa(P, DR[i] * RGBw[i]); });
    P.Aw = (2 * Rw[0] + Rw[1] + 0.05 * Rw[2] - 0.305) * Nbb;
    return P;
  }
  function camFa(P, x) { var q = Math.pow(P.FL * Math.abs(x) / 100, 0.42); return 400 * Math.sign(x) * q / (q + 27.13) + 0.1; }
  function viewAdapt(C, X, kind) {
    if (!M16I) M16I = inv3(M16);
    if (!CAMP[kind]) CAMP[kind] = [camCond(C, C.VIEW[kind]), camCond(C, C.VIEW.dst)];
    var ps = CAMP[kind][0], pd = CAMP[kind][1];
    var R0 = mul3(M16, [Math.max(X[0], 1e-7) * 100, Math.max(X[1], 1e-7) * 100, Math.max(X[2], 1e-7) * 100]);
    var R = [camFa(ps, R0[0] * ps.DR[0]), camFa(ps, R0[1] * ps.DR[1]), camFa(ps, R0[2] * ps.DR[2])];
    var a = R[0] - 12 * R[1] / 11 + R[2] / 11, b = (R[0] + R[1] - 2 * R[2]) / 9, h = Math.atan2(b, a);
    var et = 0.25 * (Math.cos(h + 2) + 3.8), A = (2 * R[0] + R[1] + 0.05 * R[2] - 0.305) * ps.Nbb;
    var J = 100 * Math.pow(Math.max(A / ps.Aw, 0), ps.c * ps.z);
    var t = (50000 / 13 * ps.Nc * ps.Nbb * et * Math.sqrt(a * a + b * b)) / (R[0] + R[1] + 21 / 20 * R[2]);
    var Mc = Math.pow(t, 0.9) * Math.sqrt(J / 100) * Math.pow(1.64 - Math.pow(0.29, ps.n), 0.73) * Math.pow(ps.FL, 0.25);
    /* inverse under display conditions */
    var Cd = Mc / Math.pow(pd.FL, 0.25), Js = Math.max(J, 1e-9);
    var td = Math.pow(Cd / (Math.sqrt(Js / 100) * Math.pow(1.64 - Math.pow(0.29, pd.n), 0.73)), 1 / 0.9);
    var Ad = pd.Aw * Math.pow(Js / 100, 1 / (pd.c * pd.z)), p2 = Ad / pd.Nbb + 0.305, p3 = 21 / 20, sh = Math.sin(h), ch = Math.cos(h), aa = 0, bb = 0;
    if (td > 1e-12) {
      var p1 = 50000 / 13 * pd.Nc * pd.Nbb * et / td;
      if (Math.abs(sh) >= Math.abs(ch)) {
        bb = p2 * (2 + p3) * (460 / 1403) / (p1 / sh + (2 + p3) * (220 / 1403) * (ch / sh) - 27 / 1403 + p3 * (6300 / 1403)); aa = bb * ch / sh;
      } else {
        aa = p2 * (2 + p3) * (460 / 1403) / (p1 / ch + (2 + p3) * (220 / 1403) - (27 / 1403 - p3 * (6300 / 1403)) * (sh / ch)); bb = aa * sh / ch;
      }
    }
    var Ra = [(460 * p2 + 451 * aa + 288 * bb) / 1403 - 0.1, (460 * p2 - 891 * aa - 261 * bb) / 1403 - 0.1, (460 * p2 - 220 * aa - 6300 * bb) / 1403 - 0.1];
    var Rc = Ra.map(function (r, i) { return Math.sign(r) * 100 / pd.FL * Math.pow(27.13 * Math.abs(r) / (400 - Math.abs(r)), 1 / 0.42) / pd.DR[i]; });
    var o = mul3(M16I, Rc); return [o[0] / 100, o[1] / 100, o[2] / 100];
  }
  function baseRender(C, film, v, xyz) {
    var H = exposures(film, spectrum(C, xyz)), t = film.bases[v.id], X;
    if (v.bpaper) X = printRender(C, film, { paper: v.bpaper, k: v.k, ps: film.pbscale[v.bpaper] }, H);
    else X = film.kind === "neg" ? negRender(C, film, { deep: false, k: v.k }, H) : posRender(C, film, v, H);
    var Y = Math.max(X[1], 1e-9), ly = Math.min(Math.max(Math.log10(Y), t.logYo[0]), t.logYo[t.logYo.length - 1]);
    var yin = Math.pow(10, interp(ly, t.logYo, t.logYin)), L = mul3(C.BRAD, X);
    var o = mul3(C.BRADI, [L[0] * interp(ly, t.logYo, t.r[0]), L[1] * interp(ly, t.logYo, t.r[1]), L[2] * interp(ly, t.logYo, t.r[2])]);
    var s = yin / Y, w = interp(Math.log10(Math.max(xyz[1], 1e-12)), t.logYin, t.w);
    var fb = v.bpaper ? baseRender(C, film, film.variants[0], xyz) : xyz;
    return [w * o[0] * s + (1 - w) * fb[0], w * o[1] * s + (1 - w) * fb[1], w * o[2] * s + (1 - w) * fb[2]];
  }
  /* Black and white: the ICC is the negative only (film + contrast filter).
     The filter is already inside v.mk, so it acts on the spectrum before the
     emulsion integrates it.  The negative's density relative to mid-grey is
     written linearly into Capture One's curve domain (linear ** 1/ENC); paper
     and grade are a curve style on top.  Output is neutral (a = b = 0). */
  function monoRender(C, film, v, xyz) {
    var S = spectrum(C, xyz), k = v.mk, H = 0, P = C.MONO;
    for (var i = 0; i < S.length; i++) H += S[i] * k[i];
    H = Math.max(H, 1e-7);
    var xs = film.x, lo = xs[0], hi = xs[xs.length - 1];
    var pos = Math.min(Math.max(film.sp + 1 + Math.log10(H / C.GRAY), lo), hi);
    var u = film.ref - interp(pos, xs, film.d);
    var val = Math.min(Math.max(P.V_MID - u / P.NEG_SPAN, 0), 1), Y = Math.pow(val, P.ENC), w = C.D65W;
    return [Y * w[0], Y * w[1], Y * w[2]];
  }
  function renderXYZ(C, film, v, xyz) {
    if (film.kind === "mono") return monoRender(C, film, v, xyz);
    if (v.base) return baseRender(C, film, v, xyz);
    var H = exposures(film, spectrum(C, xyz));
    if (v.paper) return viewAdapt(C, printRender(C, film, v, H), "print");
    return film.kind === "neg" ? negRender(C, film, v, H) : viewAdapt(C, posRender(C, film, v, H), "slide");
  }
  /* linear sRGB in -> linear sRGB out (for previews) */
  function filmLinear(C, film, v, lin) {
    var o = mul3(C.M_XYZ_to_RGB, renderXYZ(C, film, v, mul3(C.M_RGB_to_XYZ, lin)));
    return [Math.min(Math.max(o[0], 0), 1), Math.min(Math.max(o[1], 0), 1), Math.min(Math.max(o[2], 0), 1)];
  }

  /* ---------- ICC reading / writing ---------- */
  function sig(dv, o) { return String.fromCharCode(dv.getUint8(o), dv.getUint8(o + 1), dv.getUint8(o + 2), dv.getUint8(o + 3)); }

  function inspect(buf) {
    var dv = new DataView(buf);
    if (buf.byteLength < 132) throw new BakeError("too_small", "ICCプロファイルとして短すぎます。");
    if (sig(dv, 36) !== "acsp") throw new BakeError("not_icc", "ICCプロファイルではありません（acsp署名がありません）。");
    var info = {
      size: dv.getUint32(0), version: dv.getUint8(8) + "." + (dv.getUint8(9) >> 4),
      deviceClass: sig(dv, 12), colorSpace: sig(dv, 16), pcs: sig(dv, 20), creator: sig(dv, 80), tags: []
    };
    var n = dv.getUint32(128);
    for (var t = 0; t < n; t++) {
      var p = 132 + 12 * t;
      info.tags.push({ sig: sig(dv, p), off: dv.getUint32(p + 4), size: dv.getUint32(p + 8), type: sig(dv, dv.getUint32(p + 4)) });
    }
    var desc = info.tags.find(function (x) { return x.sig === "desc"; });
    info.description = desc ? readDesc(dv, desc) : "";
    if (info.colorSpace !== "RGB ") throw new BakeError("not_rgb", "RGB入力のプロファイルではありません（" + info.colorSpace.trim() + "）。");
    if (info.pcs !== "Lab ") throw new BakeError("not_lab", "接続色空間がLabではありません（" + info.pcs.trim() + "）。カメラ用の入力プロファイルを選んでください。");
    info.luts = info.tags.filter(function (x) { return /^A2B[012]$/.test(x.sig); });
    if (!info.luts.length) throw new BakeError("no_a2b", "色変換テーブル（A2B）がありません。");
    info.luts.forEach(function (x) {
      if (x.type !== "mft2") throw new BakeError("unsupported_lut", "このプロファイルの形式（" + x.type.trim() + "）にはまだ対応していません。");
    });
    return info;
  }
  function readDesc(dv, tag) {
    var o = tag.off, ty = sig(dv, o), s = "";
    if (ty === "desc") { var n = dv.getUint32(o + 8); for (var i = 0; i < n - 1; i++) s += String.fromCharCode(dv.getUint8(o + 12 + i)); }
    else if (ty === "mluc") { var len = dv.getUint32(o + 20), so = o + dv.getUint32(o + 24); for (var j = 0; j < len; j += 2) s += String.fromCharCode(dv.getUint16(so + j)); }
    return s;
  }
  function descTag(text) {
    var ascii = text.replace(/[^\x20-\x7e]/g, "?");
    var n = ascii.length + 1, size = 12 + n + 4 + 4 + 2 + 1 + 67;
    var b = new Uint8Array(size), dv = new DataView(b.buffer);
    b.set([100, 101, 115, 99], 0); dv.setUint32(8, n);
    for (var i = 0; i < ascii.length; i++) b[12 + i] = ascii.charCodeAt(i);
    return b;
  }
  function mlucTag(text) {
    var size = 28 + text.length * 2, b = new Uint8Array(size), dv = new DataView(b.buffer);
    b.set([109, 108, 117, 99], 0); dv.setUint32(8, 1); dv.setUint32(12, 12);
    b.set([101, 110, 85, 83], 16); dv.setUint32(20, text.length * 2); dv.setUint32(24, 28);
    for (var i = 0; i < text.length; i++) dv.setUint16(28 + 2 * i, text.charCodeAt(i));
    return b;
  }

  function bake(C, buf, film, variant, name, onProgress) {
    var info = inspect(buf);
    var P = prep(C);
    var src = new Uint8Array(buf);
    var work = new Uint8Array(src.length); work.set(src);
    var dv = new DataView(work.buffer), done = {};
    var nodesTotal = 0, nodesDone = 0;
    info.luts.forEach(function (t) { if (!done[t.off]) { done[t.off] = 1; nodesTotal += Math.pow(dv.getUint8(t.off + 10), 3); } });
    done = {};
    info.luts.forEach(function (t) {
      if (done[t.off]) return; done[t.off] = 1;
      var o = t.off, ni = dv.getUint8(o + 8), no = dv.getUint8(o + 9), g = dv.getUint8(o + 10);
      if (ni !== 3 || no !== 3) throw new BakeError("unsupported_lut", "3入力3出力以外の色変換テーブルには対応していません。");
      var nin = dv.getUint16(o + 48), nout = dv.getUint16(o + 50);
      var c0 = o + 52 + ni * nin * 2, nodes = g * g * g, o0 = c0 + nodes * no * 2;
      if (o0 + no * nout * 2 > o + t.size + 2) throw new BakeError("corrupt", "色変換テーブルの大きさが不正です。");
      var outTab = [];
      for (var ch = 0; ch < 3; ch++) { var tab = []; for (var e = 0; e < nout; e++) tab.push(dv.getUint16(o0 + 2 * (ch * nout + e))); outTab.push(tab); }
      var identity = outTab.every(function (tab) { return tab.every(function (v, e) { return Math.abs(v - Math.round(e * 65535 / (nout - 1))) <= 1; }); });
      function applyOut(ch, v) {
        if (identity) return v;
        var p = v / 65535 * (nout - 1), i0 = Math.min(Math.floor(p), nout - 2), f = p - i0;
        return outTab[ch][i0] * (1 - f) + outTab[ch][i0 + 1] * f;
      }
      for (var nIdx = 0; nIdx < nodes; nIdx++) {
        var p = c0 + nIdx * 6;
        var L = applyOut(0, dv.getUint16(p)) / 65280 * 100, a = applyOut(1, dv.getUint16(p + 2)) / 256 - 128, bb = applyOut(2, dv.getUint16(p + 4)) / 256 - 128;
        var X65 = mul3(P.a50to65, labToXYZ50(L, a, bb));
        var lab = xyz50ToLab(mul3(P.a65to50, renderXYZ(C, film, variant, X65)));
        if (film.kind === "mono") { lab[1] = 0; lab[2] = 0; }
        var e0 = Math.round(lab[0] / 100 * 65280), e1 = Math.round((lab[1] + 128) * 256), e2 = Math.round((lab[2] + 128) * 256);
        dv.setUint16(p, Math.min(Math.max(e0, 0), 65535)); dv.setUint16(p + 2, Math.min(Math.max(e1, 0), 65535)); dv.setUint16(p + 4, Math.min(Math.max(e2, 0), 65535));
        nodesDone++;
        if (onProgress && (nodesDone & 4095) === 0) onProgress(nodesDone / nodesTotal);
      }
      if (!identity) for (ch = 0; ch < 3; ch++) for (e = 0; e < nout; e++) dv.setUint16(o0 + 2 * (ch * nout + e), Math.round(e * 65535 / (nout - 1)));
    });
    /* new description, appended as a new tag body */
    var oldDesc = info.tags.find(function (x) { return x.sig === "desc"; });
    var body = (oldDesc && oldDesc.type === "mluc") ? mlucTag(name) : descTag(name);
    var start = (work.length + 3) & ~3, total = (start + body.length + 3) & ~3;
    var outBuf = new Uint8Array(total); outBuf.set(work); outBuf.set(body, start);
    var odv = new DataView(outBuf.buffer);
    odv.setUint32(0, total);
    for (var i = 84; i < 100; i++) outBuf[i] = 0; /* profile ID no longer valid */
    var n = odv.getUint32(128);
    for (var tI = 0; tI < n; tI++) {
      var q = 132 + 12 * tI;
      if (sig(odv, q) === "desc") { odv.setUint32(q + 4, start); odv.setUint32(q + 8, body.length); }
    }
    if (onProgress) onProgress(1);
    return outBuf;
  }

  function BakeError(code, message) { this.code = code; this.message = message; }
  BakeError.prototype = Object.create(Error.prototype);

  /* ---------- minimal ZIP (stored) ---------- */
  var CRC = (function () { var t = new Uint32Array(256); for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  function crc32(u8) { var c = 0xffffffff; for (var i = 0; i < u8.length; i++) c = CRC[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }
  /* ---------- Capture One style (Engine 1300: ICC on the background, Develop curves on one layer) ---------- */
  function xmlEsc(v) { return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function uuid4() {
    var c = root.crypto;
    if (c && c.randomUUID) { try { return c.randomUUID().toUpperCase(); } catch (e) {} }
    var b = new Uint8Array(16), i;
    if (c && c.getRandomValues) c.getRandomValues(b);
    else for (i = 0; i < 16; i++) b[i] = Math.floor(Math.random() * 256);
    b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
    var h = [];
    for (i = 0; i < 16; i++) h.push((b[i] + 0x100).toString(16).slice(1).toUpperCase());
    return h.slice(0, 4).join("") + "-" + h.slice(4, 6).join("") + "-" + h.slice(6, 8).join("") + "-" + h.slice(8, 10).join("") + "-" + h.slice(10, 16).join("");
  }
  function costyle(film, opts) {
    /* black and white: the ICC alone is the film; paper and grade are separate styles */
    if (film.kind === "mono") return ['<?xml version="1.0"?>', '<SL Engine="1300">',
      '\t<E K="FilmCurve" V="' + xmlEsc(opts.filmCurve) + '" />',
      '\t<E K="ICCProfile" V="' + xmlEsc(opts.icc) + '" />',
      '\t<E K="Name" V="' + xmlEsc(opts.name) + '" />',
      '\t<E K="StyleSource" V="Styles" />',
      '\t<E K="UUID" V="' + uuid4() + '" />',
      "</SL>", ""].join("\n");
    var d = film.dev;
    if (!d) throw new BakeError("no_curves", "このフィルムにはスタイル用のカーブがありません。");
    var layer = ["\t\t<LD>", "\t\t\t<LA>",
      '\t\t\t<E K="Clarity" V="0" />',
      '\t\t\t<E K="DehazeAmount" V="0" />',
      '\t\t\t<E K="Enabled" V="1" />',
      '\t\t\t<E K="GradationCurveBlue" V="' + d.b + '" />',
      '\t\t\t<E K="GradationCurveGreen" V="' + d.g + '" />',
      '\t\t\t<E K="GradationCurveRed" V="' + d.r + '" />',
      '\t\t\t<E K="Name" V="Develop ' + xmlEsc(film.id) + ' - color" />',
      '\t\t\t<E K="Opacity" V="100" />',
      "\t\t\t</LA>", "\t\t\t<MD>",
      '\t\t\t\t<E K="Density" V="1" />',
      '\t\t\t\t<E K="MaskType" V="1" />',
      "\t\t\t</MD>", "\t\t</LD>"].join("\n");
    if (film.slide) layer += "\n" + ["\t\t<LD>", "\t\t\t<LA>",
      '\t\t\t<E K="Clarity" V="0" />',
      '\t\t\t<E K="DehazeAmount" V="0" />',
      '\t\t\t<E K="Enabled" V="1" />',
      '\t\t\t<E K="GradationCurve" V="' + film.slide + '" />',
      '\t\t\t<E K="Name" V="Develop ' + xmlEsc(film.id) + ' - slide tone" />',
      '\t\t\t<E K="Opacity" V="100" />',
      "\t\t\t</LA>", "\t\t\t<MD>",
      '\t\t\t\t<E K="Density" V="1" />',
      '\t\t\t\t<E K="MaskType" V="1" />',
      "\t\t\t</MD>", "\t\t</LD>"].join("\n");
    return ['<?xml version="1.0"?>', '<SL Engine="1300">',
      '\t<E K="FilmCurve" V="' + xmlEsc(opts.filmCurve) + '" />',
      '\t<E K="FilmGrainAmount" V="0" />',
      '\t<E K="FilmGrainDensity" V="0" />',
      '\t<E K="FilmGrainGranularity" V="50" />',
      '\t<E K="FilmGrainType" V="0" />',
      '\t<E K="Highlight" V="1;1;1;1" />',
      '\t<E K="ICCProfile" V="' + xmlEsc(opts.icc) + '" />',
      '\t<E K="Midtone" V="0;0;0;0" />',
      '\t<E K="Name" V="' + xmlEsc(opts.name) + '" />',
      '\t<E K="Shadow" V="0;0;0;0" />',
      '\t<E K="StyleSource" V="Styles" />',
      '\t<E K="UUID" V="' + uuid4() + '" />',
      "</SL>", "<LDS>", layer, "</LDS>", ""].join("\n");
  }

  function zip(files) {
    var enc = new TextEncoder(), parts = [], central = [], offset = 0;
    var now = new Date(), dosTime = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    var dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    files.forEach(function (f) {
      var nm = enc.encode(f.name), crc = crc32(f.data), h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint16(8, 0, true);
      h.setUint16(10, dosTime, true); h.setUint16(12, dosDate, true); h.setUint32(14, crc, true);
      h.setUint32(18, f.data.length, true); h.setUint32(22, f.data.length, true); h.setUint16(26, nm.length, true); h.setUint16(28, 0, true);
      parts.push(new Uint8Array(h.buffer), nm, f.data);
      var c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true); c.setUint16(10, 0, true);
      c.setUint16(12, dosTime, true); c.setUint16(14, dosDate, true); c.setUint32(16, crc, true);
      c.setUint32(20, f.data.length, true); c.setUint32(24, f.data.length, true); c.setUint16(28, nm.length, true);
      c.setUint32(42, offset, true);
      central.push(new Uint8Array(c.buffer), nm);
      offset += 30 + nm.length + f.data.length;
    });
    var cSize = central.reduce(function (s, p) { return s + p.length; }, 0);
    var e = new DataView(new ArrayBuffer(22));
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true);
    e.setUint32(12, cSize, true); e.setUint32(16, offset, true);
    var all = parts.concat(central, [new Uint8Array(e.buffer)]), total = all.reduce(function (s, p) { return s + p.length; }, 0);
    var out = new Uint8Array(total), pos = 0; all.forEach(function (p) { out.set(p, pos); pos += p.length; });
    return out;
  }

  root.FilmBaker = { inspect: inspect, bake: bake, zip: zip, costyle: costyle, filmLinear: filmLinear, renderXYZ: renderXYZ, BakeError: BakeError };
})(typeof window !== "undefined" ? window : globalThis);

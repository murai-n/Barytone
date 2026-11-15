(function () {
  "use strict";
  var C = window.FILM_DATA, FB = window.FilmBaker;
  C.checker = C.checkerXYZ.map(function (X) {
    var M = C.M_XYZ_to_RGB; return [0, 1, 2].map(function (i) { return M[i][0] * X[0] + M[i][1] * X[1] + M[i][2] * X[2]; });
  });
  var $ = function (id) { return document.getElementById(id); };
  /* picks: the camera profiles chosen, one per camera ({ file, buf, info, cand }) */
  var state = { picks: [], cands: [] };
  var MAX_CAMERAS = 8;   /* each camera is ~75 profiles, ~17MB in the ZIP and ~8s of baking */

  /* ---------- sRGB helpers for the preview ---------- */
  function oetf(l) { l = Math.min(Math.max(l, 0), 1); return l <= 0.0031308 ? l * 12.92 : 1.055 * Math.pow(l, 1 / 2.4) - 0.055; }
  function eotf(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }

  /* ---------- what gets made: every film, every variant ---------- */
  var JOBS = [];
  C.films.forEach(function (f) { f.variants.forEach(function (v) { JOBS.push({ film: f, variant: v }); }); });
  function camName(p) { return p ? camOf(p.file.name).replace(/[\\/:*?"<>|\u0000-\u001f]/g, "").trim() || "Camera" : "Camera"; }
  function fileName(p, j) { return camName(p) + "-Film " + j.film.id + " " + j.variant.id; }
  /* 表示用のカメラ名：先頭のメーカー名のあとに空白を入れる（NikonZ5 → Nikon Z5） */
  var BRANDS = [["PhaseOne", "Phase One"], ["OMSystem", "OM System"], ["Fujifilm", "Fujifilm"], ["FUJIFILM", "FUJIFILM"], ["Hasselblad", "Hasselblad"], ["Panasonic", "Panasonic"], ["Olympus", "Olympus"], ["Pentax", "Pentax"], ["Nikon", "Nikon"], ["Canon", "Canon"], ["Sony", "Sony"], ["Leica", "Leica"], ["Ricoh", "Ricoh"], ["Sigma", "Sigma"], ["Mamiya", "Mamiya"], ["Leaf", "Leaf"], ["Samsung", "Samsung"]];
  /* exposure offset per camera, from Capture One's own curves (ds/camera_ev.json):
     the lift its default curve gives a grey card, which Linear Response drops */
  var EVT = C.CAMERA_EV || { default: 0, ev: {} }, EV_IDX = {};
  function evNorm(s) { return String(s).toLowerCase().replace(/[^a-z0-9]+/g, ""); }
  Object.keys(EVT.ev).forEach(function (k) { EV_IDX[evNorm(k)] = k; });
  function evLookup(cam) {
    var n = evNorm(cam), tries = [n, n.replace(/^sonyilce/, "sonya"), n.replace(/^sonydsc/, "sony")];
    if (EVT.ev[cam] != null) return { ev: EVT.ev[cam], src: "table" };
    for (var i = 0; i < tries.length; i++) if (EV_IDX[tries[i]]) return { ev: EVT.ev[EV_IDX[tries[i]]], src: "table" };
    return { ev: EVT.default, src: "default" };
  }
  function evClamp(v) { v = parseFloat(String(v).replace(",", ".")); return isFinite(v) ? Math.round(Math.min(Math.max(v, -3), 3) * 100) / 100 : null; }
  function evFmt(v) { return (v > 0 ? "+" : v < 0 ? "-" : "±") + Math.abs(v).toFixed(2); }
  function evText(p) { return p.evOn ? evFmt(p.ev) + " EV" : "オフ"; }
  function camDisplay(p) {
    var c = camName(p);
    for (var i = 0; i < BRANDS.length; i++) {
      var b = BRANDS[i][0];
      if (c.indexOf(b) === 0 && c.length > b.length) return BRANDS[i][1] + " " + c.slice(b.length).replace(/^[\s_-]+/, "");
    }
    return c;
  }
  /* one camera: <cam>-film-profiles.zip as before; several: one ZIP, each camera's two folders side by side */
  function rootDir() { return state.picks.length > 1 ? "film-profiles" : camName(state.picks[0]) + "-film-profiles"; }
  function zipName() { return state.picks.length > 1 ? "film-profiles-" + state.picks.length + "-cameras.zip" : camName(state.picks[0]) + "-film-profiles.zip"; }
  function iccDir(p) { return "ICC (" + camDisplay(p) + ")"; }
  function filmDir(p) { return "1 Film (" + camDisplay(p) + ")"; }
  /* inside the Film folder: one subfolder per kind, so the style list groups them */
  var KIND_DIR = { neg: "Negative", pos: "Positive", mono: "B&W" };
  function kindDir(j) { return KIND_DIR[j.film.kind] || "Other"; }
  function styleName(p, j) {
    var f = j.film.kind === "mono" && j.variant.id !== "base" ? " " + j.variant.id : "";   /* one style per contrast filter */
    return "Film " + j.film.id + f + " (" + camDisplay(p) + ")";
  }
  function filmCurveName(p) { return camName(p) + "-Linear Response.fcrv"; }

  /* ---------- preview ---------- */
  /* a mono ICC holds the negative; the preview shows it printed on the preview paper */
  function look(film, variant, lin) {
    if (!film) return lin;
    var o = FB.filmLinear(C, film, variant, lin);
    if (film.kind !== "mono") return o;
    var P = C.MONO.preview, M = C.M_RGB_to_XYZ, Y = o[0] * M[1][0] + o[1] * M[1][1] + o[2] * M[1][2];
    var n = P.v.length - 1, t = Math.min(Math.max(Math.pow(Math.max(Y, 0), 1 / C.MONO.ENC), 0), 1) * n;
    var i = Math.min(Math.floor(t), n - 1), f = t - i, A = P.rgb[i], B = P.rgb[i + 1];
    return [A[0] + f * (B[0] - A[0]), A[1] + f * (B[1] - A[1]), A[2] + f * (B[2] - A[2])];
  }
  function drawPreview(canvas, film, variant) {
    var cols = 12, rows = 2, W = 1200, ph = 64, rampH = 36, gap = 4;
    canvas.width = W; canvas.height = rows * ph + gap + rampH;
    var ctx = canvas.getContext("2d"), pw = W / cols;
    C.checker.forEach(function (lin, i) {
      var o = look(film, variant, lin);
      var r = Math.round(oetf(o[0]) * 255), g = Math.round(oetf(o[1]) * 255), b = Math.round(oetf(o[2]) * 255);
      ctx.fillStyle = "rgb(" + r + "," + g + "," + b + ")";
      var col = i % 6 + (i >= 12 ? 6 : 0), row = Math.floor(i / 6) % 2;
      ctx.fillRect(Math.round(col * pw), row * ph, Math.ceil(pw), ph);
    });
    var img = ctx.createImageData(W, rampH);
    for (var x = 0; x < W; x++) {
      var v = eotf(x / (W - 1)), o = look(film, variant, [v, v, v]);
      for (var y = 0; y < rampH; y++) { var p = (y * W + x) * 4; img.data[p] = oetf(o[0]) * 255; img.data[p + 1] = oetf(o[1]) * 255; img.data[p + 2] = oetf(o[2]) * 255; img.data[p + 3] = 255; }
    }
    ctx.putImageData(img, 0, rows * ph + gap);
  }
  function figure(title, sub, film, variant) {
    var fig = document.createElement("figure"); fig.className = "preview-item";
    var cap = document.createElement("figcaption"); cap.textContent = title;
    if (sub) { var sp = document.createElement("span"); sp.textContent = sub; cap.appendChild(sp); }
    var cv = document.createElement("canvas"); cv.setAttribute("role", "img");
    cv.setAttribute("aria-label", title + (sub ? " " + sub : "") + "の色見本");
    fig.appendChild(cap); fig.appendChild(cv); drawPreview(cv, film, variant);
    return fig;
  }

  /* ---------- refresh ---------- */
  var previewsDrawn = false;
  function drawAllPreviews() {
    if (previewsDrawn) return;
    previewsDrawn = true;
    var box = $("previews");
    box.appendChild(figure("元の色", "フィルムを通す前", null, null));
    JOBS.forEach(function (j) {
      var title = j.film.kind === "mono" ? j.film.name + " " + j.variant.label : j.film.name;
      var sub = j.film.desc + "（" + j.film.iso + (j.film.kind === "mono" ? "、" + C.MONO.preview.label + "で焼いた見本" : "") + "）";
      box.appendChild(figure(title, sub, j.film, j.variant));
    });
  }
  function refresh() {
    var n = state.picks.length, p = state.picks[0], more = n > 1 ? " など" : "";
    Array.prototype.forEach.call(document.querySelectorAll(".icc-dir"), function (el) { el.textContent = n ? iccDir(p) + more : "ICC (カメラ名)"; });
    Array.prototype.forEach.call(document.querySelectorAll(".film-dir"), function (el) { el.textContent = n ? filmDir(p) + more : "1 Film (カメラ名)"; });
    $("summary").hidden = true;   /* the picks list already says what will be made */
    $("run-button").disabled = !n;
    $("run-button").textContent = n > 1 ? n + "台分のICCプロファイルを作成してダウンロード" : "ICCプロファイルを作成してダウンロード";
  }

  /* ---------- file selection ---------- */
  var ICC_RE = /\.(icc|icm)$/i;
  function setUploadError(msg) {
    var ul = $("upload-errors");
    ul.innerHTML = msg ? "<li>" + msg.replace(/</g, "&lt;") + "</li>" : "";
    $("upload").setAttribute("data-has-error", msg ? "true" : "false");
    if (msg) $("upload-announcer").textContent = msg;
  }
  function dropPick(i) {
    state.picks.splice(i, 1);
    remember(); say("");
    $("file-input").value = ""; $("dir-input").value = "";
    renderPicks();
    if (state.cands.length) renderHits();
    refresh();
  }
  function renderPicks() {
    if (mycams.length) setTimeout(renderMyCams, 0);
    $("file-list").innerHTML = state.picks.map(function (p, i) {
      return '<li class="dads-file-upload__file-item"><div class="dads-file-upload__file-marker"></div>' +
        '<div class="dads-file-upload__file-info"><p><span class="dads-file-upload__file-name">' + esc(p.file.name) + "</span>" +
        '<span class="dads-file-upload__file-meta">' + esc(camDisplay(p) + "・" + fmtSize(p.file.size)) + "</span></p>" +
        '<p class="ev-row"><label class="ev-on"><input type="checkbox" data-evon="' + i + '"' + (p.evOn ? " checked" : "") + "> 露出オフセット</label>" +
        '<input class="ev-input" type="text" inputmode="decimal" value="' + evFmt(p.ev) + '" data-ev="' + i + '" aria-label="' + esc(camDisplay(p)) + ' の露出オフセット（EV）"' + (p.evOn ? "" : " disabled") + "> EV" +
        (p.evSrc === "default" ? '<span class="ev-note">表にない機種のため、全機種の中央値</span>' : "") + "</p></div>" +
        '<button class="dads-file-upload__remove-button dads-button" data-type="text" data-size="xs" type="button" data-remove="' + i + '" aria-label="' + esc(p.file.name) + ' を解除">解除</button></li>';
    }).join("");
    $("upload").setAttribute("data-multiple", state.picks.length > 1 ? "true" : "false");
    syncEmpty();
  }
  function syncEmpty() {
    var picked = state.picks.length > 0;
    $("file-list").hidden = !picked; $("ev-lead").hidden = !picked;
    $("empty-message").hidden = picked || !$("search-box").hidden;
  }
  function fmtSize(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + "MB" : Math.max(1, Math.round(n / 1024)) + "KB"; }
  var KIND = { scnr: "入力プロファイル（カメラ・スキャナー用）", mntr: "モニター用", prtr: "プリンター用", spac: "色空間", abst: "抽象", link: "デバイスリンク" };
  function pickIndex(file) {
    for (var i = 0; i < state.picks.length; i++) if (state.picks[i].file === file) return i;
    return -1;
  }
  function takeFile(file, fromCache, cand, evSaved) {
    setUploadError("");
    if (!file) return;
    if (!ICC_RE.test(file.name)) { setUploadError("ICCプロファイル（.icc または .icm）を選んでください。"); return; }
    if (file.size > 64 * 1048576) { setUploadError("ファイルが大きすぎます（64MBまで）。"); return; }
    var reader = new FileReader();
    reader.onload = function () {
      var buf = reader.result, info;
      try { info = FB.inspect(buf); } catch (err) { setUploadError(file.name + "：" + (err && err.message ? err.message : "読み込めませんでした。")); return; }
      var p = { file: file, buf: buf, info: info, cand: cand || null }, cam = camName(p), msg = file.name + " を読み込みました。";
      if (evSaved == null) { var mine = mycams.find(function (m) { return myCamOf(m.name) === cam && m.ev != null; }); if (mine) evSaved = { ev: mine.ev, on: mine.evOn }; }
      var lk = evLookup(cam); p.evSrc = lk.src;
      if (evSaved != null) { p.ev = evSaved.ev; p.evOn = evSaved.on !== false; if (p.ev !== lk.ev) p.evSrc = "saved"; } else { p.ev = lk.ev; p.evOn = true; }
      /* one profile per camera: the names inside the ZIP are per camera, so a second pick replaces the first */
      var same = state.picks.findIndex(function (q) { return camName(q) === cam; });
      if (same >= 0) { msg = camDisplay(p) + " は " + file.name + " に入れ替えました。"; state.picks[same] = p; }
      else if (state.picks.length >= MAX_CAMERAS) { setUploadError("一度に選べるのは" + MAX_CAMERAS + "台までです。どれかを解除してから選んでください。"); return; }
      else state.picks.push(p);
      renderPicks();
      $("upload-announcer").textContent = msg;
      if (fromCache) say("前回選んだプロファイルです。別のカメラにするときは「解除」を押してください。");
      else { say(""); remember(); }
      if (state.cands.length) renderHits();
      refresh();
    };
    reader.onerror = function () { setUploadError("ファイルを読み込めませんでした。"); };
    reader.readAsArrayBuffer(file);
  }

  /* ---------- candidate list and search ---------- */
  function norm(s) { return String(s).toLowerCase().replace(/[^a-z0-9]+/g, ""); }
  /* Capture One names profiles <カメラ名>-<プロファイル名>, and the camera name
     itself can hold a hyphen (SonyILCE-7RM4)。プロファイル名らしい部分が続く
     最後のハイフンで切る。 */
  function splitName(stem) {
    var at = -1;
    for (var i = 1; i < stem.length - 1; i++) {
      /* a hyphen inside the profile name ("Nikon_-_Neutral", "Nikon - Neutral") is not the split */
      if (stem.charAt(i) !== "-" || /[_ ]/.test(stem.charAt(i - 1)) || /[_ ]/.test(stem.charAt(i + 1))) continue;
      if (stem.slice(0, i).indexOf(" ") >= 0) break;   /* camera ids have no spaces */
      var tail = stem.slice(i + 1);
      if (/[_ ]/.test(tail) || /^[A-Za-z][A-Za-z0-9]{3,}$/.test(tail)) at = i;
    }
    return at > 0 ? [stem.slice(0, at), stem.slice(at + 1)] : [stem, ""];
  }
  function camOf(name) { return splitName(name.replace(ICC_RE, ""))[0]; }
  /* ベースは演出の入っていないものを選ぶ。元プロファイルが出した色を、
     フィルムが見た被写体の色として扱うため。 */
  var GOOD = /(^| )(neutral|faithful|generic|standard)( |$)/, 
      BAD = /(^| )(portrait|landscape|vivid|monochrome|mono|sepia|night|autumn|clear|deep|bw|b w|film standard|black white|effect|provia|velvia|astia|acros|eterna|nostalgic|classic chrome|classic neg|pro neg|soft|dramatic|toy|miniature|pop)( |$)/;
  function rankOf(rest) {
    var t = " " + String(rest).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim() + " ";
    if (BAD.test(t)) return 2;
    if (GOOD.test(t)) return 0;
    return 1;
  }

  function makeCand(file, path) {
    var parts = splitName(file.name.replace(ICC_RE, ""));
    return {
      file: file, name: file.name, norm: norm(file.name.replace(ICC_RE, "")),
      cam: parts[0], rest: parts[1].replace(/_/g, " "), rank: rankOf(parts[1]),
      dir: path ? path.replace(/[^/\\]*$/, "").replace(/[/\\]$/, "") : ""
    };
  }
  var HIT_MAX = 60;
  function renderHits() {
    var box = $("hits"), raw = $("camera-query").value;
    var terms = raw.trim().split(/\s+/).map(norm).filter(Boolean);
    var hits = terms.length
      ? state.cands.filter(function (c) { return terms.every(function (t) { return c.norm.indexOf(t) >= 0; }); })
      : state.cands;
    var shown = hits.slice(0, HIT_MAX);
    box.innerHTML = shown.map(function (c) {
      var i = state.cands.indexOf(c), sub = [c.rest, state.showDir ? c.dir : ""].filter(Boolean).join("　/　");
      var tag = c.rank === 0 ? '<span class="tag tag-good">おすすめ</span>' : c.rank === 2 ? '<span class="tag tag-bad">向きません</span>' : "";
      return '<li><button type="button" class="hit" data-i="' + i + '"' + (state.picks.some(function (p) { return p.cand === c; }) ? ' aria-pressed="true"' : ' aria-pressed="false"') + ">" +
        '<span class="hit-cam">' + esc(c.cam) + "</span>" + tag +
        (sub ? '<span class="hit-rest">' + esc(sub) + "</span>" : "") + "</button></li>";
    }).join("");
    var n = hits.length, total = state.cands.length;
    $("hit-summary").textContent = !total ? ""
      : !terms.length ? total.toLocaleString("ja-JP") + "個のプロファイルがあります。カメラ名を入れて絞り込んでください。"
      : !n ? "見つかりませんでした。「Z5」「ILCE-7M4」のように、機種名の一部だけで試してください。"
      : n > HIT_MAX ? n.toLocaleString("ja-JP") + "個のうち" + HIT_MAX + "個を表示しています。語を足すと絞り込めます。"
      : n + "個見つかりました。";
  }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  $("hits").addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest(".hit"); if (!btn) return;
    var c = state.cands[+btn.getAttribute("data-i")]; if (!c) return;
    var k = state.picks.findIndex(function (p) { return p.cand === c; });
    if (k >= 0) { dropPick(k); $("upload-announcer").textContent = c.name + " を解除しました。"; return; }   /* clicking a picked one unpicks it */
    takeFile(c.file, false, c);
  });
  var qTimer = null;
  $("camera-query").addEventListener("input", function () {
    clearTimeout(qTimer); qTimer = setTimeout(renderHits, 80);
  });

  /* ---------- copy a path ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-copy]"); if (!b) return;
    var text = $(b.getAttribute("data-copy")).textContent.trim(), label = b.getAttribute("data-label") || b.textContent;
    b.setAttribute("data-label", label);
    function tell(msg) { b.textContent = msg; setTimeout(function () { b.textContent = label; }, 1800); }
    function legacy() {
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      var ok = false; try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      ta.remove(); tell(ok ? "コピーしました" : "コピーできません");
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { tell("コピーしました"); }, legacy);
    } else legacy();
  });

  /* ---------- Mac / Windows switch ---------- */
  function syncOs() {
    var win = document.body.getAttribute("data-os") === "win", label = win ? "Mac の場合を表示" : "Windows の場合を表示";
    Array.prototype.forEach.call(document.querySelectorAll(".os-toggle"), function (b) { b.textContent = label; });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".os-toggle"); if (!b) return;
    document.body.setAttribute("data-os", document.body.getAttribute("data-os") === "win" ? "mac" : "win");
    syncOs();
  });

  /* ---------- paths for the dialog ---------- */
  function buildPaths() {
    var app = $("mac-app"), fw = $("mac-fw"), ver = $("win-ver");
    function upd() {
      var a = (app.value || "Capture One").trim().replace(/\.app$/i, "") || "Capture One";
      $("path-mac").textContent = "/Applications/" + a + ".app/Contents/Frameworks/" + fw.value + ".framework/Versions/A/Resources/Profiles/Input";
      $("path-win").textContent = "C:\\Program Files\\Capture One\\" + ((ver.value || "Capture One 23").trim() || "Capture One 23") + "\\Color Profiles\\DSLR";
    }
    app.addEventListener("input", upd); fw.addEventListener("change", upd); ver.addEventListener("input", upd);
    upd();
  }

  /* ---------- remember the chosen profile in this browser ---------- */
  var DB_NAME = "film-baker", STORE = "profile", KEY = "last";
  function idb() {
    return new Promise(function (res, rej) {
      var r;
      try { r = indexedDB.open(DB_NAME, 1); } catch (e) { rej(e); return; }
      r.onupgradeneeded = function () { try { r.result.createObjectStore(STORE); } catch (e) {} };
      r.onsuccess = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
      r.onblocked = function () { rej(new Error("blocked")); };
    });
  }
  function idbRun(mode, fn) {
    return idb().then(function (db) {
      return new Promise(function (res, rej) {
        var tx = db.transaction(STORE, mode), out = fn(tx.objectStore(STORE));
        tx.oncomplete = function () { db.close(); res(out && out.result); };
        tx.onerror = function () { db.close(); rej(tx.error); };
        tx.onabort = function () { db.close(); rej(tx.error); };
      });
    });
  }
  /* every picked profile, under KEY_ALL; the one-profile record of earlier versions is still read */
  var KEY_ALL = "picks", KEY_MY = "mycams";
  /* my cameras: every camera a ZIP was saved for, newest profile per camera, kept until deleted here */
  var mycams = [];
  function saveMyCams() {
    try { var recs = mycams.map(function (m) { return { name: m.name, buf: m.buf, at: m.at, ev: m.ev, evOn: m.evOn }; });
      idbRun("readwrite", function (st) { st.put(recs, KEY_MY); })["catch"](function () {}); } catch (e) {}
  }
  function loadMyCams() {
    try {
      idbRun("readonly", function (st) { return st.get(KEY_MY); }).then(function (recs) {
        mycams = (recs || []).filter(function (r) { return r && r.buf && r.name; });
        renderMyCams();
      }, function () {});
    } catch (e) {}
  }
  function myCamOf(name) { return camName({ file: { name: name } }); }
  function addMyCams(picks) {
    var at = new Date().toISOString().slice(0, 10);
    picks.forEach(function (p) {
      var cam = camName(p), i = mycams.findIndex(function (m) { return myCamOf(m.name) === cam; }), rec = { name: p.file.name, buf: p.buf, at: at, ev: p.ev, evOn: p.evOn };
      if (i >= 0) mycams[i] = rec; else mycams.push(rec);
    });
    mycams.sort(function (a, b) { return myCamOf(a.name).localeCompare(myCamOf(b.name), "en"); });
    saveMyCams(); renderMyCams();
  }
  function renderMyCams() {
    $("mycams").hidden = !mycams.length;
    $("mycam-list").innerHTML = mycams.map(function (m, i) {
      var cam = myCamOf(m.name), on = state.picks.some(function (p) { return camName(p) === cam && p.file.name === m.name; });
      var disp = camDisplay({ file: { name: m.name } });
      return '<li class="mycam-row"><button type="button" class="hit" data-my="' + i + '" aria-pressed="' + on + '">' +
        '<span class="hit-cam">' + esc(disp) + "</span>" +
        '<span class="hit-rest">' + esc(m.name + (m.at ? "　前回 " + m.at : "") + (m.ev != null ? "　露出オフセット " + (m.evOn === false ? "オフ" : evFmt(m.ev) + " EV") : "")) + "</span></button>" +
        '<button type="button" class="dads-button mycam-del" data-type="text" data-size="xs" data-mydel="' + i + '" aria-label="' + esc(disp) + ' をマイカメラから削除">削除</button></li>';
    }).join("");
    $("lead-folder").textContent = mycams.length ? "ほかのカメラは、Capture One が持っているカメラプロファイルのフォルダを選ぶと、カメラ名で探せます。" : "Capture One が持っているカメラプロファイルのフォルダを選ぶと、カメラ名で探せます。";
  }
  function pickMyCam(i, only) {
    var m = mycams[i], cam = myCamOf(m.name), k = state.picks.findIndex(function (p) { return camName(p) === cam && p.file.name === m.name; });
    if (k >= 0) { if (!only) { dropPick(k); $("upload-announcer").textContent = m.name + " を解除しました。"; } return; }
    var f; try { f = new File([m.buf], m.name, { type: "application/vnd.iccprofile" }); } catch (e) { return; }
    takeFile(f, false, null, m.ev != null ? { ev: m.ev, on: m.evOn } : null);
  }
  function remember() {
    try {
      var recs = state.picks.map(function (p) { return { name: p.file.name, buf: p.buf, ev: p.ev, evOn: p.evOn }; });
      idbRun("readwrite", function (st) { st["delete"](KEY); if (recs.length) st.put(recs, KEY_ALL); else st["delete"](KEY_ALL); })["catch"](function () {});
    } catch (e) {}
  }
  function restore() {
    try {
      idbRun("readonly", function (st) { return st.get(KEY_ALL); }).then(function (recs) {
        if (recs && recs.length) return recs;
        return idbRun("readonly", function (st) { return st.get(KEY); }).then(function (rec) { return rec ? [rec] : []; });
      }).then(function (recs) {
        if (state.picks.length) return;
        (recs || []).forEach(function (rec) {
          if (!rec || !rec.buf || !rec.name) return;
          var f;
          try { f = new File([rec.buf], rec.name, { type: "application/vnd.iccprofile" }); } catch (e) { return; }
          takeFile(f, true, null, rec.ev != null ? { ev: rec.ev, on: rec.evOn } : null);
        });
      }, function () {});
    } catch (e) {}
  }

  /* ---------- scanning ---------- */
  function say(msg) { var el = $("scan-status"); el.textContent = msg || ""; el.hidden = !msg; }
  function beginScan() { say("フォルダの中を調べています…"); }
  function finishScan(cands, looked, stopped) {
    cands.sort(function (a, b) { return a.rank - b.rank || a.name.localeCompare(b.name, "en"); });
    state.cands = cands;
    state.showDir = cands.some(function (c) { return c.dir !== cands[0].dir; });
    if (!cands.length) {
      $("search-box").hidden = true; say("");
      setUploadError(looked ? "このフォルダにICCプロファイル（.icc / .icm）は見つかりませんでした。" : "ICCプロファイルを選んでください。");
      return;
    }
    setUploadError("");
    if (cands.length === 1) {
      $("search-box").hidden = true; say("");
      takeFile(cands[0].file, false, cands[0]); return;
    }
    say(stopped ? "フォルダが大きいため、途中までを対象にしています。見つからない場合は、もっと下の階層のフォルダを選んでください。" : "");
    $("search-box").hidden = false; syncEmpty();
    $("camera-query").value = ""; renderHits();
    $("upload-announcer").textContent = cands.length + "個のプロファイルが見つかりました。カメラ名で検索できます。";
    $("camera-query").focus();
  }
  function takeFileList(list) {
    var arr = Array.prototype.slice.call(list || []), cands = [];
    for (var i = 0; i < arr.length; i++) if (ICC_RE.test(arr[i].name)) cands.push(makeCand(arr[i], arr[i].webkitRelativePath || ""));
    finishScan(cands, arr.length, false);
  }
  var MAX_VISIT = 120000;
  function scanEntries(entries) {
    beginScan();
    var out = [], visited = 0, stopped = false;
    function walk(entry, depth) {
      if (stopped || ++visited > MAX_VISIT) { stopped = true; return Promise.resolve(); }
      if (entry.isFile) {
        if (!ICC_RE.test(entry.name)) return Promise.resolve();
        return new Promise(function (res) {
          entry.file(function (f) { out.push(makeCand(f, entry.fullPath || "")); res(); }, function () { res(); });
        });
      }
      if (!entry.isDirectory || depth >= 16) return Promise.resolve();
      var rd = entry.createReader(), kids = [];
      return new Promise(function (res) {
        (function read() {
          rd.readEntries(function (ents) {
            if (!ents.length) {
              var i = 0;
              (function next() {
                if (i >= kids.length || stopped) return res();
                walk(kids[i++], depth + 1).then(i % 300 === 0 ? function () { setTimeout(next, 0); } : next);
              })();
              return;
            }
            kids = kids.concat(Array.prototype.slice.call(ents)); read();
          }, function () { res(); });
        })();
      });
    }
    var k = 0;
    (function next() {
      if (k >= entries.length) { say(""); finishScan(out, visited, stopped); return; }
      walk(entries[k++], 0).then(next);
    })();
  }

  $("dir-button").addEventListener("click", function () { $("dir-input").click(); });
  $("dir-input").addEventListener("change", function () { if (this.files && this.files.length) { beginScan(); takeFileList(this.files); } });
  $("file-input").addEventListener("change", function () { if (this.files && this.files.length) takeFileList(this.files); });
  $("mycam-list").addEventListener("click", function (e) {
    var d = e.target.closest && e.target.closest("[data-mydel]");
    if (d) {
      var m = mycams[+d.getAttribute("data-mydel")];
      mycams.splice(+d.getAttribute("data-mydel"), 1); saveMyCams(); renderMyCams();
      $("upload-announcer").textContent = myCamOf(m.name) + " をマイカメラから削除しました。";
      return;
    }
    var b = e.target.closest && e.target.closest("[data-my]"); if (b) pickMyCam(+b.getAttribute("data-my"), false);
  });
  $("mycam-all").addEventListener("click", function () { mycams.forEach(function (m, i) { pickMyCam(i, true); }); });
  $("file-list").addEventListener("change", function (e) {
    var t = e.target;
    if (t.hasAttribute && t.hasAttribute("data-evon")) {
      var q = state.picks[+t.getAttribute("data-evon")]; if (!q) return;
      q.evOn = t.checked;
      var box = $("file-list").querySelector('[data-ev="' + t.getAttribute("data-evon") + '"]'); if (box) box.disabled = !q.evOn;
      remember(); return;
    }
    if (!t.hasAttribute || !t.hasAttribute("data-ev")) return;
    var p = state.picks[+t.getAttribute("data-ev")], v = evClamp(String(t.value).replace(/^\s*\+/, "")); if (!p) return;
    if (v == null) { t.value = evFmt(p.ev); return; }
    p.ev = v; p.evSrc = "manual"; t.value = evFmt(v);
    remember();
  });
  $("file-list").addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-remove]"); if (!b) return;
    var name = state.picks[+b.getAttribute("data-remove")].file.name;
    dropPick(+b.getAttribute("data-remove")); $("upload-announcer").textContent = name + " を解除しました。";
    var next = $("file-list").querySelector("[data-remove]");
    (next || (state.cands.length ? $("camera-query") : $("dir-button"))).focus();
  });
  var drop = $("drop-area"), depth = 0;
  drop.addEventListener("dragenter", function (e) { e.preventDefault(); depth++; drop.setAttribute("data-dragover", "true"); });
  drop.addEventListener("dragover", function (e) { e.preventDefault(); });
  drop.addEventListener("dragleave", function () { if (--depth <= 0) { depth = 0; drop.removeAttribute("data-dragover"); } });
  drop.addEventListener("drop", function (e) {
    e.preventDefault(); depth = 0; drop.removeAttribute("data-dragover");
    var dt = e.dataTransfer; if (!dt) return;
    var items = dt.items, entries = [];
    if (items) for (var i = 0; i < items.length; i++) {
      var en = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
      if (en) entries.push(en);
    }
    if (entries.length) scanEntries(entries); else takeFileList(dt.files);
  });

  /* ---------- downloads ---------- */
  var downloadsP = null;
  function hostDownloads() {
    if (!downloadsP && window.claude && typeof window.claude.use === "function") downloadsP = window.claude.use("downloads").catch(function () { return null; });
    return downloadsP;
  }
  setTimeout(hostDownloads, 0);
  function saveFile(name, bytes) {
    var p = hostDownloads();
    return (p || Promise.resolve(undefined)).then(function (dl) {
      var blob = new Blob([bytes], { type: "application/zip" });
      if (dl) return dl.save({ filename: name, data: blob }).then(function () { return "saved"; });
      if (dl === null) return Promise.reject({ code: "unavailable" });
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
      return "saved";
    });
  }
  var ERR = {
    declined: "ダウンロードがキャンセルされました。もう一度ボタンを押すと、やり直せます。",
    rate_limited: "確認画面がすでに開いています。少し待ってから、もう一度お試しください。",
    too_large: "ファイルが大きすぎて保存できませんでした。",
    not_granted: "このページにダウンロードの許可が下りていません。ツールを別のタブで開き直すと保存できることがあります。",
    capability_disabled: "このページにダウンロードの許可が下りていません。ツールを別のタブで開き直すと保存できることがあります。",
    capability_removed: "このページにダウンロードの許可が下りていません。ツールを別のタブで開き直すと保存できることがあります。",
    unavailable: "この画面では保存できません。ツールを別のタブで開き直すと保存できることがあります。",
    rejected_extension: "この形式のファイルは保存できませんでした。",
    extension_not_enabled: "この形式のファイルは、この画面では保存できません。",
    bad_request: "保存の要求に問題がありました。ページを再読み込みしてから、もう一度お試しください。",
    transform_error: "保存の要求に問題がありました。ページを再読み込みしてから、もう一度お試しください。",
    request_unknown: "保存の要求が期限切れでした。もう一度ボタンを押してください。"
  };

  /* ---------- run ---------- */
  function showError(title, body) {
    $("error-title").textContent = title; $("error-body").textContent = body;
    $("error-banner").hidden = false; $("error-banner").focus();
  }
  $("run-button").addEventListener("click", function () {
    var picks = state.picks.slice(), js = JOBS; if (!picks.length || !js.length) return;
    var btn = this; btn.disabled = true;
    $("done-banner").hidden = true; $("error-banner").hidden = true;
    $("progress").hidden = false; $("progress-bar").style.width = "0%";
    var files = [], i = 0, total = picks.length * js.length, root = rootDir(), zname = zipName();
    function step() {
      if (i >= total) return finish();
      var p = picks[Math.floor(i / js.length)], j = js[i % js.length], name = fileName(p, j);
      $("status").textContent = (picks.length > 1 ? camDisplay(p) + "　" : "") + (i % js.length + 1) + " / " + js.length + "：" + j.film.name + "（" + j.variant.label + "）を作成中…";
      setTimeout(function () {
        try {
          var bytes = FB.bake(C, p.buf.slice(0), j.film, j.variant, name);
          files.push({ name: root + "/" + iccDir(p) + "/" + name + ".icm", data: bytes });
          var sty = FB.costyle(j.film, { icc: name + ".icm", filmCurve: filmCurveName(p), name: styleName(p, j), ev: p.evOn ? p.ev : null });
          files.push({ name: root + "/" + filmDir(p) + "/" + kindDir(j) + "/" + styleName(p, j) + ".costyle", data: new TextEncoder().encode(sty) });
        } catch (err) {
          $("progress").hidden = true; $("status").textContent = ""; btn.disabled = false;
          showError("作成できませんでした", camDisplay(p) + "：" + (err && err.message ? err.message : String(err))); return;
        }
        i++; $("progress-bar").style.width = Math.round(i / total * 100) + "%";
        step();
      }, 16);
    }
    function finish() {
      var zipped = FB.zip(files);
      $("status").textContent = "ダウンロードの確認画面を開いています…";
      saveFile(zname, zipped).then(function () {
        $("status").textContent = "";
        addMyCams(picks);
        $("done-title").textContent = (picks.length > 1 ? picks.length + "台のカメラで" : "") + js.length + "種類のフィルムを作成しました";
        $("done-body").textContent = zname + " を保存しました。ICCプロファイル" + total + "個とスタイル" + total + "個が入っています。下の「Capture One での使い方」の手順で読み込んでください。";
        $("done-banner").hidden = false; $("done-banner").focus();
      }).catch(function (err) {
        $("status").textContent = "";
        var code = (err && err.code) || "unavailable";
        showError("保存できませんでした", (ERR[code] || ERR.unavailable) + "（" + code + "）");
      }).then(function () { $("progress").hidden = true; btn.disabled = false; refresh(); });
    }
    step();
  });

  loadMyCams();
  syncOs(); buildPaths(); drawAllPreviews(); restore(); refresh();
})();

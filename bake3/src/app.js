(function () {
  "use strict";
  var C = window.FILM_DATA, FB = window.FilmBaker;
  C.checker = C.checkerXYZ.map(function (X) {
    var M = C.M_XYZ_to_RGB; return [0, 1, 2].map(function (i) { return M[i][0] * X[0] + M[i][1] * X[1] + M[i][2] * X[2]; });
  });
  var $ = function (id) { return document.getElementById(id); };
  var state = { buf: null, file: null, info: null, cands: [], picked: null };

  /* ---------- sRGB helpers for the preview ---------- */
  function oetf(l) { l = Math.min(Math.max(l, 0), 1); return l <= 0.0031308 ? l * 12.92 : 1.055 * Math.pow(l, 1 / 2.4) - 0.055; }
  function eotf(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }

  /* ---------- what gets made: every film, every variant ---------- */
  var JOBS = [];
  C.films.forEach(function (f) { f.variants.forEach(function (v) { JOBS.push({ film: f, variant: v }); }); });
  function camName() { return state.file ? camOf(state.file.name).replace(/[\\/:*?"<>|\u0000-\u001f]/g, "").trim() || "Camera" : "Camera"; }
  function fileName(j) { return camName() + "-Film " + j.film.id + " " + j.variant.id; }
  /* 表示用のカメラ名：先頭のメーカー名のあとに空白を入れる（NikonZ5 → Nikon Z5） */
  var BRANDS = [["PhaseOne", "Phase One"], ["OMSystem", "OM System"], ["Fujifilm", "Fujifilm"], ["FUJIFILM", "FUJIFILM"], ["Hasselblad", "Hasselblad"], ["Panasonic", "Panasonic"], ["Olympus", "Olympus"], ["Pentax", "Pentax"], ["Nikon", "Nikon"], ["Canon", "Canon"], ["Sony", "Sony"], ["Leica", "Leica"], ["Ricoh", "Ricoh"], ["Sigma", "Sigma"], ["Mamiya", "Mamiya"], ["Leaf", "Leaf"], ["Samsung", "Samsung"]];
  function camDisplay() {
    var c = camName();
    for (var i = 0; i < BRANDS.length; i++) {
      var b = BRANDS[i][0];
      if (c.indexOf(b) === 0 && c.length > b.length) return BRANDS[i][1] + " " + c.slice(b.length).replace(/^[\s_-]+/, "");
    }
    return c;
  }
  function rootDir() { return camName() + "-film-profiles"; }
  function iccDir() { return "ICC (" + camDisplay() + ")"; }
  function filmDir() { return "1 Film (" + camDisplay() + ")"; }
  function styleName(j) { return "Film " + j.film.id + " (" + camDisplay() + ")"; }
  function filmCurveName() { return camName() + "-Linear Response.fcrv"; }

  /* ---------- preview ---------- */
  function drawPreview(canvas, film, variant) {
    var cols = 12, rows = 2, W = 1200, ph = 64, rampH = 36, gap = 4;
    canvas.width = W; canvas.height = rows * ph + gap + rampH;
    var ctx = canvas.getContext("2d"), pw = W / cols;
    C.checker.forEach(function (lin, i) {
      var o = film ? FB.filmLinear(C, film, variant, lin) : lin;
      var r = Math.round(oetf(o[0]) * 255), g = Math.round(oetf(o[1]) * 255), b = Math.round(oetf(o[2]) * 255);
      ctx.fillStyle = "rgb(" + r + "," + g + "," + b + ")";
      var col = i % 6 + (i >= 12 ? 6 : 0), row = Math.floor(i / 6) % 2;
      ctx.fillRect(Math.round(col * pw), row * ph, Math.ceil(pw), ph);
    });
    var img = ctx.createImageData(W, rampH);
    for (var x = 0; x < W; x++) {
      var v = eotf(x / (W - 1)), o = film ? FB.filmLinear(C, film, variant, [v, v, v]) : [v, v, v];
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
    JOBS.forEach(function (j) { box.appendChild(figure(j.film.name, j.film.desc + "（" + j.film.iso + "）", j.film, j.variant)); });
  }
  function refresh() {
    var ready = !!state.buf;
    Array.prototype.forEach.call(document.querySelectorAll(".icc-dir"), function (el) { el.textContent = ready ? iccDir() : "ICC (カメラ名)"; });
    Array.prototype.forEach.call(document.querySelectorAll(".film-dir"), function (el) { el.textContent = ready ? filmDir() : "1 Film (カメラ名)"; });
    $("summary").textContent = ready
      ? JOBS.length + "種類のフィルムについて、ICCプロファイルと、それを使うスタイルを作ります。" + fileName(JOBS[0]) + ".icm と " + styleName(JOBS[0]) + ".costyle のような名前で、1つのZIPにまとまります。"
      : "先に手順1でプロファイルを選んでください。";
    $("run-button").disabled = !ready;
  }

  /* ---------- file selection ---------- */
  var ICC_RE = /\.(icc|icm)$/i;
  function setUploadError(msg) {
    var ul = $("upload-errors");
    ul.innerHTML = msg ? "<li>" + msg.replace(/</g, "&lt;") + "</li>" : "";
    $("upload").setAttribute("data-has-error", msg ? "true" : "false");
    if (msg) $("upload-announcer").textContent = msg;
  }
  function clearFile() {
    state.buf = null; state.file = null; state.info = null; state.picked = null;
    forget(); say("");
    $("file-input").value = ""; $("dir-input").value = "";
    syncEmpty();
    if (state.cands.length) renderHits();
    refresh();
  }
  function syncEmpty() {
    var picked = !!state.buf;
    $("file-list").hidden = !picked;
    $("empty-message").hidden = picked || !$("search-box").hidden;
  }
  function fmtSize(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + "MB" : Math.max(1, Math.round(n / 1024)) + "KB"; }
  var KIND = { scnr: "入力プロファイル（カメラ・スキャナー用）", mntr: "モニター用", prtr: "プリンター用", spac: "色空間", abst: "抽象", link: "デバイスリンク" };
  function takeFile(file, fromCache) {
    setUploadError("");
    if (!file) return;
    if (!ICC_RE.test(file.name)) { setUploadError("ICCプロファイル（.icc または .icm）を選んでください。"); return; }
    if (file.size > 64 * 1048576) { setUploadError("ファイルが大きすぎます（64MBまで）。"); return; }
    var reader = new FileReader();
    reader.onload = function () {
      var buf = reader.result, info;
      try { info = FB.inspect(buf); } catch (err) { clearFile(); setUploadError(file.name + "：" + (err && err.message ? err.message : "読み込めませんでした。")); return; }
      state.buf = buf; state.file = file; state.info = info;
      $("file-name").textContent = file.name;
      $("file-meta").textContent = fmtSize(file.size) + "（" + file.size.toLocaleString("ja-JP") + "バイト）";
      syncEmpty();
      $("upload-announcer").textContent = file.name + " を読み込みました。";
      if (fromCache) say("前回選んだプロファイルです。別のカメラにするときは「解除」を押してください。");
      else { say(""); remember(file, buf); }
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
      if (stem.charAt(i) !== "-" || stem.charAt(i - 1) === "_" || stem.charAt(i + 1) === "_") continue;
      var tail = stem.slice(i + 1);
      if (tail.indexOf("_") >= 0 || /^[A-Za-z][A-Za-z0-9]{3,}$/.test(tail)) at = i;
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
      return '<li><button type="button" class="hit" data-i="' + i + '"' + (state.picked === c ? ' aria-current="true"' : "") + ">" +
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
    state.picked = c; takeFile(c.file);
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
  function remember(file, buf) {
    try {
      idbRun("readwrite", function (st) { st.put({ name: file.name, buf: buf }, KEY); })["catch"](function () {});
    } catch (e) {}
  }
  function forget() {
    try { idbRun("readwrite", function (st) { st["delete"](KEY); })["catch"](function () {}); } catch (e) {}
  }
  function restore() {
    try {
      idbRun("readonly", function (st) { return st.get(KEY); }).then(function (rec) {
        if (!rec || !rec.buf || !rec.name || state.buf) return;
        var f;
        try { f = new File([rec.buf], rec.name, { type: "application/vnd.iccprofile" }); } catch (e) { return; }
        takeFile(f, true);
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
      state.picked = cands[0]; takeFile(cands[0].file); return;
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
  $("remove-button").addEventListener("click", function () {
    clearFile(); $("upload-announcer").textContent = "選択を解除しました。";
    (state.cands.length ? $("camera-query") : $("dir-button")).focus();
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
    var js = JOBS; if (!state.buf || !js.length) return;
    var btn = this; btn.disabled = true;
    $("done-banner").hidden = true; $("error-banner").hidden = true;
    $("progress").hidden = false; $("progress-bar").style.width = "0%";
    var files = [], i = 0;
    function step() {
      if (i >= js.length) return finish();
      var j = js[i], name = fileName(j);
      $("status").textContent = (i + 1) + " / " + js.length + "：" + j.film.name + "（" + j.variant.label + "）を作成中…";
      setTimeout(function () {
        try {
          var bytes = FB.bake(C, state.buf.slice(0), j.film, j.variant, name);
          files.push({ name: rootDir() + "/" + iccDir() + "/" + name + ".icm", data: bytes });
          var sty = FB.costyle(j.film, { icc: name + ".icm", filmCurve: filmCurveName(), name: styleName(j) });
          files.push({ name: rootDir() + "/" + filmDir() + "/" + styleName(j) + ".costyle", data: new TextEncoder().encode(sty) });
        } catch (err) {
          $("progress").hidden = true; $("status").textContent = ""; btn.disabled = false;
          showError("作成できませんでした", err && err.message ? err.message : String(err)); return;
        }
        i++; $("progress-bar").style.width = Math.round(i / js.length * 100) + "%";
        step();
      }, 16);
    }
    function finish() {
      var zipName = camName() + "-film-profiles.zip";
      var zipped = FB.zip(files);
      $("status").textContent = "ダウンロードの確認画面を開いています…";
      saveFile(zipName, zipped).then(function () {
        $("status").textContent = "";
        $("done-title").textContent = js.length + "種類のフィルムを作成しました";
        $("done-body").textContent = zipName + " を保存しました。ICCプロファイル" + js.length + "個とスタイル" + js.length + "個が入っています。下の「Capture One での使い方」の手順で読み込んでください。";
        $("done-banner").hidden = false; $("done-banner").focus();
      }).catch(function (err) {
        $("status").textContent = "";
        var code = (err && err.code) || "unavailable";
        showError("保存できませんでした", (ERR[code] || ERR.unavailable) + "（" + code + "）");
      }).then(function () { $("progress").hidden = true; btn.disabled = false; refresh(); });
    }
    step();
  });

  syncOs(); buildPaths(); drawAllPreviews(); restore(); refresh();
})();

const { chromium } = require("playwright");
const http = require("http"), fs = require("fs");

const DIST = process.env.DIST || __dirname + "/dist/index.html";
const T = process.env.CO_TEST || "/tmp/co_test";   /* holds Input/ (camera profiles); see make_fixture.py */
let pass = 0, fail = 0;
const ok = (label, cond, extra) => { (cond ? pass++ : fail++); console.log((cond ? "PASS" : "FAIL") + "  " + label + (extra ? "  → " + extra : "")); };

(async () => {
  const srv = http.createServer((q, r) => { r.writeHead(200, { "content-type": "text/html; charset=utf-8" }); r.end(fs.readFileSync(DIST)); }).listen(8731);
  const browser = await chromium.launch(Object.assign({ args: ["--no-sandbox"] }, process.env.CHROME ? { executablePath: process.env.CHROME } : {}));
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 1000 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", e => errs.push(String(e)));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  await page.goto("http://127.0.0.1:8731/", { waitUntil: "load" });

  /* --- the removed steps are gone --- */
  ok("film picker removed", (await page.locator("#film-groups").count()) === 0);
  ok("variant picker removed", (await page.locator("#neg-variants").count()) === 0);
  ok("filename field removed", (await page.locator("#prefix").count()) === 0);
  ok("only two numbered steps", (await page.locator(".step-no").count()) === 2);
  ok("about section removed", !(await page.content()).includes("このツールについて"));
  ok("no フィルムの目 anywhere", !(await page.content()).includes("フィルムの目"));

  /* --- preview sits after the download step --- */
  const order = await page.$$eval("section.section", ss => ss.map(s => s.getAttribute("aria-labelledby")));
  ok("preview comes after the download step", order.indexOf("h-preview") > order.indexOf("h-step2"), order.join(" > "));
  ok("every film is previewed", (await page.locator(".preview-item").count()) === 76, (await page.locator(".preview-item").count()) + " figures");

  /* --- mac path builder --- */
  await page.locator(".where > summary").click();
  await page.waitForTimeout(150);
  let macPath = await page.locator("#path-mac").textContent();
  ok("mac path built on load", macPath === "/Applications/Capture One.app/Contents/Frameworks/ImageProcessing.framework/Versions/A/Resources/Profiles/Input", macPath);
  await page.fill("#mac-app", "Capture One 23");
  await page.selectOption("#mac-fw", "AppCore");
  macPath = await page.locator("#path-mac").textContent();
  ok("mac path follows app name and framework", macPath === "/Applications/Capture One 23.app/Contents/Frameworks/AppCore.framework/Versions/A/Resources/Profiles/Input", macPath);
  await page.fill("#mac-app", "Capture One 21.app");
  ok("a typed .app suffix is not doubled", (await page.locator("#path-mac").textContent()).indexOf("21.app/Contents") > 0, await page.locator("#path-mac").textContent());
  ok("windows block hidden on a mac", await page.locator("#path-win").isHidden());
  await page.locator(".where .os-toggle").click();
  await page.waitForTimeout(150);
  ok("toggle reveals the windows block", await page.locator("#path-win").isVisible());
  ok("toggle hides the mac block", await page.locator("#path-mac").isHidden());
  ok("toggle label flips", (await page.locator(".where .os-toggle").textContent()).trim() === "Mac の場合を表示", await page.locator(".where .os-toggle").textContent());
  await page.fill("#win-ver", "Capture One 16");
  ok("windows path follows the version folder", (await page.locator("#path-win").textContent()) === "C:\\Program Files\\Capture One\\Capture One 16\\Color Profiles\\DSLR", await page.locator("#path-win").textContent());
  await page.locator(".where .os-toggle").click();
  await page.waitForTimeout(150);
  ok("toggle is shared across the page", await page.locator("#dest-mac").isVisible() && await page.locator("#dest-win").isHidden());

  /* --- destination sits above the download button --- */
  const s2 = await page.$eval("section[aria-labelledby=h-step2]", el => el.innerHTML);
  ok("destination comes before the run button", s2.indexOf("dest-mac") < s2.indexOf("run-button"));
  ok("destination has no tilde", (await page.locator("#dest-mac").textContent()) === "/Library/ColorSync/Profiles", await page.locator("#dest-mac").textContent());
  ok("howto no longer repeats the path", (await page.locator("section[aria-labelledby=h-howto]").textContent()).indexOf("ColorSync") < 0);

  /* --- folder scan and search --- */
  ok("run button disabled at start", await page.locator("#run-button").isDisabled());
  await page.setInputFiles("#dir-input", T + "/Input");
  await page.waitForSelector("#search-box:not([hidden])", { timeout: 10000 });
  ok("folder scan found profiles", /12個のプロファイル/.test(await page.locator("#hit-summary").textContent()));
  await page.fill("#camera-query", "z5");
  await page.waitForTimeout(200);
  let hits = await page.locator("#hits .hit-cam").allTextContents();
  ok("'z5' narrows to NikonZ5", hits.length === 3 && hits.every(h => h === "NikonZ5"), JSON.stringify(hits));
  ok("the neutral profile is marked and listed first", (await page.locator("#hits .hit .tag-good").count()) === 1 && /Neutral/.test(await page.locator("#hits .hit").first().textContent()), await page.locator("#hits .hit").first().textContent());
  ok("styled profiles are marked unsuitable", (await page.locator("#hits .hit .tag-bad").count()) === 2, (await page.locator("#hits .hit .tag-bad").allTextContents()).join(","));
  await page.fill("#camera-query", "ilce 7m4");
  await page.waitForTimeout(200);
  hits = await page.locator("#hits .hit-cam").allTextContents();
  ok("hyphenated model kept whole", hits.length === 1 && hits[0] === "SonyILCE-7M4", JSON.stringify(hits));
  await page.fill("#camera-query", "hasselblad");
  await page.waitForTimeout(200);
  ok("no match shows guidance", /見つかりませんでした/.test(await page.locator("#hit-summary").textContent()));

  /* --- pick, and the name follows automatically --- */
  await page.fill("#camera-query", "z5 neutral");
  await page.waitForTimeout(200);
  await page.locator("#hits .hit").first().click();
  await page.waitForSelector("#file-list:not([hidden])", { timeout: 10000 });
  ok("folder names on the page follow the camera", (await page.locator(".icc-dir").first().textContent()) === "ICC (Nikon Z5)", await page.locator(".icc-dir").first().textContent());
  ok("no long summary under step 2", await page.locator("#summary").isHidden());
  ok("step 1 explains the exposure offset", (await page.locator("#ev-lead").isVisible()) && /適正なプリント/.test(await page.locator("#ev-lead").textContent()));
  ok("run button enabled", await page.locator("#run-button").isEnabled());
  ok("Z5 gets its exposure offset from the table, shown with its sign", (await page.locator("#file-list .ev-input").inputValue()) === "+1.25" && (await page.locator("#file-list .ev-note").count()) === 0, await page.locator("#file-list .ev-input").inputValue());
  ok("the offset is on by default", await page.locator("#file-list [data-evon]").isChecked());

  /* --- bake everything --- */
  const dl = page.waitForEvent("download", { timeout: 120000 });
  await page.locator("#run-button").click();
  const d = await dl;
  await d.saveAs(T + "/out.zip");
  ok("zip named from the camera", d.suggestedFilename() === "NikonZ5-film-profiles.zip", d.suggestedFilename());
  const buf = fs.readFileSync(T + "/out.zip");
  let entries = 0;
  for (let i = 0; i < buf.length - 4; i++) if (buf[i] === 0x50 && buf[i + 1] === 0x4b && buf[i + 2] === 3 && buf[i + 3] === 4) entries++;
  ok("zip holds 75 profiles and 75 styles", entries === 150, entries + " entries, " + buf.length + " bytes");
  ok("profiles are under NikonZ5-film-profiles/ICC (Nikon Z5)/", buf.includes(Buffer.from("NikonZ5-film-profiles/ICC (Nikon Z5)/NikonZ5-Film KP400 base.icm")));
  ok("styles are under NikonZ5-film-profiles/1 Film (Nikon Z5)/Negative/", buf.includes(Buffer.from("NikonZ5-film-profiles/1 Film (Nikon Z5)/Negative/Film KP400 (Nikon Z5).costyle")));
  {
    const { execSync } = require("child_process");
    execSync(`rm -rf "${T}/unz" && mkdir -p "${T}/unz" && cd "${T}/unz" && unzip -q ../out.zip`);
    const sty = fs.readFileSync(T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/Negative/Film KP400 (Nikon Z5).costyle", "utf8");
    ok("style points at the matching ICC", sty.includes('K="ICCProfile" V="NikonZ5-Film KP400 base.icm"'));
    ok("style sets the camera's linear curve", sty.includes('K="FilmCurve" V="NikonZ5-Linear Response.fcrv"'));
    ok("style carries the camera's exposure offset", sty.includes('K="Exposure" V="1.25"'));
    ok("style carries the develop layer", sty.includes('K="Name" V="Develop KP400 - color"') && sty.includes("<LDS>"));
    { const pos = fs.readFileSync(T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/Positive/Film FV50 (Nikon Z5).costyle", "utf8"); ok("positive styles carry the slide tone layer", pos.includes("Develop FV50 - slide tone") && (pos.match(/<LD>/g)||[]).length === 2); ok("negative styles stay single-layer", (sty.match(/<LD>/g)||[]).length === 1); }
    { const dir = T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/B&W/", ms = fs.readFileSync(dir + "Film IHP5 R (Nikon Z5).costyle", "utf8"), mb = fs.readFileSync(dir + "Film IHP5 (Nikon Z5).costyle", "utf8");
      ok("mono: one style per filter, pointing at its ICC", ms.includes('K="ICCProfile" V="NikonZ5-Film IHP5 R.icm"') && mb.includes('K="ICCProfile" V="NikonZ5-Film IHP5 base.icm"'));
      ok("mono styles carry no develop layer", !ms.includes("<LDS>") && ms.includes('K="FilmCurve" V="NikonZ5-Linear Response.fcrv"'));
      ok("mono ICC is in the ICC folder", fs.existsSync(T + "/unz/NikonZ5-film-profiles/ICC (Nikon Z5)/NikonZ5-Film KTX400 G.icm")); }
    ok("style has a real uuid", /K="UUID" V="[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}"/.test(sty));
    const FD = T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/", kinds = fs.readdirSync(FD).sort(), styles = [].concat(...kinds.map(k => fs.readdirSync(FD + k).map(f => FD + k + "/" + f)));
    ok("Film folder splits into Negative / Positive / B&W", JSON.stringify(kinds) === '["B&W","Negative","Positive"]' && JSON.stringify(kinds.map(k => fs.readdirSync(FD + k).length)) === "[45,18,12]", JSON.stringify(kinds.map(k => [k, fs.readdirSync(FD + k).length])));
    const n = fs.readdirSync(T + "/unz/NikonZ5-film-profiles/ICC (Nikon Z5)").length, m = styles.length;
    ok("both folders unzip cleanly", n === 75 && m === 75, n + " icc, " + m + " styles");
    const uuids = new Set(styles.map(f => /V="([0-9A-F-]{36})"/.exec(fs.readFileSync(f, "utf8").match(/UUID[^/]*/)[0])[1]));
    ok("every style has its own uuid", uuids.size === 75, uuids.size + " unique");
  }
  await page.waitForSelector("#done-banner:not([hidden])", { timeout: 10000 });

  /* --- the profile is remembered across visits --- */
  await page.reload({ waitUntil: "load" });
  await page.waitForSelector("#file-list:not([hidden])", { timeout: 10000 });
  ok("profile restored after reload", (await page.locator("#file-list .dads-file-upload__file-name").allTextContents()).join() === "NikonZ5-Nikon_-_Neutral.icm");
  ok("the baked camera is in my cameras", (await page.locator("#mycams").isVisible()) && JSON.stringify(await page.locator("#mycam-list .hit-cam").allTextContents()) === '["Nikon Z5"]', JSON.stringify(await page.locator("#mycam-list .hit-cam").allTextContents()));
  ok("my camera shows as picked when it is", (await page.locator('#mycam-list .hit[aria-pressed="true"]').count()) === 1);
  ok("restore is explained", /前回選んだプロファイル/.test(await page.locator("#scan-status").textContent()));
  ok("ready to bake with no picking", await page.locator("#run-button").isEnabled());
  ok("folder list not shown on a restored visit", await page.locator("#search-box").isHidden());

  /* --- several cameras in one ZIP --- */
  await page.setInputFiles("#dir-input", T + "/Input");
  await page.waitForSelector("#search-box:not([hidden])", { timeout: 10000 });
  await page.fill("#camera-query", "z5 portrait");
  await page.waitForTimeout(200);
  await page.locator("#hits .hit").first().click();
  await page.waitForTimeout(400);
  let picked = await page.locator("#file-list .dads-file-upload__file-name").allTextContents();
  ok("a second profile of the same camera replaces the first", picked.length === 1 && picked[0] === "NikonZ5-Nikon_-_Portrait.icm", JSON.stringify(picked));
  await page.fill("#camera-query", "z5 neutral");
  await page.waitForTimeout(200);
  await page.locator("#hits .hit").first().click();
  await page.fill("#camera-query", "ilce 7m4");
  await page.waitForTimeout(200);
  await page.locator("#hits .hit").first().click();
  await page.fill("#camera-query", "eos r5");
  await page.waitForTimeout(200);
  await page.locator("#hits .hit").first().click();
  await page.waitForTimeout(400);
  picked = await page.locator("#file-list .dads-file-upload__file-name").allTextContents();
  ok("three cameras picked", picked.length === 3, JSON.stringify(picked));
  ok("a picked hit shows as pressed", (await page.locator('#hits .hit[aria-pressed="true"]').count()) === 1);
  await page.locator("#hits .hit").first().click();   /* EOS R5 again: unpick */
  await page.waitForTimeout(400);
  picked = await page.locator("#file-list .dads-file-upload__file-name").allTextContents();
  ok("clicking a picked hit unpicks it", picked.length === 2 && !picked.some(n => /EOSR5/.test(n)), JSON.stringify(picked));
  {
    const evs = page.locator("#file-list .ev-input");
    ok("Sony ILCE name finds its curve (A7M4)", (await evs.nth(1).inputValue()) === "+1.27" && (await page.locator("#file-list .ev-note").count()) === 0, await evs.nth(1).inputValue());
    await evs.nth(1).fill("1.5"); await evs.nth(1).dispatchEvent("change");
    await page.waitForTimeout(200);
    ok("a typed offset is kept, with its sign", (await evs.nth(1).inputValue()) === "+1.50", await evs.nth(1).inputValue());
  }
  ok("run button says how many", (await page.locator("#run-button").textContent()).trim() === "2台分のICCプロファイルを作成してダウンロード");
  {
    const dl2 = page.waitForEvent("download", { timeout: 180000 });
    await page.locator("#run-button").click();
    const d2 = await dl2; await d2.saveAs(T + "/out2.zip");
    ok("multi-camera zip name", d2.suggestedFilename() === "film-profiles-2-cameras.zip", d2.suggestedFilename());
    const { execSync } = require("child_process");
    execSync(`rm -rf "${T}/unz2" && mkdir -p "${T}/unz2" && cd "${T}/unz2" && unzip -q ../out2.zip`);
    const top = fs.readdirSync(T + "/unz2/film-profiles").sort();
    ok("one folder pair per camera", JSON.stringify(top) === JSON.stringify(["1 Film (Nikon Z5)", "1 Film (Sony ILCE-7M4)", "ICC (Nikon Z5)", "ICC (Sony ILCE-7M4)"]), JSON.stringify(top));
    const cnt = d => fs.readdirSync(d, { withFileTypes: true }).reduce((n, e) => n + (e.isDirectory() ? cnt(d + "/" + e.name) : 1), 0);
    const counts = top.map(d => cnt(T + "/unz2/film-profiles/" + d));
    ok("75 files in each", counts.every(c => c === 75), JSON.stringify(counts));
    const sony = fs.readFileSync(T + "/unz2/film-profiles/1 Film (Sony ILCE-7M4)/Negative/Film KP400 (Sony ILCE-7M4).costyle", "utf8");
    ok("each camera's style carries its own exposure", sony.includes('K="Exposure" V="1.5"') && fs.readFileSync(T + "/unz2/film-profiles/1 Film (Nikon Z5)/Negative/Film KP400 (Nikon Z5).costyle", "utf8").includes('K="Exposure" V="1.25"'));
    ok("each camera's styles point at its own ICC and curve", sony.includes('V="SonyILCE-7M4-Film KP400 base.icm"') && sony.includes('V="SonyILCE-7M4-Linear Response.fcrv"'));
    const a = fs.readFileSync(T + "/unz2/film-profiles/ICC (Nikon Z5)/NikonZ5-Film KP400 base.icm"), b = fs.readFileSync(T + "/unz2/film-profiles/ICC (Sony ILCE-7M4)/SonyILCE-7M4-Film KP400 base.icm");
    ok("each camera's ICC carries its own name", a.includes(Buffer.from("NikonZ5-Film KP400 base")) && b.includes(Buffer.from("SonyILCE-7M4-Film KP400 base")));
    await page.waitForSelector("#done-banner:not([hidden])", { timeout: 10000 });
    ok("done banner counts every profile", /ICCプロファイル150個/.test(await page.locator("#done-body").textContent()), await page.locator("#done-body").textContent());
  }
  await page.reload({ waitUntil: "load" });
  await page.waitForSelector("#file-list:not([hidden])", { timeout: 10000 });
  await page.waitForTimeout(500);
  ok("both cameras restored after reload", (await page.locator("#file-list .dads-file-upload__file-name").count()) === 2);
  ok("a typed offset survives the reload", (await page.locator("#file-list .ev-input").nth(1).inputValue()) === "+1.50");
  ok("my cameras remember the offset", /露出オフセット \+1\.50 EV/.test((await page.locator("#mycam-list .hit-rest").allTextContents()).join("|")), (await page.locator("#mycam-list .hit-rest").allTextContents()).join("|"));

  /* --- a camera not in the table falls back to the median --- */
  await page.setInputFiles("#dir-input", T + "/Input");
  await page.waitForSelector("#search-box:not([hidden])", { timeout: 10000 });
  await page.fill("#camera-query", "panasonic"); await page.waitForTimeout(200);
  await page.locator("#hits .hit").first().click(); await page.waitForTimeout(400);
  { const last = page.locator("#file-list .ev-note").last(); ok("unknown camera uses the median and says so", /中央値/.test(await last.textContent()) && (await page.locator("#file-list .ev-input").last().inputValue()) === "+1.27", await last.textContent()); }
  await page.locator("#file-list [data-remove]").last().click(); await page.waitForTimeout(300);

  /* --- 解除 forgets it --- */
  await page.locator("#file-list [data-remove]").first().click();
  await page.waitForTimeout(300);
  ok("解除 removes one camera", (await page.locator("#file-list .dads-file-upload__file-name").count()) === 1);
  {
    /* switching the offset off leaves the exposure out of every style */
    await page.locator("#file-list [data-evon]").uncheck(); await page.waitForTimeout(200);
    ok("unchecking disables the value", await page.locator("#file-list .ev-input").isDisabled());
    const dl3 = page.waitForEvent("download", { timeout: 120000 });
    await page.locator("#run-button").click();
    const d3 = await dl3; await d3.saveAs(T + "/out3.zip");
    const { execSync } = require("child_process");
    execSync(`rm -rf "${T}/unz3" && mkdir -p "${T}/unz3" && cd "${T}/unz3" && unzip -q ../out3.zip`);
    const top3 = fs.readdirSync(T + "/unz3")[0], dir3 = T + "/unz3/" + top3 + "/" + fs.readdirSync(T + "/unz3/" + top3).find(n => /^1 Film/.test(n));
    const st3 = fs.readFileSync(dir3 + "/Negative/" + fs.readdirSync(dir3 + "/Negative")[0], "utf8"), mo3 = fs.readFileSync(dir3 + "/B&W/" + fs.readdirSync(dir3 + "/B&W")[0], "utf8");
    ok("offset off: no Exposure in colour or B&W styles", !st3.includes('K="Exposure"') && !mo3.includes('K="Exposure"') && st3.includes('K="ICCProfile"'));
    await page.waitForSelector("#done-banner:not([hidden])", { timeout: 10000 });
    ok("my cameras show the offset as off", /露出オフセット オフ/.test((await page.locator("#mycam-list .hit-rest").allTextContents()).join("|")), (await page.locator("#mycam-list .hit-rest").allTextContents()).join("|"));
  }
  await page.locator("#file-list [data-remove]").first().click();
  await page.waitForTimeout(400);
  await page.reload({ waitUntil: "load" });
  await page.waitForTimeout(800);
  ok("解除 clears the remembered profile", await page.locator("#file-list").isHidden());
  ok("run button disabled again", await page.locator("#run-button").isDisabled());

  /* --- my cameras survive the picks being cleared --- */
  ok("both baked cameras are in my cameras", JSON.stringify(await page.locator("#mycam-list .hit-cam").allTextContents()) === '["Nikon Z5","Sony ILCE-7M4"]', JSON.stringify(await page.locator("#mycam-list .hit-cam").allTextContents()));
  ok("my camera keeps the latest profile of that camera", /NikonZ5-Nikon_-_Neutral\.icm/.test(await page.locator("#mycam-list .hit-rest").first().textContent()), await page.locator("#mycam-list .hit-rest").first().textContent());
  await page.locator("#mycam-all").click();
  await page.waitForTimeout(500);
  ok("すべて選ぶ picks every my camera", (await page.locator("#file-list .dads-file-upload__file-name").count()) === 2 && (await page.locator("#run-button").isEnabled()));
  await page.locator("#mycam-list .hit").first().click();
  await page.waitForTimeout(400);
  ok("clicking a picked my camera unpicks it", (await page.locator("#file-list .dads-file-upload__file-name").count()) === 1);
  await page.locator("#mycam-list [data-mydel]").last().click();
  await page.waitForTimeout(400);
  await page.reload({ waitUntil: "load" });
  await page.waitForTimeout(800);
  ok("deleting a my camera is remembered", JSON.stringify(await page.locator("#mycam-list .hit-cam").allTextContents()) === '["Nikon Z5"]', JSON.stringify(await page.locator("#mycam-list .hit-cam").allTextContents()));
  await page.locator("#mycam-list [data-mydel]").first().click();
  await page.waitForTimeout(300);
  ok("no my cameras, no block", await page.locator("#mycams").isHidden());

  ok("no page errors", errs.length === 0, errs.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close(); srv.close();
  process.exit(fail ? 1 : 0);
})();

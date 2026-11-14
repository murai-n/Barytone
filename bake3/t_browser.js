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
  let hits = await page.locator(".hit-cam").allTextContents();
  ok("'z5' narrows to NikonZ5", hits.length === 3 && hits.every(h => h === "NikonZ5"), JSON.stringify(hits));
  ok("the neutral profile is marked and listed first", (await page.locator(".hit .tag-good").count()) === 1 && /Neutral/.test(await page.locator(".hit").first().textContent()), await page.locator(".hit").first().textContent());
  ok("styled profiles are marked unsuitable", (await page.locator(".hit .tag-bad").count()) === 2, (await page.locator(".hit .tag-bad").allTextContents()).join(","));
  await page.fill("#camera-query", "ilce 7m4");
  await page.waitForTimeout(200);
  hits = await page.locator(".hit-cam").allTextContents();
  ok("hyphenated model kept whole", hits.length === 1 && hits[0] === "SonyILCE-7M4", JSON.stringify(hits));
  await page.fill("#camera-query", "hasselblad");
  await page.waitForTimeout(200);
  ok("no match shows guidance", /見つかりませんでした/.test(await page.locator("#hit-summary").textContent()));

  /* --- pick, and the name follows automatically --- */
  await page.fill("#camera-query", "z5 neutral");
  await page.waitForTimeout(200);
  await page.locator(".hit").first().click();
  await page.waitForSelector("#file-list:not([hidden])", { timeout: 10000 });
  const sum = await page.locator("#summary").textContent();
  ok("folder names on the page follow the camera", (await page.locator(".icc-dir").first().textContent()) === "ICC (Nikon Z5)", await page.locator(".icc-dir").first().textContent());
  ok("summary names the camera and the count", /75種類/.test(sum) && /NikonZ5-Film /.test(sum) && /costyle/.test(sum), sum);
  ok("run button enabled", await page.locator("#run-button").isEnabled());

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
  ok("styles are under NikonZ5-film-profiles/1 Film (Nikon Z5)/", buf.includes(Buffer.from("NikonZ5-film-profiles/1 Film (Nikon Z5)/Film KP400 (Nikon Z5).costyle")));
  {
    const { execSync } = require("child_process");
    execSync(`rm -rf "${T}/unz" && mkdir -p "${T}/unz" && cd "${T}/unz" && unzip -q ../out.zip`);
    const sty = fs.readFileSync(T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/Film KP400 (Nikon Z5).costyle", "utf8");
    ok("style points at the matching ICC", sty.includes('K="ICCProfile" V="NikonZ5-Film KP400 base.icm"'));
    ok("style sets the camera's linear curve", sty.includes('K="FilmCurve" V="NikonZ5-Linear Response.fcrv"'));
    ok("style carries the develop layer", sty.includes('K="Name" V="Develop KP400 - color"') && sty.includes("<LDS>"));
    { const pos = fs.readFileSync(T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/Film FV50 (Nikon Z5).costyle", "utf8"); ok("positive styles carry the slide tone layer", pos.includes("Develop FV50 - slide tone") && (pos.match(/<LD>/g)||[]).length === 2); ok("negative styles stay single-layer", (sty.match(/<LD>/g)||[]).length === 1); }
    { const dir = T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/", ms = fs.readFileSync(dir + "Film IHP5 R (Nikon Z5).costyle", "utf8"), mb = fs.readFileSync(dir + "Film IHP5 (Nikon Z5).costyle", "utf8");
      ok("mono: one style per filter, pointing at its ICC", ms.includes('K="ICCProfile" V="NikonZ5-Film IHP5 R.icm"') && mb.includes('K="ICCProfile" V="NikonZ5-Film IHP5 base.icm"'));
      ok("mono styles carry no develop layer", !ms.includes("<LDS>") && ms.includes('K="FilmCurve" V="NikonZ5-Linear Response.fcrv"'));
      ok("mono ICC is in the ICC folder", fs.existsSync(T + "/unz/NikonZ5-film-profiles/ICC (Nikon Z5)/NikonZ5-Film KTX400 G.icm")); }
    ok("style has a real uuid", /K="UUID" V="[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}"/.test(sty));
    const n = fs.readdirSync(T + "/unz/NikonZ5-film-profiles/ICC (Nikon Z5)").length, m = fs.readdirSync(T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)").length;
    ok("both folders unzip cleanly", n === 75 && m === 75, n + " icc, " + m + " styles");
    const uuids = new Set(fs.readdirSync(T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)").map(f => /V="([0-9A-F-]{36})"/.exec(fs.readFileSync(T + "/unz/NikonZ5-film-profiles/1 Film (Nikon Z5)/" + f, "utf8").match(/UUID[^/]*/)[0])[1]));
    ok("every style has its own uuid", uuids.size === 75, uuids.size + " unique");
  }
  await page.waitForSelector("#done-banner:not([hidden])", { timeout: 10000 });

  /* --- the profile is remembered across visits --- */
  await page.reload({ waitUntil: "load" });
  await page.waitForSelector("#file-list:not([hidden])", { timeout: 10000 });
  ok("profile restored after reload", (await page.locator("#file-name").textContent()) === "NikonZ5-Nikon_-_Neutral.icm");
  ok("restore is explained", /前回選んだプロファイル/.test(await page.locator("#scan-status").textContent()));
  ok("ready to bake with no picking", await page.locator("#run-button").isEnabled());
  ok("folder list not shown on a restored visit", await page.locator("#search-box").isHidden());

  /* --- 解除 forgets it --- */
  await page.locator("#remove-button").click();
  await page.waitForTimeout(400);
  await page.reload({ waitUntil: "load" });
  await page.waitForTimeout(800);
  ok("解除 clears the remembered profile", await page.locator("#file-list").isHidden());
  ok("run button disabled again", await page.locator("#run-button").isDisabled());

  ok("no page errors", errs.length === 0, errs.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close(); srv.close();
  process.exit(fail ? 1 : 0);
})();

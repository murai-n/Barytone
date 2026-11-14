import pathlib, sys
ROOT = pathlib.Path("/home/claude/bake3"); DADS = pathlib.Path("/home/claude/bake/dads")
COMP = DADS / "html/src"
css_files = ["global.css"] + [f"components/{c}/{c}.css" for c in ("button", "checkbox", "file-upload", "form-control-label", "heading", "input-text", "notification-banner", "select")]
lic = (DADS / "html/LICENSE").read_text()
tok_lic = (DADS / "pkg/package/LICENSE").read_text()
css = "/*! Digital Agency Design System — design tokens and HTML code snippets\n * https://github.com/digital-go-jp/design-tokens\n * https://github.com/digital-go-jp/design-system-example-components-html\n\n" + tok_lic.replace("*/", "") + "\n" + lic.replace("*/", "") + "\n*/\n"
for f in css_files:
    css += f"\n/* {f} */\n" + (COMP / f).read_text()
src = ROOT / "src"
html = (src / "template.html").read_text()
import json
d = json.loads((src / "films.json").read_text())
data = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = html.replace("/*__CSS__*/", css).replace("/*__DATA__*/", data).replace("/*__ENGINE__*/", (src / "engine.js").read_text()).replace("/*__APP__*/", (src / "app.js").read_text())
out = ROOT / "dist/index.html"; out.parent.mkdir(exist_ok=True); out.write_text(html)
print(out, len(html))

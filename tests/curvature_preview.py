"""Save a standalone curvature figure from the local dashboard's actual viewers.

Start dashboard.py on port 2718, then run this script. No app settings or data
files are changed. The output contains both NHP hemispheres, lateral and medial.
"""

import base64
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notes/validation/curvature-only-2026-10-13"


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
            args=["--enable-webgl", "--use-gl=angle", "--use-angle=swiftshader"],
        )
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, device_scale_factor=2
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://localhost:2718")
        expect(page.locator("canvas")).to_have_count(3, timeout=60000)
        expect(page.get_by_text("Select...", exact=True)).to_be_visible()
        page.wait_for_timeout(4000)
        panels = []
        for view in ("Lateral", "Medial"):
            page.locator("select").nth(3).select_option(label=view)
            page.wait_for_timeout(1500)
            for index, side in ((1, "Left"), (2, "Right")):
                data = page.locator("canvas").nth(index).screenshot()
                encoded = base64.b64encode(data).decode("ascii")
                panels.append(
                    f"<section><h2>{side} NHP · {view.lower()}</h2>"
                    f'<img alt="{side} NHP curvature, {view.lower()} view" '
                    f'src="data:image/png;base64,{encoded}"></section>'
                )
        assert not errors, errors
        html = (
            """<!doctype html><html lang="en"><meta charset="utf-8">
<title>NHP curvature only</title><style>
body { margin:0; background:#fff; color:#17263b; font:16px system-ui,sans-serif; }
main { width:1040px; box-sizing:border-box; padding:28px; }
h1 { margin:0 0 8px; font-size:25px; } p { margin:0 0 20px; color:#526277; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
h2 { font-size:17px; margin:0 0 8px; } img { display:block; width:100%; border-radius:8px; }
footer { margin-top:20px; color:#526277; font-size:13px; line-height:1.5; }
</style><main><h1>NHP curvature only</h1>
<p>NMT inflated surfaces · No statistical overlays</p><div class="grid">
"""
            + "".join(panels)
            + """</div><footer>
Source: lh/rh.gray_conv.csv · Current dashboard mapping: full bilateral range,
grayscale brightness 0.45–0.75, no clipping or added spatial smoothing.<br>
Phong lighting retained. These are static captures of the dashboard's NiiVue viewers.
</footer></main></html>"""
        )
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.with_suffix(".html").write_text(html)
        page.set_viewport_size({"width": 1040, "height": 1100})
        page.set_content(html)
        page.locator("img").evaluate_all(
            "images => Promise.all(images.map(image => image.decode()))"
        )
        page.locator("main").screenshot(path=str(OUTPUT.with_suffix(".png")))
        browser.close()
    print(f"Saved {OUTPUT.with_suffix('.png')} and self-contained HTML")


if __name__ == "__main__":
    main()

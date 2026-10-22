"""Local WASM regression for rapid NHP updates and subsequent ROI/reset correctness.

Run after prepare_local_wasm.py and offline export. No external requests allowed.
"""

import json
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from browser_helpers import choose_roi, expect_canvas_images
from playwright.sync_api import expect, sync_playwright
from wasm_local import SITE, LocalHandler

REPORT = Path(".local-wasm/reports/opacity-stress.json")


def main():
    class Handler(LocalHandler):
        isolation_headers = False

    server = ThreadingHTTPServer(
        ("127.0.0.1", 2723), partial(Handler, directory=str(SITE))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {
        "checks": [],
        "bursts_seconds": [],
        "page_errors": [],
        "console_errors": [],
        "blocked": [],
    }
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                headless=True,
                args=[
                    "--enable-webgl",
                    "--use-gl=angle",
                    "--use-angle=swiftshader",
                    "--disable-background-networking",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1366, "height": 900}, service_workers="block"
            )

            def guard(route):
                url = urlparse(route.request.url)
                if (
                    url.scheme == "http"
                    and url.hostname == "127.0.0.1"
                    and url.port == 2723
                    and route.request.method in ("GET", "HEAD")
                ):
                    route.continue_()
                else:
                    report["blocked"].append(route.request.url)
                    route.abort()

            context.route("**/*", guard)
            context.route_web_socket("**/*", lambda ws: ws.close())
            page = context.new_page()
            page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
            page.on(
                "console",
                lambda m: (
                    report["console_errors"].append(m.text)
                    if m.type == "error"
                    else None
                ),
            )
            try:
                page.goto("http://127.0.0.1:2723/dashboard.html")
                expect(page.locator("canvas")).to_have_count(3, timeout=90000)
                page.wait_for_timeout(2500)

                def images():
                    return [page.locator("canvas").nth(i).screenshot() for i in (1, 2)]

                neutral = images()
                choose_roi(page, "Select...", "FST")
                page.wait_for_timeout(2000)
                toggle = page.get_by_text("Apply supplied FDR mask", exact=True)
                toggle.click()
                page.wait_for_timeout(2000)
                baseline = images()
                slider = page.get_by_role("slider").first
                for _ in range(10):
                    slider.press("Home")
                    page.wait_for_timeout(600)
                    started = time.monotonic()
                    for _ in range(5):
                        slider.press("ArrowRight")
                    report["bursts_seconds"].append(
                        round(time.monotonic() - started, 3)
                    )
                    expect(slider).to_have_attribute("aria-valuenow", "0.25")
                    expect_canvas_images(page, baseline, indices=(1, 2))
                report["checks"].append(
                    "Ten rapid 0-to-0.25 bursts restore both exact FDR images"
                )
                slider.scroll_into_view_if_needed()
                for fraction in (1, 0, 1, 0):
                    thumb = slider.bounding_box()
                    track = slider.evaluate("""el => {
                        for (let p=el.parentElement; p; p=p.parentElement) {
                            const b=p.getBoundingClientRect();
                            if (b.width>100 && b.width<800) return {x:b.x,width:b.width};
                        }
                        throw Error('Slider track not found');
                    }""")
                    y = thumb["y"] + thumb["height"] / 2
                    page.mouse.move(thumb["x"] + thumb["width"] / 2, y)
                    page.mouse.down()
                    page.mouse.move(
                        track["x"] + track["width"] + 5 if fraction else track["x"] - 5,
                        y,
                        steps=10,
                    )
                    page.mouse.up()
                    expect(slider).to_have_attribute("aria-valuenow", str(fraction))
                    page.wait_for_timeout(800)
                for _ in range(5):
                    slider.press("ArrowRight")
                expect_canvas_images(page, baseline, indices=(1, 2))
                report["checks"].append(
                    "Four ordinary mouse drags; original opacity restores both images"
                )
                choose_roi(page, "FST", "V1")
                page.wait_for_timeout(2200)
                v1 = images()
                assert all(a != b for a, b in zip(v1, baseline))
                choose_roi(page, "V1", "FST")
                expect_canvas_images(page, baseline, indices=(1, 2))
                for _ in range(3):
                    choose_roi(page, "FST", "V1")
                    choose_roi(page, "V1", "FST")
                for _ in range(6):
                    toggle.click()
                page.locator("select").nth(1).select_option(label="turbo")
                page.locator("select").nth(1).select_option(label="viridis")
                expect_canvas_images(page, baseline, indices=(1, 2))
                choose_roi(page, "FST", "V1")
                expect_canvas_images(page, v1, indices=(1, 2))
                report["checks"].append(
                    "ROI/FDR/palette bursts preserve correct FST and V1 images afterward"
                )
                page.get_by_role("button", name="Reset selection", exact=True).click()
                expect_canvas_images(page, neutral, indices=(1, 2))
                page.wait_for_timeout(11000)
                assert not report["page_errors"], report["page_errors"]
                assert not report["console_errors"], report["console_errors"]
                assert not report["blocked"], report["blocked"]
                report["checks"].append(
                    "Reset clears both maps; no delayed errors or external requests"
                )
                report["result"] = "pass"
            except Exception as exc:
                report["result"] = "fail"
                report["error"] = str(exc)
                REPORT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(REPORT.with_suffix(".png")), full_page=True)
                raise
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()

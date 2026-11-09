"""Check the actual online WASM export with static-only serving (no Python backend).

Run after a normal marimo html-wasm export. Chrome needs network access for
Pyodide/packages. Reports and screenshots go under ignored notes/ by default.
"""

import argparse
import json
import threading
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from browser_helpers import choose_roi, expect_canvas_images
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--prefix", default="")
    parser.add_argument(
        "--report-dir", type=Path, default=ROOT / "notes/bh-wasm-validation"
    )
    args = parser.parse_args()
    prefix = "/" + args.prefix.strip("/") if args.prefix.strip("/") else ""
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    name = "subpath" if prefix else "root"
    report = {
        "checks": [],
        "requests": [],
        "page_errors": [],
        "console_errors": [],
        "http_errors": [],
    }

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            if prefix and path.startswith(prefix + "/"):
                path = path[len(prefix) :]
            return super().translate_path(path)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(args.site.resolve()))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    report["url"] = origin + prefix + "/"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                headless=True,
                args=["--enable-webgl", "--use-gl=angle", "--use-angle=swiftshader"],
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1100}, service_workers="block"
            )
            page.on(
                "request",
                lambda r: report["requests"].append({"url": r.url, "method": r.method}),
            )
            page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
            page.on(
                "console",
                lambda m: (
                    report["console_errors"].append(m.text)
                    if m.type == "error"
                    else None
                ),
            )
            page.on(
                "response",
                lambda r: (
                    report["http_errors"].append({"url": r.url, "status": r.status})
                    if r.status >= 400
                    else None
                ),
            )

            def assets():
                return [
                    r["url"]
                    for r in report["requests"]
                    if "/public/data/stat_maps/" in r["url"]
                ]

            def images():
                return [page.locator("canvas").nth(i).screenshot() for i in (1, 2)]

            def pick(current, target, hemisphere="L"):
                choose_roi(page, current, target)
                expect(
                    page.get_by_text(f"{hemisphere}_{target}", exact=True)
                ).to_be_visible(timeout=30000)
                page.wait_for_timeout(1800)

            try:
                page.goto(report["url"])
                expect(page.locator("canvas")).to_have_count(3, timeout=120000)
                page.wait_for_timeout(2000)
                assert not assets()
                assert (
                    page.get_by_text("Apply supplied FDR mask", exact=True).count() == 0
                )
                filter_control = page.get_by_label(
                    "Only ROIs with BH results", exact=True
                )
                expect(filter_control).not_to_be_checked()
                toggle = page.get_by_text("Apply supplied BH mask", exact=True)
                report["checks"].append(
                    "Three WASM canvases, BH controls, no statistic downloads at startup"
                )
                print(name, report["checks"][-1], flush=True)
                neutral = images()
                pick("Select...", "FST")
                original = images()
                assert all(a != b for a, b in zip(original, neutral))
                expect(
                    page.get_by_text("0.0025 to 0.1010", exact=False)
                ).to_be_visible()
                assert len(assets()) == 4
                toggle.click()
                expect(
                    page.get_by_text(
                        "43,029 finite vertices pass the supplied BH mask.", exact=True
                    )
                ).to_be_visible()
                page.wait_for_timeout(1800)
                masked = images()
                assert all(a != b for a, b in zip(masked, original))
                slider = page.get_by_role("slider").first
                for _ in range(3):
                    slider.press("Home")
                    page.wait_for_timeout(800)
                    assert all(a != b for a, b in zip(images(), masked))
                    for _ in range(5):
                        slider.press("ArrowRight")
                    expect_canvas_images(page, masked, indices=(1, 2), timeout_ms=15000)
                toggle.click()
                expect_canvas_images(page, original, indices=(1, 2), timeout_ms=15000)
                expect(
                    page.get_by_text("0.0025 to 0.1010", exact=False)
                ).to_be_visible()
                assert len(assets()) == 4
                report["checks"].append(
                    "43,029 BH passes, reversible masking, repeated opacity bursts, unchanged limits, cached assets"
                )
                page.locator("select").nth(0).select_option(label="Across all ROIs")
                expect(
                    page.get_by_text("0.0000 to 0.1647", exact=False)
                ).to_be_visible()
                page.wait_for_timeout(1500)
                global_images = images()
                assert all(a != b for a, b in zip(global_images, original))
                page.locator("select").nth(1).select_option(label="turbo")
                page.wait_for_timeout(1500)
                assert all(a != b for a, b in zip(images(), global_images))
                report["checks"].append(
                    "Shared global range and palette update both NHP panels"
                )
                empty = page.get_by_text(
                    "No vertices pass the supplied BH mask.", exact=True
                )
                pick("FST", "46")
                expect(empty).to_have_count(2)
                filter_control.check()
                expect(
                    page.get_by_text("46 has no BH results", exact=False)
                ).to_be_visible()
                filter_control.uncheck()
                expect(page.get_by_text("L_46", exact=True)).to_be_visible()
                pick("46", "55b")
                expect(empty).to_have_count(1)
                filter_control.check()
                expect(page.get_by_text("L_55b", exact=True)).to_be_visible()
                toggle.click()
                expect(
                    page.get_by_text("3,162 finite vertices pass", exact=False)
                ).to_be_visible()
                page.get_by_label("Right", exact=True).check()
                expect(
                    page.get_by_text("55b has no BH results", exact=False)
                ).to_be_visible()
                filter_control.uncheck()
                expect(page.get_by_text("R_55b", exact=True)).to_be_visible(
                    timeout=30000
                )
                expect(empty).to_have_count(2)
                expect(
                    page.get_by_text("Outside-mask opacity", exact=True)
                ).to_be_visible()
                page.get_by_label("Left", exact=True).check()
                expect(page.get_by_text("L_55b", exact=True)).to_be_visible()
                report["checks"].append(
                    "BH-only L_55b selectable; empty masks; filter/restoration and hemisphere changes"
                )
                filter_control.check()
                before_reset = len(assets())
                page.get_by_role("button", name="Reset selection", exact=True).click()
                expect(page.get_by_text("Select...", exact=True)).to_be_visible()
                expect(filter_control).to_be_checked()
                expect(
                    page.get_by_text("Outside-mask opacity", exact=True)
                ).to_be_visible()
                pick("Select...", "FST")
                assert len(assets()) == before_reset
                expected = json.loads(
                    (args.site / "public/data/catalog.json").read_text()
                )["rois"]
                expected_urls = {
                    origin + prefix + "/public/" + info["path"]
                    for key in ("L_FST", "L_46", "L_55b", "R_55b")
                    for variant in ("unthresholded", "bh")
                    for info in expected[key]["assets"][variant].values()
                }
                assert set(assets()) == expected_urls
                assert all(count == 1 for count in Counter(assets()).values())
                assert all(r["method"] in ("GET", "HEAD") for r in report["requests"])
                local_paths = [
                    urlparse(r["url"]).path
                    for r in report["requests"]
                    if r["url"].startswith(origin)
                ]
                assert all(path.startswith(prefix + "/") for path in local_paths)
                assert not any(
                    path.endswith(".csv") or "/api/kernel/" in path
                    for path in local_paths
                )
                assert not report["page_errors"], report["page_errors"]
                assert not report["console_errors"], report["console_errors"]
                assert not report["http_errors"], report["http_errors"]
                report["checks"].append(
                    "Exactly four BH/unthresholded downloads per visited ROI, reused on reset/reselection; correct URL prefix; no CSV/backend/error traffic"
                )
                report["result"] = "pass"
                print(name, "PASS", report["checks"], flush=True)
            except Exception as exc:
                report["result"] = "fail"
                report["error"] = str(exc)
                report["body"] = page.locator("body").inner_text()[-15000:]
                print(report["body"], flush=True)
                raise
            finally:
                page.screenshot(path=str(report_dir / f"{name}.png"), full_page=True)
                (report_dir / f"{name}.json").write_text(
                    json.dumps(report, indent=2) + "\n"
                )
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()

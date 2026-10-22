"""Run the offline export with loopback-only serving and browser networking.

All generated files/reports live under .local-wasm/ (Git-ignored).
Run: .venv/bin/python tests/wasm_local.py
Preview separately: .venv/bin/python tests/wasm_local.py --serve
"""

import argparse
import json
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from browser_helpers import check_camera_resets, choose_roi, expect_canvas_images
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / ".local-wasm/site"
REPORTS = ROOT / ".local-wasm/reports"
ORIGIN = "http://127.0.0.1:2720"


class LocalHandler(SimpleHTTPRequestHandler):
    isolation_headers = True

    def end_headers(self):
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self' blob: data:; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: data:; style-src 'self' 'unsafe-inline'; connect-src 'self' blob: data:; img-src 'self' blob: data:; font-src 'self' data:; worker-src 'self' blob:; frame-src 'self' blob: data:; object-src 'none'",
        )
        if self.isolation_headers:
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument(
        "--paced-controls",
        action="store_true",
        help="Diagnostic only: pause between opacity keypresses to investigate update races",
    )
    parser.add_argument(
        "--without-isolation",
        action="store_true",
        help="Test without COOP/COEP headers, as on a basic static host",
    )
    args = parser.parse_args()
    LocalHandler.isolation_headers = not args.without_isolation
    server = ThreadingHTTPServer(
        ("127.0.0.1", 2720), partial(LocalHandler, directory=str(SITE))
    )
    if args.serve:
        print(f"Local WASM preview: {ORIGIN}/dashboard.html", flush=True)
        server.serve_forever()
        return
    REPORTS.mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {
        "mode": "offline WASM; static HTTP only",
        "isolation_headers": LocalHandler.isolation_headers,
        "paced_controls": args.paced_controls,
        "checks": [],
        "requests": [],
        "blocked": [],
        "console": [],
        "page_errors": [],
    }
    start = time.monotonic()
    p = sync_playwright().start()
    try:
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
            req = route.request
            parsed = urlparse(req.url)
            local = (
                parsed.scheme == "http"
                and parsed.hostname == "127.0.0.1"
                and parsed.port == 2720
            )
            record = {"method": req.method, "url": req.url}
            if not local or req.method not in ("GET", "HEAD"):
                report["blocked"].append(record)
                route.abort()
            else:
                report["requests"].append(record)
                route.continue_()

        context.route("**/*", guard)
        context.route_web_socket("**/*", lambda ws: ws.close())
        page = context.new_page()

        def on_console(msg):
            report["console"].append({"type": msg.type, "text": msg.text})
            if msg.type == "error" or "STDERR" in msg.text:
                print(msg.text[:1800], flush=True)

        page.on("console", on_console)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        page.goto(ORIGIN + "/index.html")
        expect(page.get_by_text("Imports ready:", exact=False)).to_be_visible(
            timeout=90000
        )
        report["checks"].append("Offline ipyniivue/nibabel/numpy imports")
        report["versions"] = page.get_by_text(
            "Imports ready:", exact=False
        ).inner_text()
        report["browser"] = browser.version
        print("Offline package imports passed", flush=True)
        boot = time.monotonic()
        page.goto(ORIGIN + "/dashboard.html")
        expect(page.locator("canvas")).to_have_count(3, timeout=90000)
        page.wait_for_timeout(2500)
        report["startup_seconds"] = round(time.monotonic() - boot, 2)
        report["checks"].append("Three dashboard canvases in WASM")
        print("Three WASM canvases ready", flush=True)

        def select(current, name):
            t = time.monotonic()
            choose_roi(page, current, name)
            expect(page.get_by_text("L_" + name, exact=True)).to_be_visible(
                timeout=30000
            )
            page.wait_for_timeout(1800)
            report.setdefault("selection_seconds_including_settle", {})[name] = round(
                time.monotonic() - t, 2
            )

        def surfaces():
            return [page.locator("canvas").nth(i).screenshot() for i in (1, 2)]

        neutral = surfaces()
        select("Select...", "FST")
        original = surfaces()
        assert all(a != b for a, b in zip(original, neutral))
        expect(page.get_by_text("0.0025 to 0.1010", exact=False)).to_be_visible()
        report["checks"].append(
            "L_FST files loaded; bilateral overlays and local range"
        )
        toggle = page.get_by_text("Apply supplied FDR mask", exact=True)
        toggle.click()
        expect(
            page.get_by_text("22,253 finite vertices pass", exact=False)
        ).to_be_visible(timeout=15000)
        page.wait_for_timeout(1800)
        masked = surfaces()
        assert all(a != b for a, b in zip(masked, original))
        page.screenshot(path=str(REPORTS / "wasm-fst-outline.png"), full_page=True)
        slider = page.get_by_role("slider").first
        slider.press("Home")
        page.wait_for_timeout(1800)
        assert all(a != b for a, b in zip(surfaces(), masked))
        for _ in range(5):
            slider.press("ArrowRight")
            if args.paced_controls:
                page.wait_for_timeout(1800)
        page.wait_for_timeout(1800)
        expect_canvas_images(page, masked, indices=(1, 2))
        report["checks"].append("FDR border/context and opacity 0/0.25")
        toggle.click()
        page.wait_for_timeout(1800)
        assert surfaces() == original
        page.locator("select").nth(0).select_option(label="Across all ROIs")
        page.wait_for_timeout(1800)
        assert surfaces() != original
        expect(page.get_by_text("0.0000 to 0.1647", exact=False)).to_be_visible()
        global_view = surfaces()
        page.locator("select").nth(1).select_option(label="turbo")
        page.wait_for_timeout(1800)
        turbo = surfaces()
        assert all(a != b for a, b in zip(global_view, turbo))
        page.locator("select").nth(3).select_option(label="Medial")
        page.wait_for_timeout(1800)
        medial = surfaces()
        assert all(a != b for a, b in zip(turbo, medial))
        report["checks"].append("Shared range/palette and medial cameras")
        human = page.locator("canvas").nth(0).screenshot()

        def change_roi_while_zoomed():
            select("FST", "V1")
            select("V1", "FST")

        check_camera_resets(page, change_roi_while_zoomed)
        report["checks"].append(
            "Human/both NHP rotation and zoom reset; ROI changes preserve cameras"
        )
        toggle.click()
        select("FST", "46")
        expect(
            page.get_by_text("No vertices pass the supplied FDR mask.", exact=True)
        ).to_have_count(2)
        select("46", "FEF")
        expect(
            page.get_by_text("No vertices pass the supplied FDR mask.", exact=True)
        ).to_have_count(1)
        report["checks"].append("Empty masks on both sides and one side")
        page.screenshot(path=str(REPORTS / "wasm-dashboard.png"), full_page=True)
        page.get_by_label("Right", exact=True).check()
        expect(page.get_by_text("R_FEF", exact=True)).to_be_visible(timeout=30000)
        page.wait_for_timeout(1800)
        assert page.locator("canvas").nth(0).screenshot() != human
        expect(page.locator("select").nth(0).locator("option:checked")).to_have_text(
            "Across all ROIs"
        )
        expect(page.get_by_role("slider").first).to_have_attribute(
            "aria-valuenow", "0.25"
        )
        expect(page.get_by_text("Outside-mask opacity", exact=True)).to_be_visible()
        report["checks"].append(
            "Human hemisphere switch; range/FDR/context settings retained"
        )
        page.get_by_role("button", name="Reset selection", exact=True).click()
        expect(page.get_by_text("Select...", exact=True)).to_be_visible()
        report["checks"].append("Reset selection")
        assert not report["page_errors"]
        assert not report["blocked"]
        assert not any(item["type"] == "error" for item in report["console"])
        assert not any(item["url"].endswith(".csv") for item in report["requests"])
        report["checks"].append(
            "Only localhost GET/HEAD traffic; no CSV loads or browser errors"
        )
        report["result"] = "pass"
        browser.close()
    except Exception as exc:
        report["result"] = "fail"
        report["error"] = str(exc)
        try:
            report["body"] = page.locator("body").inner_text(timeout=2000)
            page.screenshot(
                path=str(REPORTS / "wasm-failure.png"), full_page=True, timeout=5000
            )
        except PlaywrightError as capture_error:
            report["capture_error"] = str(capture_error)
        raise
    finally:
        p.stop()
        report["elapsed_seconds"] = round(time.monotonic() - start, 2)
        report_name = "result-no-isolation" if args.without_isolation else "result"
        if args.paced_controls:
            report_name += "-paced"
        report_path = REPORTS / f"{report_name}.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        server.shutdown()
        server.server_close()
        print(f"Local report: {report_path}", flush=True)


if __name__ == "__main__":
    main()

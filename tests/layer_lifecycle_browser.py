"""Exercise the real adapter with synthetic data and an intentional parse error."""

import json
from pathlib import Path

from browser_helpers import expect_canvas_images
from playwright.sync_api import expect, sync_playwright

REPORT = Path(".local-wasm/reports/layer-lifecycle.json")


def main():
    report = {"checks": [], "page_errors": [], "console_errors": []}
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
        page = browser.new_page()
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith("http://127.0.0.1:2722/")
                else route.abort()
            ),
        )
        page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
        page.on(
            "console",
            lambda m: (
                report["console_errors"].append(m.text) if m.type == "error" else None
            ),
        )
        try:
            page.goto("http://127.0.0.1:2722")
            expect(page.locator("canvas")).to_have_count(1, timeout=60000)
            page.wait_for_timeout(2000)
            neutral = page.locator("canvas").screenshot()
            page.get_by_role("button", name="Publish 30 maps", exact=True).click()
            page.wait_for_timeout(2500)
            original = page.locator("canvas").screenshot()
            assert original != neutral
            page.get_by_role(
                "button", name="Inspect retained widgets", exact=True
            ).click()
            expect(
                page.get_by_text(
                    'Retained: {"publications": 1, "open_widgets": 1}', exact=True
                )
            ).to_be_visible()
            report["checks"].append(
                "30 replacements coalesce; only active widget retained after acknowledgement"
            )
            page.get_by_role("button", name="Publish invalid layer", exact=True).click()
            expect(
                page.get_by_role("alert").filter(has_text="Map could not be displayed")
            ).to_be_visible(timeout=15000)
            page.get_by_role("button", name="Publish 30 maps", exact=True).click()
            expect(
                page.get_by_role("alert").filter(has_text="Map could not be displayed")
            ).to_have_count(0, timeout=15000)
            expect_canvas_images(page, [original], indices=(0,))
            page.get_by_role(
                "button", name="Inspect retained widgets", exact=True
            ).click()
            expect(
                page.get_by_text(
                    'Retained: {"publications": 1, "open_widgets": 1}', exact=True
                )
            ).to_be_visible()
            report["checks"].append(
                "Partial decode failure shows error; next replacement restores exact image and retires failed widgets"
            )
            page.wait_for_timeout(11000)
            assert not report["page_errors"], report["page_errors"]
            assert any("NHP layer update failed" in e for e in report["console_errors"])
            assert not any("Model not found" in e for e in report["console_errors"])
            report["result"] = "pass"
        except Exception as exc:
            report["result"] = "fail"
            report["error"] = str(exc)
            report["body"] = page.locator("body").inner_text()
            raise
        finally:
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report), flush=True)
            browser.close()


if __name__ == "__main__":
    main()

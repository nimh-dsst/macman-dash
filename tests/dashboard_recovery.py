"""Local full-dashboard recovery test; no production hooks or data changes.

Stages the actual dashboard with two test-only buttons publishing an invalid
layer, then checks error bounds and normal recovery controls in both NHP views.
Run: .venv/bin/python tests/dashboard_recovery.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from browser_helpers import choose_roi, expect_canvas_images
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local-wasm/dashboard-recovery"
URL = "http://127.0.0.1:2724"
FAULT_CELLS = """
@app.cell
def _(mo):
    fail_left = mo.ui.run_button(label="Inject left layer failure")
    fail_right = mo.ui.run_button(label="Inject right layer failure")
    mo.hstack([fail_left, fail_right])
    return fail_left, fail_right


@app.cell
def _(fail_left, fail_right, result_meshes):
    from macman.viewer import layer_bytes

    for _side, _button in (("lh", fail_left), ("rh", fail_right)):
        if _button.value:
            result_meshes[_side].publish_layers(
                [layer_bytes(b"invalid", "invalid.gii")]
            )


"""


def check_dashboard(page, report):
    page.goto(URL)
    expect(page.locator("canvas")).to_have_count(3, timeout=60000)
    page.wait_for_timeout(2500)
    alert = page.get_by_role("alert").filter(has_text="Map could not be displayed")

    def snapshots():
        return [page.locator("canvas").nth(i).screenshot() for i in range(3)]

    current = "Select..."
    for width, height in ((1366, 768), (1280, 800)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(500)
        neutral = snapshots()
        choose_roi(page, current, "V1")
        page.wait_for_timeout(2500)
        v1 = snapshots()
        choose_roi(page, "V1", "FST")
        page.wait_for_timeout(2500)
        fst = snapshots()
        assert all(v1[i] != fst[i] != neutral[i] for i in (1, 2))
        current = "FST"
        for index, side in ((1, "left"), (2, "right")):
            for recovery in ("select", "reset"):
                page.get_by_role(
                    "button", name=f"Inject {side} layer failure", exact=True
                ).click()
                expect(alert).to_have_count(1, timeout=15000)
                page.get_by_role(
                    "button", name="Reset selection", exact=True
                ).scroll_into_view_if_needed()
                expect(alert).to_be_visible()
                bounds = alert.bounding_box()
                canvas = page.locator("canvas").nth(index).bounding_box()
                assert bounds and canvas
                for axis, size in (("x", "width"), ("y", "height")):
                    assert bounds[axis] >= canvas[axis] - 1, (bounds, canvas)
                    assert (
                        bounds[axis] + bounds[size] <= canvas[axis] + canvas[size] + 1
                    ), (bounds, canvas)
                unaffected = tuple(i for i in range(3) if i != index)
                expect_canvas_images(
                    page, [fst[i] for i in unaffected], indices=unaffected
                )
                if recovery == "select":
                    choose_roi(page, current, "V1")
                    expect(alert).to_have_count(0, timeout=15000)
                    expect_canvas_images(page, v1)
                    current = "V1"
                else:
                    page.get_by_role(
                        "button", name="Reset selection", exact=True
                    ).click()
                    expect(alert).to_have_count(0, timeout=15000)
                    expect_canvas_images(page, neutral)
                    current = "Select..."
                choose_roi(page, current, "FST")
                expect_canvas_images(page, fst)
                current = "FST"
                report["checks"].append(
                    f"{width}x{height}: {side} alert confined; {recovery} recovers exact images"
                )
        page.get_by_role("button", name="Reset selection", exact=True).click()
        expect_canvas_images(page, neutral)
        current = "Select..."
    page.wait_for_timeout(11000)
    assert not report["page_errors"], report["page_errors"]
    assert len(report["console_errors"]) == 8, report["console_errors"]
    assert all("NHP layer update failed" in e for e in report["console_errors"])
    assert not report["blocked_requests"], report["blocked_requests"]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "dashboard.py").read_text()
    marker = 'if __name__ == "__main__":'
    assert source.count(marker) == 1
    notebook = WORK / "dashboard.py"
    notebook.write_text(source.replace(marker, FAULT_CELLS + marker))
    report = {
        "checks": [],
        "page_errors": [],
        "console_errors": [],
        "blocked_requests": [],
    }
    with (WORK / "server.log").open("w") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "marimo",
                "run",
                str(notebook),
                "--host",
                "127.0.0.1",
                "--port",
                "2724",
                "--headless",
                "--no-token",
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                assert server.poll() is None, "Server exited; inspect server.log"
                try:
                    with urlopen(URL, timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Local dashboard server did not start")
                    time.sleep(0.2)
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
                page = browser.new_page(viewport={"width": 1366, "height": 768})

                def guard(route):
                    if route.request.url.startswith(URL + "/"):
                        route.continue_()
                    else:
                        report["blocked_requests"].append(route.request.url)
                        route.abort()

                page.route("**/*", guard)
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
                    check_dashboard(page, report)
                    report["result"] = "pass"
                except Exception:
                    page.screenshot(path=str(WORK / "failure.png"), full_page=True)
                    raise
                finally:
                    browser.close()
        except Exception as exc:
            report["result"] = "fail"
            report["error"] = str(exc)
            raise
        finally:
            server.terminate()
            server.wait(timeout=10)
            (WORK / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()

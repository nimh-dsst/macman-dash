"""Manual integration check: start marimo on port 2718 first."""

import sys
from itertools import pairwise
from pathlib import Path

from browser_helpers import (
    check_camera_resets,
    choose_roi,
    expect_canvas_images,
    roi_pattern,
)
from playwright.sync_api import expect, sync_playwright

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
            args=["--enable-webgl", "--use-gl=angle", "--use-angle=swiftshader"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        console_errors = []
        page.on("pageerror", lambda error: errors.append(error.stack))
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text)
                if message.type in ("error", "warning")
                else None
            ),
        )
        page.goto("http://localhost:2718")
        try:
            page.wait_for_selector("canvas", timeout=60000)
        except Exception:
            print(page.locator("body").inner_text()[-9000:], flush=True)
            print("ERRORS:", errors, console_errors, flush=True)
            raise
        if "--reload-only" not in sys.argv:
            page.wait_for_timeout(5000)

        if "--camera-only" in sys.argv:
            choose_roi(page, "Select...", "FST")
            expect(page.get_by_text("L_FST", exact=True)).to_be_visible()
            page.wait_for_timeout(2500)
            page.locator("select").nth(3).select_option(label="Medial")
            page.wait_for_timeout(1500)

            def change_roi_while_zoomed():
                choose_roi(page, "FST", "V1")
                page.wait_for_timeout(2500)
                choose_roi(page, "V1", "FST")
                page.wait_for_timeout(2500)

            check_camera_resets(page, change_roi_while_zoomed)
            assert not errors, errors
            print(
                "Camera checks passed: human/both NHP zoom and rotation reset; ROI changes preserve cameras."
            )
            browser.close()
            raise SystemExit(0)
        if "--fdr-discovery-only" in sys.argv:
            page.set_viewport_size({"width": 1366, "height": 768})
            filter_control = page.get_by_label("Only ROIs with FDR results", exact=True)
            expect(filter_control).not_to_be_checked()
            toggle = page.get_by_text("Apply supplied FDR mask", exact=True)
            empty_status = page.get_by_text(
                "No vertices pass the supplied FDR mask.", exact=True
            )

            def pick(current, target):
                page.get_by_text(roi_pattern(current)).click()
                page.get_by_placeholder("Search...").fill(target)
                page.get_by_role("option", name=roi_pattern(target)).click()
                expect(page.get_by_text(f"L_{target}", exact=True)).to_be_visible()
                page.wait_for_timeout(1000)

            pick("Select...", "46")
            expect(page.get_by_text("Map opacity", exact=True)).to_be_visible()
            expect(empty_status).to_have_count(2)
            for message in empty_status.all():
                box = message.bounding_box()
                assert box["y"] + box["height"] <= 768, box
            filter_control.check()
            expect(page.get_by_text("Select...", exact=True)).to_be_visible()
            expect(
                page.get_by_text("46 has no FDR results", exact=False)
            ).to_be_visible()
            page.get_by_text("Select...", exact=True).click()
            page.get_by_placeholder("Search...").fill("46")
            expect(page.get_by_role("option", name=roi_pattern("46"))).to_have_count(0)
            page.keyboard.press("Escape")
            filter_control.uncheck()
            expect(page.get_by_text("L_46", exact=True)).to_be_visible()
            pick("46", "FEF")
            expect(page.get_by_text("FEF", exact=True)).to_be_visible()
            expect(empty_status).to_have_count(1)
            filter_control.check()
            expect(page.get_by_text("L_FEF", exact=True)).to_be_visible()
            toggle.click()
            expect(page.get_by_text("Outside-mask opacity", exact=True)).to_be_visible()
            page.get_by_role("slider").first.press("Home")
            pick("FEF", "FST")
            expect(empty_status).to_have_count(0)
            expect(page.get_by_role("slider").first).to_have_attribute(
                "aria-valuenow", "0"
            )
            expect(page.get_by_text("Outside-mask opacity", exact=True)).to_be_visible()
            pick("FST", "PGs")
            page.get_by_label("Right", exact=True).check()
            expect(
                page.get_by_text("PGs has no FDR results", exact=False)
            ).to_be_visible()
            expect(page.get_by_text("Select...", exact=True)).to_be_visible()
            filter_control.uncheck()
            expect(page.get_by_text("R_PGs", exact=True)).to_be_visible()
            expect(empty_status).to_have_count(2)
            expect(page.get_by_text("Outside-mask opacity", exact=True)).to_be_visible()
            expect(page.get_by_role("slider").first).to_have_attribute(
                "aria-valuenow", "0"
            )
            filter_control.check()
            page.get_by_text("Select...", exact=True).click()
            page.get_by_placeholder("Search...").fill("ProS")
            page.get_by_role("option", name="ProS", exact=True).click()
            expect(page.get_by_text("R_ProS", exact=True)).to_be_visible()
            expect(empty_status).to_have_count(1)
            page.get_by_role("button", name="Reset selection", exact=True).click()
            expect(page.get_by_text("Select...", exact=True)).to_be_visible()
            expect(filter_control).to_be_checked()
            expect(toggle).to_be_visible()
            expect(page.get_by_text("Outside-mask opacity", exact=True)).to_be_visible()
            expect(empty_status).to_have_count(0)
            expect(page.locator("canvas")).to_have_count(3)
            assert not errors, errors
            print(
                "FDR discovery passed: labels, either-side filter, pre-toggle empty status, filtered selection restoration, hemisphere changes, persistent FDR/opacity, and reset."
            )
            browser.close()
            raise SystemExit(0)
        if "--coverage-only" in sys.argv:
            for hemisphere, key in (("Left", "L_FEF"), ("Right", "R_FEF")):
                page.get_by_label(hemisphere, exact=True).check()
                page.wait_for_timeout(1500)
                current = "Select..." if hemisphere == "Left" else "FEF"
                page.get_by_text(roi_pattern(current)).click()
                for excluded in ("FEF (bilateral)", "V3_dsToCharm4", "V3"):
                    page.get_by_placeholder("Search...").fill(excluded)
                    assert (
                        page.get_by_role("option", name=roi_pattern(excluded)).count()
                        == 0
                    )
                page.get_by_placeholder("Search...").fill("FEF")
                page.get_by_role("option", name=roi_pattern("FEF")).click()
                expect(page.get_by_text(key, exact=True)).to_be_visible()
                page.wait_for_timeout(1500)
            expect(page.locator("canvas")).to_have_count(3)
            assert not errors, errors
            print(
                "Excluded B_FEF/dsToCharm4 and incomplete V3 absent on both sides; L/R FEF load; three canvases, no page errors."
            )
            browser.close()
            raise SystemExit(0)
        if "--layout-only" in sys.argv:
            for width, height in [(1366, 768), (1280, 800), (1440, 900)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(1500)
                boxes = [page.locator("canvas").nth(i).bounding_box() for i in range(3)]
                print(width, height, boxes, flush=True)
                page.screenshot(path=f"/tmp/macman-layout-{width}.png")
                for box in boxes:
                    assert box["width"] >= 260, boxes
                    assert box["y"] >= 0 and box["y"] + box["height"] <= height, boxes
                    assert box["x"] >= 0 and box["x"] + box["width"] <= width, boxes
                assert max(b["y"] for b in boxes) - min(b["y"] for b in boxes) < 3, (
                    boxes
                )
                for left, right in pairwise(boxes):
                    assert left["x"] + left["width"] <= right["x"] + 1, boxes
            page.get_by_text("Select...", exact=True).click()
            page.get_by_placeholder("Search...").fill("FST")
            page.get_by_text(roi_pattern("FST")).click()
            page.locator("select").nth(3).select_option(label="Medial")
            page.wait_for_timeout(2500)
            page.set_viewport_size({"width": 1366, "height": 768})
            page.wait_for_timeout(1000)
            page.screenshot(path="/tmp/macman-layout-selected.png")
            assert not errors, errors
            print("All three surfaces fit without scrolling at laptop sizes.")
            browser.close()
            raise SystemExit(0)
        if "--split-only" in sys.argv:
            expect(page.locator("canvas")).to_have_count(3)
            expect(
                page.get_by_text("Left NHP hemisphere · NMT", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text("Right NHP hemisphere · NMT", exact=True)
            ).to_be_visible()
            camera = page.locator("select").nth(3)
            assert camera.input_value() == "Lateral"

            def snapshots():
                return [page.locator("canvas").nth(i).screenshot() for i in range(3)]

            lateral = snapshots()
            camera.select_option(label="Medial")
            page.wait_for_timeout(1500)
            medial = snapshots()
            assert medial[0] == lateral[0]
            assert all(medial[i] != lateral[i] for i in (1, 2))
            camera.select_option(label="Lateral")
            page.wait_for_timeout(1500)
            assert snapshots() == lateral
            camera.select_option(label="Medial")
            page.wait_for_timeout(1500)
            current = "Select..."

            def select_roi(label):
                global current
                choose_roi(page, current, label)
                current = label
                page.wait_for_timeout(2500)

            select_roi("FST")
            original = snapshots()
            assert all(original[i] != medial[i] for i in (1, 2))
            expect(page.get_by_text("0.0025 to 0.1010", exact=False)).to_be_visible()
            toggle = page.get_by_text("Apply supplied FDR mask", exact=True)
            toggle.click()
            page.wait_for_timeout(1500)
            masked = snapshots()
            assert masked[0] == original[0]
            assert all(masked[i] != original[i] for i in (1, 2))
            expect(
                page.get_by_text("22,253 finite vertices pass", exact=False)
            ).to_be_visible()
            expect(page.get_by_text("0.0025 to 0.1010", exact=False)).to_be_visible()
            expect(page.get_by_text("Outside-mask opacity", exact=True)).to_be_visible()
            page.screenshot(path="/tmp/macman-native-outline.png", full_page=True)
            slider = page.get_by_role("slider").first
            slider.press("Home")
            page.wait_for_timeout(1200)
            zero_context = snapshots()
            assert all(zero_context[i] != masked[i] for i in (1, 2))
            for _ in range(5):
                slider.press("ArrowRight")
            page.wait_for_timeout(1200)
            expect_canvas_images(page, masked)

            toggle.click()
            page.wait_for_timeout(1500)
            assert snapshots() == original
            page.locator("select").nth(0).select_option(label="Across all ROIs")
            page.wait_for_timeout(1500)
            global_maps = snapshots()
            assert all(global_maps[i] != original[i] for i in (1, 2))
            select_roi("V1")
            expect(page.get_by_text("0.0000 to 0.1647", exact=False)).to_be_visible()
            select_roi("FST")
            assert snapshots() == global_maps
            page.locator("select").nth(1).select_option(label="turbo")
            page.wait_for_timeout(1500)
            turbo = snapshots()
            assert all(turbo[i] != global_maps[i] for i in (1, 2))

            def change_roi_while_zoomed():
                select_roi("V1")
                select_roi("FST")

            check_camera_resets(page, change_roi_while_zoomed)
            toggle.click()
            select_roi("46")
            empty = snapshots()
            assert all(empty[i] != medial[i] for i in (1, 2))
            expect(
                page.get_by_text("No vertices pass the supplied FDR mask.", exact=True)
            ).to_have_count(2)
            page.get_by_role("button", name="Reset selection", exact=True).click()
            page.wait_for_timeout(1500)
            assert snapshots() == medial
            assert camera.input_value() == "Medial"
            assert not errors, errors
            assert not [m for m in console_errors if "colormap" in m.lower()], (
                console_errors
            )
            print(
                "Split views passed: both overlays, medial/lateral presets, independent rotation/zoom, human/NHP camera reset, shared ranges/palette/FDR, ROI changes and selection reset."
            )
            browser.close()
            raise SystemExit(0)
        if "--fst-only" in sys.argv:
            page.get_by_text("Select...", exact=True).click()
            page.get_by_placeholder("Search...").fill("FST")
            page.get_by_text(roi_pattern("FST")).click()
            page.wait_for_timeout(4000)
            expect(page.get_by_text("L_FST", exact=True)).to_be_visible()
            expect(page.get_by_text("0.0025 to 0.1010", exact=False)).to_be_visible()
            original = page.locator("canvas").nth(1).screenshot()
            page.get_by_text("Apply supplied FDR mask", exact=True).click()
            page.wait_for_timeout(2000)
            expect(
                page.get_by_text(
                    "22,253 finite vertices pass the supplied FDR mask.", exact=True
                )
            ).to_be_visible()
            expect(page.get_by_text("0.0025 to 0.1010", exact=False)).to_be_visible()
            assert page.locator("canvas").nth(1).screenshot() != original
            page.screenshot(path="/tmp/macman-fst-validation.png", full_page=True)
            page.get_by_text("Apply supplied FDR mask", exact=True).click()
            page.wait_for_timeout(2000)
            assert page.locator("canvas").nth(1).screenshot() == original
            assert not errors, errors
            print(
                "L_FST browser validation passed: 22,253 retained vertices, unchanged limits, reversible masking."
            )
            browser.close()
            raise SystemExit(0)
        assert page.locator("select").nth(2).input_value() == "Lateral"
        assert page.get_by_text("NHP lighting", exact=True).count() == 0
        expect(
            page.get_by_text("Left hemisphere · HCP-MMP1", exact=True)
        ).to_be_visible()
        atlas_before = page.locator("canvas").first.screenshot()
        neutral = page.locator("canvas").nth(1).screenshot()
        page.get_by_text("Select...", exact=True).click()
        page.get_by_placeholder("Search...").fill("V1")
        page.get_by_text(roi_pattern("V1")).click()
        page.wait_for_timeout(6000)
        assert page.locator("canvas").first.screenshot() != atlas_before
        expect(
            page.get_by_text(
                "Left hemisphere · HCP-MMP1 · Primary Visual Cortex", exact=True
            )
        ).to_be_visible()
        assert page.locator("select").nth(0).input_value() == "Selected map min–max"
        expect(page.get_by_text("0.0019 to 0.1367", exact=False)).to_be_visible()
        assert page.get_by_text("Colors rescale per map.", exact=False).count() == 0
        assert page.get_by_text("348 available bilateral maps", exact=True).count() == 0
        page.locator("select").nth(0).select_option(label="Across all ROIs")
        page.wait_for_timeout(1500)
        if "--fdr-only" in sys.argv:
            unmasked = page.locator("canvas").nth(1).screenshot()
            toggle = page.get_by_text("Apply supplied FDR mask", exact=True)
            toggle.click()
            page.wait_for_timeout(2000)
            expect(
                page.get_by_text(
                    "finite vertices pass the supplied FDR mask.", exact=False
                )
            ).to_be_visible()
            expect(page.get_by_text("0.0000 to 0.1647", exact=False)).to_be_visible()
            assert page.locator("canvas").nth(1).screenshot() != unmasked
            page.screenshot(path="/tmp/macman-fdr.png", full_page=True)
            toggle.click()
            page.wait_for_timeout(2000)
            assert page.locator("canvas").nth(1).screenshot() == unmasked
            toggle.click()
            page.get_by_text(roi_pattern("V1")).click()
            page.get_by_placeholder("Search...").fill("46")
            page.get_by_text(roi_pattern("46")).click()
            page.wait_for_timeout(3000)
            expect(
                page.get_by_text("No vertices pass the supplied FDR mask.", exact=True)
            ).to_have_count(2)
            empty_context = page.locator("canvas").nth(1).screenshot()
            assert empty_context != neutral
            toggle.click()
            page.wait_for_timeout(2000)
            assert page.locator("canvas").nth(1).screenshot() != neutral
            assert not errors, errors
            print(
                "FDR toggle masks V1, preserves limits, restores values, and retains faint context for all-zero-mask ROI 46."
            )
            browser.close()
            raise SystemExit(0)
        first_image = page.locator("canvas").nth(1).screenshot()
        page.locator("select").nth(0).select_option(label="Selected map min–max")
        page.wait_for_timeout(1500)
        assert page.locator("canvas").nth(1).screenshot() != first_image
        expect(page.get_by_text("0.0019 to 0.1367", exact=False)).to_be_visible()
        local_image = page.locator("canvas").nth(1).screenshot()
        for next_roi in ("V2", "V1"):
            current_roi = "V1" if next_roi == "V2" else "V2"
            page.get_by_text(roi_pattern(current_roi)).click()
            page.get_by_placeholder("Search...").fill(next_roi)
            page.get_by_text(roi_pattern(next_roi)).click()
            page.wait_for_timeout(2000)
            long_name = (
                "Second Visual Area" if next_roi == "V2" else "Primary Visual Cortex"
            )
            expect(
                page.get_by_text(
                    f"Left hemisphere · HCP-MMP1 · {long_name}", exact=True
                )
            ).to_be_visible()
            assert page.locator("select").nth(0).input_value() == "Selected map min–max"
        assert page.locator("canvas").nth(1).screenshot() == local_image
        expect(page.get_by_text("0.0019 to 0.1367", exact=False)).to_be_visible()
        page.locator("select").nth(0).select_option(label="Across all ROIs")
        page.wait_for_timeout(1500)
        assert page.locator("canvas").nth(1).screenshot() == first_image
        for next_roi in ("V2", "V1"):
            current_roi = "V1" if next_roi == "V2" else "V2"
            page.get_by_text(roi_pattern(current_roi)).click()
            page.get_by_placeholder("Search...").fill(next_roi)
            page.get_by_text(roi_pattern(next_roi)).click()
            page.wait_for_timeout(2000)
            long_name = (
                "Second Visual Area" if next_roi == "V2" else "Primary Visual Cortex"
            )
            expect(
                page.get_by_text(
                    f"Left hemisphere · HCP-MMP1 · {long_name}", exact=True
                )
            ).to_be_visible()
            assert page.locator("select").nth(0).input_value() == "Across all ROIs"
            expect(page.get_by_text("0.0000 to 0.1647", exact=False)).to_be_visible()
            global_image = page.locator("canvas").nth(1).screenshot()
            page.locator("select").nth(0).select_option(label="Selected map min–max")
            page.wait_for_timeout(1500)
            assert page.locator("canvas").nth(1).screenshot() != global_image
            page.locator("select").nth(0).select_option(label="Across all ROIs")
            page.wait_for_timeout(1500)
            assert page.locator("canvas").nth(1).screenshot() == global_image
        assert page.locator("canvas").nth(1).screenshot() == first_image
        if "--range-only" in sys.argv:
            assert not errors, errors
            print(
                "Range selection, labels, and rendered colors remain consistent across ROI switches in both modes."
            )
            browser.close()
            raise SystemExit(0)
        if "--reload-only" in sys.argv:
            for _ in range(2):
                page.reload()
                page.wait_for_selector("canvas", timeout=60000)
                page.wait_for_timeout(4000)
                if page.get_by_text("Select...", exact=True).count():
                    page.get_by_text("Select...", exact=True).click()
                    page.get_by_placeholder("Search...").fill("V1")
                    page.get_by_text(roi_pattern("V1")).click()
                    page.wait_for_timeout(3000)
                page.screenshot(path="/tmp/macman-reload.png", full_page=True)
                expect(page.get_by_text("L_V1", exact=True)).to_be_visible()
                assert not errors, errors
                assert not [
                    message
                    for message in console_errors
                    if "colormap" in message.lower()
                ], console_errors
                assert (
                    page.locator("select").nth(0).input_value()
                    == "Selected map min–max"
                )
                assert page.locator("canvas").nth(1).screenshot() == local_image
            print(
                "Early ROI selection and two page reloads preserved the same rendered statistical map; no palette errors."
            )
            browser.close()
            raise SystemExit(0)
        page.locator("select").nth(1).select_option(label="magma")
        page.wait_for_timeout(1500)
        assert page.locator("canvas").nth(1).screenshot() != first_image
        for _ in range(2):
            page.get_by_role("button", name="Reset selection", exact=True).click()
            page.wait_for_timeout(1500)
            expect(page.get_by_text("Select...", exact=True)).to_be_visible()
            assert page.get_by_text("L_V1", exact=True).count() == 0
            assert page.locator("canvas").first.screenshot() == atlas_before
            assert page.locator("canvas").nth(1).screenshot() == neutral
            page.get_by_text("Select...", exact=True).click()
            page.get_by_placeholder("Search...").fill("V1")
            page.get_by_text(roi_pattern("V1")).click()
            page.wait_for_timeout(2000)
            expect(page.get_by_text("L_V1", exact=True)).to_be_visible()
        previous = "V1"
        for label in ["V2", "V1", "V2", "V1"]:
            page.get_by_text(roi_pattern(previous)).click()
            page.get_by_placeholder("Search...").fill(label)
            page.get_by_text(roi_pattern(label)).click()
            page.wait_for_timeout(2000)
            previous = label
            assert page.locator("canvas").count() == 3
        page.locator("select").nth(1).select_option(label="viridis")
        page.wait_for_timeout(1000)
        nhp_before = page.locator("canvas").nth(1).screenshot()
        page.locator("select").nth(2).select_option(label="Dorsal")
        page.wait_for_timeout(1000)
        assert page.locator("canvas").first.screenshot() != atlas_before
        assert page.locator("canvas").nth(1).screenshot() == nhp_before
        atlas_before = page.locator("canvas").first.screenshot()
        page.locator("select").nth(3).select_option(label="Ventral")
        page.wait_for_timeout(1000)
        assert page.locator("canvas").nth(1).screenshot() != nhp_before
        assert page.locator("canvas").first.screenshot() == atlas_before
        page.locator("select").nth(2).select_option(label="Medial")
        page.locator("select").nth(3).select_option(label="Dorsal")
        page.wait_for_timeout(1000)
        left_map = page.locator("canvas").nth(1).screenshot()
        page.get_by_label("Right", exact=True).check()
        # Hemisphere changes rebuild the ROI dropdown before loading its maps.
        # Wait for completion instead of assuming a fixed two-second duration.
        expect(page.get_by_text("R_V1", exact=True)).to_be_visible(timeout=15000)
        assert page.get_by_text(roi_pattern("V1")).count() == 1
        assert page.locator("canvas").nth(1).screenshot() != left_map
        page.get_by_label("Left", exact=True).check()
        expect(page.get_by_text("L_V1", exact=True)).to_be_visible(timeout=15000)
        page.locator("select").nth(3).select_option(label="Lateral")
        page.wait_for_timeout(1000)
        page.get_by_text(roi_pattern("V1")).click()
        page.get_by_placeholder("Search...").fill("V3_dsToCharm4")
        assert (
            page.get_by_role("option", name=roi_pattern("V3_dsToCharm4")).count() == 0
        )
        page.get_by_placeholder("Search...").fill("V3")
        assert page.get_by_role("option", name=roi_pattern("V3")).count() == 0
        # Standard L_4 is available; R_4 still lacks an NHP counterpart.
        page.get_by_placeholder("Search...").fill("4")
        page.get_by_role("option", name=roi_pattern("4")).click()
        page.wait_for_timeout(2000)
        page.get_by_label("Right", exact=True).check()
        page.wait_for_timeout(2000)
        expect(
            page.get_by_text("4 is unavailable for the right", exact=False)
        ).to_be_visible()
        assert page.locator("canvas").nth(1).screenshot() == neutral
        page.get_by_text("Select...", exact=True).click()
        page.get_by_placeholder("Search...").fill("V3_dsToCharm4")
        assert (
            page.get_by_role("option", name=roi_pattern("V3_dsToCharm4")).count() == 0
        )
        page.get_by_placeholder("Search...").fill("V3")
        assert page.get_by_role("option", name=roi_pattern("V3")).count() == 0
        page.keyboard.press("Escape")
        page.get_by_label("Left", exact=True).check()
        expect(page.get_by_text("L_4", exact=True)).to_be_visible(timeout=15000)
        page.get_by_text(roi_pattern("4")).click()
        page.get_by_placeholder("Search...").fill("FEF")
        assert (
            page.get_by_role("option", name=roi_pattern("FEF (bilateral)")).count() == 0
        )
        page.get_by_role("option", name=roi_pattern("FEF")).click()
        expect(page.get_by_text("L_FEF", exact=True)).to_be_visible(timeout=15000)
        page.get_by_label("Right", exact=True).check()
        expect(page.get_by_text("R_FEF", exact=True)).to_be_visible(timeout=15000)
        page.get_by_label("Left", exact=True).check()
        page.wait_for_timeout(1500)
        page.get_by_text(roi_pattern("FEF")).click()
        page.get_by_placeholder("Search...").fill("V1")
        page.get_by_text(roi_pattern("V1")).click()
        page.wait_for_timeout(2000)
        expect(page.get_by_text("L_V1", exact=True)).to_be_visible()
        print(page.locator("body").inner_text()[-9000:])
        print("ERRORS:", errors)
        assert not errors
        assert page.locator("canvas").count() == 3
        page.screenshot(path="/tmp/macman-dashboard.png", full_page=True)
        Path("/tmp/macman-dom.html").write_text(page.content())
        browser.close()

"""Shared interactions for the local-server and browser-only WASM checks."""

import re
import time


def roi_pattern(label):
    """Current UI labels are bare abbreviations (or the Select... placeholder)."""
    return re.compile(rf"^{re.escape(label)}$")


def choose_roi(page, current, target):
    page.get_by_text(roi_pattern(current)).click()
    page.get_by_placeholder("Search...").fill(target)
    page.get_by_role("option", name=roi_pattern(target)).click()


def expect_canvas_images(page, expected, indices=(0, 1, 2), timeout_ms=10000):
    """Wait for exact rendered restoration instead of assuming a decode duration."""
    assert len(expected) == len(indices)
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        actual = [page.locator("canvas").nth(i).screenshot() for i in indices]
        if actual == expected:
            return
        if time.monotonic() >= deadline:
            changed = [i for i, a, b in zip(indices, actual, expected) if a != b]
            raise AssertionError(f"Canvases did not restore expected images: {changed}")
        page.wait_for_timeout(200)


def check_camera_resets(page, while_zoomed=None):
    """Exercise real mouse zoom/rotation on every canvas, then both reset buttons."""

    def snapshots():
        return [page.locator("canvas").nth(i).screenshot() for i in range(3)]

    original = snapshots()
    for index in range(3):
        canvas = page.locator("canvas").nth(index)
        canvas.scroll_into_view_if_needed()
        box = canvas.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        before = snapshots()
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 40, y + 20, steps=8)
        page.mouse.up()
        page.wait_for_timeout(500)
        rotated = snapshots()
        assert rotated[index] != before[index], f"Canvas {index} did not rotate"
        page.mouse.move(x, y)
        page.mouse.wheel(0, -300)
        page.wait_for_timeout(500)
        zoomed = snapshots()
        assert zoomed[index] != rotated[index], f"Canvas {index} did not zoom"
        for other in set(range(3)) - {index}:
            assert zoomed[other] == before[other], (
                f"Canvas {other} changed unexpectedly"
            )

    zoomed = snapshots()
    if while_zoomed is not None:
        while_zoomed()
        assert snapshots() == zoomed, "ROI changes did not preserve the cameras"
    page.get_by_role("button", name="Reset human camera", exact=True).click()
    page.wait_for_timeout(1500)
    human_reset = snapshots()
    assert human_reset[0] == original[0], "Human rotation/zoom did not reset"
    assert human_reset[1:] == zoomed[1:], "Human reset affected NHP cameras"
    page.get_by_role("button", name="Reset NHP cameras", exact=True).click()
    page.wait_for_timeout(1500)
    assert snapshots() == original, "NHP rotation/zoom did not reset"

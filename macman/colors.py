"""Sequential palettes and shared bilateral display limits."""

import numpy as np

DEFAULT_PALETTE = "viridis"
DEFAULT_PALETTE_LABEL = "viridis"
PALETTES = {name: name for name in ("viridis", "magma", "warm", "turbo")}
RANGE_MODES = {"Across all ROIs": "global", "Selected map min–max": "local"}


def display_range(mode, global_range, values=None):
    low, high = map(float, global_range)
    if mode == "local" and values is not None:
        finite = np.asarray(values)[np.isfinite(values)]
        if finite.size:
            low, high = float(finite.min()), float(finite.max())
    # A constant map needs a nonzero display interval; never divide by zero.
    if high <= low:
        high = low + max(abs(low) * 0.01, 1e-6)
    return low, high


def map_style(palette, maximum, signed=False, minimum=0):
    return {
        "colormap": palette,
        "cal_min": minimum,
        "cal_max": maximum,
        "use_negative_cmap": signed,
        "colormap_negative": "winter",
    }

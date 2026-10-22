"""Generate preview brightness using Nilearn 0.11.1 / Matplotlib 3.10.3.

Run with the researcher's existing macman-toy virtualenv (Nilearn installed).
Then run stats_display_comparison.py --nilearn-feedback with the dashboard venv.
This diagnostic uses Nilearn's internal helper; it is not a dashboard dependency.
"""

from pathlib import Path

import matplotlib
import nilearn
import numpy as np
from matplotlib import colormaps, colors
from nilearn.plotting.html_surface import get_vertexcolor

ROOT = Path(__file__).resolve().parents[1]


def main():
    assert nilearn.__version__ == "0.11.1"
    assert matplotlib.__version__ == "3.10.3"
    result = {}
    for side in ("lh", "rh"):
        rows = np.loadtxt(ROOT / f"data/surfaces/{side}.gray_conv.csv")
        assert np.array_equal(rows[:, 0], np.arange(40962))
        source = rows[:, 1].astype(np.float32)
        # Transparent statistics extract the actual serialized background colors.
        # Preserve vertex zero, unlike the prototype's header/padding mistake.
        hexcolors = get_vertexcolor(
            np.zeros(len(source)),
            colormaps["viridis"],
            colors.Normalize(0, 1),
            absolute_threshold=1,
            bg_map=-source,
            bg_on_data=True,
            darkness=0.7,
        )
        rgb = np.array([colors.to_rgb(c) for c in hexcolors])
        assert np.array_equal(rgb[:, 0], rgb[:, 1])
        assert np.array_equal(rgb[:, 1], rgb[:, 2])
        result[side] = rgb[:, 0].astype(np.float32)
    output = ROOT / "notes/validation/nilearn-background-brightness-2026-10-15.npz"
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        **result,
    )


if __name__ == "__main__":
    main()

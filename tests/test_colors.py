import numpy as np
import pytest

from macman.colors import DEFAULT_PALETTE, PALETTES, display_range, map_style


def test_global_range_does_not_follow_selected_values():
    assert display_range("global", (0, 0.165), [0.02, 0.08]) == (0, 0.165)
    assert DEFAULT_PALETTE == "viridis"
    assert "rdbu_r" not in PALETTES.values()


def test_local_range_uses_all_finite_bilateral_values():
    limits = display_range(
        "local", (0, 0.165), np.array([0.02, np.nan, 0.08, np.inf, 0.12])
    )
    assert limits == (0.02, 0.12)
    style = map_style(DEFAULT_PALETTE, limits[1], minimum=limits[0])
    assert style["cal_min"] == 0.02
    assert style["cal_max"] == 0.12
    assert not style["use_negative_cmap"]


@pytest.mark.parametrize("values", [None, [], [np.nan, np.inf]])
def test_empty_map_falls_back_to_global(values):
    assert display_range("local", (0, 0.165), values) == (0, 0.165)


def test_constant_map_has_valid_display_interval():
    low, high = display_range("local", (0, 0.165), [0, 0])
    assert low == 0
    assert np.isfinite(high) and high > low

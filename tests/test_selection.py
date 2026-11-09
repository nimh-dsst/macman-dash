import pytest

from macman.selection import region_options, resolve_roi


@pytest.fixture
def rois():
    return {
        key: {
            "hemisphere": key[0],
            "label": key[2:],
            "mask_counts": {"bh": {"lh": left, "rh": right}},
            # Deliberately opposite legacy FDR counts detect use of the wrong mask.
            "hemisphere_counts": {"lh": {"passing": not left}, "rh": {"passing": not right}},
        }
        for key, left, right in [
            ("L_V1", 10, 20),
            ("R_V1", 0, 0),
            ("L_V3", 1, 0),
            ("R_25", 0, 1),
            ("B_FEF", 5, 5),
        ]
    }


def test_options_are_prefixless_and_match_hemisphere(rois):
    assert region_options(rois, "Left") == {
        "V1": "V1",
        "V3": "V3",
    }
    assert region_options(rois, "Right") == {
        "25": "25",
        "V1": "V1",
    }


def test_bh_filter_accepts_either_nhp_hemisphere_and_preserves_lookup(rois):
    assert list(region_options(rois, "Left", only_bh=True).values()) == ["V1", "V3"]
    assert list(region_options(rois, "Right", only_bh=True).values()) == ["25"]
    for region in region_options(rois, "Left", only_bh=True).values():
        assert resolve_roi(rois, "Left", region) == f"L_{region}"


def test_bh_filter_can_return_an_empty_list(rois):
    assert region_options({"R_V1": rois["R_V1"]}, "Right", only_bh=True) == {}


def test_switch_resolves_same_region_to_other_map(rois):
    assert resolve_roi(rois, "Left", "V1") == "L_V1"
    assert resolve_roi(rois, "Right", "V1") == "R_V1"


def test_missing_counterpart_does_not_fall_back_to_wrong_side(rois):
    assert resolve_roi(rois, "Right", "V3") is None
    assert resolve_roi(rois, "Left", "25") is None
    assert resolve_roi(rois, "Right", "L_V1") is None
    assert resolve_roi(rois, "Left", None) is None


def test_out_of_analysis_bilateral_map_cannot_be_selected(rois):
    assert resolve_roi(rois, "Left", "B_FEF") is None
    assert resolve_roi(rois, "Right", "B_FEF") is None

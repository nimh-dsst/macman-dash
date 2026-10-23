import json

import nibabel as nib
import numpy as np
import pytest

from macman.data import digest, load_pair, read_map, scalar_bytes


def write_csv(path, rows):
    path.write_text(",mean_subj_acc,fdr_mask\n" + "\n".join(rows) + "\n")
    return path


def test_vertex_order_and_missing_values(tmp_path):
    path = write_csv(tmp_path / "map.csv", ["2,0.3,1", "0,,0", "1,0.1,1"])
    np.testing.assert_allclose(read_map(path, 3), [np.nan, 0.1, 0.3], equal_nan=True)


def test_catalog_excludes_b_fef_from_assets_and_range(tmp_path, monkeypatch):
    from macman.data import build_catalog

    folder = tmp_path / "data/h2m/glasser2"
    folder.mkdir(parents=True)
    for key, value in (("L_FEF", 0.1), ("R_FEF", 0.2), ("B_FEF", 99)):
        for side in ("lh", "rh"):
            write_csv(folder / f"roi-0010_{key}_NHP-{side}.csv", [f"0,{value},1"])
    monkeypatch.setattr(
        "macman.data.read_map",
        lambda path, with_mask=False: read_map(path, count=1, with_mask=with_mask),
    )
    catalog = build_catalog(tmp_path)
    assert set(catalog["rois"]) == {"L_FEF", "R_FEF"}
    assert catalog["range"] == pytest.approx([0, 0.2])
    assert catalog["excluded_incomplete_pairs"] == []
    assert "B_FEF" not in json.dumps(catalog)
    assert "B_FEF" not in (tmp_path / "data/catalog.json").read_text()
    assert not list((tmp_path / "data/stat_maps").glob("B_FEF.*"))
    assert len(list(folder.glob("*B_FEF*.csv"))) == 2


def test_catalog_ignores_suffix_maps_but_accepts_correct_v3_names(
    tmp_path, monkeypatch
):
    from macman.data import build_catalog

    folder = tmp_path / "data/h2m/glasser2"
    folder.mkdir(parents=True)
    for key, sides, value in (
        ("L_V3_dsToCharm4", ("lh", "rh"), 99),
        ("R_V3_dsToCharm4", ("rh",), 99),
        ("L_V3", ("lh", "rh"), 0.1),
        ("R_V3", ("lh", "rh"), 0.2),
    ):
        for side in sides:
            write_csv(folder / f"roi-0005_{key}_NHP-{side}.csv", [f"0,{value},1"])
    monkeypatch.setattr(
        "macman.data.read_map",
        lambda path, with_mask=False: read_map(path, count=1, with_mask=with_mask),
    )
    catalog = build_catalog(tmp_path)
    assert set(catalog["rois"]) == {"L_V3", "R_V3"}
    assert catalog["range"] == pytest.approx([0, 0.2])
    assert catalog["excluded_incomplete_pairs"] == []
    assert "dsToCharm4" not in json.dumps(catalog)
    assert "dsToCharm4" not in (tmp_path / "data/catalog.json").read_text()
    assert not list((tmp_path / "data/stat_maps").glob("*dsToCharm4*"))
    assert len(list(folder.glob("*dsToCharm4*.csv"))) == 3


@pytest.mark.parametrize(
    "rows",
    [
        ["0,1,0", "0,2,0"],
        ["0,1,0", "2,2,0"],
        ["0.5,1,0", "1,2,0"],
        ["0,inf,0", "1,2,0"],
        ["0,,0", "1,nan,0"],
        ["0,1,0"],
    ],
)
def test_reject_invalid_map(tmp_path, rows):
    with pytest.raises(ValueError):
        read_map(write_csv(tmp_path / "map.csv", rows), 2)


def test_scalar_roundtrip_preserves_nan_and_order():
    expected = np.array([0, 0.2, np.nan, 0.1], dtype=np.float32)
    actual = nib.gifti.GiftiImage.from_bytes(scalar_bytes(expected)).agg_data()
    np.testing.assert_array_equal(actual, expected)


def test_changed_source_rejected(tmp_path):
    path = write_csv(tmp_path / "map.csv", ["0,1,0"])
    original = digest(path)
    path.write_text("modified")
    entry = {"files": {"lh": "map.csv"}, "sha256": {"lh": original}}
    with pytest.raises(ValueError, match="Source data changed"):
        load_pair(entry, tmp_path)


def test_bilateral_order(tmp_path, monkeypatch):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left.write_text("left")
    right.write_text("right")
    monkeypatch.setattr(
        "macman.data.read_map",
        lambda path: np.array([1, 2]) if path == left else np.array([3, 4]),
    )
    entry = {
        "files": {"rh": "right.csv", "lh": "left.csv"},
        "sha256": {"lh": digest(left), "rh": digest(right)},
    }
    np.testing.assert_array_equal(load_pair(entry, tmp_path), [1, 2, 3, 4])


def test_mask_stays_aligned_with_shuffled_vertex_ids(tmp_path):
    path = write_csv(tmp_path / "map.csv", ["2,0.3,1", "0,,0", "1,0.1,0"])
    values, mask = read_map(path, 3, with_mask=True)
    np.testing.assert_allclose(values, [np.nan, 0.1, 0.3], equal_nan=True)
    np.testing.assert_array_equal(mask, [False, False, True])


@pytest.mark.parametrize("bad_mask", ["2", "-1", "nan", "0.5", ""])
def test_reject_invalid_fdr_mask(tmp_path, bad_mask):
    path = write_csv(tmp_path / "map.csv", [f"0,0.1,{bad_mask}"])
    with pytest.raises(ValueError):
        read_map(path, 1, with_mask=True)


def test_precomputed_assets_preserve_values_and_need_no_csv(tmp_path, monkeypatch):
    from macman.data import load_stat_assets, write_stat_assets

    values = np.array([0.1, np.nan, 0.3, 0.4], dtype=np.float32)
    mask = np.array([True, True, False, True])
    assets = write_stat_assets("L_test", values, mask, tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Runtime must not read CSVs or encode GIFTIs")

    monkeypatch.setattr("macman.data.read_map", forbidden)
    monkeypatch.setattr("macman.data.scalar_bytes", forbidden)
    loaded = load_stat_assets({"assets": assets}, tmp_path)
    for variant, expected in (
        ("unthresholded", values),
        ("fdr", np.where(mask, values, np.nan)),
    ):
        for side, hemisphere_expected in zip(("lh", "rh"), np.split(expected, 2)):
            np.testing.assert_array_equal(
                nib.gifti.GiftiImage.from_bytes(loaded[variant][side]).agg_data(),
                hemisphere_expected,
            )
    (tmp_path / assets["fdr"]["rh"]["path"]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="Precomputed map changed"):
        load_stat_assets({"assets": assets}, tmp_path)


def test_all_zero_mask_precomputes_all_missing_overlay(tmp_path):
    from macman.data import load_stat_assets, write_stat_assets

    values = np.array([0.1, 0.2], dtype=np.float32)
    assets = write_stat_assets("R_test", values, np.zeros(2, dtype=bool), tmp_path)
    loaded = load_stat_assets({"assets": assets}, tmp_path)
    for side in ("lh", "rh"):
        assert np.isnan(
            nib.gifti.GiftiImage.from_bytes(loaded["fdr"][side]).agg_data()
        ).all()


def test_one_hemisphere_empty_mask_does_not_remove_other(tmp_path):
    from macman.data import load_stat_assets, write_stat_assets

    values = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
    assets = write_stat_assets(
        "L_test", values, np.array([False, False, True, False]), tmp_path
    )
    loaded = load_stat_assets({"assets": assets}, tmp_path)
    assert np.isnan(
        nib.gifti.GiftiImage.from_bytes(loaded["fdr"]["lh"]).agg_data()
    ).all()
    np.testing.assert_array_equal(
        nib.gifti.GiftiImage.from_bytes(loaded["fdr"]["rh"]).agg_data(),
        [values[2], np.nan],
    )


def test_curvature_preserves_first_vertex_and_sorts_headerless_ids(tmp_path):
    from macman.data import curvature_brightness, read_curvature_values

    path = tmp_path / "gray_conv.csv"
    path.write_text("2\t-1\n0\t0.419745\n1\t1\n")
    values = read_curvature_values(path, count=3)
    np.testing.assert_allclose(values, [0.419745, 1, -1])
    brightness = curvature_brightness(values, [-1, 1])
    np.testing.assert_allclose(brightness, [0.45 + 0.3 * 1.419745 / 2, 0.75, 0.45])
    # Values beyond the previous +/-0.5 cutoff retain distinct brightness.
    beyond_old_cutoff = curvature_brightness(np.array([-1, -0.7, 0.7, 1]), [-1, 1])
    assert np.all(np.diff(beyond_old_cutoff) > 0)
    np.testing.assert_allclose(
        nib.gifti.GiftiImage.from_bytes(scalar_bytes(brightness)).agg_data(), brightness
    )
    path.write_text("0\t0.1\n0\t0.2\n2\t0.3\n")
    with pytest.raises(ValueError, match="vertex IDs"):
        read_curvature_values(path, count=3)


def test_saved_convexity_retains_raw_values_and_approved_native_limits():
    from macman.data import ROOT, load_curvature_assets, read_curvature_values

    for side, asset in load_curvature_assets().items():
        source = read_curvature_values(ROOT / f"data/surfaces/{side}.gray_conv.csv")
        saved = nib.gifti.GiftiImage.from_bytes(asset.data).agg_data()
        np.testing.assert_array_equal(saved, source.astype(np.float32))
        low, high = asset.display_range
        np.testing.assert_allclose(
            (np.array([source.min(), source.max()]) - low) / (high - low),
            [94 / 255, 1],
        )


def test_scene_preserves_source_geometry_without_reencoding_nhp(monkeypatch):
    from macman.data import ROOT, VERTICES, scene_assets

    load = nib.load

    def human_only(path):
        assert "gray_surface" not in str(path), "Pass NHP files to the viewer directly"
        return load(path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Runtime must not encode replacement NHP GIFTIs")

    monkeypatch.setattr("macman.data.nib.load", human_only)
    monkeypatch.setattr("macman.data.surface_bytes", forbidden)
    nhp_paths, human = scene_assets()
    for side, word in (("lh", "left"), ("rh", "right")):
        source = ROOT / f"data/surfaces/{side}.gray_surface.inf_300.rsl.gii"
        assert nhp_paths[side] == source
        assert load(source).agg_data()[0].shape == (VERTICES, 3)
        points, faces = load(ROOT / f"data/surfaces/infl_{word}.gii.gz").agg_data()
        np.testing.assert_array_equal(human[side]["points"], points)
        np.testing.assert_array_equal(human[side]["faces"], faces)

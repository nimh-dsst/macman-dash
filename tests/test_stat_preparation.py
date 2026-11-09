"""A full replacement rebuild preserves source values and optional mask coverage."""

import json

import nibabel as nib
import numpy as np
import pytest

from macman.data import digest
from scripts.prepare_stat_maps import prepare_stat_maps, validate_stat_assets


def make_sources(folder):
    folder.mkdir()
    # Deliberately shuffled IDs/columns and different masks per side.
    (folder / "roi-0001_L_V1_NHP-lh.csv").write_text(
        "bh_mask,,mean_subj_acc,tfce_mask,fdr_mask\n"
        "1,2,0.75,0,0\n0,0,,0,0\n1,1,0.125,1,1\n"
    )
    (folder / "roi-0001_L_V1_NHP-rh.csv").write_text(
        ",mean_subj_acc,fdr_mask,bh_mask\n1,0.5,0,0\n2,0.25,1,0\n0,0.875,1,0\n"
    )
    return folder


def test_fresh_rebuild_preserves_all_variants_and_optional_hemisphere(tmp_path):
    source = make_sources(tmp_path / "source")
    output = tmp_path / "prepared"
    assert prepare_stat_maps(source, output, count=3) == {
        "source_files": 2,
        "rois": 1,
        "assets": 7,
    }
    catalog = json.loads((output / "data/catalog.json").read_text())
    entry = catalog["rois"]["L_V1"]
    assert entry["mask_counts"] == {
        "fdr": {"lh": 1, "rh": 2},
        "bh": {"lh": 2, "rh": 0},
        "tfce": {"lh": 1},
    }
    assert entry["passing_vertices"] == 3
    assert set(entry["assets"]["tfce"]) == {"lh"}
    expected = {
        ("unthresholded", "lh"): [np.nan, 0.125, 0.75],
        ("unthresholded", "rh"): [0.875, 0.5, 0.25],
        ("fdr", "lh"): [np.nan, 0.125, np.nan],
        ("fdr", "rh"): [0.875, np.nan, 0.25],
        ("bh", "lh"): [np.nan, 0.125, 0.75],
        ("bh", "rh"): [np.nan, np.nan, np.nan],
        ("tfce", "lh"): [np.nan, 0.125, np.nan],
    }
    for (variant, side), array in expected.items():
        info = entry["assets"][variant][side]
        np.testing.assert_array_equal(nib.load(output / info["path"]).agg_data(), array)
    for original in source.glob("*.csv"):
        assert (
            output / "data/h2m/glasser2" / original.name
        ).read_bytes() == original.read_bytes()
    with pytest.raises(FileExistsError):
        prepare_stat_maps(source, output, count=3)
    # A second fresh build yields the same content-addressed assets and catalog.
    second = tmp_path / "second"
    prepare_stat_maps(source, second, count=3)
    assert (second / "data/catalog.json").read_bytes() == (
        output / "data/catalog.json"
    ).read_bytes()
    # Even if somebody updates the checksum, validation detects corrupted data.
    info = entry["assets"]["bh"]["lh"]
    path = output / info["path"]
    image = nib.load(path)
    image.darrays[0].data[2] = 0.5
    nib.save(image, path)
    info["sha256"] = digest(path)
    (output / "data/catalog.json").write_text(json.dumps(catalog))
    with pytest.raises(AssertionError):
        validate_stat_assets(output, count=3)


def test_incomplete_sources_are_still_validated(tmp_path):
    source = make_sources(tmp_path / "source")
    (source / "roi-0002_L_MST_NHP-lh.csv").write_text(
        ",mean_subj_acc,fdr_mask,bh_mask\n0,0.5,1,9\n1,0.5,0,0\n2,0.5,0,0\n"
    )
    output = tmp_path / "prepared"
    with pytest.raises(ValueError, match="bh_mask"):
        prepare_stat_maps(source, output, count=3)
    assert not (output / "data/catalog.json").exists()

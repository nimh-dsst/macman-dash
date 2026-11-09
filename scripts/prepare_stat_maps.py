"""Build and verify a full replacement statistics collection in a fresh directory.

Usage: python -m scripts.prepare_stat_maps --source CSV_DIR --output FRESH_DIR
The output contains data/h2m/glasser2, data/stat_maps, and data/catalog.json.
"""

import argparse
import json
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np

from macman.data import VERTICES, build_catalog, digest, read_map_masks


def validate_stat_assets(root, *, count=VERTICES):
    """Decode every saved map and compare values/NaNs to its supplied CSV mask."""
    catalog = json.loads((root / "data/catalog.json").read_text())
    active = set()
    for key, entry in catalog["rois"].items():
        expected_assets = set()
        expected_counts = {}
        for side in ("lh", "rh"):
            source = root / entry["files"][side]
            if digest(source) != entry["sha256"][side]:
                raise ValueError(f"Source checksum mismatch: {source.name}")
            values, masks = read_map_masks(source, count)
            expected = {"unthresholded": values}
            for name, mask in masks.items():
                variant = name.removesuffix("_mask")
                expected[variant] = np.where(mask, values, np.nan)
                expected_counts.setdefault(variant, {})[side] = int(
                    (mask & np.isfinite(values)).sum()
                )
            for variant, array in expected.items():
                expected_assets.add((variant, side))
                info = entry["assets"][variant][side]
                path = root / info["path"]
                if digest(path) != info["sha256"]:
                    raise ValueError(f"Asset checksum mismatch: {path.name}")
                actual = nib.load(path).agg_data()
                np.testing.assert_array_equal(
                    actual, array, err_msg=f"{key}/{side}/{variant}"
                )
                if actual.dtype != np.float32:
                    raise ValueError(f"Expected float32: {path.name}")
                active.add(path)
        actual_assets = {
            (variant, side)
            for variant, hemispheres in entry["assets"].items()
            for side in hemispheres
        }
        if actual_assets != expected_assets or entry["mask_counts"] != expected_counts:
            raise ValueError(f"Mask availability/count mismatch: {key}")
        for side in ("lh", "rh"):
            if (
                entry["hemisphere_counts"][side]["passing"]
                != expected_counts["fdr"][side]
            ):
                raise ValueError(f"FDR count mismatch: {key}/{side}")
        if entry["passing_vertices"] != sum(expected_counts["fdr"].values()):
            raise ValueError(f"FDR total mismatch: {key}")
    if active != set((root / "data/stat_maps").glob("*.shape.gii")):
        raise ValueError("Statistical asset inventory differs from catalog")
    return len(active)


def prepare_stat_maps(source, output, *, count=VERTICES):
    """Copy the full source snapshot; generate and verify all supported variants."""
    files = sorted(source.glob("*.csv"))
    if not files:
        raise ValueError(f"No CSV files in {source}")
    # Refuse reuse: a full rebuild must not inherit stale files from a prior run.
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "data/h2m/glasser2"
    destination.mkdir(parents=True)
    for path in files:
        target = destination / path.name
        shutil.copyfile(path, target)
        if digest(path) != digest(target):
            raise ValueError(f"Source copy checksum mismatch: {path.name}")
        # Validate incomplete groups too, although they remain unselectable.
        read_map_masks(target, count)
    catalog = build_catalog(output, count=count, require_bh=True)
    asset_count = validate_stat_assets(output, count=count)
    return {
        "source_files": len(files),
        "rois": len(catalog["rois"]),
        "assets": asset_count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare_stat_maps(args.source.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

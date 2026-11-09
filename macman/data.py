"""Explicit vertex IDs, bilateral ordering, and fixed collection-wide scaling."""

import csv
import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VERTICES = 40962
PATTERN = re.compile(r"roi-(\d+)_([LRB])_(.+)_NHP-(lh|rh)\.csv$")


def excluded_source_key(key):
    """Skip unsupported source groups without publishing their inventory."""
    return key == "B_FEF" or key.endswith("_dsToCharm4")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_map_masks(path, count=VERTICES, *, require_bh=True):
    """Read named masks and float32 statistics in ascending vertex-ID order.

    Replacement data requires BH; ``require_bh=False`` also accepts the legacy
    FDR-only schema. Optional TFCE is absent from the returned mask dictionary
    when unavailable. All supplied columns are validated, regardless of use.
    """
    path = Path(path)
    with path.open(newline="") as stream:
        header = next(csv.reader(stream), [])
    required = {"", "mean_subj_acc", "fdr_mask"}
    if require_bh:
        required.add("bh_mask")
    allowed = required | {"bh_mask", "tfce_mask"}
    if (
        len(header) != len(set(header))
        or not required.issubset(header)
        or not set(header).issubset(allowed)
        or ("tfce_mask" in header and "bh_mask" not in header)
    ):
        raise ValueError(
            f"{path.name}: expected unique vertex-ID (unnamed), mean_subj_acc, "
            "fdr_mask, and bh_mask columns (optional tfce_mask)"
            + ("; legacy FDR-only schema also accepted" if not require_bh else "")
        )
    value_column = header.index("mean_subj_acc")
    try:
        data = np.loadtxt(
            path,
            delimiter=",",
            skiprows=1,
            comments=None,
            ndmin=2,
            converters={
                value_column: lambda value: (
                    float(value) if value.strip() else float("nan")
                )
            },
        )
    except ValueError as exc:
        raise ValueError(f"{path.name}: invalid numeric CSV: {exc}") from exc
    if data.shape != (count, len(header)):
        raise ValueError(f"{path.name}: expected {count} rows and {len(header)} columns")
    ids, values = data[:, header.index("")], data[:, value_column]
    if not np.array_equal(np.sort(ids), np.arange(count)):
        raise ValueError(
            f"{path.name}: vertex IDs must cover 0..{count - 1} exactly once"
        )
    if np.isinf(values).any() or not np.isfinite(values).any():
        raise ValueError(f"{path.name}: infinite or entirely missing values")
    if np.any(np.abs(values[np.isfinite(values)]) > np.finfo(np.float32).max):
        raise ValueError(f"{path.name}: statistic outside float32 range")
    order = np.argsort(ids)
    masks = {}
    for name in ("fdr_mask", "bh_mask", "tfce_mask"):
        if name not in header:
            continue
        mask = data[:, header.index(name)]
        if not np.isin(mask, [0, 1]).all():
            raise ValueError(f"{path.name}: {name} must contain only 0 or 1")
        masks[name] = mask[order].astype(bool)
    return values[order].astype(np.float32), masks


def read_map(path, count=VERTICES, with_mask=False):
    """Compatibility interface: return statistics and, optionally, supplied FDR."""
    values, masks = read_map_masks(path, count, require_bh=False)
    if with_mask:
        return values, masks["fdr_mask"]
    return values


def build_catalog(root=ROOT, *, count=VERTICES, require_bh=False):
    grouped = {}
    for path in sorted((root / "data/h2m/glasser2").glob("*.csv")):
        match = PATTERN.fullmatch(path.name)
        if not match:
            raise ValueError(f"Unrecognized map filename: {path.name}")
        number, hemi, label, side = match.groups()
        key = f"{hemi}_{label}"
        entry = grouped.setdefault(
            key, {"label": label, "hemisphere": hemi, "source_id": number, "files": {}}
        )
        if entry["source_id"] != number:
            raise ValueError(f"Inconsistent source IDs for {key}")
        if side in entry["files"]:
            raise ValueError(f"Duplicate map for {key}/{side}")
        entry["files"][side] = str(path.relative_to(root))
    rois, excluded = {}, []
    low, high = 0.0, 0.0
    for key, entry in grouped.items():
        if excluded_source_key(key):
            continue
        if set(entry["files"]) != {"lh", "rh"}:
            excluded.append(key)
            continue
        entry["sha256"] = {}
        arrays = []
        masks = []
        entry["assets"] = {}
        entry["mask_counts"] = {}
        for side in ("lh", "rh"):
            relative = entry["files"][side]
            path = root / relative
            values, supplied_masks = read_map_masks(
                path, count, require_bh=require_bh
            )
            arrays.append(values)
            masks.append(supplied_masks["fdr_mask"])
            for variant, info in write_hemisphere_stat_assets(
                key, side, values, supplied_masks, root
            ).items():
                entry["assets"].setdefault(variant, {})[side] = info
            for name, supplied_mask in supplied_masks.items():
                entry["mask_counts"].setdefault(name.removesuffix("_mask"), {})[
                    side
                ] = int((supplied_mask & np.isfinite(values)).sum())
            low = min(low, float(np.nanmin(values)))
            high = max(high, float(np.nanmax(values)))
            entry["sha256"][side] = digest(path)
        entry["identical_hemispheres"] = bool(np.array_equal(*arrays, equal_nan=True))
        values = np.concatenate(arrays)
        mask = np.concatenate(masks)
        entry["hemisphere_counts"] = {
            side: {
                "finite": int(np.isfinite(array).sum()),
                "passing": int((hemi_mask & np.isfinite(array)).sum()),
            }
            for side, array, hemi_mask in zip(("lh", "rh"), arrays, masks)
        }
        entry["value_range"] = [float(np.nanmin(values)), float(np.nanmax(values))]
        entry["finite_vertices"] = int(np.isfinite(values).sum())
        entry["missing_vertices"] = int(np.isnan(values).sum())
        entry["passing_vertices"] = int((mask & np.isfinite(values)).sum())
        rois[key] = entry
    if not rois or high <= low:
        raise ValueError("No usable bilateral maps or statistic range")
    maximum = max(abs(low), abs(high))
    catalog = {
        "schema_version": 3,
        "development": True,
        "statistic": "mean_subj_acc",
        "range": [-maximum if low < 0 else 0, maximum],
        "vertex_count_per_hemisphere": count,
        "excluded_incomplete_pairs": excluded,
        "rois": rois,
    }
    target = root / "data/catalog.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(catalog, indent=2) + "\n")
    temporary.replace(target)
    return catalog


def write_hemisphere_stat_assets(key, side, values, masks, root=ROOT):
    """Save original statistics and every supplied supported mask for one side."""
    folder = root / "data/stat_maps"
    folder.mkdir(parents=True, exist_ok=True)
    if side not in ("lh", "rh") or np.ndim(values) != 1:
        raise ValueError("Expected one hemisphere of scalar values")
    variants = {"unthresholded": values}
    for name, mask in masks.items():
        if name not in ("fdr_mask", "bh_mask", "tfce_mask"):
            raise ValueError(f"Unsupported mask: {name}")
        if np.shape(mask) != np.shape(values) or not np.isin(mask, [0, 1]).all():
            raise ValueError(f"{name}: expected one binary mask entry per vertex")
        variants[name.removesuffix("_mask")] = np.where(mask, values, np.nan)
    assets = {}
    for variant, data in variants.items():
        payload = scalar_bytes(data)
        checksum = hashlib.sha256(payload).hexdigest()
        path = folder / f"{key}.{side}.{variant}.{checksum[:12]}.shape.gii"
        temporary = path.with_suffix(".gii.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
        assets[variant] = {"path": str(path.relative_to(root)), "sha256": checksum}
    return assets


def write_stat_assets(key, values, mask, root=ROOT):
    """Legacy bilateral FDR helper; input order is left then right."""
    if len(values) % 2 or len(values) != len(mask):
        raise ValueError("Expected equally sized left/right values and masks")
    assets = {}
    for side, array, hemi_mask in zip(
        ("lh", "rh"), np.split(values, 2), np.split(mask, 2)
    ):
        for variant, info in write_hemisphere_stat_assets(
            key, side, array, {"fdr_mask": hemi_mask}, root
        ).items():
            assets.setdefault(variant, {})[side] = info
    return assets


def load_stat_assets(entry, root=ROOT):
    """Load prepared bytes without reading CSVs or generating GIFTIs."""
    if "assets" not in entry:
        raise ValueError("Precomputed maps missing; run python -m macman.data")
    assets = {}
    for variant in ("unthresholded", "fdr"):
        assets[variant] = {}
        for side in ("lh", "rh"):
            info = entry["assets"][variant][side]
            payload = (root / info["path"]).read_bytes()
            if hashlib.sha256(payload).hexdigest() != info["sha256"]:
                raise ValueError("Precomputed map changed; run python -m macman.data")
            assets[variant][side] = payload
    return assets


def load_roi_names(root=ROOT):
    with (root / "data/atlases/glasser_roi_names.tsv").open() as stream:
        return {
            row["abbreviation"]: row["long_name"]
            for row in csv.DictReader(stream, delimiter="\t")
        }


def load_pair(entry, root=ROOT, with_mask=False):
    arrays = []
    masks = []
    for side in ("lh", "rh"):
        path = root / entry["files"][side]
        if digest(path) != entry["sha256"][side]:
            raise ValueError("Source data changed; rebuild the catalog before viewing")
        if with_mask:
            values, mask = read_map(path, with_mask=True)
            arrays.append(values)
            masks.append(mask)
        else:
            arrays.append(read_map(path))
    if with_mask:
        return np.concatenate(arrays), np.concatenate(masks)
    return np.concatenate(arrays)


def surface_bytes(points, faces):
    return nib.gifti.GiftiImage(
        darrays=[
            nib.gifti.GiftiDataArray(
                np.asarray(points, dtype=np.float32), intent="NIFTI_INTENT_POINTSET"
            ),
            nib.gifti.GiftiDataArray(
                np.asarray(faces, dtype=np.int32), intent="NIFTI_INTENT_TRIANGLE"
            ),
        ]
    ).to_bytes()


def scalar_bytes(values):
    return nib.gifti.GiftiImage(
        darrays=[
            nib.gifti.GiftiDataArray(
                np.asarray(values, dtype=np.float32), intent="NIFTI_INTENT_SHAPE"
            )
        ]
    ).to_bytes()


def read_curvature_values(path, count=VERTICES):
    """Read every headerless convexity TSV row in validated vertex-ID order."""
    data = np.loadtxt(path, delimiter="\t", ndmin=2)
    if data.shape != (count, 2) or not np.isfinite(data).all():
        raise ValueError(f"{Path(path).name}: expected finite vertex ID/convexity rows")
    if not np.array_equal(np.sort(data[:, 0]), np.arange(count)):
        raise ValueError(f"{Path(path).name}: invalid convexity vertex IDs")
    return data[np.argsort(data[:, 0]), 1]


def curvature_brightness(values, value_range):
    """Historical soft mapping for comparison scripts, not dashboard assets."""
    # The prototype uses -convexity with Nilearn's reversed gray palette.
    # NiiVue gray is increasing: positive source values must be brighter.
    low, high = value_range
    if high <= low:
        return np.full(np.shape(values), 0.6, dtype=np.float32)
    # Shared full range and brightness bounds; never normalize ROI statistics.
    return (0.45 + 0.3 * (values - low) / (high - low)).astype(np.float32)


@dataclass(frozen=True)
class CurvatureAsset:
    """Saved raw convexity bytes and native grayscale display limits."""

    data: bytes
    display_range: tuple[float, float]


def convexity_display_range(source_range):
    """Approximate Nilearn brightness endpoints using native linear gray limits."""
    low, high = source_range
    floor = 94 / 255
    return (low - floor / (1 - floor) * (high - low), high)


def build_curvature_assets(root=ROOT):
    """Prepare two reusable grayscale layers, independent of the ROI catalog."""
    folder = root / "data/surfaces"
    manifest = {}
    values = {
        side: read_curvature_values(folder / f"{side}.gray_conv.csv")
        for side in ("lh", "rh")
    }
    for side in ("lh", "rh"):
        source = folder / f"{side}.gray_conv.csv"
        target = folder / f"{side}.curvature.shape.gii"
        source_range = [float(values[side].min()), float(values[side].max())]
        payload = scalar_bytes(values[side])
        temporary = target.with_suffix(".gii.tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        manifest[side] = {
            "source": source.name,
            "source_sha256": digest(source),
            "path": target.name,
            "sha256": digest(target),
            "mapping": "raw convexity; native gray with per-hemisphere display limits",
            "source_range": source_range,
            "display_range": convexity_display_range(source_range),
            "brightness_range": [94 / 255, 1.0],
        }
    target = folder / "curvature.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(target)


def load_curvature_assets(root=ROOT):
    folder = root / "data/surfaces"
    manifest = json.loads((folder / "curvature.json").read_text())
    result = {}
    for side in ("lh", "rh"):
        entry = manifest[side]
        payload = (folder / entry["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise ValueError("Curvature asset changed; run python -m macman.data")
        result[side] = CurvatureAsset(payload, tuple(entry["display_range"]))
    return result


def colored_mesh_bytes(points, faces, colors):
    """MZ3 vertex RGBA avoids the viewer's FreeSurfer annotation LUT parser."""
    return (
        struct.pack("<HHIII", 23117, 7, len(faces), len(points), 0)
        + np.asarray(faces, dtype="<u4").tobytes()
        + np.asarray(points, dtype="<f4").tobytes()
        + np.asarray(colors, dtype=np.uint8).tobytes()
    )


def scene_assets(root=ROOT):
    """Use source coordinates; let the viewer frame each hemisphere."""
    folder = root / "data/surfaces"
    nhp = {
        side: folder / f"{side}.gray_surface.inf_300.rsl.gii" for side in ("lh", "rh")
    }
    human = {}
    for side, word in (("lh", "left"), ("rh", "right")):
        p, f = nib.load(folder / f"infl_{word}.gii.gz").agg_data()
        labels, colors, names = nib.freesurfer.read_annot(
            folder / f"{side}.HCP-MMP1.annot"
        )
        if len(labels) != len(p):
            raise ValueError("Human atlas and surface vertex counts differ")
        rgba = np.full((len(p), 4), 180, dtype=np.uint8)
        valid = labels >= 0
        rgba[valid, :3] = colors[labels[valid], :3]
        rgba[:, 3] = 255
        human[side] = {
            "points": p,
            "faces": f,
            "colors": rgba,
            "labels": labels,
            "names": [name.decode().removesuffix("_ROI") for name in names],
        }
    return nhp, human


if __name__ == "__main__":
    build_curvature_assets()
    result = build_catalog()
    print(f"Validated {len(result['rois'])} bilateral maps; range {result['range']}")
    print(f"Excluded incomplete pairs: {result['excluded_incomplete_pairs']}")

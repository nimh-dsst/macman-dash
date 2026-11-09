# Precomputed hemisphere statistical maps

This directory contains 2,080 scalar GIFTIs for 346 human ROIs, each with maps
for both NHP hemispheres. The dashboard loads these prepared files directly;
source CSVs are not required to run it.

## File contents

Each human ROI has six files: three variants for each NHP hemisphere.
Two ROIs additionally have TFCE maps for both hemispheres (four more files).

- `<ROI>.<lh|rh>.unthresholded.<hash>.shape.gii`: original float32 `mean_subj_acc`.
- `<ROI>.<lh|rh>.fdr.<hash>.shape.gii`: the same values where `fdr_mask == 1`, NaN elsewhere.
- `<ROI>.<lh|rh>.bh.<hash>.shape.gii`: the same values where `bh_mask == 1`, NaN elsewhere.
- `<ROI>.<lh|rh>.tfce.<hash>.shape.gii`: generated only when `tfce_mask` is supplied;
  the same values where that mask is 1, NaN elsewhere.

`<ROI>` identifies the human parcel, including its `L_` or `R_` prefix;
`lh` or `rh` identifies the NHP hemisphere receiving the map.
Each file contains 40,962 values in ascending source vertex-ID order.
Missing source values remain NaN. If no vertices pass a supplied mask, its masked file
contains only NaNs.

## Catalog and related assets

The [catalog](../catalog.json) lists active file paths, full SHA-256 checksums,
unmasked value ranges, and finite/missing/FDR-passing counts. The additive
`mask_counts` field records finite passing counts for each supplied variant and
hemisphere. Existing `passing_vertices` and `hemisphere_counts.*.passing` still
mean FDR. An absent mask produces no asset/count entry, never an invented empty
mask. The catalog remains schema 3 with its existing FDR fields intact. Filename hash
fragments identify file contents. Use catalog references to identify deployment
assets rather than including every file found in this directory.

Only complete exact-name NHP hemisphere pairs are included.
`excluded_incomplete_pairs` lists groups missing one NHP hemisphere file;
unsupported source groups are omitted from the catalog.

Surface meshes and the two shared convexity GIFTIs are stored separately in
`data/surfaces/` and are not included in the 2,080-file count above. See
[surface provenance](../surfaces/PROVENANCE.md) for these assets and
[implementation details](../../docs/implementation.md) for opacity, outlines,
color scales, and convexity rendering.

## Source CSV reader

`macman.data.read_map_masks(path)` validates replacement CSVs and returns
`(values, masks)`, where `masks` is a dictionary keyed by source column name.
Required columns are the unnamed vertex-ID column, `mean_subj_acc`, `fdr_mask`,
and `bh_mask`; `tfce_mask` is optional. Column order may vary. An absent TFCE
column produces no dictionary entry, so unavailable results remain distinct
from an available mask with no passing vertices. TFCE without BH is rejected.

`read_map_masks(..., require_bh=False)` additionally accepts the legacy schema
with just IDs, statistics, and FDR. The existing `read_map` interface uses this
compatibility mode: it returns statistics, or `(values, fdr_mask)` when
`with_mask=True`. Catalog preparation generates unthresholded maps and every supported supplied
mask variant. The dashboard currently loads/displays only unthresholded and FDR
maps; BH/TFCE display controls remain future work.

All supplied masks must contain only 0 or 1, even when the caller requests only
statistics. Duplicate/unknown/missing columns, wrong row widths/counts, invalid
vertex IDs, nonnumeric data, infinite/all-missing statistics, and statistics
outside float32 range are rejected. Blank statistic fields remain NaN.

The reader retains the established transformation: sort rows by explicit vertex
ID, convert statistics to float32 for the viewer, and represent binary masks as
Boolean arrays in the same order. Mask membership is preserved independently of
statistic missingness; no mask is applied during reading. There is no
normalization, threshold recomputation, or geometry change. Applying FDR during
asset preparation continues to replace failing statistics with NaN. Synthetic
regression tests cover reordered columns/rows, missing values, independent masks,
invalid inputs, and unchanged serialized FDR/unthresholded viewer inputs across
all three supported schemas.

## Full replacement build

```sh
uv run python -m scripts.prepare_stat_maps --source /path/to/replacement-csvs --output notes/stat-rebuild
```

The output directory must not already exist. Preparation copies and validates
all CSVs, including incomplete groups, requiring BH for this replacement path.
It builds `data/catalog.json` and all supported variants under `data/stat_maps/`
from complete, eligible hemisphere pairs. Every GIFTI is freshly encoded, even
when its bytes and content-based filename match a previous release. Geometry
and convexity assets are outside this statistics-only rebuild.

Before reporting success, preparation verifies source and asset checksums,
decodes every GIFTI, compares its values and NaN positions to the source mask,
and checks catalog mask coverage/counts and the exact asset inventory. No mask
method or threshold is recomputed. TFCE availability is tracked per hemisphere.

Activate only the validated build: preserve the previous source directory,
statistical-map directory and catalog for recovery; replace the sources and
maps, then the catalog. Preserve this README when replacing the map directory.
This local activation is separate from publishing a deployment. The November 9
replacement contains 702 source CSVs and 346 eligible complete pairs, producing
692 unthresholded, 692 FDR, 692 BH and four TFCE GIFTIs. Shared source geometry
and the convexity background were not regenerated.

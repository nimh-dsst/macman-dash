# Precomputed hemisphere statistical maps

This directory contains 1,384 scalar GIFTIs for 346 human ROIs, each with maps
for both NHP hemispheres. The dashboard loads these prepared files directly;
source CSVs are not required to run it.

## File contents

Each human ROI has four files: two variants for each NHP hemisphere.

- `<ROI>.<lh|rh>.unthresholded.<hash>.shape.gii`: original float32 `mean_subj_acc`.
- `<ROI>.<lh|rh>.fdr.<hash>.shape.gii`: the same values where `fdr_mask == 1`, NaN elsewhere.

`<ROI>` identifies the human parcel, including its `L_` or `R_` prefix;
`lh` or `rh` identifies the NHP hemisphere receiving the map.
Each file contains 40,962 values in ascending source vertex-ID order.
Missing source values remain NaN. If no vertices pass FDR, the masked file
contains only NaNs.

## Catalog and related assets

The [catalog](../catalog.json) lists active file paths, full SHA-256 checksums,
unmasked value ranges, and finite/missing/FDR-passing counts. Filename hash
fragments identify file contents. Use catalog references to identify deployment
assets rather than including every file found in this directory.

Only complete exact-name NHP hemisphere pairs are included.
`excluded_incomplete_pairs` lists groups missing one NHP hemisphere file;
unsupported source groups are omitted from the catalog.

Surface meshes and the two shared convexity GIFTIs are stored separately in
`data/surfaces/` and are not included in the 1,384-file count above. See
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
`with_mask=True`. Catalog preparation still generates only the unthresholded
and FDR variants described above. Reading BH/TFCE does not generate their assets
or expose new dashboard controls.

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

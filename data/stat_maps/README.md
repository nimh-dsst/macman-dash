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

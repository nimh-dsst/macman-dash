# Glasser ROI full-name lookup

`glasser_roi_names.tsv` contains all 180 cortical parcels from Supplemental
Table 1 (pages 81–85) of the Neuroanatomical Supplementary Results for
Glasser et al., *A Multi-modal Parcellation of Human Cerebral Cortex* (2016).

[Source PDF](https://www.humanconnectome.org/storage/app/media/documentation/AABC2/AreaNamesAndIndices%20-%20NIHMS68870-supplement-Neuroanatomical_Supplementary_Results.pdf)

Extracted October 5, 2026. Source PDF SHA-256:
`cc290c80a80047870711273096646fc0d666afc85b38fab6d808334fa95b096e`.

Columns:

- `parcel_index`: the paper's index, 1–180; not the CSV source identifier.
- `abbreviation`: key matching the local annotations without hemisphere prefix
  or `_ROI` suffix. The same lookup applies to both hemispheres.
- `long_name`: the paper's Area Description, with whitespace normalized.
- `source_abbreviation`: spelling in the paper.
- `source_page`: one-based PDF page number.

All 180 indices and abbreviation keys were checked against both local
`HCP-MMP1.annot` files. Background is excluded; join by abbreviation rather
than assuming a zero-based row position is a parcel index.

Extraction notes:

- The paper uses `7Pl` at index 46; the annotations use `7PL`. Both spellings
  are retained in separate columns.
- Wrapped `p9-46v` and `a9-46v` abbreviations were rejoined.
- PIT's description continues onto page 82; its complete name is
  `Posterior InferoTemporal Complex`.
- Line-wrapped `TemporoParietoOccipital` was rejoined for TPOJ1–3.
- Source capitalization and wording are preserved, including `Pirform Cortex`
  for Pir. Some descriptions remain brief, such as `Area 55b`; no expansions
  were invented.

This lookup adds descriptive metadata only. It does not modify the annotations,
vertex assignments, statistical values, or dashboard dropdown labels. The
selected ROI’s long name is displayed above the human atlas figure.

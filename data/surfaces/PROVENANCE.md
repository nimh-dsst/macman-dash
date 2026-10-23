# Surface and atlas provenance

## Included assets

| Files | Source | Contents |
|---|---|---|
| `infl_left.gii.gz`, `infl_right.gii.gz` | Nilearn full-resolution `fsaverage`; matches the distributed [archive](https://osf.io/svf8k/download) | Inflated human surfaces, 163,842 vertices per hemisphere |
| `lh.HCP-MMP1.annot`, `rh.HCP-MMP1.annot` | Supplied HCP-MMP1 annotations from the example-data `glasser_surface` folder; original upstream download unverified | 180 cortical parcels plus background per hemisphere |
| `lh.gray_surface.inf_300.rsl.gii`, `rh.gray_surface.inf_300.rsl.gii` | Supplied `NMT_v2.1_asym_surfaces` dataset | Inflated NHP gray surfaces, 40,962 vertices per hemisphere |
| `lh.gray_conv.csv`, `rh.gray_conv.csv` | Same supplied NMT dataset | Per-vertex convexity values for anatomical folding shading |
| `lh.curvature.shape.gii`, `rh.curvature.shape.gii` | Derived from the corresponding `gray_conv.csv` files | Raw convexity values cast to float32; no smoothing, clipping, or sign reversal |

Original asset hashes are in [checksums.json](checksums.json). Derived background
hashes, source ranges, and display limits are in [curvature.json](curvature.json).
“Curvature” is a legacy filename; the supplied measure is labeled convexity,
not a separately verified mean-curvature or sulcal-depth measure.

## Visualization changes

- Human and NHP meshes retain source coordinates and vertex/face ordering;
  the viewer frames each hemisphere. NHP meshes load from the original GIFTI
  paths through ipyniivue, without Python geometry decoding or re-encoding.
  Human geometry is read by NiBabel and encoded as MZ3 with atlas colors,
  preserving source coordinates. No translation, rotation, scaling, resampling,
  or smoothing is applied by the dashboard. Scalar overlays attach by vertex
  index. Source files are unchanged.
- Human annotations are decoded into opaque MZ3 vertex colors. Selection adds
  an outline and fades other parcels; source annotations are not rewritten.
  Corresponding left/right parcel RGB values differ, but labels and indices align.
- Convexity uses native grayscale with per-hemisphere display limits, background
  opacity 1, and Phong lighting. Display mapping changes appearance, not stored
  values. See [implementation details](../../docs/implementation.md) and
  [viewer compatibility](../../docs/compatibility.md#human-annotation-handling).

## Attribution and unresolved provenance

Full Glasser ROI names and their published source are documented in the
[ROI-name source notes](../atlases/glasser_roi_names_source.md).
The original annotation download, origin of its hemisphere color differences,
and exact NHP surface/convexity generation commands remain unverified.
Matching vertex counts alone does not establish registration to statistical maps.
Redistribution terms and required citations for third-party assets must be
verified separately from permission to publish the statistical GIFTIs.

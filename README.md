# MACMAN Dashboard

An interactive marimo + ipyniivue dashboard linking Glasser HCP-MMP1
parcels to statistical maps on left and right NHP inflated surfaces.

## Quick start: run the prepared dashboard

Requires Python 3.13+ and `uv`. From the repository root run the following and open the local URL printed by marimo:

```bash
uv run marimo run dashboard.py
```

To edit the notebook instead:

```bash
uv run marimo edit dashboard.py
```

## Using the dashboard

- Select a hemisphere and ROI to display its maps in both NHP panels.
  The selected atlas parcel is outlined in black.
- **Only ROIs with BH results** filters the ROI list; **Apply supplied BH mask**
  independently controls the masked display. Outside-mask colors can remain
  visible at reduced opacity. Both controls start off; BH is the sole displayed
  masking method, using the supplied `bh_mask` without recomputation.
- Only ROIs with both NHP hemisphere files are selectable.
- Maps use **viridis** colors at **0.7 opacity**, allowing the grayscale
  anatomical folding background to show through.
- **Selected map min–max** (default) adjusts the color scale to the selected
  ROI’s values across both NHP hemispheres. The scale changes when you select
  another ROI. Choose **Across all ROIs** to keep the scale fixed, so the same
  color represents the same value across ROI selections.
- Rotate and zoom each figure independently. Use **Medial** under NHP views
  to see both inner surfaces. Camera reset restores the chosen preset and zoom.
- Surfaces retain their source coordinates; the viewer handles framing.
- **Reset selection** clears statistical maps and human highlighting while
  preserving cameras and display settings.

## Export for static hosting

From the repository root:

```bash
uv run python -m scripts.prepare_wasm_assets
uv run marimo export html-wasm dashboard.py -o site --mode run
python -m http.server --bind 127.0.0.1 --directory site
```

Open <http://127.0.0.1:8000/>. The preparation step copies only required runtime
assets into `public/`; marimo packages the app and local Python modules into
`site/`. Both generated directories are Git-ignored. The browser downloads shared
assets at startup and statistical maps when selected, reusing files within the
session. Internet access is needed for runtime/package downloads.

For GitHub Pages, select **Settings → Pages → Build and deployment → Source:
GitHub Actions** in the repository. The [Pages workflow](.github/workflows/pages.yml)
runs the reusable [CI workflow](.github/workflows/ci.yml), then prepares assets,
exports the app, and deploys `site/` only if checks pass. It runs on pushes to
`main` and can also be started from the Actions tab. CI runs independently on
pull requests to `main`. Generated files are published
as an artifact; they are not committed to a branch. The deployment job reports
the resulting site URL.

## Development

```bash
uv run python -m pytest -q
uv run ruff check macman dashboard.py tests
uv run marimo check dashboard.py
# With the app running on port 2718 and Chrome installed:
uv run python tests/browser_smoke.py
```

Edit runtime dependencies in `pyproject.toml`, then synchronize the notebook's
PEP 723 metadata for molab:

```bash
uv run python scripts/sync_notebook_dependencies.py
# Detect metadata drift:
uv run python scripts/sync_notebook_dependencies.py --check
```

Source CSV preparation accepts named FDR/BH mask columns and optional TFCE.
`read_map_masks` requires BH by default for replacement-data validation; the
existing `read_map` interface also accepts legacy FDR-only files. Preparation
generates unthresholded maps and every supplied supported mask variant;
dashboard controls use BH. See the
[CSV reader contract](data/stat_maps/README.md#source-csv-reader) for details.

To build a full replacement statistical collection in a fresh directory:

```bash
uv run python -m scripts.prepare_stat_maps --source /path/to/replacement-csvs --output notes/stat-rebuild
```

This copies and validates all sources, regenerates every applicable GIFTI, and
checks saved values and masks before activation. See the
[replacement build procedure](data/stat_maps/README.md#full-replacement-build).

To check a fresh standard WASM export in Chrome at both hosting paths:

```bash
.venv/bin/python tests/standard_wasm.py --site site
.venv/bin/python tests/standard_wasm.py --site site --prefix /macman-dash
```

These checks serve static files locally, download browser runtime dependencies,
and exercise BH controls, rendering, filtering, and on-demand asset reuse.
Reports/screenshots are saved under `notes/bh-wasm-validation/` by default.

## Further documentation

- [Compatibility notes](docs/compatibility.md): viewer adaptations, testing, and maintenance details.
- [Implementation](docs/implementation.md): behavior, defaults, and architecture.
- [Statistical assets](data/stat_maps/README.md): GIFTI layout and catalog metadata.
- [Surface provenance](data/surfaces/PROVENANCE.md): source meshes and convexity background.

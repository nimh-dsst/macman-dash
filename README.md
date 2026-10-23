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
- **Only ROIs with FDR results** filters the ROI list; **Apply supplied FDR mask**
  independently controls the masked display. Outside-mask colors can remain
  visible at reduced opacity.
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

## Further documentation

- [Compatibility notes](docs/compatibility.md): viewer adaptations, testing, and maintenance details.
- [Implementation](docs/implementation.md): behavior, defaults, and architecture.
- [Statistical assets](data/stat_maps/README.md): GIFTI layout and catalog metadata.
- [Surface provenance](data/surfaces/PROVENANCE.md): source meshes and convexity background.

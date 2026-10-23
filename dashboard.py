# /// script
# # Generated from pyproject.toml; run scripts/sync_notebook_dependencies.py
# requires-python = ">=3.13"
# dependencies = [
#     "ipyniivue==2.4.4",
#     "marimo==0.25.2",
#     "nibabel>=5.3,<6",
#     "numpy>=2,<3",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full", app_title="MACMAN Dashboard")


@app.cell
async def _():
    import json
    import sys

    import marimo as mo

    from macman.assets import INITIAL_ASSETS, ensure_assets
    from macman.colors import (
        DEFAULT_PALETTE_LABEL,
        PALETTES,
        RANGE_MODES,
        display_range,
    )
    from macman.data import ROOT, load_roi_names, load_stat_assets
    from macman.selection import region_options, resolve_roi
    from macman.viewer import (
        DEFAULT_MAP_OPACITY,
        create_viewers,
        nhp_camera_angles,
        replace_map,
    )

    asset_base = (
        str(mo.notebook_location() / "public") if sys.platform == "emscripten" else None
    )
    await ensure_assets(INITIAL_ASSETS, asset_base)

    return (
        asset_base,
        ensure_assets,
        DEFAULT_PALETTE_LABEL,
        DEFAULT_MAP_OPACITY,
        PALETTES,
        RANGE_MODES,
        display_range,
        ROOT,
        create_viewers,
        nhp_camera_angles,
        json,
        load_stat_assets,
        load_roi_names,
        mo,
        region_options,
        replace_map,
        resolve_roi,
    )


@app.cell
def _(load_roi_names):
    roi_long_names = load_roi_names()
    return (roi_long_names,)


@app.cell
def _(ROOT, json, mo):
    mo.stop(
        not (ROOT / "data/catalog.json").exists(),
        mo.callout(
            "Data catalog missing. Run `uv run python -m macman.data`, then restart.",
            kind="warn",
        ),
    )
    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    mo.stop(
        catalog.get("schema_version") != 3,
        mo.callout(
            "Precomputed maps required. Run `uv run python -m macman.data`, then restart.",
            kind="warn",
        ),
    )
    return (catalog,)


@app.cell
def _(DEFAULT_PALETTE_LABEL, PALETTES, mo):
    hemisphere = mo.ui.radio(
        ["Left", "Right"], value="Left", label="Human hemisphere", inline=True
    )
    palette = mo.ui.dropdown(
        PALETTES,
        value=DEFAULT_PALETTE_LABEL,
        label="Colormap",
        full_width=True,
    )
    apply_fdr = mo.ui.switch(value=False, label="Apply supplied FDR mask")
    only_fdr = mo.ui.checkbox(value=False, label="Only ROIs with FDR results")
    camera = mo.ui.dropdown(
        ["Lateral", "Medial", "Dorsal", "Ventral"],
        value="Lateral",
        label="NHP views (both hemispheres)",
        full_width=True,
    )
    reset = mo.ui.run_button(label="Reset NHP cameras")
    human_camera = mo.ui.dropdown(
        ["Lateral", "Medial", "Dorsal", "Ventral"],
        value="Lateral",
        label="Human camera",
        full_width=True,
    )
    human_reset = mo.ui.run_button(label="Reset human camera")
    atlas_context_opacity = mo.ui.slider(
        0,
        1,
        step=0.05,
        value=0.4,
        label="Other ROI color opacity",
        show_value=True,
        debounce=True,
        full_width=True,
    )
    return (
        apply_fdr,
        atlas_context_opacity,
        camera,
        hemisphere,
        human_camera,
        human_reset,
        palette,
        only_fdr,
        reset,
    )


@app.cell
def _(mo, DEFAULT_MAP_OPACITY):
    get_map_opacity, set_map_opacity = mo.state(DEFAULT_MAP_OPACITY)
    get_mask_context, set_mask_context = mo.state(0.25)
    return get_map_opacity, set_map_opacity, get_mask_context, set_mask_context


@app.cell
def _(
    apply_fdr, get_map_opacity, get_mask_context, mo, set_map_opacity, set_mask_context
):
    opacity = mo.ui.slider(
        0,
        1,
        step=0.05,
        value=get_mask_context() if apply_fdr.value else get_map_opacity(),
        label="Outside-mask opacity" if apply_fdr.value else "Map opacity",
        show_value=True,
        debounce=True,
        full_width=True,
        on_change=set_mask_context if apply_fdr.value else set_map_opacity,
    )
    return (opacity,)


@app.cell
def _(mo):
    get_range_mode, set_range_mode = mo.state("local")
    return get_range_mode, set_range_mode


@app.cell
def _(RANGE_MODES, get_range_mode, mo, set_range_mode):
    range_mode = mo.ui.dropdown(
        RANGE_MODES,
        value=next(
            label for label, mode in RANGE_MODES.items() if mode == get_range_mode()
        ),
        label="Color range",
        full_width=True,
        on_change=set_range_mode,
    )
    return (range_mode,)


@app.cell
def _(mo):
    get_region, set_region = mo.state(None)
    return get_region, set_region


@app.cell
def _(mo, set_region):
    reset_selection = mo.ui.button(
        label="Reset selection",
        on_click=lambda _: set_region(None),
    )
    return (reset_selection,)


@app.cell
def _(catalog, get_region, hemisphere, mo, only_fdr, region_options, set_region):
    _options = region_options(catalog["rois"], hemisphere.value, only_fdr.value)
    requested_region = get_region()
    _initial = next(
        (label for label, value in _options.items() if value == requested_region), None
    )
    roi = mo.ui.dropdown(
        options=_options,
        value=_initial,
        label="Human ROI",
        searchable=True,
        full_width=True,
        on_change=set_region,
    )
    return requested_region, roi


@app.cell
def _(create_viewers, mo):
    try:
        atlas_viewer, result_viewers, atlas_display, result_meshes, curvature_data = (
            create_viewers()
        )
        initialization_error = None
    except (ValueError, OSError) as exc:
        initialization_error = str(exc)
    mo.stop(
        initialization_error is not None,
        mo.callout(
            f"Surface initialization failed: {initialization_error}", kind="danger"
        ),
    )
    left_nhp_ui = mo.ui.anywidget(result_viewers["lh"])
    right_nhp_ui = mo.ui.anywidget(result_viewers["rh"])
    atlas_ui = mo.ui.anywidget(atlas_viewer)
    return (
        atlas_display,
        atlas_ui,
        atlas_viewer,
        result_meshes,
        curvature_data,
        result_viewers,
        left_nhp_ui,
        right_nhp_ui,
    )


@app.cell
def _(atlas_context_opacity, atlas_display, hemisphere, selected_roi):
    atlas_note = atlas_display.update(
        hemisphere.value, selected_roi, "Black outline", atlas_context_opacity.value
    )
    return (atlas_note,)


@app.cell
def _(atlas_viewer, hemisphere, human_camera, human_reset):
    if human_reset.value:
        atlas_viewer.scene.vol_scale_multiplier = 1.0
    _azimuth, _elevation = {
        "Dorsal": (0, 90),
        "Ventral": (0, -90),
        "Lateral": (90 if hemisphere.value == "Left" else 270, 0),
        "Medial": (270 if hemisphere.value == "Left" else 90, 0),
    }[human_camera.value]
    atlas_viewer.set_render_azimuth_elevation(_azimuth, _elevation)


@app.cell
def _(camera, nhp_camera_angles, reset, result_viewers):
    for _side, _viewer in result_viewers.items():
        if reset.value:
            _viewer.scene.vol_scale_multiplier = 1.0
        _viewer.set_render_azimuth_elevation(*nhp_camera_angles(_side, camera.value))


@app.cell
async def _(
    asset_base, catalog, ensure_assets, hemisphere, load_stat_assets, resolve_roi, roi
):
    selected_roi = resolve_roi(catalog["rois"], hemisphere.value, roi.value)
    selected_entry = catalog["rois"].get(selected_roi)
    map_error = None
    stat_assets = None
    if selected_entry:
        try:
            await ensure_assets(
                [
                    info["path"]
                    for variant in selected_entry["assets"].values()
                    for info in variant.values()
                ],
                asset_base,
            )
            stat_assets = load_stat_assets(selected_entry)
        except (ValueError, OSError) as exc:
            map_error = str(exc)
    return map_error, selected_entry, selected_roi, stat_assets


@app.cell
def _(catalog, display_range, range_mode, selected_entry, stat_assets):
    # Metadata uses the original unmasked values, regardless of FDR setting.
    _range = selected_entry["value_range"] if stat_assets is not None else None
    color_limits = display_range(range_mode.value, catalog["range"], _range)
    return (color_limits,)


@app.cell
def _(selected_entry, stat_assets):
    passing_vertices = (
        selected_entry["passing_vertices"] if stat_assets is not None else 0
    )
    displayed_data = None
    if stat_assets is not None:
        displayed_data = stat_assets["unthresholded"]
    return displayed_data, passing_vertices


@app.cell
def _(
    apply_fdr,
    catalog,
    color_limits,
    displayed_data,
    opacity,
    palette,
    replace_map,
    result_meshes,
    curvature_data,
    selected_entry,
    stat_assets,
):
    # Both panels use bilateral unmasked limits, including when one mask is empty.
    for _side, _mesh in result_meshes.items():
        _count = (
            selected_entry["hemisphere_counts"][_side]["finite"]
            if displayed_data is not None
            else 0
        )
        if _count:
            replace_map(
                _mesh,
                displayed_data[_side],
                color_limits[1],
                palette.value,
                opacity.value,
                signed=catalog["range"][0] < 0,
                minimum=color_limits[0],
                curvature_data=curvature_data[_side],
                mask_data=(
                    stat_assets["fdr"][_side]
                    if apply_fdr.value
                    and selected_entry["hemisphere_counts"][_side]["passing"]
                    else None
                ),
            )
        else:
            replace_map(
                _mesh,
                None,
                color_limits[1],
                palette.value,
                0,
                curvature_data=curvature_data[_side],
            )


@app.cell
def _(
    apply_fdr,
    passing_vertices,
    atlas_context_opacity,
    atlas_note,
    atlas_ui,
    camera,
    catalog,
    color_limits,
    range_mode,
    hemisphere,
    human_camera,
    human_reset,
    map_error,
    mo,
    opacity,
    only_fdr,
    palette,
    reset,
    reset_selection,
    requested_region,
    roi,
    selected_entry,
    selected_roi,
    roi_long_names,
    stat_assets,
    left_nhp_ui,
    right_nhp_ui,
):
    _low, _high = color_limits
    _atlas_keys = {f"{side}_{label}" for side in ("L", "R") for label in roi_long_names}
    _excluded_keys = set(catalog["excluded_incomplete_pairs"])
    _csv_keys = set(catalog["rois"]) | _excluded_keys
    _absent_atlas_keys = sorted(_atlas_keys - _csv_keys)
    _partial_atlas_keys = _atlas_keys & _excluded_keys
    _unavailable_atlas_count = len(_absent_atlas_keys) + len(_partial_atlas_keys)
    _human_title = f"{hemisphere.value} hemisphere · HCP-MMP1"
    if selected_roi is not None:
        _abbreviation = selected_roi[2:]
        _long_name = roi_long_names.get(
            _abbreviation, f"{_abbreviation} (full name unavailable)"
        )
        _human_title += f" · {_long_name}"
    _status = mo.md("Choose a human ROI to display its bilateral macaque result.")
    if map_error:
        _status = mo.callout(
            f"Could not load the selected map: {map_error}. No statistical map is displayed. Select another ROI or rebuild the catalog and restart.",
            kind="danger",
        )
    elif stat_assets is not None:
        _status = mo.md(f"**{selected_roi}**")
        if apply_fdr.value and passing_vertices:
            _status = mo.vstack(
                [
                    _status,
                    mo.md(
                        f"{passing_vertices:,} finite vertices pass the supplied FDR mask."
                    ),
                ]
            )
        if selected_entry["identical_hemispheres"]:
            _status = mo.vstack(
                [
                    _status,
                    mo.callout(
                        "The supplied left and right maps are identical.", kind="warn"
                    ),
                ]
            )
    elif requested_region is not None:
        _requested_key = f"{hemisphere.value[0]}_{requested_region}"
        _filtered_out = only_fdr.value and _requested_key in catalog["rois"]
        _status = mo.callout(
            (
                f"{requested_region} has no FDR results for the {hemisphere.value.lower()} human hemisphere. "
                "Choose another ROI or turn off the FDR-results filter. No statistical map is displayed."
                if _filtered_out
                else f"{requested_region} is unavailable for the {hemisphere.value.lower()} human hemisphere. "
                "Choose another ROI or switch hemispheres. No statistical map is displayed."
            ),
            kind="warn",
        )
    # Public layout/style APIs only; inline styles also travel with WASM exports.
    _font = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    _control_style = {
        "padding": "12px",
        "background": "#f4f7fb",
        "border": "1px solid #e2e8f0",
        "border-radius": "10px",
        "min-width": "0",
        "box-sizing": "border-box",
    }
    _panel_style = {
        "padding": "12px",
        "border": "1px solid #e2e8f0",
        "border-radius": "12px",
        "background": "#ffffff",
        "min-width": "0",
        "box-sizing": "border-box",
    }
    # Keep absolute-positioned viewer errors inside their own figure.
    _viewer_style = {
        "position": "relative",
        "border-radius": "8px",
        "overflow": "hidden",
    }
    _secondary_style = {"font-size": "0.8rem", "color": "#526277"}
    _controls = mo.hstack(
        [
            mo.vstack(
                [
                    hemisphere,
                    mo.hstack(
                        [roi, reset_selection], widths=[3, 2], align="end", gap=0.5
                    ),
                    only_fdr,
                ],
                gap=0.5,
            ).style(_control_style),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            range_mode,
                            mo.md(f"**Color limits:** {_low:.4f} to {_high:.4f}").style(
                                _secondary_style
                            ),
                        ],
                        gap=0.25,
                    ),
                    palette,
                    mo.vstack([opacity, apply_fdr], gap=0.5),
                ],
                widths=[1, 1, 1],
                align="start",
                gap=1,
            ).style(_control_style),
        ],
        widths=[1, 2],
        align="start",
        gap=1,
    )
    _title_style = {
        "height": "2.75rem",
        "overflow-y": "auto",
        "font-size": "0.85rem",
        "line-height": "1.4",
        "color": "#334155",
    }
    _heading_style = f"margin:0;font-family:{_font};font-size:1.05rem;font-weight:650;line-height:1.4;color:#17263b"
    _nhp_title_style = {
        "min-height": _title_style["height"],
        "font-size": _title_style["font-size"],
        "line-height": _title_style["line-height"],
        "color": _title_style["color"],
    }
    _nhp_titles = {}
    for _side, _name in (("lh", "Left"), ("rh", "Right")):
        _title_parts = [
            mo.Html(f"<div><strong>{_name} NHP hemisphere · NMT</strong></div>")
        ]
        if (
            stat_assets is not None
            and selected_entry["hemisphere_counts"][_side]["passing"] == 0
        ):
            _title_parts.append(
                mo.Html("<div>No vertices pass the supplied FDR mask.</div>").style(
                    {"font-size": "0.8rem", "color": "#9c4200"}
                )
            )
        _nhp_titles[_side] = mo.vstack(_title_parts, gap=0).style(_nhp_title_style)
    _human_panel = mo.vstack(
        [
            mo.Html(f'<h2 style="{_heading_style}">Human Glasser atlas</h2>'),
            mo.md(f"**{_human_title}**").style(_title_style),
            atlas_ui.style(_viewer_style),
            mo.hstack([human_camera, human_reset], align="end", gap=0.5),
            atlas_context_opacity,
            mo.callout(atlas_note, kind="warn") if atlas_note else mo.md(""),
        ],
        gap=0.5,
    ).style(_panel_style)
    _nhp_panel = mo.vstack(
        [
            mo.Html(f'<h2 style="{_heading_style}">NHP statistical maps</h2>'),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            _nhp_titles["lh"],
                            left_nhp_ui.style(_viewer_style),
                        ],
                        gap=0.5,
                    ),
                    mo.vstack(
                        [
                            _nhp_titles["rh"],
                            right_nhp_ui.style(_viewer_style),
                        ],
                        gap=0.5,
                    ),
                ],
                widths=[1, 1],
                align="start",
                gap=1,
            ),
            mo.hstack([camera, reset], align="end", justify="start", gap=0.5),
            _status.style(_secondary_style),
        ],
        gap=0.5,
    ).style(_panel_style)
    mo.vstack(
        [
            mo.Html(
                f'<h1 style="margin:0 0 4px;font-family:{_font};font-size:1.5rem;'
                "font-weight:700;letter-spacing:-0.025em;line-height:1.3;"
                'color:#17263b">MACMAN Dashboard</h1>'
            ),
            _controls,
            mo.hstack([_human_panel, _nhp_panel], widths=[1, 2], align="start", gap=1),
            mo.md("Drag each brain to rotate; scroll to zoom.").style(_secondary_style),
            mo.accordion(
                {
                    "Data and display notes · Development preview": mo.md(
                        "**Human:** Glasser / HCP-MMP1 on inflated fsaverage. "
                        "**Macaque:** NMT v2.1 asymmetric inflated surfaces. "
                        "Grayscale folding background comes from the supplied gray-convexity maps. "
                        "\n\n**Map coverage:** 4,779 vertices have no supplied statistic across all available maps and appear as neutral surface. "
                        f"\n\n**CSV coverage:** {len(_excluded_keys)} incomplete CSV filename groups are excluded: "
                        + ", ".join(catalog["excluded_incomplete_pairs"])
                        + ". "
                        f"\n\n**Atlas coverage (exact-name matching):** {_unavailable_atlas_count} of {len(_atlas_keys)} Glasser ROIs lack a complete NHP pair: "
                        f"{len(_partial_atlas_keys)} have one NHP file; {len(_absent_atlas_keys)} have neither file under the exact atlas name: "
                        + ", ".join(_absent_atlas_keys)
                        + ". "
                        "\n\n"
                        "Built with [marimo](https://docs.marimo.io/) and [ipyniivue](https://niivue.github.io/ipyniivue/)."
                    ),
                }
            ),
        ],
        gap=0.75,
    ).style({"font-family": _font, "color": "#17263b"})


if __name__ == "__main__":
    app.run()

"""Local feedback figures using production map-layer configuration and built-in shaders.

Run: PYTHONPATH=. .venv/bin/python tests/stats_display_comparison.py
Add --background-only for the matching four-choice figure without statistics.
Add --feedback-only to assemble two clean option-B sheets from saved captures.
Add --nilearn-feedback for two Nilearn-background-matched sheets (saved brightness fixture).
Add --native-feedback for raw convexity with native gray/color limits only.
The test-only constructor export bypasses widget transport, as in the convexity
probe. Uses existing compatibility fixes; registers no custom shader.
"""

import base64
import json
import sys

import nibabel as nib
import numpy as np
from convexity_comparison import uri
from playwright.sync_api import sync_playwright

from macman.colors import DEFAULT_PALETTE, display_range
from macman.compat import patched_esm
from macman.data import (
    ROOT,
    CurvatureAsset,
    curvature_brightness,
    load_stat_assets,
    read_curvature_values,
    scalar_bytes,
    surface_bytes,
)
from macman.layers import ResultMesh
from macman.viewer import DEFAULT_MAP_OPACITY, nhp_camera_angles, replace_map

OUT = ROOT / "notes/validation"
CHOICES = [
    ("A · Current soft / Phong", "soft", "Phong"),
    ("B · Full range / Phong", "full", "Phong"),
    ("C · Full range / Matte", "full", "Matte"),
    ("D · Full range / Flat", "full", "Flat"),
]


def layers_for(entry, assets, side, background, fdr, limits):
    mesh = ResultMesh(
        path=str(ROOT / f"data/surfaces/{side}.gray_surface.inf_300.rsl.gii")
    )
    replace_map(
        mesh,
        assets["unthresholded"][side] if assets is not None else None,
        limits[1],
        DEFAULT_PALETTE,
        0.25 if fdr else DEFAULT_MAP_OPACITY,
        minimum=limits[0],
        mask_data=assets["fdr"][side]
        if fdr and entry["hemisphere_counts"][side]["passing"]
        else None,
        curvature_data=CurvatureAsset(background, (0, 1)),
    )
    layers = []
    for layer in mesh.layers:
        layers.append(
            {
                "url": uri(layer.data),
                "name": layer.name,
                "colormap": layer.colormap,
                "cal_min": layer.cal_min,
                "cal_max": layer.cal_max,
                "opacity": layer.opacity,
                "outlineBorder": layer.outline_border,
                "colorbarVisible": layer.colorbar_visible,
                "useNegativeCmap": layer.use_negative_cmap,
            }
        )
        layer.close()
    mesh.close()
    return layers


def figure_html(key, fdr, limits, panels):
    details = (
        "FDR on · passing opacity 0.8 · context opacity 0.25 · black boundaries"
        if fdr
        else "FDR off · statistical map opacity 0.8"
    )
    heading = f"NHP display options · human {key}"
    subtitle = (
        f"{details}<br>Viridis · selected-map bilateral limits {limits[0]:.4f}–{limits[1]:.4f}"
        " · same statistics, geometry, cameras and opacity across columns"
    )
    if key is None:
        heading = "NHP convexity background · no statistical maps"
        subtitle = (
            "Same inflated surfaces and camera views as the statistical comparison sheets"
            "<br>Convexity opacity 1 · no statistical layers or colorbars · built-in shading only"
        )
    return (
        """<!doctype html><html lang="en"><meta charset="utf-8"><title>NHP display options</title><style>
body{margin:0;background:white;color:#17263b;font:16px system-ui}main{width:1800px;padding:24px;box-sizing:border-box}h1{font-size:26px;margin:0 0 8px}p{color:#526277;margin:0 0 14px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}h2{font-size:16px;line-height:1.4;margin:0 0 6px}img{display:block;width:100%;border-radius:8px}footer{font-size:14px;line-height:1.5;margin-top:18px;color:#526277}
</style><main>"""
        + f'<h1>{heading}</h1><p>{subtitle}</p><div class="grid">'
        + "".join(panels)
        + """</div><footer>A: current convexity brightness 0.45–0.75. B–D: full brightness 0–1. Both mappings use the shared bilateral source range; no clipping or added smoothing.<br>All shaders are built into the installed NiiVue. Matte removes shiny highlights; Flat remains lit. These are local candidate renders, not changes to dashboard defaults.</footer></main></html>"""
    )


def feedback_figures(context):
    """Reuse verified option-B captures without resampling their source data."""
    for source_name, output_name, heading, subtitle in (
        (
            "convexity-built-in-comparison-2026-10-13.html",
            "researcher-preview-convexity-2026-10-13",
            "NHP anatomical background",
            "Inflated NMT surfaces · Anatomical folding detail without statistical maps",
        ),
        (
            "stats-display-L_FST-unmasked-2026-10-13.html",
            "researcher-preview-FST-2026-10-13",
            "NHP statistical maps · human left FST",
            "Mean accuracy · FDR mask off · Shared color scale across both NHP hemispheres",
        ),
    ):
        page = context.new_page()
        page.set_content((OUT / source_name).read_text())
        panels = (
            page.locator("section")
            .filter(has_text="B · Full range / Phong")
            .evaluate_all(
                "sections => sections.map(s => ({label:s.querySelector('h2').innerText.split('\\n')[0],src:s.querySelector('img').src}))"
            )
        )
        assert len(panels) == 4
        assert [p["label"] for p in panels] == [
            "Left NHP · lateral",
            "Right NHP · lateral",
            "Left NHP · medial",
            "Right NHP · medial",
        ]
        images = "".join(
            f'<section><h2>{p["label"]}</h2><img src="{p["src"]}" alt="{p["label"]}"></section>'
            for p in panels
        )
        html = (
            '<!doctype html><html lang="en"><meta charset="utf-8"><title>'
            + heading
            + "</title>"
            "<style>body{margin:0;background:white;color:#17263b;font:15px system-ui}"
            "main{width:908px;padding:24px;box-sizing:border-box}h1{font-size:24px;margin:0 0 8px}"
            "p{margin:0 0 22px;color:#526277;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}"
            "h2{font-size:16px;margin:0 0 8px}img{display:block;width:100%;border-radius:8px}"
            "footer{margin-top:20px;color:#526277;font-size:13px}</style>"
            f'<main><h1>{heading}</h1><p>{subtitle}</p><div class="grid">{images}</div>'
            "<footer>Display preview with increased anatomical background contrast.</footer></main></html>"
        )
        target = OUT / output_name
        target.with_suffix(".html").write_text(html)
        page.set_viewport_size({"width": 908, "height": 1000})
        page.set_content(html)
        page.locator("img").evaluate_all(
            "images=>Promise.all(images.map(i=>i.decode()))"
        )
        page.screenshot(path=str(target.with_suffix(".png")), full_page=True)
        assert page.locator("img").count() == 4
        page.close()
        print(target.with_suffix(".png"), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    native_feedback = "--native-feedback" in sys.argv
    nilearn_feedback = "--nilearn-feedback" in sys.argv
    clean_feedback = native_feedback or nilearn_feedback
    feedback_prefix = "researcher-native" if native_feedback else "researcher-nilearn"
    background_only = "--background-only" in sys.argv
    if "--assemble-only" in sys.argv or "--feedback-only" in sys.argv:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                headless=True,
            )
            context = browser.new_context(
                viewport={"width": 1800, "height": 1100}, device_scale_factor=2
            )
            if "--feedback-only" in sys.argv:
                feedback_figures(context)
                browser.close()
                return
            for source in sorted(OUT.glob("stats-display-*-2026-10-13.html")):
                page = context.new_page()
                page.set_content(source.read_text())
                page.locator("img").evaluate_all(
                    "images=>Promise.all(images.map(i=>i.decode()))"
                )
                page.screenshot(path=str(source.with_suffix(".png")), full_page=True)
                page.close()
                print(source.with_suffix(".png"), flush=True)
            browser.close()
        return
    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    values = {
        s: read_curvature_values(ROOT / f"data/surfaces/{s}.gray_conv.csv")
        for s in ("lh", "rh")
    }
    low = min(v.min() for v in values.values())
    high = max(v.max() for v in values.values())
    backgrounds = {
        "soft": {
            s: scalar_bytes(curvature_brightness(v, (low, high)))
            for s, v in values.items()
        },
        "full": {s: scalar_bytes((v - low) / (high - low)) for s, v in values.items()},
    }
    if nilearn_feedback:
        with np.load(
            OUT / "nilearn-background-brightness-2026-10-15.npz"
        ) as brightness:
            backgrounds["nilearn"] = {
                s: scalar_bytes(brightness[s]) for s in ("lh", "rh")
            }
    if native_feedback:
        backgrounds["native"] = {s: scalar_bytes(v) for s, v in values.items()}
    choices = (
        [("Nilearn background / Phong", "nilearn", "Phong")]
        if nilearn_feedback
        else CHOICES
    )
    if native_feedback:
        choices = [("Native grayscale / Phong", "native", "Phong")]
    geometries = {}
    for side in ("lh", "rh"):
        pts, faces = nib.load(
            ROOT / f"data/surfaces/{side}.gray_surface.inf_300.rsl.gii"
        ).agg_data()
        pts = pts - (pts.min(axis=0) + pts.max(axis=0)) / 2
        geometries[side] = uri(surface_bytes(pts, faces))
    report = {"renders": [], "page_errors": [], "blocked_requests": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
            args=["--enable-webgl", "--use-gl=angle", "--use-angle=swiftshader"],
        )
        context = browser.new_context(
            viewport={"width": 1800, "height": 1100},
            device_scale_factor=2,
            service_workers="block",
        )

        def block(route):
            report["blocked_requests"].append(route.request.url)
            route.abort()

        context.route("http://**/*", block)
        context.route("https://**/*", block)
        page = context.new_page()
        page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
        page.set_content(
            '<div style="width:420px;height:320px"><canvas></canvas></div>'
        )
        page.evaluate(
            """async source => {
            const {PreviewNiivue}=await import(URL.createObjectURL(new Blob([source],{type:'text/javascript'})));
            window.nv=new PreviewNiivue({backColor:[0.035,0.055,0.09,1],fontColor:[0.85,0.89,0.94,1],crosshairColor:[0.65,0.72,0.8,1],showColorbarBorder:false,show3Dcrosshair:false,isColorbar:true});
            await nv.attachToCanvas(document.querySelector('canvas'));
        }""",
            patched_esm() + "\nexport {t2 as PreviewNiivue};",
        )
        cases = (
            [(None, False)]
            if background_only
            else [("L_FST", False), ("L_FST", True), ("L_V1", False)]
        )
        if clean_feedback:
            cases = [(None, False), ("L_FST", False)]
        for key, fdr in cases:
            entry = catalog["rois"][key] if key is not None else None
            assets = load_stat_assets(entry) if entry is not None else None
            limits = (
                display_range("local", catalog["range"], entry["value_range"])
                if entry is not None
                else (0, 1)
            )
            panels = []
            for view in ("Lateral", "Medial"):
                for side, word in [("lh", "Left NHP"), ("rh", "Right NHP")]:
                    for title, contrast, shader in choices:
                        layers = layers_for(
                            entry,
                            assets,
                            side,
                            backgrounds[contrast][side],
                            fdr,
                            limits,
                        )
                        if native_feedback:
                            # Match Nilearn's background brightness endpoints through
                            # native linear color limits, retaining raw scalar values.
                            vmin, vmax = (
                                float(values[side].min()),
                                float(values[side].max()),
                            )
                            floor = 94 / 255
                            layers[0]["cal_min"] = vmin - floor / (1 - floor) * (
                                vmax - vmin
                            )
                            layers[0]["cal_max"] = vmax
                        if clean_feedback and assets is not None:
                            layers[1]["opacity"] = 0.7
                        info = page.evaluate(
                            """async ({mesh,layers,shader,angles}) => {
                            await nv.loadMeshes([{url:mesh,name:'NMT.gii',rgba255:[195,204,216,255],layers}]);
                            const m=nv.meshes[0]; m.colorbarVisible=true;
                            m.layers.forEach((l,i)=>{l.outlineBorder=layers[i].outlineBorder;l.colorbarVisible=layers[i].colorbarVisible;l.useNegativeCmap=layers[i].useNegativeCmap;});
                            m.updateMesh(nv.gl); nv.setMeshShader(m.id,shader);
                            nv.setRenderAzimuthElevation(...angles); nv.updateGLVolume(); nv.drawScene();
                            return {shader:nv.meshShaderNames(false)[m.meshShaderIndex],layers:m.layers.map(l=>({opacity:l.opacity,minimum:l.cal_min,maximum:l.cal_max,border:l.outlineBorder,colorbar:l.colorbarVisible,vertices:l.values.length,finite:Array.from(l.values).filter(Number.isFinite).length}))};
                        }""",
                            {
                                "mesh": geometries[side],
                                "layers": layers,
                                "shader": shader,
                                "angles": nhp_camera_angles(side, view),
                            },
                        )
                        assert info["shader"] == shader and len(info["layers"]) == len(
                            layers
                        ), info
                        for i, (actual, expected) in enumerate(
                            zip(info["layers"], layers)
                        ):
                            assert (
                                actual["vertices"] == 40962
                                and actual["opacity"] == expected["opacity"]
                                and actual["border"] == expected["outlineBorder"]
                                and actual["colorbar"] == expected["colorbarVisible"]
                            ), actual
                            np.testing.assert_allclose(
                                [actual["minimum"], actual["maximum"]],
                                [expected["cal_min"], expected["cal_max"]],
                            )
                            count = (
                                40962
                                if i == 0
                                else entry["hemisphere_counts"][side][
                                    "passing" if i == 2 else "finite"
                                ]
                            )
                            assert actual["finite"] == count, actual
                        report["renders"].append(
                            {
                                "roi": key,
                                "fdr": fdr,
                                "side": side,
                                "view": view,
                                "choice": title,
                                **info,
                            }
                        )
                        page.wait_for_timeout(200)
                        encoded = base64.b64encode(
                            page.locator("canvas").screenshot()
                        ).decode()
                        panels.append(
                            f'<section><h2>{word} · {view.lower()}<br>{title}</h2><img src="data:image/png;base64,{encoded}"></section>'
                        )
            target = (
                OUT / "convexity-built-in-comparison-2026-10-13"
                if background_only
                else OUT
                / f"stats-display-{key}-{'fdr' if fdr else 'unmasked'}-2026-10-13"
            )
            html = figure_html(key, fdr, limits, panels)
            if clean_feedback:
                target = (
                    OUT
                    / f"{feedback_prefix}-{'FST' if key else 'convexity'}-2026-10-15"
                )
                heading = (
                    "NHP statistical maps · human left FST"
                    if key
                    else "NHP anatomical background"
                )
                subtitle = (
                    "Mean accuracy · FDR mask off · Shared color scale across both NHP hemispheres"
                    if key
                    else "Inflated NMT surfaces · Anatomical folding detail without statistical maps"
                )
                html = (
                    '<!doctype html><html lang="en"><meta charset="utf-8"><style>'
                    "body{margin:0;background:white;color:#17263b;font:15px system-ui}"
                    "main{width:908px;padding:24px;box-sizing:border-box}h1{font-size:24px;margin:0 0 8px}"
                    "p{margin:0 0 22px;color:#526277;line-height:1.5}"
                    ".grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}"
                    "h2{font-size:16px;margin:0 0 8px}img{display:block;width:100%;border-radius:8px}"
                    f'</style><main><h1>{heading}</h1><p>{subtitle}</p><div class="grid">'
                    + "".join(panels).replace("<br>" + choices[0][0], "")
                    + "</div></main></html>"
                )
            target.with_suffix(".html").write_text(html)
            figure = context.new_page()
            if clean_feedback:
                figure.set_viewport_size({"width": 908, "height": 850})
            figure.set_content(html)
            figure.locator("img").evaluate_all(
                "images=>Promise.all(images.map(i=>i.decode()))"
            )
            figure.screenshot(path=str(target.with_suffix(".png")), full_page=True)
            figure.close()
            print(target.with_suffix(".png"), flush=True)
        assert not report["page_errors"], report["page_errors"]
        assert not report["blocked_requests"], report["blocked_requests"]
        report_name = (
            "convexity-built-in-comparison"
            if background_only
            else "stats-display-comparison"
        )
        report_file = OUT / (
            f"{feedback_prefix}-2026-10-15.json"
            if clean_feedback
            else f"{report_name}-2026-10-13.json"
        )
        report_file.write_text(json.dumps(report, indent=2) + "\n")
        browser.close()


if __name__ == "__main__":
    main()

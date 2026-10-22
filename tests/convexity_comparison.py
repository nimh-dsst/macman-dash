"""Local diagnostic: soft/full convexity contrast and Phong/unlit rendering.

Run: PYTHONPATH=. .venv/bin/python tests/convexity_comparison.py
Uses the pinned dashboard bundle, exporting its NiiVue constructor for this
standalone probe only. The unlit fragment shader uses NiiVue's public custom
shader API. No application/bundle files or source data are modified.
"""

import base64
import json

import nibabel as nib
import numpy as np
from playwright.sync_api import sync_playwright

from macman.compat import patched_esm
from macman.data import (
    ROOT,
    curvature_brightness,
    read_curvature_values,
    scalar_bytes,
    surface_bytes,
)

OUTPUT = ROOT / "notes/validation/convexity-comparison-2026-10-13"
UNLIT = """#version 300 es
precision highp float;
in vec4 vClr;
uniform float opacity;
out vec4 color;
void main() { color = vec4(vClr.rgb, vClr.a * opacity); }
"""


def uri(data):
    return "data:application/octet-stream;base64," + base64.b64encode(data).decode()


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    folder = ROOT / "data/surfaces"
    values = {
        s: read_curvature_values(folder / f"{s}.gray_conv.csv") for s in ("lh", "rh")
    }
    limits = (
        min(v.min() for v in values.values()),
        max(v.max() for v in values.values()),
    )
    panels = []
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
            args=["--enable-webgl", "--use-gl=angle", "--use-angle=swiftshader"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100},
            device_scale_factor=2,
            service_workers="block",
        )
        blocked = []

        def block(route):
            blocked.append(route.request.url)
            route.abort()

        context.route("http://**/*", block)
        context.route("https://**/*", block)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(
            '<div style="width:460px;height:340px"><canvas id="brain"></canvas></div>'
        )
        await_source = """async ({source, unlit}) => {
            const {PreviewNiivue} = await import(URL.createObjectURL(new Blob([source], {type:'text/javascript'})));
            window.nv = new PreviewNiivue({backColor:[0.035,0.055,0.09,1], isColorbar:false, show3Dcrosshair:false});
            await nv.attachToCanvas(document.querySelector('canvas'));
            nv.setCustomMeshShader(unlit, 'Unlit diagnostic');
        }"""
        page.evaluate(
            await_source,
            {
                "source": patched_esm() + "\nexport {t2 as PreviewNiivue};",
                "unlit": UNLIT,
            },
        )
        for side, word in (("lh", "Left"), ("rh", "Right")):
            points, faces = nib.load(
                folder / f"{side}.gray_surface.inf_300.rsl.gii"
            ).agg_data()
            points -= (points.min(axis=0) + points.max(axis=0)) / 2
            mesh_uri = uri(surface_bytes(points, faces))
            normalized = ((values[side] - limits[0]) / (limits[1] - limits[0])).astype(
                np.float32
            )
            soft = curvature_brightness(values[side], limits)
            np.testing.assert_allclose(soft, 0.45 + 0.3 * normalized, atol=1e-7)
            for view in ("Lateral", "Medial"):
                angle = (
                    (90 if side == "lh" else 270)
                    if view == "Lateral"
                    else (270 if side == "lh" else 90)
                )
                for title, scalar, shader in (
                    ("Current soft · Phong", soft, "Phong"),
                    ("Full range · Phong", normalized, "Phong"),
                    ("Full range · no lighting", normalized, "Unlit diagnostic"),
                ):
                    info = page.evaluate(
                        """async ({mesh, scalar, angle, shader}) => {
                        await nv.loadMeshes([{url:mesh,name:'surface.gii',layers:[{url:scalar,name:'convexity.shape.gii',colormap:'gray',cal_min:0,cal_max:1,opacity:1}]}]);
                        nv.setMeshShader(nv.meshes[0].id,shader);
                        nv.setRenderAzimuthElevation(angle,0);
                        nv.drawScene();
                        const l=nv.meshes[0].layers[0];
                        return {minimum:l.cal_min, maximum:l.cal_max, vertices:l.values.length, shader:nv.meshShaderNames(false)[nv.meshes[0].meshShaderIndex]};
                    }""",
                        {
                            "mesh": mesh_uri,
                            "scalar": uri(scalar_bytes(scalar)),
                            "angle": angle,
                            "shader": shader,
                        },
                    )
                    assert (
                        info["minimum"] == 0
                        and info["maximum"] == 1
                        and info["vertices"] == 40962
                    ), info
                    assert info["shader"] == shader, info
                    checks.append({"side": side, "view": view, **info})
                    page.wait_for_timeout(250)
                    encoded = base64.b64encode(
                        page.locator("canvas").screenshot()
                    ).decode()
                    panels.append(
                        f'<section><h2>{word} · {view.lower()}<br>{title}</h2><img src="data:image/png;base64,{encoded}"></section>'
                    )
        assert not errors, errors
        assert not blocked, blocked
        html = (
            """<!doctype html><html lang="en"><meta charset="utf-8"><title>Convexity contrast comparison</title><style>
body{margin:0;font:15px system-ui;color:#17263b;background:white}main{width:1440px;padding:24px;box-sizing:border-box}h1{margin:0 0 8px;font-size:26px}p{margin:0 0 20px;color:#526277}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}h2{font-size:16px;line-height:1.5;margin:0 0 6px}img{width:100%;display:block;border-radius:8px}footer{font-size:13px;margin-top:18px;color:#526277}
</style><main><h1>NHP convexity: contrast and lighting</h1><p>Same source values and inflated geometry in every column · No statistical overlays</p><div class="grid">"""
            + "".join(panels)
            + """</div><footer>Soft: grayscale 0.45–0.75. Full range: 0–1. Both use the full shared bilateral source range, without clipping or added smoothing.<br>No-lighting column: diagnostic custom shader passes vertex colors through unchanged. Dashboard defaults are unchanged.</footer></main></html>"""
        )
        OUTPUT.with_suffix(".html").write_text(html)
        page.set_content(html)
        page.locator("img").evaluate_all(
            "images => Promise.all(images.map(i=>i.decode()))"
        )
        page.locator("main").screenshot(path=str(OUTPUT.with_suffix(".png")))
        OUTPUT.with_suffix(".json").write_text(
            json.dumps(
                {"checks": checks, "page_errors": errors, "blocked_requests": blocked},
                indent=2,
            )
            + "\n"
        )
        browser.close()
    print(OUTPUT.with_suffix(".png"))


if __name__ == "__main__":
    main()

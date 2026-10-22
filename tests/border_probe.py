"""Browser check of bundled NiiVue scalar blending against independent mask boundaries.

Run from the root: PYTHONPATH=. .venv/bin/python tests/border_probe.py
Uses existing compatibility fixes, but no border-specific patch or extra asset.
"""

import json

import nibabel as nib
import numpy as np
from playwright.sync_api import sync_playwright

from macman.compat import patched_esm
from macman.data import ROOT, load_stat_assets

PROBE = r"""
export function probe(values, masked, triangles, minimum, maximum, opacity) {
  const n = values.length;
  const mesh = {pts: new Float32Array(n*3), tris: new Uint32Array(triangles), f32PerVertex: 7};
  const output = new Uint8Array(n*28);
  for(let i=0;i<n;i++) output.set([195,204,216,255],i*28+24);
  const layer = {values:Float32Array.from(values,v=>v===null?NaN:v), opacity,
    frame4D:0,nFrame4D:1,isTransparentBelowCalMin:true,colormapType:0,
    outlineBorder:0,isAdditiveBlend:false};
  const lut=kA.colormap('viridis');
  dI.prototype.blendColormap.call(mesh,output,new Uint8Array(n*4),layer,minimum,maximum,lut);
  const base=Array.from({length:n},(_,i)=>Array.from(output.slice(i*28+24,i*28+27)));
  layer.values=Float32Array.from(masked,v=>v===null?NaN:v);
  layer.opacity=1; layer.outlineBorder=-0.01;
  dI.prototype.blendColormap.call(mesh,output,new Uint8Array(n*4),layer,minimum,maximum,lut);
  return {base,rgb:Array.from({length:n},(_,i)=>Array.from(output.slice(i*28+24,i*28+27)))};
}
"""


def serial(values):
    return [float(v) if np.isfinite(v) else None for v in values]


def main():
    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        page = browser.new_page()
        page.evaluate(
            "async source => {window.borderProbe = (await import(URL.createObjectURL(new Blob([source], {type:'text/javascript'})))).probe}",
            patched_esm() + PROBE,
        )
        checks = 0
        for key in ("L_FST", "L_V1", "L_46"):
            entry = catalog["rois"][key]
            assets = load_stat_assets(entry)
            for side in ("lh", "rh"):
                _, faces = nib.load(
                    ROOT / f"data/surfaces/{side}.gray_surface.inf_300.rsl.gii"
                ).agg_data()
                values = nib.gifti.GiftiImage.from_bytes(
                    assets["unthresholded"][side]
                ).agg_data()
                masked = nib.gifti.GiftiImage.from_bytes(assets["fdr"][side]).agg_data()
                inside = np.isfinite(masked)
                crossing = inside[faces].any(axis=1) & ~inside[faces].all(axis=1)
                boundary = np.zeros(len(values), dtype=bool)
                boundary[np.unique(faces[crossing])] = True
                boundary &= inside
                interior = inside & ~boundary
                reference = None
                for limits in (entry["value_range"], catalog["range"]):
                    for opacity in (0, 0.25, 1):
                        result = page.evaluate(
                            "args => window.borderProbe(...args)",
                            [
                                serial(values),
                                serial(masked),
                                faces.flatten().tolist(),
                                *limits,
                                opacity,
                            ],
                        )
                        rgb, base = (
                            np.asarray(result["rgb"]),
                            np.asarray(result["base"]),
                        )
                        np.testing.assert_array_equal((rgb == 0).all(axis=1), boundary)
                        np.testing.assert_array_equal(rgb[~inside], base[~inside])
                        assert (rgb[~np.isfinite(values)] == [195, 204, 216]).all()
                        if opacity == 0:
                            reference = rgb[interior]
                        else:
                            np.testing.assert_array_equal(rgb[interior], reference)
                        checks += 1
                print(
                    f"{key} {side}: {boundary.sum()} border vertices; NaNs/context/interior verified",
                    flush=True,
                )
        browser.close()
    print(
        f"Passed {checks} native browser blending checks; no border-specific patch or extra GIFTIs."
    )


if __name__ == "__main__":
    main()

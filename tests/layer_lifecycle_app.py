"""Synthetic local probe for widget retirement and recovery after decode failure.

Run marimo on port 2722, then tests/layer_lifecycle_browser.py.
Uses no research data and exercises the actual compatibility adapter/mesh owner.
"""

import marimo

__generated_with = "0.25.1"
app = marimo.App()


@app.cell
def _():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import json

    import marimo as mo
    import nibabel as nib
    import numpy as np

    from macman.compat import LeftResultNiiVue
    from macman.layers import ResultMesh
    from macman.viewer import layer_bytes

    return LeftResultNiiVue, ResultMesh, json, layer_bytes, mo, nib, np


@app.cell
def _(LeftResultNiiVue, ResultMesh, mo, nib, np):
    _points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype="float32")
    _faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], dtype="int32")
    _image = nib.gifti.GiftiImage(
        darrays=[
            nib.gifti.GiftiDataArray(_points, intent="NIFTI_INTENT_POINTSET"),
            nib.gifti.GiftiDataArray(_faces, intent="NIFTI_INTENT_TRIANGLE"),
        ]
    )
    scalar_data = nib.gifti.GiftiImage(
        darrays=[
            nib.gifti.GiftiDataArray(np.array([0.01, 0.1, 0.5, 1], dtype="float32"))
        ]
    ).to_bytes()
    mesh = ResultMesh(data=_image.to_bytes(), name="synthetic.gii")
    viewer = LeftResultNiiVue(height=300)
    viewer.load_meshes([mesh])
    mo.ui.anywidget(viewer)
    return mesh, scalar_data, viewer


@app.cell
def _(mo):
    burst = mo.ui.run_button(label="Publish 30 maps")
    fail = mo.ui.run_button(label="Publish invalid layer")
    inspect = mo.ui.run_button(label="Inspect retained widgets")
    mo.hstack([burst, fail, inspect])
    return burst, fail, inspect


@app.cell
def _(burst, fail, layer_bytes, mesh, scalar_data):
    if burst.value:
        for _index in range(30):
            mesh.publish_layers(
                [
                    layer_bytes(
                        scalar_data,
                        "synthetic.gii",
                        cal_min=0.01,
                        cal_max=1,
                        opacity=(_index + 1) / 30,
                    )
                ]
            )
    if fail.value:
        # Valid first layer tests partial-parse cleanup when the second fails.
        mesh.publish_layers(
            [
                layer_bytes(scalar_data, "synthetic.gii", cal_min=0.01, cal_max=1),
                layer_bytes(b"invalid", "invalid.gii"),
            ]
        )


@app.cell
def _(inspect, json, mesh, mo):
    mo.stop(not inspect.value)
    mo.md(
        "Retained: "
        + json.dumps(
            {
                "publications": len(mesh._publications),
                "open_widgets": sum(
                    layer.comm is not None
                    for _, layers in mesh._publications
                    for layer in layers
                ),
            }
        )
    )


if __name__ == "__main__":
    app.run()

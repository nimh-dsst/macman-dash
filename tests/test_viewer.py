from macman.data import CurvatureAsset
from macman.layers import ResultMesh
from macman.viewer import FDR_MAP_OPACITY, replace_map


def test_context_opacity_preserves_passing_layer_and_border():
    mesh = ResultMesh(data=b"mesh", name="mesh.gii")
    replace_map(mesh, b"base", 0.2, "viridis", 1)
    base = mesh.layers[0]
    replace_map(mesh, b"base", 0.2, "viridis", 0.25, mask_data=b"mask")
    base = mesh.layers[0]
    overlay = mesh.layers[1]
    assert base.opacity == 0.25
    assert overlay.opacity == FDR_MAP_OPACITY
    assert overlay.outline_border == -0.01
    assert not base.colorbar_visible and overlay.colorbar_visible
    replace_map(mesh, b"base", 0.1, "turbo", 0, minimum=0.01, mask_data=b"mask")
    base, overlay = mesh.layers
    assert base.opacity == 0 and overlay.opacity == FDR_MAP_OPACITY
    assert all(layer.cal_min == 0.01 and layer.cal_max == 0.1 for layer in mesh.layers)
    replace_map(mesh, b"base", 0.1, "turbo", 1)
    assert len(mesh.layers) == 1
    base = mesh.layers[0]
    assert base.outline_border == 0 and base.colorbar_visible
    mesh.close()


def test_empty_mask_keeps_context_layer():
    mesh = ResultMesh(data=b"mesh", name="mesh.gii")
    replace_map(mesh, b"base", 0.2, "viridis", 0.25, mask_data=None)
    assert len(mesh.layers) == 1
    assert mesh.layers[0].opacity == 0.25
    assert mesh.layers[0].outline_border == 0
    mesh.close()


def test_curvature_survives_map_changes_empty_mask_and_reset():
    mesh = ResultMesh(data=b"mesh", name="mesh.gii")
    replace_map(
        mesh,
        b"base",
        0.2,
        "viridis",
        0.8,
        curvature_data=CurvatureAsset(b"folds", (-2.0, 1.25)),
    )
    assert len(mesh.layers) == 2
    background, stats = mesh.layers
    assert background.colormap == "gray" and not background.colorbar_visible
    assert background.data == b"folds" and background.opacity == 1
    assert (background.cal_min, background.cal_max) == (-2.0, 1.25)
    assert not background.use_negative_cmap
    assert stats.colorbar_visible and stats.cal_max == 0.2
    replace_map(
        mesh,
        b"base",
        0.1,
        "turbo",
        0,
        minimum=0.01,
        mask_data=b"mask",
        curvature_data=CurvatureAsset(b"folds", (-2.0, 1.25)),
    )
    assert len(mesh.layers) == 3
    assert mesh.layers[0].data == b"folds"
    assert mesh.layers[1].opacity == 0
    assert mesh.layers[2].outline_border == -0.01
    assert sum(layer.colorbar_visible for layer in mesh.layers) == 1
    replace_map(
        mesh,
        None,
        0.1,
        "turbo",
        0,
        curvature_data=CurvatureAsset(b"folds", (-2.0, 1.25)),
    )
    assert len(mesh.layers) == 1
    assert mesh.layers[0].data == b"folds"
    assert not mesh.layers[0].colorbar_visible
    mesh.close()

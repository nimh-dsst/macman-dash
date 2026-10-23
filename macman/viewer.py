"""Independent persistent figures for the human atlas and NHP results."""

import uuid

from ipyniivue import MeshLayer

from .atlas import AtlasDisplay
from .colors import map_style
from .compat import HumanNiiVue, LeftResultNiiVue, RightResultNiiVue
from .data import load_curvature_assets, scene_assets
from .layers import ResultMesh

DEFAULT_MAP_OPACITY = 0.7
FDR_MAP_OPACITY = 0.8


def layer_bytes(data, name, **kwargs):
    # 2.4.4 omits name from constructor kwargs; set this synchronized trait explicitly.
    layer = MeshLayer(id=str(uuid.uuid4()), data=data, **kwargs)
    layer.name = name
    return layer


def create_viewers():
    nhp_paths, human = scene_assets()
    curvature_data = load_curvature_assets()
    options = {
        "height": 320,
        "back_color": [0.035, 0.055, 0.09, 1],
        "font_color": [0.85, 0.89, 0.94, 1],
        "crosshair_color": [0.65, 0.72, 0.8, 1],
        "show_colorbar_border": False,
        "show_3d_crosshair": False,
    }
    atlas_viewer = HumanNiiVue(**options, is_colorbar=False)
    result_viewers = {
        "lh": LeftResultNiiVue(**options, is_colorbar=True),
        "rh": RightResultNiiVue(**options, is_colorbar=True),
    }
    atlas_display = AtlasDisplay(atlas_viewer, human)
    atlas_display.update("Left", None, "Black outline")
    result_meshes = {}
    for side, viewer in result_viewers.items():
        mesh = ResultMesh(
            path=nhp_paths[side],
            name=f"NMT_{side}.gii",
            rgba255=[195, 204, 216, 255],
            layers=[curvature_layer(curvature_data[side])],
        )
        mesh.colorbar_visible = True
        viewer.load_meshes([mesh])
        viewer.set_mesh_shader(mesh.id, "Phong")
        viewer.scene.render_azimuth, viewer.scene.render_elevation = nhp_camera_angles(
            side, "Lateral"
        )
        result_meshes[side] = mesh
    atlas_viewer.scene.render_azimuth = 90
    atlas_viewer.scene.render_elevation = 0
    return atlas_viewer, result_viewers, atlas_display, result_meshes, curvature_data


def curvature_layer(asset):
    layer = layer_bytes(
        asset.data,
        "curvature.gii",
        colormap="gray",
        cal_min=asset.display_range[0],
        cal_max=asset.display_range[1],
        use_negative_cmap=False,
        opacity=1,
    )
    layer.colorbar_visible = False
    return layer


def nhp_camera_angles(side, view):
    return {
        "Dorsal": (0, 90),
        "Ventral": (0, -90),
        "Lateral": (90 if side == "lh" else 270, 0),
        "Medial": (270 if side == "lh" else 90, 0),
    }[view]


def replace_map(
    mesh,
    data,
    maximum,
    palette,
    opacity,
    signed=False,
    minimum=0,
    mask_data=None,
    curvature_data=None,
):
    """Publish configured layers; retain old widgets until frontend acknowledgment."""
    desired = [(data, opacity, 0)] if data is not None else []
    if mask_data is not None:
        desired.append((mask_data, FDR_MAP_OPACITY, -0.01))
    layers = [curvature_layer(curvature_data)] if curvature_data is not None else []
    for index, (payload, layer_opacity, border) in enumerate(desired):
        layer = layer_bytes(
            payload,
            "statistic.gii",
            opacity=layer_opacity,
            outline_border=border,
            **map_style(palette, maximum, signed, minimum=minimum),
        )
        layer.colorbar_visible = index == len(desired) - 1
        layers.append(layer)
    mesh.publish_layers(layers)

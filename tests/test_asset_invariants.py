"""Protect source data at the Python-to-viewer boundary, without private CSVs."""

import struct

import nibabel as nib
import numpy as np

from macman.data import (
    ROOT,
    CurvatureAsset,
    load_stat_assets,
    read_map,
    scalar_bytes,
    write_stat_assets,
)
from macman.layers import ResultMesh
from macman.viewer import create_viewers, replace_map


def forbid_gifti_encoding(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Runtime must reuse saved GIFTIs, not encode new ones")

    monkeypatch.setattr(nib.gifti.GiftiImage, "to_bytes", forbidden)


def test_viewers_receive_source_geometry_during_creation_and_atlas_selection(
    monkeypatch,
):
    expected = {
        side: nib.load(ROOT / f"data/surfaces/infl_{word}.gii.gz").agg_data()
        for side, word in (("lh", "left"), ("rh", "right"))
    }
    forbid_gifti_encoding(monkeypatch)
    atlas_viewer, viewers, atlas, meshes, _ = create_viewers()
    try:
        for side, mesh in meshes.items():
            source = ROOT / f"data/surfaces/{side}.gray_surface.inf_300.rsl.gii"
            # Inspect the actual serialized widget input, not just scene_assets().
            assert mesh.path == source
            assert mesh.data is None and mesh.url is None
            assert mesh.get_state("path")["path"]["data"] == source.read_bytes()

        for side, hemisphere in (("lh", "Left"), ("rh", "Right")):
            points, faces = expected[side]
            for roi in (None, f"{side[0].upper()}_V1", None):
                atlas.update(hemisphere, roi, "Black outline")
                payload = atlas_viewer.meshes[0].data
                # Read MZ3 geometry independently of the application's encoder.
                magic, flags, nfaces, nvertices, skip = struct.unpack_from(
                    "<HHIII", payload
                )
                assert (magic, flags, nfaces, nvertices, skip) == (
                    23117,
                    7,
                    len(faces),
                    len(points),
                    0,
                )
                actual_faces = np.frombuffer(
                    payload, dtype="<u4", count=nfaces * 3, offset=16
                ).reshape(-1, 3)
                actual_points = np.frombuffer(
                    payload, dtype="<f4", count=nvertices * 3, offset=16 + nfaces * 12
                ).reshape(-1, 3)
                np.testing.assert_array_equal(actual_faces, faces)
                np.testing.assert_array_equal(actual_points, points)
    finally:
        for mesh in atlas_viewer.meshes:
            mesh.close()
        atlas_viewer.close()
        for side, viewer in viewers.items():
            meshes[side].close()
            viewer.close()


def test_csv_values_reach_overlay_widgets_unchanged_across_display_updates(
    tmp_path,
    monkeypatch,
):
    # Different values per vertex/hemisphere detect sorting and hemisphere swaps.
    sources = (
        "2,0.75,1\n0,0.125,0\n1,,0\n",
        "1,0.5,1\n2,0.25,0\n0,0.875,1\n",
    )
    pairs = []
    for side, rows in zip(("lh", "rh"), sources):
        path = tmp_path / f"{side}.csv"
        path.write_text(",mean_subj_acc,fdr_mask\n" + rows)
        pairs.append(read_map(path, count=3, with_mask=True))
    entry = {
        "assets": write_stat_assets(
            "L_test",
            np.concatenate([p[0] for p in pairs]),
            np.concatenate([p[1] for p in pairs]),
            tmp_path,
        )
    }
    background = CurvatureAsset(scalar_bytes(np.array([0.1, -0.4, 0.8])), (-1, 1))
    expected_values = {
        "lh": [0.125, np.nan, 0.75],
        "rh": [0.875, 0.5, 0.25],
    }
    expected_masked = {
        "lh": [np.nan, np.nan, 0.75],
        "rh": [0.875, 0.5, np.nan],
    }
    forbid_gifti_encoding(monkeypatch)
    assets = load_stat_assets(entry, root=tmp_path)
    for side in ("lh", "rh"):
        for variant, expected in (
            ("unthresholded", expected_values),
            ("fdr", expected_masked),
        ):
            payload = assets[variant][side]
            saved = tmp_path / entry["assets"][variant][side]["path"]
            assert payload == saved.read_bytes()
            np.testing.assert_array_equal(
                nib.gifti.GiftiImage.from_bytes(payload).agg_data(), expected[side]
            )
        mesh = ResultMesh(data=b"unused geometry", name="mesh.gii")
        try:
            for palette, opacity, minimum, maximum, masked in (
                ("viridis", 0.7, 0.125, 0.875, False),
                ("turbo", 0, 0, 1, True),
                ("magma", 1, 0.125, 0.875, False),
            ):
                replace_map(
                    mesh,
                    assets["unthresholded"][side],
                    maximum,
                    palette,
                    opacity,
                    minimum=minimum,
                    mask_data=assets["fdr"][side] if masked else None,
                    curvature_data=background,
                )
                expected_payloads = [background.data, assets["unthresholded"][side]]
                if masked:
                    expected_payloads.append(assets["fdr"][side])
                assert [layer.get_state("data")["data"] for layer in mesh.layers] == (
                    expected_payloads
                )
            replace_map(mesh, None, 1, "viridis", 0.7, curvature_data=background)
            assert [layer.data for layer in mesh.layers] == [background.data]
        finally:
            mesh.close()

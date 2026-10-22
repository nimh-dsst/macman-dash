import numpy as np

from macman.atlas import NEUTRAL_RGB, selection_geometry


def test_outline_marks_only_boundary_and_preserves_source():
    faces = np.array([[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]])
    labels = np.array([1, 1, 1, 2, 2, 2])
    colors = np.full((6, 4), 200, dtype=np.uint8)
    actual_faces, actual_colors = selection_geometry(
        faces, colors, labels, 1, "Black outline", context_opacity=1
    )
    np.testing.assert_array_equal(actual_faces, faces)
    np.testing.assert_array_equal(actual_colors[[1, 2, 3, 4], :3], 0)
    np.testing.assert_array_equal(actual_colors[[0, 5]], colors[[0, 5]])
    np.testing.assert_array_equal(colors, 200)
    np.testing.assert_array_equal(actual_colors[:, 3], 200)


def test_full_atlas_preserves_surface_and_all_parcel_colors():
    faces = np.array([[0, 1, 2], [1, 2, 3], [2, 3, 4]])
    labels = np.array([1, 1, 1, 2, 2])
    colors = np.full((5, 4), 200, dtype=np.uint8)
    actual_faces, actual_colors = selection_geometry(
        faces, colors, labels, 1, "Full atlas"
    )
    np.testing.assert_array_equal(actual_faces, faces)
    np.testing.assert_array_equal(actual_colors, colors)
    np.testing.assert_array_equal(actual_colors[:, 3], colors[:, 3])
    np.testing.assert_array_equal(colors, 200)


def test_outline_fades_other_colors_without_fading_selected_roi():
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    labels = np.array([1, 1, 1, 2, 2, 2])
    colors = np.tile([40, 80, 120, 255], (6, 1)).astype(np.uint8)
    for opacity in [0, 0.4, 1]:
        actual_faces, actual_colors = selection_geometry(
            faces, colors, labels, 1, "Black outline", opacity
        )
        np.testing.assert_array_equal(actual_faces, faces)
        np.testing.assert_array_equal(actual_colors[:3], colors[:3])
        expected = np.rint(opacity * colors[3:, :3] + (1 - opacity) * NEUTRAL_RGB)
        np.testing.assert_array_equal(actual_colors[3:, :3], expected)
        np.testing.assert_array_equal(actual_colors[:, 3], 255)

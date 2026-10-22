"""Selection rendering on the annotation's actual vertex labels."""

import numpy as np
from ipyniivue import Mesh

from .data import colored_mesh_bytes

NEUTRAL_RGB = np.array([205, 210, 218], dtype=np.uint8)


def selection_geometry(faces, colors, labels, parcel, mode, context_opacity=0.4):
    """Composite parcel colors over an opaque neutral surface; keep all faces."""
    if not 0 <= context_opacity <= 1:
        raise ValueError("Context opacity must be between zero and one")
    selected = labels == parcel
    face_selection = selected[faces]
    rgba = colors.copy()
    if mode == "Black outline":
        rgba[~selected, :3] = np.rint(
            context_opacity * colors[~selected, :3]
            + (1 - context_opacity) * NEUTRAL_RGB
        ).astype(np.uint8)
        crossing = face_selection.any(axis=1) & ~face_selection.all(axis=1)
        boundary = np.unique(faces[crossing])
        rgba[boundary, :3] = 0
    return faces, rgba


class AtlasDisplay:
    def __init__(self, viewer, surfaces):
        self.viewer = viewer
        self.surfaces = surfaces
        self.previous = None

    def update(self, hemisphere, roi, mode, context_opacity=0.4):
        side = "lh" if hemisphere == "Left" else "rh"
        surface = self.surfaces[side]
        key = (side, roi, mode, context_opacity if mode == "Black outline" else None)
        if key == self.previous:
            return self.note
        self.note = None
        faces, colors = surface["faces"], surface["colors"]
        if roi is not None and mode != "Full atlas":
            # Match the selected hemisphere-qualified annotation name exactly.
            label = roi
            if label in surface["names"]:
                parcel = surface["names"].index(label)
                faces, colors = selection_geometry(
                    faces,
                    colors,
                    surface["labels"],
                    parcel,
                    mode,
                    context_opacity,
                )
            else:
                self.note = f"No exact Glasser label matches {label}; showing the full atlas without a highlight."
        data = colored_mesh_bytes(surface["points"], faces, colors)
        mesh = Mesh(data=data, name=f"human_{side}.mz3")
        mesh.colorbar_visible = False
        old = self.viewer.meshes
        self.viewer.load_meshes([mesh])
        self.viewer.set_mesh_shader(mesh.id, "Phong")
        for previous_mesh in old:
            previous_mesh.close()
        self.previous = key
        return self.note

"""Fetch prepared assets for browser Python; local execution uses existing files."""

import asyncio

from .data import ROOT

INITIAL_ASSETS = (
    "data/catalog.json",
    "data/atlases/glasser_roi_names.tsv",
    "data/surfaces/lh.gray_surface.inf_300.rsl.gii",
    "data/surfaces/rh.gray_surface.inf_300.rsl.gii",
    "data/surfaces/infl_left.gii.gz",
    "data/surfaces/infl_right.gii.gz",
    "data/surfaces/lh.HCP-MMP1.annot",
    "data/surfaces/rh.HCP-MMP1.annot",
    "data/surfaces/curvature.json",
    "data/surfaces/lh.curvature.shape.gii",
    "data/surfaces/rh.curvature.shape.gii",
)


async def ensure_assets(paths, base_url=None, root=ROOT):
    """Download missing files unchanged; reuse them for this Python session.

    ``base_url=None`` means local execution: the repository already has the files.
    In WASM, the notebook supplies ``mo.notebook_location() / 'public'``.
    """
    if base_url is None:
        return

    from pyodide.http import pyfetch

    async def fetch_one(relative):
        destination = root / relative
        if destination.is_file():
            return
        response = await pyfetch(f"{str(base_url).rstrip('/')}/{relative}")
        if not response.ok:
            raise OSError(f"Asset unavailable: {relative} (HTTP {response.status})")
        payload = await response.bytes()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    await asyncio.gather(*(fetch_one(path) for path in dict.fromkeys(paths)))

"""Prepare an isolated WASM test copy. Does not export, upload, or modify the app.

Run: .venv/bin/python tests/prepare_local_wasm.py
Then export the generated notebook with marimo html-wasm --offline --no-execute.
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".local-wasm" / "dashboard"


def notebook_metadata(source):
    """Reuse the deployment header; do not maintain a second dependency list."""
    match = re.match(r"\A# /// script\n(?:#(?: .*)?\n)*?# ///\n", source)
    if match is None:
        raise ValueError("Run scripts/sync_notebook_dependencies.py first")
    return match.group()


BOOTSTRAP = """    import asyncio as _asyncio
    import sys as _sys
    from urllib.parse import urlparse as _urlparse
    from pyodide.http import pyfetch as _pyfetch

    assert _sys.platform == "emscripten", "This copy must run in browser Python"
    _asset_base = str(mo.notebook_location() / "public")
    assert _urlparse(_asset_base).hostname in ("127.0.0.1", "localhost"), "Local test only"

    async def ensure_local_assets(paths):
        async def fetch_one(relative):
            destination = ROOT / relative
            if destination.exists():
                return
            response = await _pyfetch(_asset_base + "/" + relative)
            if not response.ok:
                raise OSError(f"Local asset unavailable: {relative} ({response.status})")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(await response.bytes())
        await _asyncio.gather(*(fetch_one(path) for path in paths))

    await ensure_local_assets(INITIAL_ASSETS)
    print("MACMAN_WASM_RUNTIME", _sys.platform, _sys.version)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--complete-export",
        action="store_true",
        help="Download the missing public dependency into the offline export; no data uploads",
    )
    args = parser.parse_args()
    if args.complete_export:
        # Observed omission in marimo 0.25.1's export; keep this test-only.
        with urlopen(
            "https://pypi.org/pypi/ipython-pygments-lexers/1.1.1/json", timeout=60
        ) as response:
            metadata = json.load(response)
        item = next(
            item
            for item in metadata["urls"]
            if item["filename"].endswith("-py3-none-any.whl")
        )
        with urlopen(item["url"], timeout=60) as response:
            data = response.read()
        digest = hashlib.sha256(data).hexdigest()
        assert (
            digest == "a9462224a505ade19a605f71f8fa63c2048833ce50abc86768a0d81d876dc81c"
        )
        packages = ROOT / ".local-wasm/site/packages"
        wheel = packages / digest / item["filename"]
        wheel.parent.mkdir(parents=True, exist_ok=True)
        wheel.write_bytes(data)
        index = packages / "index/ipython-pygments-lexers/index.html"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            f'<a href="../../{digest}/{wheel.name}#sha256={digest}">{wheel.name}</a>'
        )
        print(f"Added public dependency {wheel.name} to local offline export")
        return
    source = (ROOT / "dashboard.py").read_text()
    metadata = notebook_metadata(source)
    bootstrap = ROOT / ".local-wasm/bootstrap/dependencies.py"
    bootstrap.parent.mkdir(parents=True, exist_ok=True)
    bootstrap.write_text(
        metadata
        + """import marimo
app = marimo.App()
@app.cell
def _():
    import marimo as mo
    import ipyniivue
    import nibabel
    import numpy
    mo.md(f"Imports ready: ipyniivue {ipyniivue.__version__}, NiBabel {nibabel.__version__}, NumPy {numpy.__version__}")
    return
if __name__ == "__main__":
    app.run()
"""
    )
    STAGE.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "macman",
        STAGE / "macman",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    source = source.replace(
        "def _():\n    import json", "async def _():\n    import json", 1
    )
    initial = ["data/catalog.json", "data/atlases/glasser_roi_names.tsv"]
    initial += [
        "data/surfaces/" + name
        for name in (
            "lh.gray_surface.inf_300.rsl.gii",
            "rh.gray_surface.inf_300.rsl.gii",
            "infl_left.gii.gz",
            "infl_right.gii.gz",
            "lh.HCP-MMP1.annot",
            "rh.HCP-MMP1.annot",
            "curvature.json",
            "lh.curvature.shape.gii",
            "rh.curvature.shape.gii",
        )
    ]
    marker = """    from macman.viewer import (
        DEFAULT_MAP_OPACITY,
        create_viewers,
        nhp_camera_angles,
        replace_map,
    )
"""
    assert source.count(marker) == 1
    source = source.replace(
        marker, marker + "\n" + BOOTSTRAP.replace("INITIAL_ASSETS", repr(initial))
    )
    source = source.replace(
        "    return (\n        DEFAULT_PALETTE_LABEL,",
        "    return (\n        ensure_local_assets,\n        DEFAULT_PALETTE_LABEL,",
        1,
    )
    old = "def _(catalog, hemisphere, load_stat_assets, resolve_roi, roi):"
    assert source.count(old) == 1
    source = source.replace(
        old,
        "async def _(catalog, hemisphere, load_stat_assets, resolve_roi, roi, ensure_local_assets):",
    )
    source = source.replace(
        "            stat_assets = load_stat_assets(selected_entry)",
        """            await ensure_local_assets([
                info["path"] for variant in selected_entry["assets"].values()
                for info in variant.values()
            ])
            stat_assets = load_stat_assets(selected_entry)""",
    )
    (STAGE / "dashboard.py").write_text(source)
    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    active = set(initial)
    for entry in catalog["rois"].values():
        for variant in entry["assets"].values():
            active.update(info["path"] for info in variant.values())
    for relative in sorted(active):
        target = STAGE / "public" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    manifest = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(active)
    }
    (STAGE / "input-checksums.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Staged {len(active)} local input files, including {len(catalog['rois']) * 4:,} active GIFTIs; no CSVs or obsolete maps."
    )
    print(STAGE / "dashboard.py")


if __name__ == "__main__":
    main()

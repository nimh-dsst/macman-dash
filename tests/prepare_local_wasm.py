"""Stage the unchanged dashboard for the optional offline-only WASM test.

Run: .venv/bin/python tests/prepare_local_wasm.py
Then export the generated notebook with marimo html-wasm --offline --no-execute.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
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
    (STAGE / "dashboard.py").write_text(source)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.prepare_wasm_assets",
            "--output",
            str(STAGE / "public"),
        ],
        cwd=ROOT,
        check=True,
    )
    manifest = {
        str(path.relative_to(STAGE / "public")): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted((STAGE / "public").rglob("*"))
        if path.is_file()
    }
    (STAGE / "input-checksums.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(STAGE / "dashboard.py")


if __name__ == "__main__":
    main()

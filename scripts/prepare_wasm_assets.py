"""Stage only prepared runtime data in public/ for marimo's standard WASM export.

Run from the repository root: uv run python -m scripts.prepare_wasm_assets
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from macman.assets import INITIAL_ASSETS
from macman.data import ROOT


def prepare_assets(output, root=ROOT):
    catalog = json.loads((root / "data/catalog.json").read_text())
    active = set(INITIAL_ASSETS)
    for entry in catalog["rois"].values():
        for variant in entry["assets"].values():
            active.update(info["path"] for info in variant.values())
    # Refuse stale or unexpected files rather than silently publishing them.
    existing = {
        str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()
    }
    unexpected = existing - active
    if unexpected:
        raise ValueError(
            f"Unexpected files in {output}; review/remove them before staging: "
            + ", ".join(sorted(unexpected))
        )
    for relative in sorted(active):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "data":
            raise ValueError(f"Expected a repository-relative data path: {relative}")
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, target)
    for entry in catalog["rois"].values():
        for variant in entry["assets"].values():
            for info in variant.values():
                actual = hashlib.sha256(
                    (output / info["path"]).read_bytes()
                ).hexdigest()
                if actual != info["sha256"]:
                    raise ValueError(f"Catalog checksum mismatch: {info['path']}")
    return len(active)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "public")
    output = parser.parse_args().output.resolve()
    if output == ROOT or output == ROOT / "data":
        raise ValueError("Output must be a separate staging directory")
    count = prepare_assets(output)
    print(f"Staged {count:,} runtime files in {output}; source CSVs are excluded.")


if __name__ == "__main__":
    main()

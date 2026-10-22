"""Generate dashboard.py's PEP 723 metadata from the project runtime requirements.

Run with --check before publishing to detect drift without changing files.
Development dependencies are intentionally excluded from the browser notebook.
"""

import argparse
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA = re.compile(r"\A# /// script\n(?:#(?: .*)?\n)*?# ///\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    lines = [
        "# /// script",
        "# # Generated from pyproject.toml; run scripts/sync_notebook_dependencies.py",
        f"# requires-python = {json.dumps(project['requires-python'])}",
        "# dependencies = [",
        *(f"#     {json.dumps(dep)}," for dep in project["dependencies"]),
        "# ]",
        "# ///",
    ]
    notebook = ROOT / "dashboard.py"
    source = notebook.read_text()
    body = METADATA.sub("", source, count=1).lstrip("\n")
    if source.startswith("# /// script") and body == source:
        raise SystemExit("Unrecognized metadata block; inspect dashboard.py first.")
    updated = "\n".join(lines) + "\n\n" + body
    if args.check:
        if updated != source:
            raise SystemExit(
                "Metadata differs: run scripts/sync_notebook_dependencies.py"
            )
        print("Notebook dependencies match pyproject.toml.")
    elif updated != source:
        notebook.write_text(updated)
        print("Updated dashboard.py dependency metadata.")
    else:
        print("Notebook dependencies already match pyproject.toml.")


if __name__ == "__main__":
    main()

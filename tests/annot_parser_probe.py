"""Probe the unmodified ipyniivue 2.4.4 annotation reader in a local browser.

Run: PYTHONPATH=. .venv/bin/python tests/annot_parser_probe.py
Appends test exports only; never changes the application or installed bundle.
"""

import base64
import csv
import json

import nibabel as nib
import numpy as np
from ipyniivue import NiiVue
from playwright.sync_api import sync_playwright

from macman.data import ROOT, excluded_source_key

PROBE = """
export async function probeMZ3(encoded) {
  const bytes = Uint8Array.from(atob(encoded), c=>c.charCodeAt(0));
  const view = new DataView(bytes.buffer);
  const nf = view.getUint32(4,true), nv = view.getUint32(8,true);
  const mesh = await uA.readMZ3(bytes.buffer);
  let offset=16, faceErrors=0, pointErrors=0, maxColorError=0;
  for(let i=0;i<nf*3;i++,offset+=4) faceErrors += mesh.indices[i]!==view.getUint32(offset,true);
  for(let i=0;i<nv*3;i++,offset+=4) pointErrors += mesh.positions[i]!==view.getFloat32(offset,true);
  for(let i=0;i<nv;i++,offset+=4) for(let c=0;c<3;c++) maxColorError=Math.max(maxColorError,Math.abs(mesh.colors[i*3+c]-view.getUint8(offset+c)/255));
  return {faces:nf,vertices:nv,faceErrors,pointErrors,maxColorError};
}
export function probe(encoded, expected) {
  const bytes = Uint8Array.from(atob(encoded), c=>c.charCodeAt(0));
  const raw = uA.readANNOT(bytes.buffer, expected.length, false);
  const output = {raw_length:raw.length, raw_first_values:Array.from(raw.slice(0,8))};
  try {
    const result = uA.readANNOT(bytes.buffer, expected.length, true);
    output.kind = result.constructor.name;
    if (result.scalars) {
      output.mismatched_vertices = result.scalars.reduce((n,v,i)=>n+(v!==expected[i]),0);
      output.distinct_indices = Array.from(new Set(result.scalars)).sort((a,b)=>a-b);
      output.lut_keys = Object.keys(result.colormapLabel);
      output.lut = result.colormapLabel;
    }
  } catch(error) { output.error = String(error); }
  return output;
}
"""


def main():
    result = {"bundle": "unpatched ipyniivue 2.4.4", "console": [], "hemispheres": {}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        context = browser.new_context(service_workers="block")
        context.route("**/*", lambda route: route.abort())
        page = context.new_page()
        page.on(
            "console",
            lambda msg: result["console"].append({"type": msg.type, "text": msg.text}),
        )
        page.evaluate(
            "async source => {const m=await import(URL.createObjectURL(new Blob([source], {type:'text/javascript'}))); window.annotProbe=m.probe; window.mz3Probe=m.probeMZ3}",
            str(NiiVue._esm) + PROBE,
        )
        for side in ("lh", "rh"):
            path = ROOT / f"data/surfaces/{side}.HCP-MMP1.annot"
            labels, ctab, names = nib.freesurfer.read_annot(path)
            encoded = base64.b64encode(path.read_bytes()).decode()
            output = page.evaluate(
                "args => window.annotProbe(...args)", [encoded, labels.tolist()]
            )
            # JSON serializes a typed LUT array as an object with numeric keys.
            lut = output.pop("lut", None)
            if lut:
                output["lut_metadata"] = {k: v for k, v in lut.items() if k != "lut"}
                colors = lut.get("lut", {})
                data = list(colors.values()) if isinstance(colors, dict) else colors
                rgba = np.asarray(data).reshape(-1, 4)
                output["lut_rgba_first_rows"] = rgba[:12].tolist()
                output["RGB_rows_matching_source"] = int(
                    np.all(rgba[:, :3] == ctab[:, :3], axis=1).sum()
                )
                output["names_match_source"] = lut["labels"] == [
                    name.decode() for name in names
                ]
                output["alpha_matches_FreeSurfer_T"] = bool(
                    np.array_equal(rgba[:, 3], ctab[:, 3])
                )
                output["alpha_matches_255_minus_T"] = bool(
                    np.array_equal(rgba[:, 3], 255 - ctab[:, 3])
                )
            result["hemispheres"][side] = output
        result["MZ3_reader"] = {}
        for path in sorted((ROOT / ".local-atlas-audit").glob("*.mz3")):
            output = page.evaluate(
                "encoded => window.mz3Probe(encoded)",
                base64.b64encode(path.read_bytes()).decode(),
            )
            assert output["faceErrors"] == output["pointErrors"] == 0
            assert output["maxColorError"] < 1e-7
            result["MZ3_reader"][path.name] = output
        page.set_content((ROOT / "notes/atlas-audit/index.html").read_text())
        # Independent saved inventory, rather than hard-coded historical counts
        # or expectations derived from the HTML being tested.
        audit_dir = ROOT / "notes/atlas-audit"
        with (audit_dir / "annotation-labels.tsv").open() as stream:
            annotations = list(csv.DictReader(stream, delimiter="\t"))
        with (audit_dir / "csv-coverage.tsv").open() as stream:
            coverage = list(csv.DictReader(stream, delimiter="\t"))
        catalog = json.loads((ROOT / "data/catalog.json").read_text())
        excluded = set(catalog["excluded_incomplete_pairs"]) | {
            row["human_ROI"]
            for row in coverage
            if excluded_source_key(row["human_ROI"])
        }
        assert excluded == {
            row["human_ROI"]
            for row in coverage
            if row["catalog_status"].startswith("excluded")
        }, "Audit inventory is stale; rerun tests/atlas_audit.py"
        expected_rows = len(annotations) + len(coverage)
        assert page.locator("tbody tr").count() == expected_rows
        page.locator("#q").fill("excluded")
        actual_excluded = page.locator(
            "tbody tr:visible td:first-child"
        ).all_text_contents()
        assert len(actual_excluded) == len(excluded)
        assert set(actual_excluded) == excluded
        page.locator("#q").fill("a32pr")
        expected_matches = sum(
            "a32pr" in " ".join(row.values()).lower() for row in annotations + coverage
        )
        assert page.locator("tbody tr:visible").count() == expected_matches
        result["inspection_page_search"] = (
            f"pass: {expected_rows} rows, {len(excluded)} exclusions, {expected_matches} a32pr matches"
        )
        browser.close()
    output = ROOT / "notes/atlas-audit/parser-probe.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "console": result["console"],
                "hemispheres": {
                    side: {
                        key: value
                        for key, value in output.items()
                        if key
                        not in (
                            "lut_metadata",
                            "distinct_indices",
                            "lut_rgba_first_rows",
                        )
                    }
                    for side, output in result["hemispheres"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

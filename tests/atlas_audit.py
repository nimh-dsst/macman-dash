"""Read-only audit of annotations, CSV coverage, saved maps, and human MZ3 bytes.

Run: PYTHONPATH=. .venv/bin/python tests/atlas_audit.py
Writes inspection tables under notes/atlas-audit/; never rebuilds source assets.
"""

import csv
import hashlib
import html
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

import nibabel as nib
import numpy as np

from macman.atlas import selection_geometry
from macman.data import (
    PATTERN,
    ROOT,
    colored_mesh_bytes,
    excluded_source_key,
    scene_assets,
)

OUT = ROOT / "notes/atlas-audit"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mesh_exports = ROOT / ".local-atlas-audit"
    mesh_exports.mkdir(exist_ok=True)
    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    inputs = sorted((ROOT / "data/h2m/glasser2").glob("*.csv"))
    surface_hashes = json.loads((ROOT / "data/surfaces/checksums.json").read_text())
    for name, expected in surface_hashes.items():
        assert sha(ROOT / "data/surfaces" / name) == expected, name
    names_long = {
        row["abbreviation"]: row
        for row in csv.DictReader(
            (ROOT / "data/atlases/glasser_roi_names.tsv").open(), delimiter="\t"
        )
    }
    annotations, rows, vertex_samples = {}, [], []
    for side in ("lh", "rh"):
        path = ROOT / f"data/surfaces/{side}.HCP-MMP1.annot"
        payload = path.read_bytes()
        labels, ctab, names = nib.freesurfer.read_annot(path)
        # Decode stored vertex IDs and packed RGB codes independently of NiBabel.
        n = struct.unpack_from(">i", payload)[0]
        pairs = np.frombuffer(payload, dtype=">i4", count=n * 2, offset=4).reshape(n, 2)
        assert np.array_equal(pairs[:, 0], np.arange(n))
        packed = ctab[:, 0] + (ctab[:, 1] << 8) + (ctab[:, 2] << 16)
        assert len(np.unique(packed)) == len(packed)
        assert np.array_equal(pairs[:, 1], packed[labels])
        assert labels.min() == 0 and labels.max() == 180
        assert (np.bincount(labels, minlength=181) > 0).all()
        assert len(set(names)) == len(names) == 181
        present, version = struct.unpack_from(">ii", payload, 4 + n * 8)
        assert present == 1 and version == -2
        annotations[side] = {
            "vertices": n,
            "rows": len(names),
            "background_vertices": int((labels == 0).sum()),
            "sha256": sha(path),
            "format": "new-style v2",
            "raw_vertex_order_sequential": True,
        }
        for i, name in enumerate(names):
            label = name.decode().removesuffix("_ROI")
            abbreviation = label[2:] if i else ""
            if i:
                assert label.startswith("L_" if side == "lh" else "R_")
                assert int(names_long[abbreviation]["parcel_index"]) == i
            rows.append(
                {
                    "hemisphere": side,
                    "annotation_index": i,
                    "raw_name": name.decode(),
                    "lookup_key": label,
                    "long_name": names_long.get(abbreviation, {}).get("long_name", ""),
                    "vertices": int((labels == i).sum()),
                    "R": int(ctab[i, 0]),
                    "G": int(ctab[i, 1]),
                    "B": int(ctab[i, 2]),
                    "T": int(ctab[i, 3]),
                    "source_alpha": 255 - int(ctab[i, 3]),
                    "packed_RGB_ID": int(packed[i]),
                    "CSV_ID_by_observed_convention": i + (1000 if side == "rh" else 0)
                    if i
                    else "",
                }
            )
        for vertex in range(12):
            vertex_samples.append(
                {
                    "hemisphere": side,
                    "vertex_id": vertex,
                    "stored_annotation_value": int(pairs[vertex, 1]),
                    "decoded_table_index": int(labels[vertex]),
                    "raw_name": names[labels[vertex]].decode(),
                }
            )
    lookup = {row["lookup_key"]: row for row in rows if row["annotation_index"]}
    groups = defaultdict(dict)
    for path in inputs:
        match = PATTERN.fullmatch(path.name)
        assert match, path.name
        number, hemi, label, side = match.groups()
        key = f"{hemi}_{label}"
        assert side not in groups[key]
        groups[key][side] = {"path": path, "number": int(number)}
    coverage = []
    for key, members in sorted(groups.items()):
        numbers = {m["number"] for m in members.values()}
        assert len(numbers) == 1, key
        number = next(iter(numbers))
        atlas = lookup.get(key)
        if atlas:
            assert number == atlas["CSV_ID_by_observed_convention"], key
        complete = set(members) == {"lh", "rh"}
        out_of_analysis = excluded_source_key(key)
        assert (key in catalog["rois"]) == (complete and not out_of_analysis)
        coverage.append(
            {
                "human_ROI": key,
                "source_ID": number,
                "NHP_lh": members.get("lh", {}).get("path", Path()).name
                if "lh" in members
                else "",
                "NHP_rh": members.get("rh", {}).get("path", Path()).name
                if "rh" in members
                else "",
                "catalog_status": "excluded: outside analysis"
                if out_of_analysis
                else "included"
                if complete
                else "excluded: missing NHP-" + ("rh" if "lh" in members else "lh"),
                "annotation_match": "exact"
                if atlas
                else ("outside analysis" if out_of_analysis else "no exact label"),
                "annotation_index": atlas["annotation_index"] if atlas else "",
            }
        )
    assert set(catalog["excluded_incomplete_pairs"]) == {
        key
        for key, members in groups.items()
        if len(members) != 2 and not excluded_source_key(key)
    }
    for row in rows:
        members = groups.get(row["lookup_key"], {})
        row["CSV_coverage"] = (
            "background"
            if row["annotation_index"] == 0
            else (
                "both NHP files"
                if len(members) == 2
                else (
                    "only NHP-" + next(iter(members))
                    if members
                    else "no exact CSV name"
                )
            )
        )
    csv_rows, verified_assets, errors = [], 0, []
    value_hashes = defaultdict(list)
    for index, path in enumerate(inputs):
        number, hemi, label, side = PATTERN.fullmatch(path.name).groups()
        key = f"{hemi}_{label}"
        with path.open() as stream:
            assert next(csv.reader(stream)) == ["", "mean_subj_acc", "fdr_mask"]
        # Independent CSV parsing; do not call build_catalog or read_map.
        data = np.genfromtxt(path, delimiter=",", skip_header=1)
        ids, values, masks = data.T
        issues = []
        if not np.array_equal(np.sort(ids), np.arange(40962)):
            issues.append("invalid vertex IDs")
        if np.isinf(values).any() or not np.isfinite(values).any():
            issues.append("invalid statistic values")
        if not np.isin(masks, [0, 1]).all():
            issues.append("nonbinary mask")
        order = np.argsort(ids)
        values, masks = values[order].astype(np.float32), masks[order].astype(bool)
        checksum = sha(path)
        value_hashes[
            hashlib.sha256(values.tobytes() + masks.tobytes()).hexdigest()
        ].append(path.name)
        if key in catalog["rois"]:
            entry = catalog["rois"][key]
            assert checksum == entry["sha256"][side]
            for variant, expected in (
                ("unthresholded", values),
                ("fdr", np.where(masks, values, np.nan)),
            ):
                asset = entry["assets"][variant][side]
                target = ROOT / asset["path"]
                assert sha(target) == asset["sha256"]
                actual = nib.load(target).agg_data()
                assert actual.shape == (40962,)
                np.testing.assert_array_equal(actual, expected)
                verified_assets += 1
        csv_rows.append(
            {
                "filename": path.name,
                "human_ROI": key,
                "NHP_side": side,
                "rows": len(ids),
                "finite": int(np.isfinite(values).sum()),
                "missing": int(np.isnan(values).sum()),
                "passing_finite": int((masks & np.isfinite(values)).sum()),
                "mask_1_but_missing": int((masks & ~np.isfinite(values)).sum()),
                "sha256": checksum,
                "validation": "; ".join(issues) if issues else "pass",
            }
        )
        errors.extend((path.name, issue) for issue in issues)
        if (index + 1) % 100 == 0:
            print(f"Validated {index + 1}/{len(inputs)} CSVs", flush=True)
    _, human = scene_assets()
    mz3 = {}
    for side, surface in human.items():
        source_labels, source_ctab, _ = nib.freesurfer.read_annot(
            ROOT / f"data/surfaces/{side}.HCP-MMP1.annot"
        )
        np.testing.assert_array_equal(
            surface["colors"][:, :3], source_ctab[source_labels, :3]
        )
        raw_p, raw_f = nib.load(
            ROOT
            / (
                "data/surfaces/infl_left.gii.gz"
                if side == "lh"
                else "data/surfaces/infl_right.gii.gz"
            )
        ).agg_data()
        np.testing.assert_array_equal(surface["faces"], raw_f)
        np.testing.assert_array_equal(
            surface["points"], raw_p - (raw_p.min(axis=0) + raw_p.max(axis=0)) / 2
        )
        assert raw_f.min() == 0 and raw_f.max() == len(raw_p) - 1
        checks = []
        for parcel in (None, 1, 10, 179):
            faces, colors = surface["faces"], surface["colors"]
            if parcel is not None:
                faces, colors = selection_geometry(
                    faces, colors, surface["labels"], parcel, "Black outline", 0.4
                )
            blob = colored_mesh_bytes(surface["points"], faces, colors)
            magic, flags, nf, nv, skip = struct.unpack_from("<HHIII", blob)
            assert (magic, flags, skip) == (23117, 7, 0)
            offset = 16
            decoded_faces = np.frombuffer(blob, "<u4", nf * 3, offset).reshape(nf, 3)
            offset += nf * 12
            decoded_points = np.frombuffer(blob, "<f4", nv * 3, offset).reshape(nv, 3)
            offset += nv * 12
            decoded_colors = np.frombuffer(blob, np.uint8, nv * 4, offset).reshape(
                nv, 4
            )
            np.testing.assert_array_equal(decoded_faces, raw_f)
            np.testing.assert_array_equal(decoded_points, surface["points"])
            np.testing.assert_array_equal(decoded_colors, colors)
            assert len(blob) == offset + nv * 4 and (decoded_colors[:, 3] == 255).all()
            if parcel in (None, 179):
                label = "full" if parcel is None else "a32pr-outline"
                (mesh_exports / f"human_{side}.{label}.mz3").write_bytes(blob)
            checks.append("full atlas" if parcel is None else surface["names"][parcel])
        mz3[side] = {
            "vertices": nv,
            "faces": nf,
            "bytes": len(blob),
            "roundtrips": checks,
            "background_RGB": surface["colors"][surface["labels"] == 0][0].tolist(),
        }
    report = {
        "annotations": annotations,
        "csv_files": len(inputs),
        "groups": len(groups),
        "groups_by_human_prefix": dict(Counter(k[0] for k in groups)),
        "complete_by_human_prefix": dict(
            Counter(k[0] for k, v in groups.items() if len(v) == 2)
        ),
        "excluded": [r for r in coverage if r["catalog_status"] != "included"],
        "non_annotation_names": [
            r for r in coverage if r["annotation_match"] != "exact"
        ],
        "annotation_names_without_exact_CSV": sorted(set(lookup) - set(groups)),
        "CSV_validation_errors": errors,
        "duplicate_values_and_masks": [v for v in value_hashes.values() if len(v) > 1],
        "verified_GIFTIs": verified_assets,
        "human_MZ3": mz3,
    }
    table(OUT / "annotation-labels.tsv", rows)
    table(OUT / "annotation-vertex-sample.tsv", vertex_samples)
    table(OUT / "csv-coverage.tsv", coverage)
    table(OUT / "csv-validation.tsv", csv_rows)
    (OUT / "audit.json").write_text(json.dumps(report, indent=2) + "\n")

    def html_table(items):
        headers = list(items[0])
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{html.escape(k)}</th>" for k in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>"
                + "".join(
                    f'<td style="{f"background:rgb({r['R']},{r['G']},{r['B']});" if k == "R" else ""}">{html.escape(str(r[k]))}</td>'
                    for k in headers
                )
                + "</tr>"
                for r in items
            )
            + "</tbody></table>"
        )

    (OUT / "index.html").write_text(
        """<!doctype html><meta charset="utf-8"><title>Atlas and CSV audit</title>
<style>body{font:14px system-ui;margin:24px}input{padding:10px;width:360px}table{border-collapse:collapse;margin:20px 0}th,td{border:1px solid #ddd;padding:6px;text-align:left}th{background:#eee;position:sticky;top:0}td{white-space:nowrap}</style>
<h1>Atlas and CSV inspection</h1><p>Local read-only audit. 180 parcels plus background per human hemisphere; 707 source NHP CSVs: 5 B_FEF/dsToCharm4 files excluded, 346 active complete pairs, 10 incomplete groups. Missing CSVs await completion of analysis; V3 is being rerun with proper filenames.</p>
<p>Filter either table by name or status. Color swatches show source RGB, without lighting. T is source transparency; the dashboard renders all human vertices opaque. Source CSV IDs and packed RGB IDs are different numbering systems.</p>
<label>Search <input id="q" placeholder="e.g. a32pr, V3, excluded"></label><h2>Annotation color tables</h2>"""
        + html_table(rows)
        + "<h2>All CSV groups</h2>"
        + html_table(coverage)
        + """<script>document.querySelector('#q').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script>"""
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("excluded", "non_annotation_names")
            },
            indent=2,
        )
    )
    assert not errors, errors


if __name__ == "__main__":
    main()

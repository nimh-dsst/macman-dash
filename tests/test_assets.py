import asyncio
import hashlib
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from macman.assets import ensure_assets
from scripts.prepare_wasm_assets import prepare_assets


def test_local_execution_needs_no_pyodide_or_download(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pyodide.http", None)
    asyncio.run(ensure_assets(["data/example.gii"], root=tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_fetch_preserves_binary_bytes_and_reuses_files(tmp_path, monkeypatch):
    payload = b"\x1f\x8b\xff\x00\x80binary"
    requests = []

    async def read_bytes():
        return payload

    async def fetch(url):
        requests.append(url)
        return SimpleNamespace(ok=True, status=200, bytes=read_bytes)

    module = ModuleType("pyodide.http")
    module.pyfetch = fetch
    monkeypatch.setitem(sys.modules, "pyodide.http", module)
    path = "data/surfaces/example.gii.gz"
    url = "https://example.org/macman-dash/public/"
    asyncio.run(ensure_assets([path, path], url, tmp_path))
    asyncio.run(ensure_assets([path], url, tmp_path))
    assert requests == [url + path]
    assert (tmp_path / path).read_bytes() == payload


def test_failed_fetch_does_not_leave_cached_file(tmp_path, monkeypatch):
    async def fetch(url):
        return SimpleNamespace(ok=False, status=404)

    module = ModuleType("pyodide.http")
    module.pyfetch = fetch
    monkeypatch.setitem(sys.modules, "pyodide.http", module)
    with pytest.raises(OSError, match="HTTP 404"):
        asyncio.run(
            ensure_assets(["data/missing.gii"], "https://example.org/public", tmp_path)
        )
    assert not (tmp_path / "data/missing.gii").exists()


def test_staging_copies_only_runtime_assets_and_rejects_leftovers(
    tmp_path, monkeypatch
):
    source = tmp_path / "repo"
    data = source / "data"
    data.mkdir(parents=True)
    payload = b"\x00\xffprepared"
    (data / "map.gii").write_bytes(payload)
    (data / "private.csv").write_text("not for export")
    catalog = {
        "rois": {
            "L_test": {
                "assets": {
                    "unthresholded": {
                        "lh": {
                            "path": "data/map.gii",
                            "sha256": hashlib.sha256(payload).hexdigest(),
                        }
                    }
                }
            }
        }
    }
    (data / "catalog.json").write_text(json.dumps(catalog))
    monkeypatch.setattr(
        "scripts.prepare_wasm_assets.INITIAL_ASSETS", ("data/catalog.json",)
    )
    output = tmp_path / "public"
    assert prepare_assets(output, source) == 2
    assert (output / "data/map.gii").read_bytes() == payload
    assert not (output / "data/private.csv").exists()
    (output / "leftover.csv").write_text("must not publish")
    with pytest.raises(ValueError, match="Unexpected files"):
        prepare_assets(output, source)

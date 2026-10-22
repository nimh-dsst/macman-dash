"""Widget lifetime regression: pending frontend work must retain its inputs."""

from macman.layers import ResultMesh
from macman.viewer import layer_bytes


def acknowledge(mesh, layers):
    mesh._layers_settled(
        mesh,
        {"type": "macman_layers_settled", "model_ids": [x.model_id for x in layers]},
        [],
    )


def test_replacement_waits_for_acknowledgment_and_skipped_updates_are_retired():
    original, first, skipped, latest = [layer_bytes(b"x", "x.gii") for _ in range(4)]
    mesh = ResultMesh(data=b"mesh", name="mesh.gii", layers=[original])
    mesh.publish_layers([first])
    mesh.publish_layers([skipped])
    mesh.publish_layers([latest])
    assert all(x.comm is not None for x in (original, first, skipped, latest))

    acknowledge(mesh, [first])
    assert original.comm is None
    assert all(x.comm is not None for x in (first, skipped, latest))
    acknowledge(mesh, [latest])
    assert first.comm is None and skipped.comm is None
    assert latest.comm is not None
    assert len(mesh._publications) == 1
    # An obsolete/duplicate acknowledgement must not close the active layer.
    mesh._layers_settled(mesh, {"type": "macman_layers_settled", "model_ids": []}, [])
    acknowledge(mesh, [latest])
    assert latest.comm is not None
    mesh.close()
    assert latest.comm is None


def test_close_releases_all_pending_layers_even_without_a_browser_ack():
    mesh = ResultMesh(data=b"mesh", name="mesh.gii")
    pending = [layer_bytes(b"x", "x.gii") for _ in range(3)]
    for layer in pending:
        mesh.publish_layers([layer])
    mesh.close()
    assert all(x.comm is None for x in pending)

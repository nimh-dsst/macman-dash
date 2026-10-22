"""Readable JS adapter, embedded so marimo includes it in local-module WASM exports."""

LAYER_UPDATE_HANDLER = r"""
// Inserted inside ipyniivue's mesh listener scope: I=model, A=mesh, B=viewer.
// Keep the replacement readable; compat.py verifies the exact pinned insertion.
let layerQueue = Promise.resolve();
let layerDisposers = initialLayerDisposers;
let layerRevision = 0;
let layersDisposed = false;
let layerError;
function showLayerError(error) {
    console.error("NHP layer update failed; cleared overlays", error);
    if (!layerError) {
        layerError = document.createElement("div");
        layerError.setAttribute("role", "alert");
        layerError.style.cssText = "position:absolute;inset:0;display:grid;place-items:center;background:#09101a;color:white;padding:1rem;text-align:center;z-index:1";
        B.canvas.parentElement.appendChild(layerError);
    }
    layerError.textContent = "Map could not be displayed. Select another ROI or reset selection.";
}
function disposeLayers() {
    layersDisposed = true;
    for (const dispose of layerDisposers) dispose();
    layerDisposers = [];
    layerError?.remove();
}
function R() {
    // Coalesce updates that have not started. Never capture model IDs for a
    // future task: a later acknowledgment may legitimately retire those IDs.
    const revision = ++layerRevision;
    layerQueue = layerQueue.then(async () => {
        if (layersDisposed || revision !== layerRevision) return;
        const references = I.get("layers");
        try {
            for (const dispose of layerDisposers) dispose();
            layerDisposers = [];
            layerError?.remove();
            layerError = undefined;
            A.layers = [];
            A.updateMesh(B.gl);
            B.updateGLVolume();
            layerDisposers = await r2(I, A, B);
            if (layersDisposed) disposeLayers();
        } catch (error) {
            // Do not leave the previous ROI (or a partially parsed new one)
            // visible. Handle the rejection so the next update can run.
            A.layers = [];
            if (!layersDisposed) showLayerError(error);
        } finally {
            if (!layersDisposed) {
                A.updateMesh(B.gl);
                B.updateGLVolume();
            }
            await I.send({
                type: "macman_layers_settled",
                model_ids: references.map(ref => ref.slice(10)),
            });
        }
    }).catch(error => {
        // Also handle redraw/message failures; never poison the queue.
        if (!layersDisposed) showLayerError(error);
    });
}
"""

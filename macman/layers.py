"""Keep published layer widgets alive until the frontend finishes replacing them."""

from ipyniivue import Mesh


class ResultMesh(Mesh):
    """Own current/pending layers; retire them on ordered frontend acknowledgments.

    A Python assignment is not a browser acknowledgment. Closing a widget just
    after publishing its replacement can race with asynchronous model lookup.
    The compatibility adapter sends the IDs it has finished reading (or rejected).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._publications = []
        self._remember(self.layers)
        self.on_msg(self._layers_settled)

    def _remember(self, layers):
        key = tuple(layer.model_id for layer in layers)
        self._publications.append((key, list(layers)))

    def publish_layers(self, layers):
        self._remember(layers)
        self.layers = layers

    def _layers_settled(self, widget, content, buffers):
        if content.get("type") != "macman_layers_settled":
            return
        key = tuple(content.get("model_ids", []))
        for index, (published, _) in enumerate(self._publications):
            if published == key:
                retired = self._publications[:index]
                self._publications = self._publications[index:]
                # Layers can be shared between consecutive publications.
                keep = {id(layer) for _, group in self._publications for layer in group}
                closed = set()
                for _, group in retired:
                    for layer in group:
                        if id(layer) not in keep | closed:
                            layer.close()
                            closed.add(id(layer))
                break

    def close(self):
        closed = set()
        for _, group in getattr(self, "_publications", []):
            for layer in group:
                if id(layer) not in closed:
                    layer.close()
                    closed.add(id(layer))
        self._publications = []
        super().close()

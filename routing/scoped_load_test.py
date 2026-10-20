import json
from pathlib import Path
import tempfile
import unittest

from barrier_policy import MODEL_ID
from barrier_policy_test import xml
from compact_load import load_graph as legacy_load
from compact_storage import encoded_blocks, save_json
from import_capacity import graph_data
from outgoing_import import import_barriers as old_import
from scoped_import import import_barriers
from scoped_load import load_graph
from scoped_member_lookup import POLICY_ID


class ScopedLoaderTests(unittest.TestCase):
    def graph(self, directory, scoped):
        source = directory / "source.osm"
        source.write_text(xml({"barrier": "gate", "access": "yes"}))
        model = {"id": MODEL_ID, "signalDelayMs": 5000, "uTurnDelayMs": 20000}
        if scoped: model["restrictionGeometryPolicy"] = POLICY_ID
        graph, _ = (import_barriers if scoped else old_import)(source, directory / "barriers.osm", [-1, -1, 1, 1], model)
        data = graph_data(graph, model)
        save_json(directory / "graph.json", data)
        return graph, model

    def test_legacy_payload_and_identity_match_the_frozen_loader(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.graph(directory, False)
            old, old_model = legacy_load(directory / "graph.json", block_size=3)
            actual, model = load_graph(directory / "graph.json", block_size=3)
            self.assertEqual(b"".join(encoded_blocks(graph_data(actual, model))), b"".join(encoded_blocks(graph_data(old, old_model))))

    def test_declared_policy_roundtrips_and_is_required_by_its_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            expected, model = self.graph(directory, True)
            actual, loaded_model = load_graph(directory / "graph.json", block_size=3)
            self.assertEqual(actual.identity, expected.identity)
            self.assertEqual(loaded_model, model)
            data = json.loads((directory / "graph.json").read_text())
            del data["model"]["restrictionGeometryPolicy"]
            (directory / "graph.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "identity"): load_graph(directory / "graph.json")

    def test_unknown_policy_cannot_silently_use_legacy_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.graph(directory, False)
            data = json.loads((directory / "graph.json").read_text())
            data["model"]["restrictionGeometryPolicy"] = "unqualified-policy"
            (directory / "graph.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Unsupported"): load_graph(directory / "graph.json")


if __name__ == "__main__": unittest.main()

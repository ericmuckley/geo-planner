from array import array
import io
import json
from pathlib import Path
import tempfile
import unittest

from anchors import encoded, digest as frozen_digest
from barrier_policy import MODEL_ID
from barrier_policy_test import xml as barrier_xml
from compact_import import import_barriers, import_maneuvers
from compact_load import Reader, load_graph
from compact_storage import Csr, digest, encoded_blocks, save_json, write_csr
from import_capacity import graph_data
from maneuver_graph import replay
from maneuver_graph_test import MODEL, osm
from native_support import pack_graph
from state_graph import bellman_ford, dijkstra
from stream_import import import_barriers as old_barriers, import_maneuvers as old_maneuvers


class CompactStorageTests(unittest.TestCase):
    def compare(self, source, model, barriers=False):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "source.osm"
            path.write_text(source)
            if barriers:
                actual, audit = import_barriers(path, directory / "new.osm", [-1, -1, 1, 1], model)
                expected, old_audit = old_barriers(path, directory / "old.osm", [-1, -1, 1, 1], model)
                self.assertEqual((directory / "new.osm").read_bytes(), (directory / "old.osm").read_bytes())
            else:
                actual, audit = import_maneuvers(path, [-1, -1, 1, 1], model)
                expected, old_audit = old_maneuvers(path, [-1, -1, 1, 1], model)
            data = graph_data(actual, model)
            self.assertEqual(b"".join(encoded_blocks(data)), encoded(graph_data(expected, model)))
            self.assertEqual(audit, old_audit)
            self.assertEqual(actual.identity, expected.identity)
            write_csr(directory / "graph.csr", actual.adjacency, actual.identity)
            self.assertEqual((directory / "graph.csr").read_bytes(), pack_graph(expected.adjacency, expected.identity))
            save_json(directory / "graph.json", data)
            self.assertEqual((directory / "graph.json").read_bytes(), encoded(graph_data(expected, model)))
            loaded, loaded_model = load_graph(directory / "graph.json", block_size=7)
            self.assertEqual(loaded_model, model)
            self.assertEqual(b"".join(encoded_blocks(graph_data(loaded, model))), encoded(graph_data(expected, model)))
            for state in range(len(actual.states)):
                labels = dijkstra(actual.adjacency, [(state, 1)]).labels
                self.assertEqual(labels, bellman_ford(expected.adjacency, [(state, 1)]))
            for rule in actual.patterns:
                self.assertFalse(replay(actual, rule["roads"])["allowed"])

    def test_history_fallback_modes_and_duplicate_geometry_preserve_all_bytes(self):
        sources = [osm(), osm("only_straight_on"), osm(extra='<tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/>'),
                   osm(from_nodes=(1, 2, 3)), osm(extra='<tag k="except" v="motorcar"/>'),
                   osm().replace('type" v="restriction"', 'type" v="restriction:bicycle"'),
                   osm().replace('</osm>', '<way id="50"><nd ref="5"/><nd ref="6"/><nd ref="5"/><nd ref="6"/><tag k="highway" v="residential"/></way></osm>')]
        for source in sources:
            with self.subTest(source=source): self.compare(source, MODEL)

    def test_v3_access_permissions_and_closures_preserve_bytes(self):
        for props in ({"barrier": "border_control", "motorcar": "yes"}, {"barrier": "gate", "access": "permissive"},
                      {"barrier": "gate", "motorcar": "no", "access": "yes"}, {"barrier": "gate", "motorcar": "yes", "access:conditional": "no @ (Su)"}):
            self.compare(barrier_xml(props), {**MODEL, "id": MODEL_ID}, True)

    def test_canonical_stream_handles_unicode_floats_empty_rows_and_integer_ranges(self):
        graph = Csr(); graph.append([]); graph.append([(0, 0), (1, 4294967295)])
        value = {"unicode": "México", "float": -0.0, "rows": graph, "initial": range(2)}
        plain = {**value, "rows": [[], [(0, 0), (1, 4294967295)]], "initial": [0, 1]}
        self.assertEqual(b"".join(encoded_blocks(value)), encoded(plain))
        self.assertEqual(digest(value), frozen_digest(plain))
        with self.assertRaises(ValueError): digest({"cost": float("nan")})
        with self.assertRaises((ValueError, OverflowError)): graph.append([(0, -1)])
        self.assertIsInstance(graph.targets, array)

    def test_reload_rejects_truncated_duplicate_and_trailing_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            for source in ('{"graphIdentity":"x"', '{"graphIdentity":"x","graphIdentity":"x"}', '{}[]'):
                path.write_text(source)
                with self.assertRaises((ValueError, KeyError)): load_graph(path, block_size=2)

    def test_stream_reader_preserves_split_numeric_exponents_and_decimal_tokens(self):
        values = [-0.0, 1.234e-100, 1e100, 4294967295]
        for size in range(1, 20):
            with self.subTest(block_size=size):
                self.assertEqual(list(Reader(io.StringIO(json.dumps(values)), size).rows()), values)


if __name__ == "__main__": unittest.main()

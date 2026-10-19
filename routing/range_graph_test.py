from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from base_ids_test import compact, road
from compact_load import load_graph as frozen_load_graph
from compact_storage import build_graph, build_maneuver_graph, save_json
from import_capacity import graph_data
from range_graph import load_graph, TextReader


class RangeGraphTests(unittest.TestCase):
    def test_utf8_boundaries_and_completed_read_advice(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "text"
            path.write_text('Aé🗺️Z', encoding="utf-8")
            with patch("xml_stream.discard_range") as advise:
                with TextReader(path, threshold=0, window=4) as stream:
                    chunks = []
                    while part := stream.read(1): chunks.append(part)
                self.assertEqual("".join(chunks), 'Aé🗺️Z')
                self.assertEqual(sum(call.args[2] for call in advise.call_args_list), path.stat().st_size)
                self.assertTrue(stream.reader.stream.closed)

    def test_frozen_parser_identity_and_arrays_are_unchanged(self):
        graph = build_maneuver_graph(build_graph(compact([road("10:0:f", 1, 2, 1000), road("20:0:f", 2, 3, 2000)])), [])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "graph.json"
            save_json(path, graph_data(graph, {"id": "exploratory-static-car-v2"}))
            old, old_model = frozen_load_graph(path, 3)
            actual, model = load_graph(path, 3, advise=False)
            self.assertEqual(actual.identity, old.identity)
            self.assertEqual(model, old_model)
            self.assertEqual(list(actual.base.roads), list(old.base.roads))
            self.assertEqual([list(row) for row in actual.adjacency], [list(row) for row in old.adjacency])

    def test_parse_error_closes_stream_without_changing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "graph.json"
            path.write_bytes(b'{"broken":[')
            with self.assertRaises(ValueError): load_graph(path, 2, advise=False)
            self.assertEqual(path.read_bytes(), b'{"broken":[')


if __name__ == "__main__": unittest.main()

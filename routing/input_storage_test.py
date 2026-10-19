import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from barrier_policy import MODEL_ID
from barrier_policy_test import xml as barrier_xml
from compact_import import import_barriers as old_barriers, import_maneuvers as old_maneuvers, read_osm as old_read
from compact_storage import encoded_blocks
from import_capacity import graph_data
from input_import import import_barriers, import_maneuvers
from input_storage import read_osm
from maneuver_graph_test import MODEL, osm
from native_support import pack_graph
from state_graph import bellman_ford, dijkstra


class InputStorageTests(unittest.TestCase):
    def compare(self, source, barriers=False):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "source.osm"
            path.write_text(source)
            measurements = {}
            model = {**MODEL, "id": MODEL_ID} if barriers else MODEL
            if barriers:
                actual, audit = import_barriers(path, directory / "new.osm", [-1, -1, 1, 1], model, measurements)
                expected, old_audit = old_barriers(path, directory / "old.osm", [-1, -1, 1, 1], model)
                self.assertEqual((directory / "new.osm").read_bytes(), (directory / "old.osm").read_bytes())
            else:
                actual, audit = import_maneuvers(path, [-1, -1, 1, 1], model, measurements)
                expected, old_audit = old_maneuvers(path, [-1, -1, 1, 1], model)
            self.assertEqual(audit, old_audit)
            self.assertEqual(actual.identity, expected.identity)
            self.assertEqual(b"".join(encoded_blocks(graph_data(actual, model))), b"".join(encoded_blocks(graph_data(expected, model))))
            self.assertEqual(pack_graph(actual.adjacency, actual.identity), pack_graph(expected.adjacency, expected.identity))
            self.assertIn("inputStorage", measurements)
            for state in range(len(actual.states)):
                self.assertEqual(dijkstra(actual.adjacency, [(state, 1)]).labels, bellman_ford(expected.adjacency, [(state, 1)]))

    def test_maneuver_fallback_and_modes_have_identical_graph_and_audit(self):
        for source in (osm(), osm("only_straight_on"), osm(extra='<tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/>'),
                       osm(from_nodes=(1, 2, 3)), osm(extra='<tag k="except" v="motorcar"/>'),
                       osm().replace('type" v="restriction"', 'type" v="restriction:bicycle"'),
                       osm().replace('</osm>', '<way id="50"><nd ref="5"/><nd ref="6"/><nd ref="5"/><nd ref="6"/><tag k="highway" v="residential"/></way></osm>')):
            with self.subTest(source=source): self.compare(source)

    def test_barrier_permissions_closures_and_conditionals_are_unchanged(self):
        for properties in ({"barrier": "border_control", "motorcar": "yes"}, {"barrier": "gate", "access": "private"},
                           {"barrier": "gate", "access": "permissive"}, {"barrier": "gate", "motorcar": "no", "access": "yes"},
                           {"barrier": "gate", "motorcar": "yes", "access:conditional": "no @ (Su)"}):
            with self.subTest(properties=properties): self.compare(barrier_xml(properties), True)

    def test_unordered_and_duplicate_ids_preserve_last_values_and_insertion_order(self):
        root = ET.fromstring(osm())
        root[:] = list(reversed(list(root)))
        node = next(element for element in root if element.tag == "node")
        node.append(ET.Element("tag", {"k": "name", "v": "obsolete"}))
        root.append(ET.Element("node", {"id": node.get("id"), "lon": node.get("lon"), "lat": node.get("lat")}))
        way = next(element for element in root if element.tag == "way")
        root.append(ET.fromstring(ET.tostring(way)))
        self.compare(ET.tostring(root, encoding="unicode"))
        self.compare_inputs(ET.tostring(root, encoding="unicode"), ordered=False)

    def compare_inputs(self, source, ordered):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.osm"
            path.write_text(source)
            nodes, ways, relations = read_osm(path)
            old_nodes, old_ways, old_relations = old_read(path)
            self.assertEqual(list(nodes), list(old_nodes))
            self.assertEqual(list(ways), list(old_ways))
            self.assertEqual({identifier: dict(row) for identifier, row in nodes.items()}, old_nodes)
            self.assertEqual({identifier: {"nodes": list(row["nodes"]), "tags": row["tags"]} for identifier, row in ways.items()}, old_ways)
            self.assertEqual([ET.tostring(row) for row in relations], [ET.tostring(row) for row in old_relations])
            self.assertEqual(nodes.ordered, ordered)
            with self.assertRaises(KeyError): nodes[999999]
            self.assertNotIn(999999, ways)
            self.assertGreater(nodes.storage_summary()["arrayBytes"], 0)
            json.dumps(ways.storage_summary())
            for row in ways.values():
                refs = row["nodes"]
                self.assertEqual(refs[::-1], list(reversed(refs)))
                self.assertEqual(refs[-1], list(refs)[-1])
                with self.assertRaises(IndexError): _ = refs[len(refs)]

    def test_ordered_arrays_preserve_large_ids_unicode_and_float_precision(self):
        source = '<osm><node id="9007199254740993" lon="-0.0" lat="1.23456789012345"/><node id="9007199254740994" lon="1e-100" lat="0"><tag k="name" v="México 🌎"/></node><way id="12"><nd ref="9007199254740993"/><nd ref="9007199254740994"/><tag k="name" v="México 🌎"/></way></osm>'
        self.compare_inputs(source, ordered=True)

    def test_missing_node_and_invalid_document_fail_like_frozen_parser(self):
        for source in ('<other/>', osm().replace('<nd ref="1"', '<nd ref="99999"')):
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "source.osm"
                path.write_text(source)
                errors = []
                for importer in (old_maneuvers, import_maneuvers):
                    with self.assertRaises(ValueError) as caught: importer(path, [-1, -1, 1, 1], MODEL)
                    errors.append(str(caught.exception))
                self.assertEqual(*errors)


if __name__ == "__main__": unittest.main()

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from barrier_policy import MODEL_ID, import_barriers as frozen_barriers
from barrier_policy_test import xml as barrier_xml
from import_maneuvers import import_maneuvers as frozen_maneuvers
from import_roads import import_roads
from maneuver_graph_test import MODEL, osm
from stream_import import build_base, import_barriers, import_maneuvers, read_osm


class StreamingImportTests(unittest.TestCase):
    def compare_maneuvers(self, source):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "roads.osm"
            path.write_text(source)
            self.assertEqual(import_maneuvers(path, [-1, -1, 1, 1], MODEL), frozen_maneuvers(path, [-1, -1, 1, 1], MODEL))

    def test_supported_maneuvers_and_unsafe_fallbacks_match_frozen_graph_and_audit(self):
        for source in (osm(), osm("only_straight_on"), osm(extra='<tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/>'),
                       osm(from_nodes=(1, 2, 3)), osm(extra='<tag k="except" v="motorcar"/>'),
                       osm().replace('type" v="restriction"', 'type" v="restriction:bicycle"')):
            with self.subTest(source=source): self.compare_maneuvers(source)

    def test_reinstated_closure_invalidates_another_candidate_identically(self):
        source = osm().replace('</osm>', '''<relation id="100"><member type="way" role="from" ref="20"/>
        <member type="node" role="via" ref="4"/><member type="way" role="to" ref="30"/>
        <tag k="type" v="restriction"/><tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/></relation></osm>''')
        self.compare_maneuvers(source)

    def test_duplicate_geometry_preserves_per_rule_fallback_instead_of_aborting(self):
        source = osm().replace('</osm>', '''<way id="50"><nd ref="5"/><nd ref="6"/><nd ref="5"/><nd ref="6"/>
        <tag k="highway" v="residential"/></way></osm>''')
        self.compare_maneuvers(source)

    def test_streamed_cost_access_direction_barrier_cut_and_audit_match_frozen_base(self):
        variants = ({}, {"oneway": "-1", "maxspeed": "25 mph"}, {"access": "private", "motorcar": "yes"},
                    {"motorcar:backward": "no"}, {"maxspeed": "signals"}, {"oneway": "reversible"},
                    {"motorcar:lanes": "yes|no"}, {"access:conditional": "no @ (Su)"}, {"service": "parking_aisle"}, {"ford": "yes"})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "roads.osm"
            for properties in variants:
                extra = ''.join(f'<tag k="{key}" v="{value}"/>' for key, value in properties.items())
                source = (osm().split('<relation')[0] + '</osm>').replace('<tag k="highway" v="residential"/>', '<tag k="highway" v="residential"/>'+extra, 1)
                source = source.replace('<node id="3" lon="0.003" lat="0"/>', '<node id="3" lon="0.003" lat="0"><tag k="barrier" v="gate"/></node>')
                path.write_text(source)
                for bounds in ([-1, -1, 1, 1], [-1, -1, .0045, 1]):
                    with self.subTest(properties=properties, bounds=bounds):
                        self.assertEqual(build_base(*read_osm(path), bounds, MODEL), import_roads(path, bounds, MODEL))

    def test_v3_permissions_prohibitions_and_conditionals_match_frozen_policy_and_bytes(self):
        model = {**MODEL, "id": MODEL_ID}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "source.osm"
            for props in ({"barrier": "border_control", "motorcar": "yes", "foot": "no"},
                          {"barrier": "gate", "motorcar": "no", "access": "yes"},
                          {"barrier": "gate", "access": "permissive"},
                          {"barrier": "gate", "motorcar": "yes", "access:conditional": "no @ (Su)"},
                          {"barrier": "bollard", "motorcar": "yes"}):
                path.write_text(barrier_xml(props))
                before = frozen_barriers(path, directory / "before.osm", [-1, -1, 1, 1], model)
                after = import_barriers(path, directory / "after.osm", [-1, -1, 1, 1], model)
                self.assertEqual(before, after)
                self.assertEqual((directory / "before.osm").read_bytes(), (directory / "after.osm").read_bytes())

    def test_malformed_and_missing_reference_inputs_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.osm"
            for source in ('<not-osm/>', '<osm><node', osm().replace('ref="1"', 'ref="999"', 1)):
                path.write_text(source)
                with self.assertRaises((ValueError, KeyError, ET.ParseError)): import_maneuvers(path, [-1, -1, 1, 1], MODEL)


if __name__ == "__main__": unittest.main()

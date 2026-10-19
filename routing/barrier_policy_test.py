from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from barrier_policy import MODEL_ID, barrier_decision, import_barriers, prepare_barriers
from import_maneuvers import import_maneuvers
from import_roads import tags
from maneuver_graph import replay


MODEL = {"id": MODEL_ID, "signalDelayMs": 5000, "uTurnDelayMs": 20000}


def xml(properties, restriction=""):
    props = ''.join(f'<tag k="{key}" v="{value}"/>' for key, value in properties.items())
    return f'''<osm version="0.6" generator="barrier-test">
    <node id="1" lon="0" lat="0"/><node id="2" lon="0.001" lat="0">{props}</node>
    <node id="3" lon="0.002" lat="0"/>
    <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/><tag k="oneway" v="yes"/></way>
    <way id="20"><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/><tag k="oneway" v="yes"/></way>
    {restriction}</osm>'''


class BarrierPolicyTests(unittest.TestCase):
    def test_recognized_control_points_require_explicit_permission(self):
        for kind in ("gate", "lift_gate", "border_control", "toll_booth"):
            for key, value in (("motorcar", "yes"), ("motor_vehicle", "designated"), ("access", "permissive")):
                self.assertTrue(barrier_decision({"barrier": kind, key: value})["open"])
            self.assertFalse(barrier_decision({"barrier": kind})["open"])

    def test_access_precedence_and_other_modes(self):
        base = {"barrier": "border_control", "foot": "no", "bicycle": "no"}
        self.assertTrue(barrier_decision({**base, "motorcar": "yes", "motor_vehicle": "no", "access": "private"})["open"])
        for props in ({"motorcar": "no", "motor_vehicle": "yes"}, {"motor_vehicle": "no", "vehicle": "yes"},
                      {"vehicle": "no", "access": "yes"}, {"foot": "yes"}, {"motorcar": "permit"}, {"access": "designated"}):
            self.assertFalse(barrier_decision({**base, **props})["open"])

    def test_conditional_directional_locked_dimensions_and_unknown_are_closed(self):
        base = {"barrier": "gate", "motorcar": "yes"}
        for extra in ({"motorcar:conditional": "no @ (Mo-Fr)"}, {"foot:conditional": "yes @ (Su)"},
                      {"motorcar:forward": "yes"}, {"access:citizenship": "local"}, {"oneway": "yes"},
                      {"locked": "yes"}, {"locked": "unknown"}, {"opening_hours": "Mo-Fr"}, {"maxwidth": "2"},
                      {"barrier": "bollard"}, {"barrier": "yes"}):
            with self.subTest(extra=extra): self.assertFalse(barrier_decision({**base, **extra})["open"])

    def test_stream_transform_preserves_original_tags_ways_and_relations(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source.osm", Path(temporary) / "prepared.osm"
            original = xml({"barrier": "gate", "motorcar": "yes", "name": "A &amp; B"})
            source.write_text(original)
            audit = prepare_barriers(source, output, [-1, -1, 1, 1])
            before, after = ET.parse(source).getroot(), ET.parse(output).getroot()
            self.assertEqual(source.read_text(), original)
            self.assertEqual(before.attrib, after.attrib)
            self.assertEqual(tags(after.find("node[@id='2']")), {"motorcar": "yes", "name": "A & B"})
            self.assertEqual([ET.tostring(w) for w in before.findall('way')], [ET.tostring(w) for w in after.findall('way')])
            self.assertEqual(audit["decisions"][0]["tags"]["barrier"], "gate")
            with self.assertRaises(ValueError): prepare_barriers(source, source, [-1, -1, 1, 1])

    def test_qualified_permission_changes_transition_but_preserves_oneway_and_costs(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source.osm", Path(temporary) / "prepared.osm"
            source.write_text(xml({"barrier": "border_control", "motorcar": "yes"}))
            before, _ = import_maneuvers(source, [-1, -1, 1, 1], MODEL)
            after, audit = import_barriers(source, output, [-1, -1, 1, 1], MODEL)
            self.assertEqual(before.base.roads, after.base.roads)
            self.assertEqual([road["id"] for road in after.base.roads], ["10:0:f", "20:0:f"])
            self.assertFalse(replay(before, [0, 1])["allowed"])
            self.assertTrue(replay(after, [0, 1])["allowed"])
            self.assertNotEqual(before.identity, after.identity)
            self.assertFalse(audit["barrierPolicy"]["decisions"][0]["blockedByModel"])

    def test_car_prohibition_and_conditional_keep_through_transition_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source.osm", Path(temporary) / "prepared.osm"
            for extra in ({"motorcar": "no", "access": "yes"}, {"motorcar": "yes", "access:conditional": "no @ (Su)"}):
                source.write_text(xml({"barrier": "gate", **extra}))
                graph, audit = import_barriers(source, output, [-1, -1, 1, 1], MODEL)
                self.assertFalse(replay(graph, [0, 1])["allowed"])
                self.assertTrue(audit["barrierPolicy"]["decisions"][0]["blockedByModel"])

    def test_permitted_node_does_not_override_turn_restriction(self):
        restriction = '''<relation id="99"><member type="way" role="from" ref="10"/>
        <member type="node" role="via" ref="2"/><member type="way" role="to" ref="20"/>
        <tag k="type" v="restriction"/><tag k="restriction" v="no_straight_on"/></relation>'''
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source.osm", Path(temporary) / "prepared.osm"
            source.write_text(xml({"barrier": "gate", "motorcar": "yes"}, restriction))
            graph, audit = import_barriers(source, output, [-1, -1, 1, 1], MODEL)
            self.assertFalse(replay(graph, [0, 1])["allowed"])
            self.assertEqual(audit["appliedRestrictions"][0]["id"], 99)

    def test_outside_nodes_and_wrong_model_are_not_opened(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source.osm", Path(temporary) / "prepared.osm"
            source.write_text(xml({"barrier": "gate", "motorcar": "yes"}))
            audit = prepare_barriers(source, output, [1, 1, 2, 2])
            self.assertEqual(audit["decisions"][0]["reason"], "outside-bounds")
            self.assertIn("barrier", tags(ET.parse(output).find("node[@id='2']")))
            with self.assertRaises(ValueError): import_barriers(source, output, [-1, -1, 1, 1], {**MODEL, "id": "v2"})


if __name__ == "__main__": unittest.main()

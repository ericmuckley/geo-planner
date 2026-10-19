from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

from buffer_resources import check_policy
from cut_inventory import boundary_links, cut_states, minimum_witness, outward_allowed, outside_sides
from native_support import UINT64_MAX


class CutInventoryTests(unittest.TestCase):
    def test_history_state_can_be_the_first_arrival_and_infinite_nodes_stay_unreachable(self):
        graph = SimpleNamespace(base=SimpleNamespace(roads=SimpleNamespace(heads=[10, 11, 12])),
                                states=[{"road": 0}, {"road": 1}, {"road": 2}, {"road": 0}])
        states = cut_states(graph, {10, 11, 99})
        self.assertEqual(states, {10: [0, 3], 11: [1], 99: []})
        labels = struct.pack("<4Q", 100, UINT64_MAX, 5, 20)
        self.assertEqual(minimum_witness(labels, states[10]), {"costMs": 20, "state": 3})
        self.assertEqual(minimum_witness(labels, states[11]), {"costMs": None, "state": None})
        self.assertEqual(minimum_witness(labels, states[99]), {"costMs": None, "state": None})

    def test_direction_access_and_boundary_corner_sides(self):
        self.assertEqual(outside_sides([-2, 2], [-1, -1, 1, 1]), ["west", "north"])
        self.assertEqual(outside_sides([1, 1], [-1, -1, 1, 1]), [])
        self.assertTrue(outward_allowed({"highway": "motorway"}, True))
        self.assertFalse(outward_allowed({"highway": "motorway"}, False))
        self.assertTrue(outward_allowed({"highway": "residential", "oneway": "-1"}, False))
        for props in ({"access": "no"}, {"motor_vehicle:forward": "no"}, {"access:conditional": "yes @ (Su)"}):
            self.assertFalse(outward_allowed({"highway": "residential", **props}, True))

    def test_boundary_source_links_keep_restricted_and_excluded_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.osm"
            source.write_text('<osm><node id="1" lon="0" lat="0"/><node id="2" lon="2" lat="0"/>'
                              '<way id="3"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/><tag k="oneway" v="-1"/></way></osm>')
            row = boundary_links(source, [-1, -1, 1, 1], {1}, {3})[1]
            self.assertEqual(row["point"], [0, 0])
            link = row["links"][0]
            self.assertEqual(link["outsideSides"], ["east"])
            self.assertFalse(link["wayOnlyOutwardAllowed"])
            self.assertTrue(link["wayExcludedByModel"])

    def test_resource_policy_rejects_allowed_swap_wrong_cap_and_oom(self):
        value = {"memory.max": str(4 * 1024 ** 3), "memory.swap.max": "0", "memory.swap.current": "0", "memory.swap.peak": "0",
                 "memory.events": {"oom": "0", "oom_kill": "0", "oom_group_kill": "0"}}
        check_policy(value)
        for key, changed in (("memory.max", "1"), ("memory.swap.max", "1"), ("memory.swap.peak", "1")):
            with self.assertRaises(ValueError): check_policy({**value, key: changed})
        with self.assertRaises(ValueError): check_policy({**value, "memory.events": {**value["memory.events"], "oom": "1"}})


if __name__ == "__main__": unittest.main()

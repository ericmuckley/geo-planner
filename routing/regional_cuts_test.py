from pathlib import Path
import tempfile
import unittest

from cut_inventory import boundary_links as frozen_links
from regional_cuts import boundary_links


class RegionalCutTests(unittest.TestCase):
    def test_source_links_match_for_loops_corners_direction_access_and_exclusions(self):
        xml = '''<osm><node id="1" lon="0" lat="0"/><node id="2" lon="2" lat="2"/>
        <node id="3" lon="1" lat="1"/><node id="4" lon="-2" lat="0"/>
        <way id="10"><nd ref="2"/><nd ref="1"/><nd ref="2"/><tag k="highway" v="motorway"/></way>
        <way id="11"><nd ref="1"/><nd ref="4"/><tag k="highway" v="service"/><tag k="oneway" v="-1"/></way>
        <way id="12"><nd ref="3"/><nd ref="4"/><tag k="highway" v="residential"/><tag k="access:conditional" v="yes @ (Su)"/></way>
        <way id="13"><nd ref="2"/><nd ref="4"/><tag k="highway" v="path"/></way></osm>'''
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.osm"
            source.write_text(xml)
            actual = boundary_links(source, [-1, -1, 1, 1], {1, 3}, {11})
            self.assertEqual(actual, frozen_links(source, [-1, -1, 1, 1], {1, 3}, {11}))
            self.assertEqual(len(actual[1]["links"]), 3)
            self.assertEqual(actual[1]["links"][0]["direction"], "r")
            self.assertTrue(actual[1]["links"][-1]["wayExcludedByModel"])

    def test_missing_source_neighbor_cannot_silently_hide_a_cut(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.osm"
            source.write_text('<osm><node id="1" lon="0" lat="0"/><way id="2"><nd ref="1"/><nd ref="99"/></way></osm>')
            with self.assertRaises(KeyError): boundary_links(source, [-1, -1, 1, 1], {1}, set())

    def test_duplicate_ways_are_rejected_instead_of_reordering_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.osm"
            source.write_text('<osm><node id="1" lon="0" lat="0"/><way id="2"/><way id="2"/></osm>')
            with self.assertRaisesRegex(ValueError, "ordered"): boundary_links(source, [-1, -1, 1, 1], {1}, set())


if __name__ == "__main__": unittest.main()

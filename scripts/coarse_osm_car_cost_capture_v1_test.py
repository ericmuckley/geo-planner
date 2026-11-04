"""Tiny mutable-writer controls before any captured input conversion."""
from pathlib import Path
import tempfile
import unittest

from coarse_osm_car_cost_capture_v1 import add, writer
from coarse_osm_car_capacity_v2_test import CAPS
from coarse_osm_country_wire_v4 import reference_seal
from coarse_osm_native_smoke import STATE, fixture_records
from coarse_osm_topology_source_v1 import NativeScreen
from coarse_timing_input import PilotError

ARTIFACT = None


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Protected constructor artifact/cached pyosmium required')
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root = Path(temp.name)

    def generate(self, rows):
        path = self.root/'fixture.osm.pbf'
        with writer(path) as output:
            for row in rows:add(output, row)
        return path

    def test_every_object_metadata_unicode_members_and_coordinate_seal(self):
        rows = fixture_records();rows[0]['tags']['name'] = 'fixture 雪'
        receipt = NativeScreen(*ARTIFACT).scan(self.generate(rows), STATE, CAPS)
        self.assertEqual(receipt['semanticSha256'], reference_seal(rows));self.assertTrue(receipt['nativeEof'])
        self.assertEqual(receipt['pythonProjectionFrames'], 0)

    def test_repeated_nodes_reverse_and_relation_member_types(self):
        rows = fixture_records();rows[4]['nodes'] = [1, 2, 1, 1]
        rows[-1]['members'].append({'type': 'relation', 'ref': 91, 'role': 'fixture'})
        receipt = NativeScreen(*ARTIFACT).scan(self.generate(rows), STATE, CAPS)
        self.assertEqual(receipt['semanticSha256'], reference_seal(rows))

    def test_wrong_epoch_still_fails_after_conversion(self):
        engine = NativeScreen(*ARTIFACT)
        with self.assertRaises(PilotError):engine.scan(self.generate(fixture_records()), '2001-01-01T00:00:00Z', CAPS)

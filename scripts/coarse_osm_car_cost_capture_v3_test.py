"""Tiny mutable-writer controls before any captured input conversion."""
from array import array
from collections import Counter
import hashlib
import json
from coarse_osm_records import canonical
from pathlib import Path
import tempfile
import unittest

from coarse_osm_car_cost_capture_v3 import add, writer, convert
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


class QueryOracleTests(unittest.TestCase):
    def case(self, source, target, raw, quantized):
        return {'windowId': 'fixture', 'sourceNodeIds': [source, target], 'raw': {'costMs': raw}, 'binaryQuantizedMs': quantized}

    def fixture(self, closed, cases):
        from graph_capture_query_oracle_v2 import query_checks
        arcs = [(0, 1, 0, 0, 3, 1, 300), (1, 0, 0, 0, 3, -1, 450)]
        fragments = {(0, 0, 3): {'chain': (11, 22, 33, 44), 'prefix': {1: [0, 100, 200, 300], -1: [0, 150, 300, 450]}}}
        return query_checks(array('Q', [11, 22, 33, 44]), array('i', [0, 0, 1, 0, 2, 0, 3, 0]),
                            array('I', [0, 3]), bytes([4, 4]), [101], arcs, fragments, closed, [], cases)

    def test_paid_internal_aliases_direct_travel_and_directional_costs(self):
        result = self.fixture(set(), [self.case(22, 33, 100, 250), self.case(33, 22, 150, 250), self.case(22, 44, 200, 250)])
        self.assertEqual(result['internalPaidAliases'], 2);self.assertTrue(result['exactRawCostsAllMatch'])

    def test_closed_source_way_retains_native_points_and_unreachable_cases(self):
        result = self.fixture({101}, [self.case(22, 33, None, None), self.case(11, 44, None, None)])
        self.assertEqual(result['unreachableCasesPreserved'], 2);self.assertEqual(result['allNativePointsRetained'], 4)

    def test_only_turn_respects_history_and_allows_pretrip_source(self):
        from graph_capture_query_oracle_v2 import query_checks
        arcs = [(0, 1, 0, 0, 1, 1, 100), (1, 2, 1, 0, 1, 1, 100), (1, 3, 2, 0, 1, 1, 100)]
        fragments = {(i, 0, 1): {'chain': chain, 'prefix': {1: [0, 100]}} for i, chain in enumerate(((11, 22), (22, 33), (22, 44)))}
        rules = [{'fromWay': 101, 'via': 22, 'toWay': 202, 'kind': 'only_right_turn'}]
        result = query_checks(array('Q', [11, 22, 33, 44]), array('i', [0]*8), array('I', [0, 1, 2, 3]),
                              bytes([4]*4), [101, 202, 303], arcs, fragments, set(), rules,
                              [self.case(11, 33, 200, 250), self.case(11, 44, None, None), self.case(22, 44, 100, 125)])
        self.assertTrue(result['exactRawCostsAllMatch']);self.assertEqual(result['unreachableCasesPreserved'], 1)


class ConversionTests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Protected constructor artifact/cached pyosmium required')
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root = Path(temp.name)

    def capture(self, elements):
        source = self.root/'capture.jsonl'
        records = [{'publisherStateUtc': STATE, 'windowIds': ['fixture'], 'element': e,
                    'elementSha256': hashlib.sha256(canonical(e)).hexdigest()} for e in elements]
        raw = b''.join(canonical(record)+b'\n' for record in records);source.write_bytes(raw)
        return source, {'rows': len(records), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'types': dict(Counter(e['type'] for e in elements)), 'memberships': len(records)}

    def test_lexical_capture_is_reordered_with_exact_metadata_and_semantic_seal(self):
        elements = sorted(fixture_records(), key=lambda e: (e['type'], e['id']))
        source, expected = self.capture(elements);destination = self.root/'captured.osm.pbf'
        result = convert(source, destination, expected)
        ordered = sorted(elements, key=lambda e: (('node','way','relation').index(e['type']), e['id']))
        self.assertEqual(result['semanticSha256'], reference_seal(ordered))
        receipt = NativeScreen(*ARTIFACT).scan(destination, STATE, CAPS)
        self.assertEqual(receipt['semanticSha256'], result['semanticSha256']);self.assertTrue(receipt['nativeEof'])

    def test_source_hash_corruption_is_not_admitted(self):
        source, expected = self.capture(sorted(fixture_records(), key=lambda e: (e['type'], e['id'])))
        with self.assertRaises(PilotError):convert(source, self.root/'captured.osm.pbf', expected | {'sha256': '0'*64})

    def test_duplicate_capture_identity_is_rejected(self):
        elements = sorted(fixture_records(), key=lambda e: (e['type'], e['id']));elements[1] = elements[0]
        source, expected = self.capture(elements)
        with self.assertRaises(PilotError):convert(source, self.root/'captured.osm.pbf', expected)

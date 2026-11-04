"""Independent water-selector/count oracle; target artifact supplied explicitly."""
import random
import unittest

from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_native_smoke import STATE
from coarse_osm_water_census_v2 import WaterCensus
from coarse_timing_input import PilotError

ARTIFACT = None
CAPS = {'singleNormalizedElementBytes': 4194304, 'scanNodesPerPass': 10000, 'scanWaysPerPass': 10000,
        'scanRelationsPerPass': 10000, 'scanObjectVisitsTotal': 30000,
        'pbfHeaderBytesExclusiveMaximum': 65536, 'pbfUncompressedBlobBytesExclusiveMaximum': 33554432}


def way(identity, tags, nodes=None):
    return {'type': 'way', 'id': identity, 'version': 1, 'timestamp': STATE, 'visible': True,
            'tags': tags, 'nodes': [1, 2, 3, 1] if nodes is None else nodes}


def relation(identity, tags, members):
    return {'type': 'relation', 'id': identity, 'version': 1, 'timestamp': STATE, 'visible': True, 'tags': tags, 'members': members}


def oracle(rows):
    selected = [r for r in rows if r['type'] != 'node' and (r['tags'].get('natural') == 'water' or r['tags'].get('waterway') == 'riverbank' or r['tags'].get('landuse') == 'reservoir')]
    ways = [r for r in selected if r['type'] == 'way']
    relations = [r for r in selected if r['type'] == 'relation']
    members = [m for r in relations for m in r['members']]
    return {'nodes': sum(r['type'] == 'node' for r in rows), 'ways': sum(r['type'] == 'way' for r in rows),
            'relations': sum(r['type'] == 'relation' for r in rows), 'waterWays': len(ways),
            'waterWayReferences': sum(len(r['nodes']) for r in ways),
            'closedWaterWays': sum(r['nodes'][0] == r['nodes'][-1] for r in ways),
            'openWaterWays': sum(r['nodes'][0] != r['nodes'][-1] for r in ways),
            'waterRelations': len(relations), 'waterWayMembers': sum(m['type'] == 'way' for m in members),
            'waterNodeMembers': sum(m['type'] == 'node' for m in members), 'waterRelationMembers': sum(m['type'] == 'relation' for m in members),
            'outerWayMembers': sum(m['type'] == 'way' and m['role'] == 'outer' for m in members),
            'innerWayMembers': sum(m['type'] == 'way' and m['role'] == 'inner' for m in members),
            'otherRoleWayMembers': sum(m['type'] == 'way' and m['role'] not in ('outer', 'inner') for m in members),
            'selectedEncodedBytes': sum(len(framed_records([r]))-4 for r in selected),
            'maximumWaterWayReferences': max((len(r['nodes']) for r in ways), default=0),
            'maximumWaterRelationMembers': max((len(r['members']) for r in relations), default=0),
            'selectedTagUtf8Bytes': sum(len(k.encode())+len(v.encode()) for r in selected for k, v in r['tags'].items()),
            'naturalWaterFeatures': sum(r['tags'].get('natural') == 'water' for r in selected),
            'riverbankFeatures': sum(r['tags'].get('waterway') == 'riverbank' for r in selected),
            'reservoirLanduseFeatures': sum(r['tags'].get('landuse') == 'reservoir' for r in selected),
            'multipolygonWaterRelations': sum(r['tags'].get('type') == 'multipolygon' for r in relations),
            'otherTypeWaterRelations': sum(r['tags'].get('type') != 'multipolygon' for r in relations),
            'waterWaysAlsoHighways': sum('highway' in r['tags'] for r in ways),
            'lastWaterWayId': max((r['id'] for r in ways), default=0), 'lastWaterRelationId': max((r['id'] for r in relations), default=0),
            'shortClosedWaterWays': sum(r['nodes'][0] == r['nodes'][-1] and len(r['nodes']) < 4 for r in ways), 'complete': 1,
            **{label+'Features': sum(r['tags'].get('water') == label for r in selected) for label in ('lake', 'reservoir', 'river', 'pond', 'basin', 'canal', 'lagoon')},
            'otherWaterSubtypeFeatures': sum(r['tags'].get('water') not in ('lake', 'reservoir', 'river', 'pond', 'basin', 'canal', 'lagoon') for r in selected)}


class Tests(unittest.TestCase):
    def engine(self):
        if ARTIFACT is None:
            self.skipTest('Explicit compiled water target artifact required')
        return WaterCensus(*ARTIFACT)

    def compare(self, rows, proof=False):
        engine = self.engine()
        engine.begin()
        try:
            receipt = engine.validate_frames(framed_records(rows), STATE, CAPS, proof=proof)
            actual = engine.finish()
            expected = oracle(rows)
            self.assertEqual({k: actual[k] for k in expected}, expected)
            self.assertEqual(receipt['pythonProjectionFrames'], len(rows) if proof else 0)
            return actual
        finally:
            engine.release()

    def test_selector_union_and_all_member_roles(self):
        members = [{'type': 'way', 'ref': i+1, 'role': role} for i, role in enumerate(('outer', 'inner', '', 'unknown'))]
        members += [{'type': 'node', 'ref': 1, 'role': 'label'}, {'type': 'relation', 'ref': 2, 'role': 'outer'}]
        self.compare([way(10, {'natural': 'water', 'water': 'lake'}), way(11, {'waterway': 'riverbank'}, [1, 2]),
                      way(12, {'landuse': 'reservoir', 'natural': 'water', 'highway': 'service'}, [1, 1]),
                      way(13, {'waterway': 'stream'}), relation(100, {'type': 'multipolygon', 'natural': 'water'}, members)])

    def test_unrelated_water_tags_and_nodes_are_not_polygons(self):
        node = {'type': 'node', 'id': 1, 'version': 1, 'timestamp': STATE, 'visible': True, 'tags': {'natural': 'water'}, 'lon': 0., 'lat': 0.}
        self.compare([node, way(10, {'water': 'lake'}), way(11, {'natural': 'wetland'}), relation(100, {'type': 'multipolygon'}, [])])

    def test_nonmultipolygon_nested_and_unknown_tags_stay_explicit(self):
        result = self.compare([relation(100, {'natural': 'water', 'water': 'unknown', 'type': 'boundary'}, [{'type': 'relation', 'ref': 1, 'role': 'outer'}])])
        self.assertEqual((result['otherTypeWaterRelations'], result['waterRelationMembers']), (1, 1))

    def test_one_hundred_generated_unfiltered_way_sets(self):
        rng = random.Random(20261103)
        choices = [{'natural': 'water', 'water': 'lake'}, {'waterway': 'riverbank'}, {'landuse': 'reservoir'}, {'water': 'lake'}, {'natural': 'wood'}, {'natural': 'water', 'water': 'pond'}]
        for _ in range(100):
            self.compare([way(10+i, dict(rng.choice(choices)), [1, 2, 3, 1] if rng.randrange(2) else [1, 2, 3]) for i in range(20)])

    def test_selected_semantic_frame_crosses_callback_boundaries(self):
        self.compare([way(10, {'natural': 'water', 'note': 'x'*1200000})])

    def test_proof_mode_source_frames_equal_summary_counters(self):
        rows = [way(10, {'natural': 'water'}), way(11, {'landuse': 'reservoir'})]
        self.assertEqual(self.compare(rows), self.compare(rows, proof=True))

    def test_finish_reentry_and_repeated_finish_fail_closed(self):
        engine, other = self.engine(), self.engine()
        engine.begin()
        try:
            with self.assertRaises(PilotError): engine.finish()
            with self.assertRaises(PilotError): other.begin()
            engine.validate_frames(framed_records([way(10, {'natural': 'water'})]), STATE, CAPS)
            engine.finish()
            with self.assertRaises(PilotError): engine.finish()
            with self.assertRaises(PilotError): engine.validate_frames(framed_records([]), STATE, CAPS)
        finally:
            engine.release()

    def test_source_failure_never_yields_complete_water_counts(self):
        engine = self.engine()
        engine.begin()
        try:
            with self.assertRaises(PilotError): engine.validate_frames(framed_records([way(10, {'natural': 'water'}, [1, 0])]), STATE, CAPS)
            with self.assertRaises(PilotError): engine.finish()
        finally:
            engine.release()

    def test_zero_count_types_and_empty_stream_match_unchanged_source_receipt(self):
        for rows in ([], [way(10, {'natural': 'water'})], [relation(100, {'natural': 'water'}, [])]):
            self.compare(rows)

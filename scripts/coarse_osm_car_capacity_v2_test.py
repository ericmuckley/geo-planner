"""Independent tiny source-way/permission/count controls for the composed source reader."""
from array import array
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_car_capacity_v2 import Capacity
from coarse_osm_car_partition_v1_test import splits
from coarse_osm_car_policy_v1 import POLICY, restriction_policy, way_policy
from coarse_osm_country_wire_v4 import framed_records, reference_seal
from coarse_osm_native_smoke import STATE
from coarse_osm_topology_source_v1 import NativeScreen
from coarse_timing_input import PilotError

ARTIFACT = None
CAPS = {'singleNormalizedElementBytes': 4194304, 'scanNodesPerPass': 100000, 'scanWaysPerPass': 100000,
        'scanRelationsPerPass': 100000, 'scanObjectVisitsTotal': 300000,
        'pbfHeaderBytesExclusiveMaximum': 65536, 'pbfUncompressedBlobBytesExclusiveMaximum': 33554432}


def records(ways, node_tags=None, relations=None):
    node_tags, relations = node_tags or {}, relations or []
    identities = sorted({node for _, refs, _ in ways for node in refs} | set(node_tags))
    base = {'version': 1, 'timestamp': STATE, 'visible': True}
    nodes = [base | {'type': 'node', 'id': i, 'lat': i/1000, 'lon': i/1000, 'tags': node_tags.get(i, {})} for i in identities]
    rows = nodes + [base | {'type': 'way', 'id': way, 'nodes': refs, 'tags': tags} for way, refs, tags in sorted(ways)]
    rows += [base | {'type': 'relation', 'id': identity, 'tags': tags, 'members': members} for identity, tags, members in relations]
    return rows


def member(kind, identity, role):
    return {'type': kind, 'ref': identity, 'role': role}


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:
            self.skipTest('Protected composed car capacity artifact required')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.index = 0

    def engine(self):
        engine = Capacity(*ARTIFACT, aggregate_visits=1000000, codec_rows=2000000)
        self.addCleanup(engine.release)
        return engine

    def verify(self, ways, node_tags=None, relations=None):
        node_tags, relations = node_tags or {}, relations or []
        rows = records(ways, node_tags, relations)
        selected = {way: refs for way, refs, tags in ways if tags.get('highway') in POLICY['roles']}
        via = [m['ref'] for _, _, members in relations for m in members if m['type'] == 'node']
        partitions, anchors = splits(selected, [n for n, tags in node_tags.items() if tags], via)
        self.index += 1
        directory = self.root/str(self.index)
        directory.mkdir()
        engine = self.engine()
        engine.begin(array('Q', partitions), max(r['id'] for r in rows if r['type'] == 'node'), directory)
        try:
            receipt = engine.validate_frames(framed_records(rows), STATE, CAPS)
            self.assertEqual(receipt['semanticSha256'], reference_seal(rows))
            self.assertEqual(receipt['pythonProjectionFrames'], 0)
            report = engine.finish()
        finally:
            engine.release()
        closed = set()
        for identity, tags, members in relations:
            rule = restriction_policy({'id': identity, 'tags': tags, 'members': members})
            if rule['status'] == 'closed-unsupported':
                closed.update(rule['memberWays'])
        expected = []
        for way, refs, tags in sorted(ways):
            if way not in selected:
                continue
            cuts = [i for i, node in enumerate(refs) if node in anchors]
            segments = sum(any(n != refs[first] for n in refs[first:last+1]) for first, last in zip(cuts, cuts[1:]))
            policy = way_policy(tags)
            directions = int(policy.forward is not None) + int(policy.backward is not None)
            expected.append((way, refs[0], refs[-1], segments, directions, way in closed))
        facts = [r for p in sorted(directory.glob('ways-*.bin')) for r in struct.iter_unpack('<QQQII', p.read_bytes())]
        self.assertEqual([f[:4] for f in facts], [f[:4] for f in expected])
        self.assertEqual(report['preClosureArcs'], sum(f[3]*f[4] for f in expected))
        self.assertEqual(report['postLocatableClosureArcs'], sum(f[3]*f[4] for f in expected if not f[5]))
        self.assertEqual(report['lineageSegmentsIncludingZero'], len(selected)+len(partitions))
        self.assertEqual(report['nonzeroLineageSegments'], sum(f[3] for f in expected))
        return report, directory

    def test_roles_directions_access_and_default_speed_counts(self):
        ways = [(i+1, [1, 2, 3], {'highway': role, 'oneway': 'yes' if i%2 else 'no'}) for i, role in enumerate(POLICY['roles'])]
        ways += [(99, [1, 3], {'highway': 'residential'}), (100, [2, 3], {'highway': 'primary', 'access': 'private'})]
        report, _ = self.verify(ways, {2: {'highway': 'traffic_signals'}})
        self.assertEqual(report['majorWays'], 11)
        self.assertEqual(report['allSignalNodes'], 1)
        self.assertEqual(report['wayReasons']['access'], 1)

    def test_unsupported_closures_and_supported_turns_remain_distinct(self):
        ways = [(1, [1, 2], {'highway': 'primary'}), (2, [2, 3], {'highway': 'primary'}), (3, [3, 4], {'highway': 'primary'})]
        relations = [(1, {'type': 'restriction', 'restriction': 'no_left_turn'}, [member('way', 1, 'from'), member('node', 2, 'via'), member('way', 2, 'to')]),
                     (2, {'type': 'restriction', 'restriction': 'no_u_turn'}, [member('way', 1, 'from'), member('way', 2, 'via'), member('way', 3, 'to')])]
        report, _ = self.verify(ways, relations=relations)
        self.assertEqual(report['supportedViaNodeRules'], 1)
        self.assertEqual(report['unsupportedRelations'], 1)
        self.assertEqual(report['postLocatableClosureArcs'], 0)

    def test_ferry_conditional_and_directional_access_exclusions(self):
        self.verify([(1, [1, 2], {'highway': 'primary', 'route': 'ferry'}),
                     (2, [2, 3], {'highway': 'primary', 'motorcar:forward': 'no', 'motorcar:backward': 'no'}),
                     (3, [3, 4], {'highway': 'primary', 'maxspeed:conditional': '50 @ Mo'})])

    def test_zero_repeated_parallel_and_closed_native_geometry(self):
        self.verify([(1, [1, 2, 3, 1], {'highway': 'primary'}), (2, [1, 2, 2, 3], {'highway': 'primary'}),
                     (3, [1, 1, 1], {'highway': 'primary'}), (4, [1, 3], {'highway': 'trunk'})])

    def test_seeded_graphs_match_independent_explicit_anchor_cuts(self):
        rng = random.Random(20261105)
        for _ in range(100):
            ways = [(i+1, [rng.randrange(1, 20) for _ in range(rng.randrange(2, 15))],
                     {'highway': rng.choice(POLICY['roles']), 'oneway': rng.choice(['yes', 'no', '-1'])}) for i in range(rng.randrange(1, 10))]
            self.verify(ways, {2: {'barrier': 'gate'}})

    def test_semantic_frame_crosses_callback_chunks_without_projection(self):
        self.verify([(1, [1, 2], {'highway': 'primary'})], {1: {'note': 'x' * 1100000}})

    def test_unlocatable_restriction_is_counted_without_permission_admission(self):
        rows = records([(1, [1, 2], {'highway': 'primary'})], relations=[(1, {'type': 'restriction', 'restriction': 'unknown'}, [])])
        engine = self.engine()
        engine.begin(array('Q'), 2, self.root)
        engine.validate_frames(framed_records(rows), STATE, CAPS)
        result = engine.finish()
        self.assertEqual(result['unlocatableRestrictions'], 1)
        self.assertFalse(result['policyFullyLocatable'])
        self.assertEqual((self.root/'unlocatable-restrictions.u64').read_bytes(), struct.pack('<Q', 1))

    def test_missing_native_nodes_and_invalid_source_fail_before_finish(self):
        rows = records([(1, [1, 2], {'highway': 'primary'})])
        rows[2]['nodes'] = [1, 3]
        engine = self.engine()
        engine.begin(array('Q'), 3, self.root)
        with self.assertRaisesRegex(PilotError, 'car_missing_selected_source_node'):
            engine.validate_frames(framed_records(rows), STATE, CAPS)
        with self.assertRaises(PilotError):
            engine.finish()
        self.assertFalse(list(self.root.glob('ways-*')))

    def test_partition_order_cap_and_orphan_way_fail_closed(self):
        engine = self.engine()
        with self.assertRaises(PilotError):
            engine.begin(array('Q', [2, 1]), 4, self.root)
        engine.begin(array('Q', [999]), 2, self.root)
        engine.validate_frames(framed_records(records([(1, [1, 2], {'highway': 'primary'})])), STATE, CAPS)
        with self.assertRaises(PilotError):
            engine.finish()

    def test_session_reentry_and_duplicate_finish_preserve_output(self):
        engine = self.engine()
        engine.begin(array('Q'), 2, self.root)
        other = self.engine()
        with self.assertRaises(PilotError):
            other.begin(array('Q'), 2, self.root)
        engine.validate_frames(framed_records(records([(1, [1, 2], {'highway': 'primary'})])), STATE, CAPS)
        engine.finish()
        before = (self.root/'ways-0000.bin').read_bytes()
        with self.assertRaises(PilotError):
            engine.finish()
        self.assertEqual((self.root/'ways-0000.bin').read_bytes(), before)

    def test_existing_output_and_early_finish_fail_closed(self):
        engine = self.engine()
        engine.begin(array('Q'), 2, self.root)
        with self.assertRaises(PilotError):
            engine.finish()
        engine.validate_frames(framed_records(records([(1, [1, 2], {'highway': 'primary'})])), STATE, CAPS)
        (self.root/'ways-0000.bin').write_bytes(b'preserved')
        with self.assertRaises(PilotError):
            engine.finish()
        self.assertEqual((self.root/'ways-0000.bin').read_bytes(), b'preserved')

    def test_release_during_callback_cannot_destroy_active_consumer(self):
        engine = self.engine()
        engine.begin(array('Q'), 2, self.root)
        def visit(record):
            engine.library.gp_car_capacity_release()
            with self.assertRaises(PilotError):
                engine.release()
        engine.validate_frames(framed_records(records([(1, [1, 2], {'highway': 'primary'})])), STATE, CAPS, proof=True, on_record=visit)
        self.assertEqual(engine.finish()['majorWays'], 1)

    def test_absent_source_types_mean_explicit_zero_not_mismatch(self):
        report, _ = self.verify([], {1: {}})
        self.assertEqual((report['nodes'], report['ways'], report['relations']), (1, 0, 0))
        self.assertEqual(report['preClosureArcs'], 0)

"""Draft independent tiny source geometry/permission/cost-fact oracle."""
from array import array
import math
from pathlib import Path
import random
import struct
import tempfile
import unittest

from import_roads import distance_m
from coarse_osm_car_capacity_v2_test import CAPS, member, records
from coarse_osm_car_cost_graph_v1 import CostGraph
from coarse_osm_car_native_policy_v1 import TURNS
from coarse_osm_car_partition_v1_test import splits
from coarse_osm_car_policy_v2 import POLICY, node_policy, restriction_policy, way_policy
from coarse_osm_country_wire_v4 import framed_records, reference_seal
from coarse_osm_native_smoke import STATE
from coarse_timing_input import PilotError

ARTIFACT = None
WAY = struct.Struct('<QddII')
ARC = struct.Struct('<IIIIIb3xQ')
TURN = struct.Struct('<QQQQB7x')


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Compiled draft cost graph required')
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root = Path(temp.name);self.counter = 0

    def fixture(self, ways, node_tags=None, relations=None, mutate=lambda rows: rows):
        rows = records(ways, node_tags, relations)
        selected = {way: refs for way, refs, tags in ways if tags.get('highway') in POLICY['roles']}
        tagged = [row['id'] for row in rows if row['type'] == 'node' and row['tags']]
        relation_nodes = sorted(m['ref'] for row in rows if row['type'] == 'relation' for m in row['members'] if m['type'] == 'node')
        anchors = splits(selected, tagged, relation_nodes)[1]
        references = [(node, way, 1 if i in (0, len(refs)-1) else 2, int(i in (0, len(refs)-1))) for way, refs in selected.items() for i, node in enumerate(refs)]
        references.sort(key=lambda r: (r[0], r[1], r[3], r[2]))
        self.counter += 1;root = self.root/str(self.counter);root.mkdir();output = root/'output';output.mkdir()
        files = []
        for i in range(0, len(references), 7):
            path = root/f'refs-{i}';path.write_bytes(b''.join(struct.pack('<QQII', *row) for row in references[i:i+7]));files.append(path)
        tags = root/'tags';tags.write_bytes(b''.join(struct.pack('<Q', n) for n in tagged))
        expected = {'reference_count': len(references), 'way_count': len(selected), 'tag_count': len(tagged),
                    'maximum': max((row['id'] for row in rows if row['type'] == 'node'), default=1),
                    'selected': len({r[0] for r in references}), 'anchors': len(anchors)}
        engine = CostGraph(*ARTIFACT, aggregate_visits=1000000, codec_rows=2000000)
        self.addCleanup(engine.release)
        engine.begin(files, [tags], array('Q', relation_nodes), output, **expected)
        return engine, mutate(rows), output, anchors

    def read(self, root, prefix, code=None):
        raw = b''.join(path.read_bytes() for path in sorted(root.glob(prefix+'-*.bin')))
        if code is None:return raw
        values = array(code);values.frombytes(raw);return values

    def verify(self, ways, node_tags=None, relations=None, mutate=lambda rows: rows):
        engine, rows, output, anchor_ids = self.fixture(ways, node_tags, relations, mutate)
        receipt = engine.validate_frames(framed_records(rows), STATE, CAPS)
        self.assertEqual(receipt['semanticSha256'], reference_seal(rows));self.assertEqual(receipt['pythonProjectionFrames'], 0)
        result = engine.finish();engine.release()
        major = [(way, refs, tags) for way, refs, tags in sorted(ways) if tags.get('highway') in POLICY['roles']]
        ids = sorted({node for _, refs, _ in major for node in refs});positions = {node: i for i, node in enumerate(ids)}
        anchors = sorted(anchor_ids);vertex = {node: i for i, node in enumerate(anchors)}
        self.assertEqual(list(self.read(output, 'ids', 'Q')), ids)
        self.assertEqual(list(self.read(output, 'anchors', 'I')), [positions[node] for node in anchors])
        node_rows = {row['id']: row for row in rows if row['type'] == 'node'}
        xy = {node: (round(node_rows[node]['lon']*1e7), round(node_rows[node]['lat']*1e7)) for node in ids}
        self.assertEqual(list(self.read(output, 'xy', 'i')), [v for node in ids for v in xy[node]])
        self.assertEqual(list(self.read(output, 'geometry', 'I')), [positions[node] for _, refs, _ in major for node in refs])
        facts = list(WAY.iter_unpack(self.read(output, 'ways')))
        self.assertEqual([row[0] for row in facts], [way for way, _, _ in major])
        end = 0;expected = [];physical = 0
        for ordinal, (way, refs, tags) in enumerate(major):
            end += len(refs);self.assertEqual(facts[ordinal][-1], end)
            policy = way_policy(tags);mask = int(policy.forward is not None)+2*int(policy.backward is not None)
            self.assertEqual(facts[ordinal][3] & 3, mask)
            for i, speed in enumerate((policy.forward, policy.backward), 1):
                if speed is not None:self.assertEqual(facts[ordinal][i], speed)
            cuts = [i for i, node in enumerate(refs) if node in anchor_ids]
            for first, last in zip(cuts, cuts[1:]):
                if all(node == refs[first] for node in refs[first:last+1]):continue
                physical += 1
                for direction, speed in ((1, policy.forward), (-1, policy.backward)):
                    if speed is None:continue
                    cost = 0
                    for a, b in zip(refs[first:last], refs[first+1:last+1]):
                        p = [v/1e7 for v in xy[a]];q = [v/1e7 for v in xy[b]]
                        cost += 0 if a == b else max(1, math.ceil(distance_m(p, q)*3600/speed))
                    tail, head = (refs[first], refs[last]) if direction == 1 else (refs[last], refs[first])
                    expected.append((vertex[tail], vertex[head], ordinal, first, last, direction, cost))
        actual = list(ARC.iter_unpack(self.read(output, 'arcs')));self.assertEqual(actual, expected)
        closures = set();blocked = set();turns = [];invalid = 0
        for row in rows:
            if row['type'] != 'relation':continue
            rule = restriction_policy(row)
            if rule['status'] == 'closed-unsupported':
                closures.update(rule['memberWays'])
                if not rule['memberWays']:blocked.update(rule['memberNodes'])
            elif rule['status'] == 'via-node':turns.append((row['id'], rule['fromWay'], rule['via'], rule['toWay'], TURNS.index(rule['kind'])))
            elif rule['status'] == 'invalid-unlocatable':invalid += 1
        self.assertEqual(list(TURN.iter_unpack(self.read(output, 'turns'))), turns)
        self.assertEqual(list(self.read(output, 'closures', 'Q')), sorted(closures))
        self.assertEqual(list(self.read(output, 'flags')), [4 | int(node_policy(node_rows[n]['tags'])['blocked'] or n in blocked) | 2*int(node_policy(node_rows[n]['tags'])['signal']) for n in anchors])
        self.assertEqual(result['invalidUnlocatableRestrictions'], invalid)
        self.assertEqual(result['preClosureArcs'], len(expected));self.assertEqual(result['nonzeroLineageSegments'], physical)
        retained = [row for row in expected if major[row[2]][0] not in closures]
        self.assertEqual(result['postClosureArcs'], len(retained))
        for key, arcs in (('preClosureCostOverflows', expected), ('postClosureCostOverflows', retained)):
            self.assertEqual(result[key], sum((row[-1]+124)//125 >= 65535 for row in arcs))
        self.assertEqual(result['outputBytes'], sum(p.stat().st_size for p in output.iterdir()))
        self.assertTrue(all(p.stat().st_size <= 16*1048576 for p in output.iterdir()))
        return result, output

    def test_all_roles_directions_and_access_exclusions(self):
        ways = [(i+1, [1, 2, 3], {'highway': role, 'oneway': 'yes' if i%2 else 'no'}) for i, role in enumerate(POLICY['roles'])]
        ways += [(99, [3, 4], {'highway': 'residential'}), (100, [1, 4], {'highway': 'primary', 'access': 'private'})]
        self.verify(ways)

    def test_curved_full_geometry_cost_is_preserved(self):
        def curve(rows):
            for row in rows:
                if row['type'] == 'node':row.update(lon={1: 0., 2: 1., 3: 0.}[row['id']], lat={1: 0., 2: 1., 3: .0000001}[row['id']])
            return rows
        result, _ = self.verify([(1, [1, 2, 3], {'highway': 'primary'})], mutate=curve)
        self.assertGreater(result['maximumMacroMs'], 10000000)

    def test_signals_barriers_and_junction_cut_metadata(self):
        self.verify([(1, [1, 2, 3, 4], {'highway': 'primary'}), (2, [3, 5], {'highway': 'secondary'})],
                    {2: {'highway': 'traffic_signals'}, 4: {'barrier': 'bollard'}})

    def test_parallel_loops_repeats_and_distinct_coincident_nodes(self):
        def coincident(rows):
            for row in rows:
                if row['type'] == 'node' and row['id'] in (8, 9):row.update(lon=0., lat=0.)
            return rows
        self.verify([(1, [1, 2, 3, 1], {'highway': 'primary'}), (2, [1, 2, 3], {'highway': 'secondary'}),
                     (3, [4, 4, 5], {'highway': 'tertiary'}), (4, [8, 9], {'highway': 'primary'})], mutate=coincident)

    def test_supported_via_node_rules_remain_source_rules(self):
        relations = [(1, {'type': 'restriction', 'restriction': 'only_right_turn'}, [member('way', 1, 'from'), member('node', 2, 'via'), member('way', 2, 'to')])]
        self.verify([(1, [1, 2], {'highway': 'primary'}), (2, [2, 3], {'highway': 'primary'})], relations=relations)

    def test_unsupported_way_and_node_only_closures_are_preserved(self):
        relations = [(1, {'type': 'restriction', 'restriction': 'unknown'}, [member('way', 1, 'from')]),
                     (2, {'type': 'restriction', 'restriction': 'unknown'}, [member('node', 2, 'via')])]
        self.verify([(1, [1, 2], {'highway': 'primary'}), (2, [2, 3], {'highway': 'secondary'})], relations=relations)

    def test_invalid_unlocatable_records_retain_the_complete_frame(self):
        relations = [(1, {'type': 'restriction', 'restriction': 'unknown', 'note': 'fixture 雪'}, [member('relation', 91, 'from')])]
        _, output = self.verify([(1, [1, 2], {'highway': 'primary'})], relations=relations)
        raw = self.read(output, 'invalid');self.assertEqual(int.from_bytes(raw[:4], 'little'), len(raw)-4)
        self.assertEqual(raw[4:8], b'GPF1');self.assertIn('fixture 雪'.encode(), raw)

    def test_missing_selected_coordinate_and_extra_reference_fail(self):
        for mutate in (lambda rows: [r for r in rows if not (r['type'] == 'node' and r['id'] == 2)],
                       lambda rows: [r | {'nodes': [1, 3]} if r['type'] == 'way' else r for r in rows]):
            engine, rows, _, _ = self.fixture([(1, [1, 2], {'highway': 'primary'})], mutate=mutate)
            with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows), STATE, CAPS)
            with self.assertRaises(PilotError):engine.finish()
            engine.release()

    def test_prepare_rejects_bad_expected_counts(self):
        engine = CostGraph(*ARTIFACT);self.addCleanup(engine.release)
        for kwargs in ({'selected': 64000001}, {'maximum': True}, {'anchors': 2}):
            values = {'reference_count': 0, 'way_count': 0, 'tag_count': 0, 'maximum': 1, 'selected': 0, 'anchors': 0} | kwargs
            with self.assertRaises(PilotError):engine.begin([], [], array('Q'), self.root, **values)

    def test_bad_source_epoch_is_not_completion(self):
        engine, rows, _, _ = self.fixture([(1, [1, 2], {'highway': 'primary'})])
        with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows), '2001-01-01T00:00:00Z', CAPS)
        with self.assertRaises(PilotError):engine.finish()

    def test_finish_replay_and_reentrant_begin_fail(self):
        engine, rows, output, _ = self.fixture([(1, [1, 2], {'highway': 'primary'})])
        with self.assertRaises(PilotError):engine.finish()
        with self.assertRaises(PilotError):engine.begin([], [], array('Q'), output, reference_count=0, way_count=0, tag_count=0, maximum=1, selected=0, anchors=0)
        engine.validate_frames(framed_records(rows), STATE, CAPS);engine.finish()
        with self.assertRaises(PilotError):engine.finish()
        with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows), STATE, CAPS)

    def test_release_during_callback_cannot_destroy_the_consumer(self):
        engine, rows, _, _ = self.fixture([(1, [1, 2], {'highway': 'primary'})])
        def visit(record):
            engine.library.gp_car_graph_release()
            with self.assertRaises(PilotError):engine.release()
        engine.validate_frames(framed_records(rows), STATE, CAPS, proof=True, on_record=visit)
        self.assertEqual(engine.finish()['majorWays'], 1)

    def test_seeded_small_graphs_match_all_source_facts(self):
        rng = random.Random(20261103)
        for _ in range(25):
            ways = [(i, [rng.randrange(1, 30) for _ in range(rng.randrange(2, 12))],
                     {'highway': rng.choice(POLICY['roles']), 'oneway': rng.choice(['yes', 'no', '-1']), 'maxspeed': rng.choice(['30', '45 mph', '50'])}) for i in range(1, 12)]
            self.verify(ways)

    def test_empty_selected_profile_and_absent_source_types(self):
        result, _ = self.verify([], {1: {}})
        self.assertEqual((result['nodes'], result['ways'], result['relations']), (1, 0, 0))
        self.assertEqual((result['selectedCoordinatesSeen'], result['preClosureArcs']), (0, 0))

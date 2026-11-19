import copy
import unittest

from coarse_osm_blocked_node_causes_v1 import node_cause
from coarse_osm_conditional_node_facts_v1 import (
    TURN, audit_turns, merge_turns, native_passable_flags, relation_overlay,
)
from coarse_osm_conditional_node_ports_v1 import qualify
from coarse_osm_conditional_node_ports_v1_test import fixture
from coarse_osm_conditional_node_turns_v2 import classify
from coarse_timing_input import PilotError


def relation(identity=2, kind='no_left_turn', extra=None):
    return {'type': 'relation', 'id': identity,
            'tags': {'type': 'restriction', 'restriction:conditional': kind + ' @ (Mo-Fr)', **(extra or {})},
            'members': [{'type': 'way', 'ref': 10, 'role': 'from'},
                        {'type': 'node', 'ref': 200, 'role': 'via'},
                        {'type': 'way', 'ref': 20, 'role': 'to'}]}


def prepared(element=None):
    from dataclasses import asdict
    element = element or relation()
    rule = classify(element)['rule']
    metadata = [{'source': element, 'derived': {k: str(v) if type(v) is int else v
                                             for k, v in asdict(rule).items()}}]
    return metadata, qualify(fixture(), [rule])['rows']


class Tests(unittest.TestCase):
    def test_exact_contributor_replacement_shared_ways_and_unrelated_fallback(self):
        metadata, ports = prepared()
        retained = relation(3, extra={'access:conditional': 'no @ (snow)'})
        result = relation_overlay([relation(), retained], {}, {}, {10, 20}, metadata, ports)
        self.assertEqual(result['closed'], {10, 20})
        self.assertEqual(result['sharedClosedWaysRetained'], 2)
        self.assertEqual(result['added'][2], (2, 10, 200, 20, 0, bytes(7)))
        result = relation_overlay([relation()], {}, {}, {10, 20}, metadata, ports)
        self.assertEqual(result['reopenedWayIds'], [10, 20])

    def test_missing_physical_ports_or_outside_local_relations_never_converts(self):
        metadata, ports = prepared()
        ports[0]['status'] = 'no-directed-incoming-source-port'
        result = relation_overlay([relation()], {}, {}, {10, 20}, metadata, ports)
        self.assertFalse(result['added'])
        self.assertEqual(result['closed'], {10, 20})
        metadata, ports = prepared()
        result = relation_overlay([], {}, {}, set(), metadata, ports)
        self.assertFalse(result['added'])
        self.assertEqual(result['sourceSupportedOutsideLocalMetadata'], 1)

    def test_union_metadata_source_descriptor_and_decision_drift_refuse(self):
        metadata, ports = prepared()
        with self.assertRaises(PilotError):
            relation_overlay([relation()], {}, {}, {10}, metadata, ports)
        for key, value in [('toWayId', '30'), ('incomingPreArcIds', [])]:
            altered = copy.deepcopy(ports)
            altered[0][key] = value
            with self.assertRaises(PilotError):
                relation_overlay([relation()], {}, {}, {10, 20}, metadata, altered)
        with self.assertRaises(PilotError):
            relation_overlay([relation()], {123: 0}, {}, {10, 20}, metadata, ports)
        changed = relation(extra={'name': 'changed source'})
        with self.assertRaises(PilotError):
            relation_overlay([changed], {}, {}, {10, 20}, metadata, ports)

    def test_sorted_turn_merge_preserves_every_old_byte_and_native_ids(self):
        original = b''.join(TURN.pack(i, 10, 200, 20, 7, bytes(7)) for i in (1, 3, 5))
        additions = {i: (i, 10, 200, 20, i % 4, bytes(7)) for i in (2, 4, 6, 2**53 + 1)}
        proposed = merge_turns(original, additions)
        proof = audit_turns(original, proposed, additions)
        self.assertEqual(proof['oldSourceTurnsByteExact'], 3)
        self.assertEqual(proof['newAllStateJunctionBans'], 4)
        self.assertEqual(merge_turns(original, {}), original)
        self.assertEqual(len(merge_turns(b'', additions)), 4 * TURN.size)
        with self.assertRaises(PilotError):
            merge_turns(original, {1: additions[2]})
        altered = bytearray(proposed)
        altered[TURN.size + 32] = 1
        with self.assertRaises(PilotError):
            audit_turns(original, bytes(altered), additions)

    def test_native_flag_rebase_preserves_signals_reversals_and_node_contributors(self):
        ids = [100, 200, 300]
        anchors = [0, 2]
        flags = bytes([7, 5])
        tags = {'barrier': 'cattle_grid', 'highway': 'traffic_signals'}
        evidence = {'100': node_cause(100, 7, {'type': 'node', 'id': 100, 'tags': tags}, []),
                    '300': node_cause(300, 5, {'type': 'node', 'id': 300, 'tags': {}}, [99])}
        mapping = [{'vertex': 1, 'sourceAnchor': 0, 'sourceNodeIndex': 0, 'sourceNodeId': '100', 'flags': 7},
                   {'vertex': 0, 'sourceAnchor': 1, 'sourceNodeIndex': 2, 'sourceNodeId': '300', 'flags': 5}]
        proposed, proof = native_passable_flags(flags, mapping, evidence, ids, anchors)
        self.assertEqual(proposed, bytes([6, 5]))
        self.assertEqual(proof['changedVertices'], [0])
        self.assertTrue(proof['everyIndependentRestrictionContributorRetained'])
        for key, value in [('sourceAnchor', 1), ('sourceNodeIndex', 1), ('sourceNodeId', '200')]:
            altered = copy.deepcopy(mapping)
            altered[0][key] = value
            with self.assertRaises(PilotError):
                native_passable_flags(flags, altered, evidence, ids, anchors)

    def test_all_four_ban_kinds_retain_exact_static_native_meaning(self):
        for kind, native_kind in [('no_left_turn', 0), ('no_right_turn', 1),
                                  ('no_straight_on', 2), ('no_u_turn', 3)]:
            element = relation(kind=kind)
            metadata, ports = prepared(element)
            result = relation_overlay([element], {}, {}, {10, 20}, metadata, ports)
            self.assertEqual(result['added'][2][4], native_kind)
            self.assertFalse(result['closed'])


if __name__ == '__main__':
    unittest.main()

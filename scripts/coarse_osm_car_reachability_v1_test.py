"""Diagnostic switch/witness controls; no source files or producer replay."""
import unittest
from unittest.mock import patch

from coarse_osm_car_policy_v1 import way_policy
from coarse_osm_car_reachability_v1 import Network
from coarse_timing_input import PilotError


def network(ways, flags=None, rules=None, closures=None):
    identities = list(range(1, 7))
    policies = {identity: way_policy({'highway': 'primary'} | tags) for identity, _, tags in ways}
    graph = Network(identities, bytearray(flags or [4] * 6), policies, rules or {}, closures or {})
    for identity, refs, _ in ways:
        graph.add_way(identity, refs)
    return graph


class DiagnosticTests(unittest.TestCase):
    def test_direction_switch_keeps_access_closures(self):
        graph = network([(1, [0, 1], {'oneway': 'yes'})])
        self.assertFalse(graph.query(1, 0)['reachable'])
        result = graph.query(1, 0, 'without-direction-limits')
        self.assertTrue(result['reachable'])
        self.assertEqual(graph.witness(result)['disallowedDirectionWaysUsed'], [1])

    def test_excluded_way_has_separate_witness(self):
        graph = network([(1, [0, 1], {'access': 'private'})])
        self.assertFalse(graph.query(0, 1, 'without-direction-limits')['reachable'])
        result = graph.query(0, 1, 'without-way-exclusions')
        self.assertEqual(graph.witness(result)['excludedWaysUsed'], {'1': 'access'})

    def test_unsupported_closure_identifies_source_relation(self):
        graph = network([(1, [0, 1], {})], closures={1: [99]})
        self.assertFalse(graph.query(0, 1)['reachable'])
        result = graph.query(0, 1, 'without-unsupported-closures')
        self.assertTrue(result['reachable'])
        self.assertEqual(graph.witness(result)['unsupportedClosuresUsed'], {'1': [99]})

    def test_control_crossing_start_and_destination_differ(self):
        graph = network([(1, [0, 1, 2], {})], flags=[4, 5, 4, 4, 4, 4])
        self.assertFalse(graph.query(0, 2)['reachable'])
        self.assertTrue(graph.query(0, 1)['reachable'])
        self.assertTrue(graph.query(1, 2)['reachable'])
        result = graph.query(0, 2, 'without-blocked-controls')
        self.assertEqual(graph.witness(result)['blockedControlsCrossed'], [2])

    def test_supported_turn_override_does_not_open_unsupported_closures(self):
        rule = {'id': 99, 'kind': 'only_right_turn', 'fromWay': 1, 'toWay': 3, 'via': 2}
        graph = network([(1, [0, 1], {}), (2, [1, 2], {})], rules={(1, 2): [rule]})
        self.assertFalse(graph.query(0, 2)['reachable'])
        result = graph.query(0, 2, 'without-supported-turns')
        self.assertEqual(graph.witness(result)['supportedTurnRuleIdsAtViolations'], [99])

    def test_parallel_arcs_have_distinct_physical_reverse(self):
        graph = network([(1, [0, 1], {}), (2, [0, 1], {})], flags=[4, 0, 4, 4, 4, 4])
        self.assertFalse(graph.transition(0, 1, frozenset()))
        self.assertTrue(graph.transition(0, 3, frozenset()))

    def test_combined_obstacles_are_not_called_single_causes(self):
        graph = network([(1, [0, 1], {'oneway': 'yes'})], closures={1: [99]})
        for mode in ('baseline', 'without-unsupported-closures', 'without-direction-limits'):
            self.assertFalse(graph.query(1, 0, mode)['reachable'])
        self.assertTrue(graph.query(1, 0, 'geometry-only')['reachable'])

    def test_settle_bound_and_deadline_fail_closed(self):
        graph = network([(1, [0, 1, 2], {})])
        with patch('coarse_osm_car_reachability_v1.MAX_SETTLES', 0):
            with self.assertRaises(PilotError):
                graph.query(0, 2)
        self.assertTrue(graph.query(0, 0)['reachable'])
        long = Network(list(range(1100)), bytearray([4] + [0] * 1098 + [4]),
                       {1: way_policy({'highway': 'primary'})}, {}, {})
        long.add_way(1, list(range(1100)))
        def expired():
            raise PilotError('deadline')
        with self.assertRaisesRegex(PilotError, 'deadline'):
            long.query(0, 1099, check=expired)

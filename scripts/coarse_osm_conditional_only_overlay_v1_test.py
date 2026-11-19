import copy
from dataclasses import asdict
import unittest

from coarse_osm_conditional_node_ports_v1_test import fixture, rule
from coarse_osm_conditional_only_node_v1 import classify
from coarse_osm_conditional_only_overlay_v1 import overlay
from coarse_osm_conditional_only_ports_v1 import qualify
from coarse_timing_input import PilotError


def inputs(target=20):
    source = {'id': 7, 'tags': {'type': 'restriction', 'restriction:conditional': 'only_right_turn @ wet'},
              'members': [{'type': 'way', 'role': 'from', 'ref': 10}, {'type': 'node', 'role': 'via', 'ref': 200},
                          {'type': 'way', 'role': 'to', 'ref': target}]}
    typed = classify(source)['rule']
    metadata = [{'source': source, 'derived': {k: str(v) if type(v) is int else v for k, v in asdict(typed).items()}}]
    ports = qualify(fixture(), [rule(identity=7, kind='only_right_turn', to_way=target)])['rows']
    contributors = [{'sourceRelation': 1, 'closedWays': ['40']},
                    {'sourceRelation': 7, 'closedWays': ['10', str(target)]}]
    return [contributors, {1}, {10, target}, metadata, ports, [(2, 3)], 4]


class Tests(unittest.TestCase):
    def test_only_certified_contribution_changes_and_old_bans_inputs_preserved(self):
        args = inputs()
        before = copy.deepcopy(args)
        result = overlay(*args)
        self.assertEqual(result['closed'], set())
        self.assertEqual(result['openedWayIds'], [10, 20])
        self.assertEqual(result['convertedRelations'], [7])
        self.assertEqual(result['entryPairs'], [(0, 1), (2, 3)])
        self.assertTrue(result['allOldAllowedTransitionsPreservedByPreviouslyClosedFromWays'])
        self.assertEqual(args, before)

    def test_every_independent_shared_contributor_still_closes_its_roads(self):
        args = inputs()
        args[0].append({'sourceRelation': 9, 'closedWays': ['10', '30']})
        args[2].add(30)
        result = overlay(*args)
        self.assertEqual(result['closed'], {10, 30})
        self.assertEqual(result['openedWayIds'], [20])
        self.assertEqual(result['entryPairs'], [(0, 1), (2, 3)])

    def test_missing_to_port_forbids_every_other_exit_and_old_overlap_is_deduplicated(self):
        args = inputs(30)
        args[5] = [(0, 1), (2, 3)]
        result = overlay(*args)
        self.assertEqual(result['mandatoryPairs'], [(0, 1), (0, 2)])
        self.assertEqual(result['newEntryPairs'], [(0, 2)])
        self.assertEqual(result['entryPairs'], [(0, 1), (0, 2), (2, 3)])

    def test_fallback_contributors_and_all_old_bans_remain(self):
        args = inputs()
        args[4][0]['status'] = 'source-port-complexity-fallback'
        args[4][0]['forbiddenPreArcPairs'] = []
        result = overlay(*args)
        self.assertEqual(result['closed'], {10, 20})
        self.assertEqual(result['entryPairs'], args[5])
        self.assertEqual(result['fallbackRelations'], [7])

    def test_forged_baseline_or_nonmember_contribution_refuses(self):
        for change in [lambda a: a[2].remove(10), lambda a: a[2].add(99),
                       lambda a: a[0][1]['closedWays'].append('99'),
                       lambda a: a[1].add(7), lambda a: a[0].append(copy.deepcopy(a[0][1]))]:
            args = inputs()
            change(args)
            with self.assertRaises(PilotError):
                overlay(*args)

    def test_tampered_source_identity_ports_pairs_or_kind_refuses(self):
        for key, value in [('sourceRelationId', '8'), ('fromWayId', '30'), ('toWayId', '10'),
                           ('viaNodeId', '100'), ('kind', 'no_right_turn'), ('incomingPreArcIds', []),
                           ('allOutgoingPreArcIds', [2, 1]), ('toOutgoingPreArcIds', [3]),
                           ('forbiddenPreArcPairs', [[0, 2]])]:
            args = inputs()
            args[4][0][key] = value
            with self.assertRaises(PilotError):
                overlay(*args)

    def test_invalid_old_pairs_profile_bounds_and_duplicate_metadata_refuse(self):
        for pairs in [[(2, 3), (2, 3)], [(3, 2), (0, 1)], [(True, 1)], [(0, 4)], [[0, 1]]]:
            args = inputs()
            args[5] = pairs
            with self.assertRaises(PilotError):
                overlay(*args)
        for count in [0, True, 0x1000000]:
            args = inputs()
            args[6] = count
            with self.assertRaises(PilotError):
                overlay(*args)
        args = inputs()
        args[3] += copy.deepcopy(args[3])
        args[4] += copy.deepcopy(args[4])
        with self.assertRaises(PilotError):
            overlay(*args)

    def test_source_change_or_invented_fallback_fact_refuses(self):
        args = inputs()
        args[3][0]['source']['tags']['restriction:conditional'] = 'no_right_turn @ wet'
        with self.assertRaises(PilotError):
            overlay(*args)
        args = inputs()
        args[4][0]['status'] = 'from-way-base-ineligible'
        with self.assertRaises(PilotError):
            overlay(*args)


if __name__ == '__main__':
    unittest.main()

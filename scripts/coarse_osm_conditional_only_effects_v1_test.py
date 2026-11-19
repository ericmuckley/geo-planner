import copy
import unittest

from coarse_osm_conditional_node_ports_v1_test import fixture, rule
from coarse_osm_conditional_only_effects_v1 import audit_effects, effects, overlay
from coarse_osm_conditional_only_node_v1 import classify
from coarse_osm_conditional_only_overlay_v1_test import inputs
from coarse_osm_conditional_only_ports_v1 import qualify
from coarse_timing_input import PilotError


def inactive_inputs(reason):
    args = inputs(30)
    item = args[3][0]
    item['source']['members'][0]['ref'] = 999 if reason == 'outside' else 30
    item['source']['members'][2]['ref'] = 20
    from dataclasses import asdict
    actual = classify(item['source'])['rule']
    item['derived'] = {k: str(v) if type(v) is int else v for k, v in asdict(actual).items()}
    args[0][1]['closedWays'] = [str(actual.from_way), '20']
    args[2] = {actual.from_way, 20}
    args[4] = qualify(fixture(), [actual])['rows']
    return args, actual


class Tests(unittest.TestCase):
    def test_from_absent_profile_has_no_represented_mandatory_approach(self):
        args, actual = inactive_inputs('outside')
        before = copy.deepcopy(args)
        result = overlay(*args)
        self.assertEqual(result['inactiveRelations'], [7])
        self.assertEqual(result['closed'], set())
        self.assertEqual(result['entryPairs'], args[5])
        audit = audit_effects(fixture(), [actual], qualify(fixture(), [actual]))
        self.assertEqual(audit['inactiveFromRules'], 1)
        self.assertEqual(args, before)

    def test_from_base_ineligible_has_no_eligible_incoming_port(self):
        args, actual = inactive_inputs('ineligible')
        result = overlay(*args)
        self.assertEqual(result['inactiveRelations'], [7])
        self.assertEqual(result['openedWayIds'], [20, 30])
        self.assertEqual(audit_effects(fixture(), [actual], qualify(fixture(), [actual]))['inactiveFromRules'], 1)

    def test_known_junction_without_directed_incoming_can_be_inactive(self):
        fields = fixture()
        candidate = rule(kind='only_right_turn', from_way=20, to_way=10, via_node=100)
        ports = qualify(fields, [candidate])
        self.assertEqual(effects(ports['rows'])['inactive'], {1})
        self.assertEqual(audit_effects(fields, [candidate], ports)['inactiveFromRules'], 1)

    def test_missing_to_ports_still_bans_every_other_exit_and_is_never_inactive(self):
        args = inputs(30)
        result = overlay(*args)
        self.assertEqual(result['inactiveRelations'], [])
        self.assertEqual(result['representedRelations'], [7])
        self.assertEqual(result['mandatoryPairs'], [(0, 1), (0, 2)])

    def test_missing_via_nonanchor_and_complexity_remain_fallback(self):
        fields = fixture()
        for candidate in [rule(kind='only_right_turn', via_node=999), rule(kind='only_right_turn', via_node=400)]:
            port = qualify(fields, [candidate])
            self.assertEqual(effects(port['rows'])['fallback'], {1})
        args = inputs()
        args[4][0]['status'] = 'source-port-complexity-fallback'
        args[4][0]['forbiddenPreArcPairs'] = []
        self.assertEqual(overlay(*args)['closed'], args[2])

    def test_every_shared_independent_contributor_stays(self):
        args, _ = inactive_inputs('outside')
        args[0].append({'sourceRelation': 9, 'closedWays': ['20']})
        self.assertEqual(overlay(*args)['closed'], {20})

    def test_forged_negative_reason_port_or_way_mapping_refuses(self):
        args, _ = inactive_inputs('outside')
        for key, value in [('incomingPreArcIds', [0]), ('fromWayRow', 0), ('forbiddenPreArcPairs', [[0, 2]])]:
            changed = copy.deepcopy(args)
            changed[4][0][key] = value
            with self.assertRaises(PilotError):
                overlay(*changed)
        port = qualify(fixture(), [rule(kind='only_right_turn')])
        port['rows'][0]['status'] = 'from-way-outside-major-facts'
        with self.assertRaises(PilotError):
            audit_effects(fixture(), [rule(kind='only_right_turn')], port)

    def test_actual_source_profile_change_invalidates_absence_certificate(self):
        fields = fixture()
        candidate = rule(kind='only_right_turn', from_way=999)
        certified = qualify(fields, [candidate])
        changed = fixture()
        changed['ways'][2] = (999, 50., 50., 3, 6)
        changed['arcs'] += [(0, 1, 2, 0, 1, 1, bytes(3), 1000)]
        with self.assertRaises(PilotError):
            audit_effects(changed, [candidate], certified)


if __name__ == '__main__':
    unittest.main()

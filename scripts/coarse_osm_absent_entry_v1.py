"""A narrow no-turn with an absent essential pre-closure leg cannot be completed.

Presence MUST come from the complete pre-relation-closure graph. Looking at
already relation-filtered arcs would be circular and could open illegal turns.
Every other relation keeps its own closure contribution.
"""
from collections import defaultdict

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_entry_graph_v1 import plan_entries as previous_plan
from coarse_osm_restriction_entry_v1 import entry_pairs, entry_restriction


def plan_entries(elements, pre_relation_arcs, expected_pre_arc_count):
    if type(expected_pre_arc_count) is not int or expected_pre_arc_count != len(pre_relation_arcs):
        raise ValueError('Complete pre-relation-closure arc count required')
    if len(elements) > 10000 or len(pre_relation_arcs) > 200000:
        raise ValueError('Captured absent-entry prototype bound')
    original = previous_plan(elements, pre_relation_arcs)
    grouped = defaultdict(list)
    for i, arc in enumerate(pre_relation_arcs):
        grouped[arc['way']].append({**arc, 'id': i})
    present = set(grouped)
    closed, pairs, converted, fallback, inactive = set(), set(), [], [], []
    for element in elements:
        source = restriction_policy(element)
        if source['status'] != 'closed-unsupported':
            continue
        rule = entry_restriction(element)
        if rule is not None:
            missing = sorted({rule.from_way, rule.via_way, rule.to_way} - present)
            if missing:
                inactive.append({'id': element['id'], 'absentEssentialWays': missing})
                converted.append({'id': element['id'], 'pairs': []})
                continue
        found = None if rule is None else entry_pairs(rule, grouped[rule.from_way], grouped[rule.via_way], present)
        if found is None:
            closed.update(source['memberWays'])
            fallback.append(element['id'])
        else:
            pairs.update(found)
            converted.append({'id': element['id'], 'pairs': found})
    assert closed <= original['closed'] and pairs == original['pairs']
    assert {r['id'] for r in original['converted']} <= {r['id'] for r in converted}
    return {'oldClosed': original['oldClosed'], 'closed': closed, 'pairs': pairs,
            'converted': converted, 'fallback': fallback, 'inactive': inactive}

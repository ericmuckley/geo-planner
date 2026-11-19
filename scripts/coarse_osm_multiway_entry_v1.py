"""Captured conservative entry bans for static no-turns with several via ways.

Ban from->any-via joins, independent of the source via-member order. Every
completion must make one such entry; unrelated traffic keeps its member roads.
This intentionally excludes legal exits too. It is not full via-way semantics.
"""
from collections import defaultdict
from dataclasses import dataclass

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_context_turns_v1 import plan_contexts


@dataclass(frozen=True)
class MultiwayEntry:
    identity: int
    from_way: int
    via_ways: tuple
    to_way: int


def multiway_rule(element):
    original = restriction_policy(element)
    if original['status'] != 'closed-unsupported':
        return None
    tags, members = element['tags'], element['members']
    if any(key.endswith(':conditional') for key in tags):
        return None
    kind = next((tags[key] for key in ('restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle', 'restriction') if key in tags), None)
    if kind not in {'no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn'}:
        return None
    if not 4 <= len(members) <= 66 or any(m['type'] != 'way' for m in members):
        return None
    roles = {role: [m['ref'] for m in members if m['role'] == role] for role in ('from', 'via', 'to')}
    if len(roles['from']) != 1 or len(roles['to']) != 1 or len(roles['via']) != len(members)-2:
        return None
    a, c = roles['from'][0], roles['to'][0]
    via = roles['via']
    if any(type(value) is not int or value <= 0 for value in [a, *via, c]):
        return None
    if a in via or c in via or len(set(via)) != len(via):
        return None
    return MultiwayEntry(element['id'], a, tuple(via), c)


def plan_multiway(elements, complete_pre_arcs, expected_pre_count):
    previous = plan_contexts(elements, complete_pre_arcs, expected_pre_count)
    grouped = defaultdict(list)
    for index, arc in enumerate(complete_pre_arcs):
        grouped[arc['way']].append((index, arc))
    present = set(grouped)
    old_converted = {row['id'] for row in previous['converted']}
    closed, pairs, converted, inactive, fallback = set(), set(), [], [], []
    for element in elements:
        source = restriction_policy(element)
        if source['status'] != 'closed-unsupported' or element['id'] in old_converted:
            continue
        rule = multiway_rule(element)
        if rule is not None:
            missing = sorted({rule.from_way, *rule.via_ways, rule.to_way}-present)
            if missing:
                inactive.append({'id':rule.identity, 'absentEssentialWays':missing})
                converted.append({'rule':rule, 'pairs':[]})
                continue
            outgoing = defaultdict(list)
            for way in rule.via_ways:
                for index, arc in grouped[way]:
                    outgoing[arc['tail']].append(index)
            found = {(index, after) for index, arc in grouped[rule.from_way] for after in outgoing[arc['head']]}
            if found:
                pairs.update(found)
                converted.append({'rule':rule, 'pairs':sorted(found)})
                continue
        closed.update(source['memberWays'])
        fallback.append(element['id'])
    assert closed <= previous['closed']
    return {**previous, 'closed':closed, 'multiPairs':pairs, 'multiConverted':converted,
            'multiInactive':inactive, 'fallback':fallback, 'previous':previous}


def audit_raw_multiway_path(elements, converted, physical_arcs, result, present):
    """Read original members, not compiled turn-pair records or query histories."""
    selected = {row['rule'].identity for row in converted}
    entries = set()
    for element in elements:
        if element['id'] not in selected:
            continue
        source = element['members']
        from_way = next(m['ref'] for m in source if m['role'] == 'from')
        to_way = next(m['ref'] for m in source if m['role'] == 'to')
        vias = {m['ref'] for m in source if m['role'] == 'via'}
        if not {from_way, to_way, *vias} <= present:
            continue
        entries.update((from_way, via) for via in vias)
    for before, after in zip(result['steps'], result['steps'][1:]):
        pair = physical_arcs[before['arc']]['way'], physical_arcs[after['arc']]['way']
        assert pair not in entries, 'Original multi-via entry prohibition violated'

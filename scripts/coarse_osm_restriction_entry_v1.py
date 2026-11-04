"""Offline conservative alternative to closing every road in a via-way no-turn."""
from dataclasses import dataclass

from coarse_osm_car_policy_v1 import restriction_policy


@dataclass(frozen=True)
class EntryRestriction:
    identity: int
    from_way: int
    via_way: int
    to_way: int


def entry_restriction(element):
    """Admit only the narrow static, single-via-way prohibitory shape."""
    original = restriction_policy(element)
    if original['status'] != 'closed-unsupported':
        return None
    tags = element['tags']
    if any(k.endswith(':conditional') for k in tags):
        return None
    kind = next((tags[k] for k in ('restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle', 'restriction') if k in tags), None)
    if kind not in {'no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn'}:
        return None
    members = element['members']
    if len(members) != 3 or any(m['type'] != 'way' for m in members):
        return None
    roles = {role: [m['ref'] for m in members if m['role'] == role] for role in ('from', 'via', 'to')}
    if any(len(v) != 1 for v in roles.values()):
        return None
    a, b, c = (roles[r][0] for r in ('from', 'via', 'to'))
    if b in (a, c) or any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in (a, b, c)):
        return None
    return EntryRestriction(element['id'], a, b, c)


def entry_pairs(rule, incoming, outgoing, present_ways):
    """Return (incoming-arc, outgoing-arc) pairs, or None for unchanged fallback.

    Callers supply complete pre-relation-closure arc groups for the two ways.
    Every from->via junction is forbidden, in both available orientations. Thus
    no path can complete the prohibited sequence, without closing the to/via
    roads for unrelated traffic. This deliberately also excludes legal exits
    after entering the via road; it is a conservative subset, not exact via-way
    semantics. Never subtract a converted relation's IDs from another closure.
    """
    if not {rule.from_way, rule.via_way, rule.to_way}.issubset(present_ways):
        return None
    if any(a['way'] != rule.from_way for a in incoming) or any(a['way'] != rule.via_way for a in outgoing):
        raise ValueError('Entry restriction arc group identity')
    if len(incoming) + len(outgoing) > 200000:
        raise ValueError('Entry restriction per-relation arc bound')
    starts = {}
    for arc in outgoing:
        starts.setdefault(arc['tail'], []).append(arc['id'])
    pairs = {(a['id'], b) for a in incoming for b in starts.get(a['head'], ())}
    return sorted(pairs) if pairs else None

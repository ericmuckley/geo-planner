"""Recognize an incomplete static maneuver without inventing a junction closure."""
from dataclasses import dataclass

from coarse_osm_car_policy_v1 import TURN_KINDS, restriction_policy
from coarse_timing_input import require

TYPES = frozenset(('restriction', 'restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle'))
KEYS = ('restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle', 'restriction')
NON_CAR = frozenset(('foot', 'bicycle', 'hgv', 'psv', 'bus', 'motorcycle', 'emergency', 'agricultural', 'forestry', 'goods'))
POLICY = {
    'id': 'incomplete-static-single-via-node-maneuver-v1',
    'shape': 'Exactly one positive native node member with role via; no from/to way or other members.',
    'tags': 'Exact documented general/car relation type; at least one known static car/general restriction key, every stated value identical and supported; no unknown restriction keys or conditional keys.',
    'meaning': 'Without from/to road members this relation cannot define a maneuver. Omit only this incomplete relation contribution; never infer an all-direction node barrier from it.',
    'fallback': 'Unknown/mixed/conditional tags, unknown/car exemptions, other member shapes and every way-containing restriction retain their current handling.',
    'unchanged': 'Direct node access/barrier/dimension/lock/hour guards, all other node and way contributors, valid turn rules, costs, directions and timing gates remain.',
}


@dataclass(frozen=True)
class IncompleteNodeRestriction:
    identity: int
    via_node: int
    kind: str


def classify(element):
    def refused(reason):
        return {'rule': None, 'reason': reason}

    if not isinstance(element, dict) or element.get('type') != 'relation' or type(element.get('id')) is not int or not 0 < element['id'] < 2**63:
        return refused('invalid-identity')
    tags, members = element.get('tags'), element.get('members')
    if not isinstance(tags, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items()):
        return refused('invalid-tags')
    if tags.get('type') not in TYPES:
        return refused('unsupported-relation-type')
    if not isinstance(members, list) or len(members) != 1:
        return refused('not-single-via-node')
    member = members[0]
    if not isinstance(member, dict) or member.get('type') != 'node' or member.get('role') != 'via' or type(member.get('ref')) is not int or not 0 < member['ref'] < 2**63:
        return refused('not-single-via-node')
    if any(k.endswith(':conditional') for k in tags):
        return refused('conditional-fallback')
    if any(k.startswith('restriction:') and k not in KEYS for k in tags):
        return refused('unknown-restriction-key')
    if 'except' in tags and not {s.strip() for s in tags['except'].split(';')} <= NON_CAR:
        return refused('unknown-or-car-exemption')
    values = [tags[k] for k in KEYS if k in tags]
    if not values or len(set(values)) != 1 or values[0] not in TURN_KINDS:
        return refused('unknown-or-mixed-static-kind')
    original = restriction_policy(element)
    if original['status'] != 'closed-unsupported' or original['memberWays'] or original['memberNodes'] != [member['ref']]:
        return refused('not-original-node-only-fallback')
    return {'rule': IncompleteNodeRestriction(element['id'], member['ref'], values[0]),
            'reason': 'missing-both-essential-road-members'}


def remaining_contributors(node, original, incomplete):
    require(type(node) is int and node > 0 and original == sorted(set(original))
            and all(type(identity) is int and identity > 0 for identity in original),
            'Exact original node contributor roster')
    for identity in original:
        if identity in incomplete:
            require(incomplete[identity].identity == identity and incomplete[identity].via_node == node,
                    'Incomplete contribution belongs to this exact native node')
    return [identity for identity in original if identity not in incomplete]

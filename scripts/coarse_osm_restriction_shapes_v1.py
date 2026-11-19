"""Describe saved unsupported car restrictions; no permission or routing change."""
from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_restriction_entry_v1 import entry_restriction

ONLY_KINDS = {'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn'}


def classify(element):
    policy = restriction_policy(element)
    if policy['status'] != 'closed-unsupported':
        return policy['status'], None
    if any(key.endswith(':conditional') for key in element['tags']):
        return 'conditional-fallback', None
    no_turn = entry_restriction(element)
    if no_turn is not None:
        return 'static-single-via-way-no', (no_turn.from_way, no_turn.via_way, no_turn.to_way)
    kind = next((element['tags'][key] for key in
                 ('restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle', 'restriction')
                 if key in element['tags']), None)
    members = element['members']
    if len(members) == 3 and all(m['type'] == 'way' for m in members):
        roles = [[m['ref'] for m in members if m['role'] == role] for role in ('from', 'via', 'to')]
        if all(len(values) == 1 for values in roles):
            a, b, c = (values[0] for values in roles)
            if all(type(value) is int and value > 0 for value in (a, b, c)) and b not in (a, c) and kind in ONLY_KINDS:
                return 'static-single-via-way-only', (a, b, c)
    return 'other-static-fallback', None

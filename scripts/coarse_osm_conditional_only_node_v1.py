"""Metadata-only all-state mandatory turns; physical source ports remain required."""
from dataclasses import replace

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_conditional_node_turns_v2 import BASE_KEYS, CONDITIONAL_KEYS
from coarse_osm_conditional_node_turns_v2 import classify as shape_guard
from coarse_timing_input import require

KINDS = {'only_left_turn': 'no_left_turn', 'only_right_turn': 'no_right_turn',
         'only_straight_on': 'no_straight_on'}
POLICY = {
    'id': 'static-car-conditional-only-via-node-envelope-v1',
    'values': sorted(KINDS),
    'shape': 'Unchanged exact known car/general type, one from way, one distinct to way, one via node; original car fallback only.',
    'scope': 'Every stated car/general base and conditional value must be the same supported mandatory kind. Opaque bounded conditions; constrain exits in every state. No time/condition evaluation.',
    'projection': 'After independently verified complete native source ports: each incoming from-way arc forbids every outgoing arc except exact to-way outgoing ports. Union bans with every prior independent constraint. Missing to ports forbids all other outgoing exits, never inactive inference.',
    'fallback': 'Unknown/mixed/no-turn/only-U-turn/same-way/via-way/key/type/exemption/syntax forms retain original whole-way fallback. Metadata alone removes no closure.',
    'limits': '65536 original Unicode characters/64 clauses/eight parenthesis levels/exactly one @/nonempty condition/no quotes; <=64 unique source ports per vector, IDs below2^24.',
    'unchanged': 'No source price/access/node/physical graph change, native permission claim, local-surrogate inference, place/coordinate exception, fit or accuracy/app activation.'
}


def _project_syntax(text):
    """Translate value tokens only, so the sealed guard can check shape and keys."""
    if not isinstance(text, str) or not 0 < len(text) <= 65536 or any(c in text for c in ('"', "'")):
        return None
    clauses = []
    depth = start = 0
    for index, char in enumerate(text):
        if char == '(':
            depth += 1
            if depth > 8:
                return None
        elif char == ')':
            depth -= 1
            if depth < 0:
                return None
        elif char == ';' and depth == 0:
            clauses.append(text[start:index])
            start = index + 1
            if len(clauses) >= 64:
                return None
    if depth:
        return None
    clauses.append(text[start:])
    values, projected = [], []
    for clause in clauses:
        if clause.count('@') != 1:
            return None
        value, condition = clause.split('@')
        kind = value.strip()
        if kind not in KINDS or not any(not c.isspace() and c not in '()' for c in condition):
            return None
        values.append(kind)
        projected.append(value.replace(kind, KINDS[kind], 1) + '@' + condition)
    return values, ';'.join(projected)


def classify(element):
    def refused(reason):
        return {'rule': None, 'reason': reason}
    if not isinstance(element, dict) or not isinstance(element.get('tags'), dict):
        return refused('invalid-tags')
    tags = element['tags']
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items()):
        return refused('invalid-tags')
    projected, values = dict(tags), []
    for key in BASE_KEYS:
        if key in tags:
            if tags[key] not in KINDS:
                return refused('unsupported-or-mixed-kind')
            values.append(tags[key])
            projected[key] = KINDS[tags[key]]
    keys = CONDITIONAL_KEYS.intersection(tags)
    if not keys:
        return refused('no-car-condition')
    for key in sorted(keys):
        parsed = _project_syntax(tags[key])
        if parsed is None:
            return refused('unsupported-conditional-syntax')
        kinds, projected[key] = parsed
        values.extend(kinds)
    if len(set(values)) != 1:
        return refused('unsupported-or-mixed-kind')
    # Translation shares validation only. Its prohibitory rule is never a driving rule.
    guard = shape_guard(element | {'tags': projected})
    if guard['rule'] is None:
        return refused('shape-guard:' + guard['reason'])
    require(restriction_policy(element)['status'] == 'closed-unsupported', 'Original only-turn car fallback')
    kind = values[0]
    static_tags = {k: v for k, v in tags.items() if k not in CONDITIONAL_KEYS}
    static_tags['restriction'] = kind
    oracle = restriction_policy(element | {'tags': static_tags})
    rule = replace(guard['rule'], kind=kind)
    require(oracle['status'] == 'via-node' and
            (oracle['fromWay'], oracle['via'], oracle['toWay'], oracle['kind']) ==
            (rule.from_way, rule.via_node, rule.to_way, rule.kind), 'Original mandatory-turn static oracle')
    return {'rule': rule, 'reason': 'single-mandatory-via-node-all-condition-envelope'}


def forbidden_exits(incoming, all_outgoing, to_outgoing):
    """Pure bounded projection; callers must independently certify every physical port."""
    for ports in (incoming, all_outgoing, to_outgoing):
        require(isinstance(ports, list) and len(ports) <= 64 and ports == sorted(set(ports)) and
                all(type(i) is int and 0 <= i < 0xffffff for i in ports), 'Canonical bounded only-turn ports')
    require(set(to_outgoing) <= set(all_outgoing), 'To-way ports belong to complete outgoing ports')
    allowed = set(to_outgoing)
    return [(a, b) for a in incoming for b in all_outgoing if b not in allowed]

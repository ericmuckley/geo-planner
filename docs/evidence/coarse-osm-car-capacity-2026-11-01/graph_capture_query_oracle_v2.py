"""Bounded independent reader checks for all original captured native queries.

This uses the existing independent payload query reader, not a graph producer.
Four-byte fields here are audit-only; no national/runtime memory fit is claimed.
"""
from array import array
from collections import defaultdict
import math

from coarse_osm_car_payload_v1 import Payload
from coarse_osm_car_policy_v1 import turn_allowed


def query_checks(ids, xy, anchors, flags, way_ids, arcs, fragments, closed, rules, cases):
    assert 0 < len(ids) <= 2000000 and 0 < len(anchors) <= len(ids) and len(arcs) <= 1000000 and 0 < len(cases) <= 1000
    active = sorted((row for row in arcs if way_ids[row[2]] not in closed), key=lambda r: (r[0], r[2], r[3], r[4], -r[5]))
    key = lambda row: (row[2], row[3], row[4], row[5])
    lookup = {key(row): i for i, row in enumerate(active)}
    assert len(lookup) == len(active)
    offsets = array('I', [0])*(len(anchors)+1)
    for row in active:offsets[row[0]+1] += 1
    for i in range(len(anchors)):offsets[i+1] += offsets[i]
    targets = array('I', (row[1] for row in active));exact = array('Q', (row[-1] for row in active))
    words = array('H');cost_keys = array('I');cost_values = array('I')
    reverse = bytearray();reverse_keys = array('I');reverse_values = array('I');reverse_ids = []
    for i, row in enumerate(active):
        ticks = (row[-1]+124)//125;assert ticks <= 0xffffffff
        words.append(min(ticks, 65535))
        if ticks >= 65535:cost_keys.append(i);cost_values.append(ticks)
        other = lookup.get((*key(row)[:3], -row[5]));reverse_ids.append(other)
        if other is None:reverse.append(255)
        else:
            ordinal = other-offsets[row[1]];assert 0 <= ordinal < offsets[row[1]+1]-offsets[row[1]]
            reverse.append(ordinal if ordinal < 254 else 254)
            if ordinal >= 254:reverse_keys.append(i);reverse_values.append(other)
    grouped = defaultdict(list)
    for rule in rules:grouped[rule['fromWay'], rule['via']].append(rule)
    pairs = array('I')
    for incoming, row in enumerate(active):
        current = grouped.get((way_ids[row[2]], ids[anchors[row[1]]]), ())
        if not current:continue
        for following in range(offsets[row[1]], offsets[row[1]+1]):
            if not turn_allowed(way_ids[row[2]], way_ids[active[following][2]], following == reverse_ids[incoming], current):
                pairs.extend((incoming, following))
    fields = {'xy.i32': array('i', (v for node in anchors for v in xy[2*node:2*node+2])).tobytes(),
              'offsets.u32': offsets.tobytes(), 'targets.u32': targets.tobytes(), 'costs.u16': words.tobytes(),
              'cost-overflow-arcs.u32': cost_keys.tobytes(), 'cost-overflow-ticks.u32': cost_values.tobytes(),
              'reverse.u8': bytes(reverse), 'reverse-overflow-arcs.u32': reverse_keys.tobytes(),
              'reverse-overflow-targets.u32': reverse_values.tobytes(), 'node-flags.u8': flags,
              'forbidden-turns.u32': pairs.tobytes()}
    payload = Payload(fields.__getitem__)
    vertices = {ids[node]: i for i, node in enumerate(anchors)};aliases = {}
    for span, fragment in fragments.items():
        for position, node in enumerate(fragment['chain'][1:-1], 1):
            assert node not in vertices and node not in aliases
            aliases[node] = span, position
    assert len(vertices)+len(aliases) == len(ids) and set(vertices) | set(aliases) == set(ids)
    def rounded(value, quantized):return ((value+124)//125)*125 if quantized else value
    def point(identity, source, quantized):
        if identity in vertices:return vertices[identity]
        span, position = aliases[identity];fragment = fragments[span];out = {}
        for direction, prefix in fragment['prefix'].items():
            arc = lookup.get((*span, direction))
            if arc is None:continue
            paid = prefix[position] if direction == 1 else prefix[-1]-prefix[position]
            out[arc] = rounded(prefix[-1]-paid if source else paid, quantized)
        return out
    def direct(source, target, quantized):
        if source == target:return 0
        a, b = aliases.get(source), aliases.get(target)
        if a is None or b is None or a[0] != b[0]:return math.inf
        span, start = a;end = b[1];best = math.inf
        for direction, prefix in fragments[span]['prefix'].items():
            if (*span, direction) in lookup and (end-start)*direction >= 0:
                best = min(best, rounded(abs(prefix[end]-prefix[start]), quantized))
        return best
    checked = [];unreachable = improved = 0
    for case in cases:
        source, target = case['sourceNodeIds']
        payload.cost_ms = lambda index: exact[index]
        raw = payload.query(point(source, True, False), point(target, False, False))
        raw = min(math.inf if raw is None else raw, direct(source, target, False))
        raw = None if math.isinf(raw) else raw
        del payload.cost_ms
        quantized = payload.query(point(source, True, True), point(target, False, True))
        quantized = min(math.inf if quantized is None else quantized, direct(source, target, True))
        quantized = None if math.isinf(quantized) else quantized
        assert raw == case['raw']['costMs'], (case['windowId'], source, target, raw, case['raw']['costMs'])
        if raw is None:
            assert quantized is case['binaryQuantizedMs'] is None;unreachable += 1
        else:
            assert raw <= quantized <= case['binaryQuantizedMs'], (case['windowId'], raw, quantized, case['binaryQuantizedMs'])
            improved += quantized < case['binaryQuantizedMs']
        checked.append({'windowId': case['windowId'], 'sourceNodeIds': [source, target], 'rawMs': raw,
                        'quantizedMs': quantized, 'originalQuantizedMs': case['binaryQuantizedMs']})
    assert unreachable == sum(case['raw']['costMs'] is None for case in cases)
    return {'originalDirectionalCases': len(checked), 'unreachableCasesPreserved': unreachable,
            'exactRawCostsAllMatch': True, 'quantizedCostsNeverWorse': True, 'quantizedCasesImproved': improved,
            'allNativePointsRetained': len(ids), 'internalPaidAliases': len(aliases),
            'readerSettlesAcrossRawAndQuantizedChecks': payload.work, 'checks': checked}

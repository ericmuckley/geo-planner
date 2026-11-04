"""Bounded captured-fact formatter and paid-point fixtures; refuses country data.

This Python object representation is a qualification adapter only. Country
encoding needs a separately bounded typed/native implementation.
"""
from array import array
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import struct
import time

from coarse_osm_car_policy_v1 import turn_allowed
from import_roads import distance_m

WAY = struct.Struct('<QddII')
ARC = struct.Struct('<IIIIIb3xQ')
TURN = struct.Struct('<QQQQB7x')
KINDS = ['no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn', 'no_entry', 'no_exit',
         'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn']
MAX_INPUT = 16*1048576
MAX_OUTPUT = 16*1048576


def pack24(values):
    out = bytearray()
    for value in values:
        if not isinstance(value, int) or not 0 <= value <= 0xffffff:
            raise ValueError('Captured uint24 index range')
        out.extend(value.to_bytes(3, 'little'))
        if len(out) > MAX_OUTPUT:raise ValueError('Captured packed output cap')
    return out


def encode(ids, xy, anchors, flags, geometry, ways, raw_arcs, closures, turns, cases):
    """Generic small-graph format, deliberately bounded before object expansion."""
    assert 0 < len(ids) <= 200000 and len(xy) == 2*len(ids)
    assert 0 < len(anchors) <= len(ids) and len(flags) == len(anchors)
    assert len(raw_arcs) <= 200000 and len(ways) <= 50000 and len(geometry) <= 500000
    assert len(turns) <= 10000 and len(cases) <= 1000
    active = sorted((row for row in raw_arcs if ways[row[2]][0] not in closures),
                    key=lambda row: (row[0], row[2], row[3], row[4], -row[5]))
    key = lambda row: (row[2], row[3], row[4], row[5])
    lookup = {key(row): i for i, row in enumerate(active)}
    assert len(lookup) == len(active)
    offsets = [0]*(len(anchors)+1)
    for row in active:offsets[row[0]+1] += 1
    for i in range(len(anchors)):offsets[i+1] += offsets[i]
    cost_keys = [];cost_values = [];costs = [];reverse_keys = [];reverse_values = [];reverse = [];reverse_ids = []
    for i, row in enumerate(active):
        ticks = (row[-1]+124)//125
        assert 0 < ticks <= 0xffffffff
        costs.append(min(ticks, 65535))
        if ticks >= 65535:cost_keys.append(i);cost_values.append(ticks)
        other = lookup.get((*key(row)[:3], -row[5]));reverse_ids.append(other)
        if other is None:reverse.append(255)
        else:
            ordinal = other-offsets[row[1]]
            assert 0 <= ordinal < offsets[row[1]+1]-offsets[row[1]]
            reverse.append(min(ordinal, 254))
            if ordinal >= 254:reverse_keys.append(i);reverse_values.append(other)
    grouped = defaultdict(list)
    for _, source, via, target, kind in turns:
        assert 0 <= kind < len(KINDS)
        grouped[source, via].append({'fromWay': source, 'toWay': target, 'kind': KINDS[kind]})
    pairs = []
    for incoming, row in enumerate(active):
        rules = grouped.get((ways[row[2]][0], ids[anchors[row[1]]]), ())
        if not rules:continue
        for following in range(offsets[row[1]], offsets[row[1]+1]):
            if not turn_allowed(ways[row[2]][0], ways[active[following][2]][0], following == reverse_ids[incoming], rules):
                pairs.extend((incoming, following))
    fields = {'xy.i32': array('i', (v for node in anchors for v in xy[2*node:2*node+2])).tobytes(),
              'offsets.u24': pack24(offsets), 'targets.u24': pack24(row[1] for row in active),
              'costs.u16': array('H', costs).tobytes(), 'cost-overflow-arcs.u24': pack24(cost_keys),
              'cost-overflow-ticks.u32': array('I', cost_values).tobytes(), 'reverse.u8': bytes(reverse),
              'reverse-overflow-arcs.u24': pack24(reverse_keys), 'reverse-overflow-targets.u24': pack24(reverse_values),
              'node-flags.u8': bytes(flags), 'forbidden-turns.u24': pack24(pairs)}
    # Full native geometry stays offline. Fixtures pay source prefixes and retain
    # direct same-span travel instead of inventing free links to either endpoint.
    vertices = {node: i for i, node in enumerate(anchors)}
    aliases = {};fragments = {};cursor = 0
    for way, (_, forward, backward, _, end) in enumerate(ways):
        chain = geometry[cursor:end];cursor = end
        cuts = [i for i, node in enumerate(chain) if node in vertices]
        assert cuts[0] == 0 and cuts[-1] == len(chain)-1
        for first, last in zip(cuts, cuts[1:]):
            nodes = chain[first:last+1]
            if all(node == nodes[0] for node in nodes):continue
            span = (way, first, last);prefixes = {}
            for direction, speed in ((1, forward), (-1, backward)):
                if (*span, direction) not in lookup:continue
                prefix = [0]
                for a, b in zip(nodes, nodes[1:]):
                    distance = distance_m([xy[2*a]/1e7, xy[2*a+1]/1e7], [xy[2*b]/1e7, xy[2*b+1]/1e7])
                    prefix.append(prefix[-1] + (0 if ids[a] == ids[b] else max(1, math.ceil(distance*3600/speed))))
                assert prefix[-1] == active[lookup[*span, direction]][-1]
                prefixes[direction] = prefix
            fragments[span] = prefixes
            for position, node in enumerate(nodes[1:-1], 1):
                assert node not in vertices and node not in aliases
                aliases[node] = span, position
    assert cursor == len(geometry) and len(vertices)+len(aliases) == len(ids)
    positions = {identity: i for i, identity in enumerate(ids)}
    def point(identity, source):
        node = positions[identity]
        if node in vertices:return {'vertex': vertices[node]}
        span, position = aliases[node];partials = []
        for direction, prefix in fragments[span].items():
            paid = prefix[position] if direction == 1 else prefix[-1]-prefix[position]
            milliseconds = prefix[-1]-paid if source else paid
            partials.append({'arc': lookup[*span, direction], 'ticks': (milliseconds+124)//125})
        return {'partials': partials}
    fixtures = []
    for case in cases:
        source, target = case['sourceNodeIds'];a = positions[source];b = positions[target]
        direct = 0 if source == target else None
        if a in aliases and b in aliases and aliases[a][0] == aliases[b][0]:
            span, start = aliases[a];end = aliases[b][1]
            for direction, prefix in fragments[span].items():
                if (end-start)*direction >= 0:
                    ticks = (abs(prefix[end]-prefix[start])+124)//125
                    direct = ticks if direct is None else min(direct, ticks)
        expected = case['binaryQuantizedMs']
        assert expected is None or expected % 125 == 0 and expected <= 12*3600000
        fixtures.append({'windowId': case['windowId'], 'sourceNodeIds': [source, target],
                         'source': point(source, True), 'target': point(target, False),
                         'directTicks': direct, 'expectedTicks': None if expected is None else expected//125})
    assert sum(map(len, fields.values())) <= MAX_OUTPUT
    return fields, fixtures, {'vertices': len(anchors), 'arcs': len(active), 'forbiddenTurnPairs': len(pairs)//2,
                              'costOverflowEntries': len(cost_keys), 'reverseOverflowEntries': len(reverse_keys),
                              'nativePointsRetainedOffline': len(vertices)+len(aliases), 'paidInternalAliases': len(aliases)}


def run(repo, output):
    began = time.monotonic()
    closed = json.loads((repo/'docs/evidence/coarse-osm-car-capacity-2026-11-01/graph-capture-closed-run-v5.json').read_bytes())
    source = repo/closed['root'];roster = closed['roster']
    assert sum(row['bytes'] for name, row in roster.items() if name.startswith('cost-facts/')) <= MAX_INPUT
    def read(name):
        pin = roster[name];path = source/name
        assert path.is_file() and not path.is_symlink() and path.stat().st_size == pin['bytes'] <= MAX_INPUT
        raw = path.read_bytes();assert hashlib.sha256(raw).hexdigest() == pin['sha256']
        return raw
    def field(prefix, code=None, shape=None):
        raw = b''.join(read(name) for name in sorted(roster) if name.startswith('cost-facts/'+prefix+'-'))
        if shape:return list(shape.iter_unpack(raw))
        if code:
            out = array(code);out.frombytes(raw);return out
        return raw
    original = json.loads((repo/'data/coarse-quality/us-osm-car-run-v1/report.json').read_bytes())
    fields, fixtures, counts = encode(field('ids', 'Q'), field('xy', 'i'), field('anchors', 'I'), field('flags'),
                                     field('geometry', 'I'), field('ways', shape=WAY), field('arcs', shape=ARC),
                                     set(field('closures', 'Q')), field('turns', shape=TURN), original['queries'])
    artifacts = {}
    for name, raw in fields.items():
        path = output/'routing'/name;path.parent.mkdir(exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
        artifacts['routing/'+name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    def save(name, value):
        with (output/name).open('x') as stream:json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n')
    save('artifacts.json', artifacts);save('query-fixtures.json', fixtures)
    result = {'status': 'captured_packed_candidate_formatted', **counts,
              'payloadBytes': sum(row['bytes'] for row in artifacts.values()), 'originalDirectionalCases': len(fixtures),
              'secondsIncludingInputHashesFormattingPaidPointFixturesAndOutput': time.monotonic()-began,
              'sourcePbfReads': 0, 'nativeExecutions': 0, 'applicationDbReads': 0, 'networkRequests': 0,
              'countryEncoder': False, 'etaQualified': False, 'vercelQualified': False, 'modelChanged': False}
    save('report.json', result)
    return result

"""One bounded captured-fact experiment; no source decoder or national inputs."""
import argparse
from array import array
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_entry_graph_v1 import plan_entries, QueryGraph
from coarse_osm_packed_capture_v1 import ARC, encode, TURN, WAY
from import_roads import distance_m

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unpack24(raw):
    assert len(raw) % 3 == 0
    return [int.from_bytes(raw[i:i+3], 'little') for i in range(0, len(raw), 3)]


def packed_arcs(raw, ways, closed):
    return sorted((a for a in raw if ways[a[2]][0] not in closed), key=lambda a: (a[0], a[2], a[3], a[4], -a[5]))


def arc_dict(a, ways):
    return {'tail': a[0], 'head': a[1], 'way': ways[a[2]][0], 'first': a[3], 'last': a[4], 'direction': a[5], 'ms': a[6]}


class SourceReplay:
    """Reprice native geometry and replay raw relation semantics, not graph labels."""
    def __init__(self, ids, xy, anchors, geometry, ways, raw_arcs, elements, closed, converted):
        self.ids, self.xy, self.anchors = ids, xy, anchors
        self.geometry, self.ways, self.arcs = geometry, ways, raw_arcs
        self.offsets = [0, *[w[4] for w in ways]][:-1]
        self.closed = closed
        converted_ids = {r['id'] for r in converted}
        self.via = defaultdict(list)
        self.sequences = set()
        for e in elements:
            rule = restriction_policy(e)
            if rule['status'] == 'via-node':
                self.via[rule['fromWay'], rule['via']].append((rule['toWay'], rule['kind']))
            elif e['id'] in converted_ids:
                members = {m['role']: m['ref'] for m in e['members']}
                self.sequences.add((members['from'], members['via'], members['to']))

    def chain(self, arc):
        a = self.arcs[arc]
        start = self.offsets[a[2]]
        nodes = list(self.geometry[start+a[3]:start+a[4]+1])
        assert nodes[0] == self.anchors[a[0] if a[5] == 1 else a[1]]
        assert nodes[-1] == self.anchors[a[1] if a[5] == 1 else a[0]]
        return nodes if a[5] == 1 else nodes[::-1]

    def price(self, arc, nodes):
        a = self.arcs[arc]
        speed = self.ways[a[2]][1 if a[5] == 1 else 2]
        assert 0 < speed <= 160 and self.ways[a[2]][0] not in self.closed
        ms = 0
        for i, j in zip(nodes, nodes[1:]):
            p = [self.xy[2*i]/1e7, self.xy[2*i+1]/1e7]
            q = [self.xy[2*j]/1e7, self.xy[2*j+1]/1e7]
            ms += 0 if self.ids[i] == self.ids[j] else max(1, math.ceil(distance_m(p, q)*3600/speed))
        return ms

    def audit(self, fixture, result, flags):
        if result['ticks'] is None:
            assert not result['steps']
            return None
        source, target = fixture['sourceNodeIds']
        if result.get('direct'):
            options = []
            if source == target:
                options.append((0, []))
            else:
                for i in range(len(self.arcs)):
                    nodes = self.chain(i)
                    native = [self.ids[n] for n in nodes]
                    if source in native and target in native:
                        a, b = native.index(source), native.index(target)
                        if a <= b:
                            options.append(((self.price(i, nodes[a:b+1])+124)//125, nodes[a:b+1]))
            assert options
            ticks, nodes = min(options)
            assert ticks == result['ticks'] == fixture['directTicks']
            return {'ticks': ticks, 'nativeNodeIds': [self.ids[n] for n in nodes] or [source], 'sourceArcSteps': 0, 'sourceTurnTransitions': 0}
        total, node_path, previous, way_sequence = 0, [], None, []
        for step in result['steps']:
            i = step['arc']
            a = self.arcs[i]
            way = self.ways[a[2]][0]
            assert way not in self.closed
            chain = self.chain(i)
            assert self.price(i, chain) == a[-1], 'Original full source primitive milliseconds'
            native = [self.ids[n] for n in chain]
            nodes = chain
            if step['kind'] == 'suffix':
                assert native.count(source) == 1
                nodes = chain[native.index(source):]
            elif step['kind'] == 'prefix':
                assert native.count(target) == 1
                nodes = chain[:native.index(target)+1]
            elif step['kind'] != 'full':
                raise ValueError('Source replay unknown portion')
            assert step['ticks'] == (self.price(i, nodes)+124)//125
            if previous is not None:
                b = self.arcs[previous]
                assert b[1] == a[0] and node_path[-1] == nodes[0]
                flag = flags[a[0]]
                reverse = b[2:5] == a[2:5] and b[5] == -a[5]
                assert not flag & 1 and (not reverse or flag & 4)
                from_way = self.ways[b[2]][0]
                only = []
                for to, kind in self.via[from_way, self.ids[self.anchors[a[0]]]]:
                    matches = way == to
                    if from_way == to:
                        matches = matches and (reverse if kind.endswith('u_turn') else not reverse)
                    if kind.startswith('only_'):
                        only.append(matches)
                    else:
                        assert not matches, 'Original no-turn restriction violated'
                assert not only or any(only), 'Original only-turn restriction violated'
                total += (40 if flag & 2 else 0)+(160 if reverse else 0)
            if not way_sequence or way_sequence[-1] != way:
                way_sequence.append(way)
            node_path.extend(nodes if not node_path else nodes[1:])
            total += step['ticks']
            previous = i
        assert not any(tuple(way_sequence[i:i+3]) in self.sequences for i in range(len(way_sequence)-2)), 'Original via-way prohibited sequence violated'
        assert self.ids[node_path[0]] == source and self.ids[node_path[-1]] == target
        assert total == result['ticks']
        return {'ticks': total, 'nativeNodeIds': [self.ids[n] for n in node_path], 'sourceArcSteps': len(result['steps']), 'sourceTurnTransitions': max(0, len(result['steps'])-1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    assert sha(REPO / args.plan) == args.pin
    plan = json.loads((REPO / args.plan).read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-car-restriction-entry-capture-v1'
    assert plan['maxOwnedBytes'] == 67108864 and plan['hostSeconds'] == 600
    assert plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes'] + plan['maxOwnedBytes'] < 64*1024**3
    for name, pin in plan['bindings'].items():
        assert sha(REPO / name) == pin, name
    root = REPO / plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes((REPO / args.plan).read_bytes())

    def check():
        assert time.monotonic()-began < 600
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss*(1 if sys.platform == 'darwin' else 1024) < 4*1024**3

    def save(name, value):
        raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
        assert len(raw) <= 1048576
        with (root/name).open('xb') as stream:
            stream.write(raw)

    try:
        source = REPO / plan['source']
        closed_source = json.loads((REPO / plan['sourceClosed']).read_bytes())
        roster = closed_source['roster']
        assert sum(p['bytes'] for n, p in roster.items() if n.startswith('cost-facts/')) <= 16*1048576

        def field(prefix, code=None, shape=None):
            raw = bytearray()
            for name in sorted(roster):
                if not name.startswith('cost-facts/'+prefix+'-'):
                    continue
                check()
                path = source/name
                assert path.stat().st_size == roster[name]['bytes'] and sha(path) == roster[name]['sha256']
                raw.extend(path.read_bytes())
            if shape:
                return list(shape.iter_unpack(raw))
            if code:
                values = array(code)
                values.frombytes(raw)
                return values
            return raw

        ids, xy, anchors, flags = field('ids', 'Q'), field('xy', 'i'), field('anchors', 'I'), field('flags')
        geometry, ways, raw_arcs = field('geometry', 'I'), field('ways', shape=WAY), field('arcs', shape=ARC)
        old_closed, turns = set(field('closures', 'Q')), field('turns', shape=TURN)
        cases = json.loads((REPO / plan['originalReport']).read_bytes())['queries']
        elements = [json.loads(line)['element'] for line in (source/'deferred-relations.jsonl').read_text().splitlines()]
        assert len(cases) == 82 and len(elements) == 4900
        proposal = plan_entries(elements, [arc_dict(a, ways) for a in raw_arcs])
        assert proposal['oldClosed'] == old_closed
        original_fields, original_fixtures, _ = encode(ids, xy, anchors, flags, geometry, ways, raw_arcs, old_closed, turns, cases)
        original_assets = json.loads((REPO / plan['originalPacked']/'artifacts.json').read_bytes())
        for name, raw in original_fields.items():
            pin = original_assets['routing/'+name]
            assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256']
        assert original_fixtures == json.loads((REPO / plan['originalPacked']/'query-fixtures.json').read_bytes())
        fields, fixtures, counts = encode(ids, xy, anchors, flags, geometry, ways, raw_arcs, proposal['closed'], turns, cases)
        active = packed_arcs(raw_arcs, ways, proposal['closed'])
        old_active = packed_arcs(raw_arcs, ways, old_closed)
        index = {tuple(a[:6]): i for i, a in enumerate(active)}
        extra = {(index[tuple(raw_arcs[a][:6])], index[tuple(raw_arcs[b][:6])]) for a, b in proposal['pairs'] if tuple(raw_arcs[a][:6]) in index and tuple(raw_arcs[b][:6]) in index}
        existing = unpack24(fields['forbidden-turns.u24'])
        forbidden = sorted(set(zip(existing[::2], existing[1::2])) | extra)
        fields['forbidden-turns.u24'] = b''.join(n.to_bytes(3, 'little') for pair in forbidden for n in pair)
        original_turns = unpack24(original_fields['forbidden-turns.u24'])
        baseline = QueryGraph([arc_dict(a, ways) for a in old_active], flags, zip(original_turns[::2], original_turns[1::2]))
        candidate = QueryGraph([arc_dict(a, ways) for a in active], flags, forbidden)
        # Prove the full baseline directed graph/turn set is preserved, not only
        # its82 sampled queries. Added prohibitions touch no old allowed pair.
        mapped = {i: index[tuple(a[:6])] for i, a in enumerate(old_active)}
        for i, a in enumerate(old_active):
            for j in baseline.outgoing[a[1]]:
                if baseline.delay(i, j) is not None:
                    assert candidate.delay(mapped[i], mapped[j]) == baseline.delay(i, j)
        replay = SourceReplay(ids, xy, anchors, geometry, ways, active, elements, proposal['closed'], proposal['converted'])
        rows, recovered, improved, finite = [], 0, 0, 0
        for ordinal, (old, new) in enumerate(zip(original_fixtures, fixtures)):
            check()
            previous = baseline.query(old['source'], old['target'], old['directTicks'], check)
            assert previous['ticks'] == old['expectedTicks'], 'Frozen82 baseline optimum identity'
            current = candidate.query(new['source'], new['target'], new['directTicks'], check)
            candidate.replay(new['source'], new['target'], new['directTicks'], current)
            if previous['ticks'] is not None:
                assert current['ticks'] is not None and current['ticks'] <= previous['ticks']
                improved += current['ticks'] < previous['ticks']
            else:
                recovered += current['ticks'] is not None
            witness = replay.audit(new, current, flags)
            finite += witness is not None
            raw = json.dumps({'fixture': new, 'result': current, 'sourceWitness': witness}, separators=(',', ':')).encode()
            packed = gzip.compress(raw, mtime=0)
            assert len(raw) <= 16*1048576 and len(packed) <= 2*1048576
            name = f'query-{ordinal:02d}.json.gz'
            with (root/name).open('xb') as stream:
                stream.write(packed)
            rows.append({'index': ordinal, 'windowId': old['windowId'], 'sourceNodeIds': old['sourceNodeIds'], 'baselineTicks': previous['ticks'], 'candidateTicks': current['ticks'], 'pathSteps': len(current['steps']), 'sourceReplayed': witness is not None, 'witness': {'filename': name, 'sha256': hashlib.sha256(packed).hexdigest(), 'bytes': len(packed)}})
            new['expectedTicks'] = current['ticks']
        (root/'routing').mkdir()
        assets = {}
        for name, raw in fields.items():
            with (root/'routing'/name).open('xb') as stream:
                stream.write(raw)
            assets['routing/'+name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        save('artifacts.json', assets)
        save('query-fixtures.json', fixtures)
        save('entry-resolution.json', {'converted': proposal['converted'], 'fallback': proposal['fallback'], 'activeEntryPairs': len(extra), 'oldClosedWays': len(old_closed), 'remainingClosedWays': len(proposal['closed'])})
        assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) < 64*1048576
        report = {'status': 'captured_conservative_entry_graph_experiment_complete', 'recipeSha256': args.pin,
                  'originalCases': 82, 'originalUnreachable': 14, 'allOriginalOptimaReproduced': True,
                  'allBaselineAllowedTransitionsPreserved': True, 'candidateFinite': finite,
                  'previousFailuresRecovered': recovered, 'previousFiniteImproved': improved,
                  'candidateStillUnreachable': 82-finite, 'convertedRelations': len(proposal['converted']),
                  'fallbackRelations': len(proposal['fallback']), 'activeEntryPairs': len(extra),
                  'candidateArcs': counts['arcs'], 'candidateForbiddenPairs': len(forbidden),
                  'payloadBytes': sum(p['bytes'] for p in assets.values()), 'rows': rows,
                  'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'providerRequests': 0, 'applicationDbReads': 0,
                  'hostSeconds': time.monotonic()-began, 'nationalPolicyChanged': False, 'appActivated': False,
                  'scope': 'Small captured facts only; full original cost/graph/transition preservation and independent native geometry/price/source-restriction path replay. New optima are not provider ETA/national/full-app acceptance. Host functional run, no cgroup/cache-inclusive peak or cloud latency claim.'}
        save('report.json', report)
        print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))
    except Exception as error:
        save('failure.json', {'status': 'captured_entry_experiment_stopped', 'error': repr(error), 'hostSeconds': time.monotonic()-began})
        raise


if __name__ == '__main__':
    main()

"""Single bounded captured turn-context/source experiment; no national execution."""
import argparse
from array import array
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_conditional_graph_v1 import augment
from coarse_osm_context_turns_v1 import ContextQueryGraph, plan_contexts
from coarse_osm_entry_graph_v1 import QueryGraph
from coarse_osm_packed_capture_v1 import ARC, TURN, WAY, encode
from evaluate_osm_conditional_capture_v1 import SourceReplay, arc_dict, packed_arcs, sha, unpack24

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    recipe = REPO/args.plan
    assert sha(recipe) == args.pin
    plan = json.loads(recipe.read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-context-turns-capture-v1'
    assert plan['controlsPassed'] == 32 and plan['expectedPreArcs'] == 79118
    assert plan['expectedActiveArcs'] == 77274 and plan['hostSeconds'] == 600
    assert plan['maxOwnedBytes'] == 67108864
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes'] < 72*1024**3
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin, name
    root = REPO/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())

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
        source = REPO/plan['source']
        roster = json.loads((REPO/plan['sourceClosed']).read_bytes())['roster']
        assert sum(p['bytes'] for n, p in roster.items() if n.startswith('cost-facts/')) <= 16*1048576
        def field(prefix, code=None, shape=None):
            raw = bytearray()
            for name in sorted(roster):
                if name.startswith('cost-facts/'+prefix+'-'):
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
        original_closed, turns = set(field('closures', 'Q')), field('turns', shape=TURN)
        elements = [json.loads(line)['element'] for line in (source/'deferred-relations.jsonl').read_text().splitlines()]
        cases = json.loads((REPO/plan['originalReport']).read_bytes())['queries']
        assert len(cases) == 82 and len(elements) == 4900
        records = json.loads((REPO/plan['conditionalRecords']).read_bytes())['records']
        assert len(records) == 109
        ways, raw_arcs, changed = augment(ids, xy, anchors, geometry, ways, raw_arcs, records, check)
        assert len(changed) == 108 and len(raw_arcs) == plan['expectedPreArcs']
        proposal = plan_contexts(elements, [arc_dict(a, ways) for a in raw_arcs], len(raw_arcs))
        assert proposal['oldClosed'] == original_closed
        fields, fixtures, counts = encode(ids, xy, anchors, flags, geometry, ways, raw_arcs, proposal['closed'], turns, cases)
        assert counts['arcs'] == plan['expectedActiveArcs']
        active = packed_arcs(raw_arcs, ways, proposal['closed'])
        index = {tuple(a[:6]): i for i, a in enumerate(active)}
        entries = {(index[tuple(raw_arcs[a][:6])], index[tuple(raw_arcs[b][:6])]) for a, b in proposal['pairs']
                   if tuple(raw_arcs[a][:6]) in index and tuple(raw_arcs[b][:6]) in index}
        values = unpack24(fields['forbidden-turns.u24'])
        supported = set(zip(values[::2], values[1::2]))
        old_forbidden = supported | entries
        baseline_root = REPO/plan['absentBaseline']
        baseline_report = json.loads((baseline_root/'report.json').read_bytes())
        baseline_assets = json.loads((baseline_root/'artifacts.json').read_bytes())
        assert baseline_report['candidateFinite'] == 81 and len(baseline_report['rows']) == 82
        for name, raw in fields.items():
            if name == 'forbidden-turns.u24':
                raw = b''.join(n.to_bytes(3, 'little') for pair in sorted(old_forbidden) for n in pair)
            pin = baseline_assets['routing/'+name]
            assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Complete frozen absent-member graph identity'
        for row, fixture in zip(baseline_report['rows'], fixtures, strict=True):
            fixture['expectedTicks'] = row['candidateTicks']
        assert fixtures == json.loads((baseline_root/'query-fixtures.json').read_bytes())
        physical_arcs = [arc_dict(a, ways) for a in active]
        baseline = QueryGraph(physical_arcs, flags, old_forbidden)
        candidate = ContextQueryGraph(QueryGraph(physical_arcs, flags, supported), proposal['contextRules'])
        allowed = 0
        for before, a in enumerate(physical_arcs):
            for after in baseline.outgoing[a['head']]:
                delay = baseline.delay(before, after)
                if delay is not None:
                    assert candidate.source.delay(before, after) == delay
                    assert candidate.following_context(-1, before, after) == -1
                    allowed += 1
        # Every old allowed transition leaves ordinary history ordinary. Thus
        # all old paths, including arbitrary endpoints, retain identical costs.
        replay = SourceReplay(ids, xy, anchors, geometry, ways, active, elements, proposal['closed'], proposal['converted'])
        rows, finite, recovered, improved = [], 0, 0, 0
        for ordinal, fixture in enumerate(fixtures):
            check()
            previous = baseline.query(fixture['source'], fixture['target'], fixture['directTicks'], check)
            assert previous['ticks'] == fixture['expectedTicks'], 'All82 baseline optima exact'
            current = candidate.query(fixture['source'], fixture['target'], fixture['directTicks'], check)
            candidate.replay(fixture['source'], fixture['target'], fixture['directTicks'], current)
            if previous['ticks'] is not None:
                assert current['ticks'] is not None and current['ticks'] <= previous['ticks']
                improved += current['ticks'] < previous['ticks']
            else:
                recovered += current['ticks'] is not None
            witness = replay.audit(fixture, current, flags)
            finite += witness is not None
            raw = json.dumps({'fixture': fixture, 'result': current, 'sourceWitness': witness}, separators=(',', ':')).encode()
            compressed = gzip.compress(raw, mtime=0)
            assert len(raw) <= 16*1048576 and len(compressed) <= 2*1048576
            name = f'query-{ordinal:02d}.json.gz'
            with (root/name).open('xb') as stream:
                stream.write(compressed)
            rows.append({'index': ordinal, 'windowId': fixture['windowId'], 'sourceNodeIds': fixture['sourceNodeIds'],
                         'baselineTicks': previous['ticks'], 'candidateTicks': current['ticks'],
                         'pathSteps': len(current['steps']), 'sourceReplayed': witness is not None,
                         'witness': {'filename': name, 'sha256': hashlib.sha256(compressed).hexdigest(), 'bytes': len(compressed)}})
        save('context-rules.json', [{'id': r.identity, 'from': r.from_way, 'via': r.via_way, 'to': r.to_way} for r in proposal['contextRules']])
        assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) < plan['maxOwnedBytes']
        report = {'status': 'captured_static_via_way_context_and_source_replay_complete', 'recipeSha256': args.pin,
                  'originalCases': 82, 'baselineFinite': 81, 'candidateFinite': finite, 'candidateStillUnreachable': 82-finite,
                  'previousFailuresRecovered': recovered, 'previousFiniteImproved': improved,
                  'allAbsentMemberArraysAndFixturesReproduced': True, 'all82BaselineOptimaReproduced': True,
                  'allBaselineAllowedTransitionsPreserved': True, 'allowedOrdinaryTransitionsChecked': allowed,
                  'preArcs': len(raw_arcs), 'activeArcs': len(active), 'addedOrRepricedArcs': 0,
                  'contextRules': len(proposal['contextRules']), 'contextPrefixGroups': len(candidate.prefixes),
                  'maximumPossibleCapturedSearchStates': candidate.maximum_states,
                  'supportedTurnPairsRetained': len(supported), 'previousEntryPairs': len(entries),
                  'unchangedClosedWays': len(proposal['closed']), 'unchangedFallbackRelations': len(proposal['fallback']),
                  'unchangedInactiveMissingMemberRules': len(proposal['inactive']), 'rows': rows,
                  'routingQueries': 164, 'smallRoutingEncodings': 1, 'sourcePbfReads': 0, 'sourceConstructorExecutions': 0,
                  'providerRequests': 0, 'applicationDbReads': 0, 'hostSeconds': time.monotonic()-began,
                  'nationalPolicyChanged': False, 'runtimeArtifactBuilt': False, 'appActivated': False,
                  'scope': 'One bounded captured experiment, unchanged narrow static single-via-way no-turn selector and absent-member union. Remember from/via while on via; reject prohibited to completion, allow unrelated exits/arrivals. Every other contributor/conditional/only/unknown closure, source price/node flag/supported turn stays. All old entry-ban-allowed paths retain ordinary context/cost. Every finite path independently raw-source geometry/price/restriction replays. No source/PBF/constructor/provider/DB, cost adjustment, fit, place exception, national layout/83ETA or app admission. Python object/state caps and hostRSS/deadline are not protected/cloud memory or latency.'}
        save('report.json', report)
        print(json.dumps({k: report[k] for k in ('status', 'candidateFinite', 'candidateStillUnreachable', 'previousFailuresRecovered', 'previousFiniteImproved', 'contextRules', 'contextPrefixGroups', 'maximumPossibleCapturedSearchStates', 'hostSeconds')}))
    except BaseException as error:
        save('failure.json', {'error': repr(error), 'hostSeconds': time.monotonic()-began})
        raise


if __name__ == '__main__':
    main()

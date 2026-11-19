"""Bounded multi-via entry prototype with complete old graph/source parity."""
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
from coarse_osm_context_turns_v1 import ContextQueryGraph
from coarse_osm_multiway_entry_v1 import plan_multiway, audit_raw_multiway_path
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
    assert plan['output'] == 'data/coarse-quality/us-osm-multiway-entry-capture-v1'
    assert plan['controlsPassed'] == 38 and plan['expectedPreArcs'] == 79118
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
        pre_arcs = [arc_dict(a, ways) for a in raw_arcs]
        proposal = plan_multiway(elements, pre_arcs, len(raw_arcs))
        previous = proposal['previous']
        assert previous['oldClosed'] == original_closed
        old_fields, old_fixtures, old_counts = encode(ids, xy, anchors, flags, geometry, ways, raw_arcs, previous['closed'], turns, cases)
        old_active = packed_arcs(raw_arcs, ways, previous['closed'])
        old_index = {tuple(a[:6]): i for i, a in enumerate(old_active)}
        old_entries = {(old_index[tuple(raw_arcs[a][:6])], old_index[tuple(raw_arcs[b][:6])]) for a,b in previous['pairs']
                       if tuple(raw_arcs[a][:6]) in old_index and tuple(raw_arcs[b][:6]) in old_index}
        old_values = unpack24(old_fields['forbidden-turns.u24'])
        old_supported = set(zip(old_values[::2], old_values[1::2]))
        baseline_root = REPO/plan['absentBaseline']
        baseline_assets = json.loads((baseline_root/'artifacts.json').read_bytes())
        absent_rows = json.loads((baseline_root/'report.json').read_bytes())['rows']
        for name, raw in old_fields.items():
            if name == 'forbidden-turns.u24':
                raw = b''.join(n.to_bytes(3,'little') for pair in sorted(old_supported|old_entries) for n in pair)
            pin = baseline_assets['routing/'+name]
            assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256']
        for row, fixture in zip(absent_rows, old_fixtures, strict=True):
            fixture['expectedTicks'] = row['candidateTicks']
        assert old_fixtures == json.loads((baseline_root/'query-fixtures.json').read_bytes())
        assert old_counts['arcs'] == plan['expectedActiveArcs'] == 77274
        old_physical = [arc_dict(a, ways) for a in old_active]
        baseline = ContextQueryGraph(QueryGraph(old_physical, flags, old_supported), previous['contextRules'])
        old_report = json.loads((REPO/plan['contextBaseline']/'report.json').read_bytes())
        assert old_report['candidateFinite'] == 81 and len(old_report['rows']) == 82
        fields, fixtures, counts = encode(ids, xy, anchors, flags, geometry, ways, raw_arcs, proposal['closed'], turns, cases)
        active = packed_arcs(raw_arcs, ways, proposal['closed'])
        index = {tuple(a[:6]): i for i,a in enumerate(active)}
        assert len(index) == len(active) >= len(old_active)
        mapping = [index[tuple(a[:6])] for a in old_active]
        for before, after in enumerate(mapping):
            assert old_active[before] == active[after]
        entries = {(index[tuple(raw_arcs[a][:6])], index[tuple(raw_arcs[b][:6])]) for a,b in proposal['multiPairs']
                   if tuple(raw_arcs[a][:6]) in index and tuple(raw_arcs[b][:6]) in index}
        values = unpack24(fields['forbidden-turns.u24'])
        supported = set(zip(values[::2], values[1::2]))
        reverse_map = {n:i for i,n in enumerate(mapping)}
        assert {(reverse_map[a],reverse_map[b]) for a,b in supported if a in reverse_map and b in reverse_map} == old_supported
        assert not any(a in reverse_map and b in reverse_map for a,b in entries)
        physical = [arc_dict(a, ways) for a in active]
        candidate = ContextQueryGraph(QueryGraph(physical, flags, supported|entries), proposal['contextRules'])
        assert baseline.prefixes == candidate.prefixes and baseline.prohibited_to == candidate.prohibited_to
        allowed = 0
        for before,a in enumerate(old_physical):
            for after in baseline.source.outgoing[a['head']]:
                delay = baseline.source.delay(before, after)
                if delay is not None:
                    assert candidate.source.delay(mapping[before],mapping[after]) == delay
                    assert baseline.following_context(-1,before,after) == candidate.following_context(-1,mapping[before],mapping[after])
                    allowed += 1
        # Way IDs, context rules and every old physical transition/cost agree;
        # all old history-state paths therefore remain identically priced.
        replay = SourceReplay(ids, xy, anchors, geometry, ways, active, elements, proposal['closed'], proposal['converted'])
        rows, finite, improved, recovered = [], 0, 0, 0
        for ordinal, (fixture, old_fixture, old_row) in enumerate(zip(fixtures,old_fixtures,old_report['rows'],strict=True)):
            check()
            assert fixture['sourceNodeIds'] == old_fixture['sourceNodeIds'] and fixture['windowId'] == old_fixture['windowId']
            prior = baseline.query(old_fixture['source'],old_fixture['target'],old_fixture['directTicks'],check)
            assert prior['ticks'] == old_row['candidateTicks']
            result = candidate.query(fixture['source'],fixture['target'],fixture['directTicks'],check)
            candidate.replay(fixture['source'],fixture['target'],fixture['directTicks'],result)
            audit_raw_multiway_path(elements,proposal['multiConverted'],physical,result,set(a['way'] for a in pre_arcs))
            witness = replay.audit(fixture,result,flags)
            if prior['ticks'] is not None:
                assert result['ticks'] is not None and result['ticks'] <= prior['ticks']
                improved += result['ticks'] < prior['ticks']
            else:
                recovered += result['ticks'] is not None
            finite += witness is not None
            raw = json.dumps({'fixture':fixture,'result':result,'sourceWitness':witness},separators=(',',':')).encode()
            compressed = gzip.compress(raw,mtime=0)
            assert len(raw) <= 16*1048576 and len(compressed) <= 2*1048576
            name = f'query-{ordinal:02d}.json.gz'
            with (root/name).open('xb') as stream:stream.write(compressed)
            rows.append({'index':ordinal,'windowId':fixture['windowId'],'sourceNodeIds':fixture['sourceNodeIds'],
                         'baselineTicks':prior['ticks'],'candidateTicks':result['ticks'],'pathSteps':len(result['steps']),
                         'sourceReplayed':witness is not None,'witness':{'filename':name,'bytes':len(compressed),'sha256':hashlib.sha256(compressed).hexdigest()}})
        assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) < plan['maxOwnedBytes']
        report = {'status':'captured_multi_via_entry_and_independent_source_replay_complete', 'recipeSha256':args.pin,
                  'originalCases':82,'baselineFinite':81,'candidateFinite':finite,'candidateStillUnreachable':82-finite,
                  'previousFailuresRecovered':recovered,'previousFiniteImproved':improved,
                  'completePreArcs':len(raw_arcs),'oldPhysicalArcs':len(old_active),'newPhysicalArcs':len(active),
                  'oldPhysicalArcsAndPricesExact':True,'allOldAllowedHistoryPathsPreserved':True,
                  'oldAllowedPhysicalTransitionsChecked':allowed,'supportedSourceTurnPairs':len(supported),
                  'oldContextRulesUnchanged':len(proposal['contextRules']),'oldFallbackRelations':len(previous['fallback']),
                  'remainingFallbackRelations':len(proposal['fallback']),'oldClosedWays':len(previous['closed']),
                  'remainingClosedWays':len(proposal['closed']),'multiViaRulesConverted':len(proposal['multiConverted']),
                  'multiViaInactiveMissingMemberRules':len(proposal['multiInactive']),
                  'completeMultiViaPreEntryPairs':len(proposal['multiPairs']),'activeMultiViaEntryPairs':len(entries),
                  'maximumCapturedQueryStates':candidate.maximum_states,'rows':rows,
                  'routingQueries':164,'sourcePbfReads':0,'nativeConstructorExecutions':0,'providerRequests':0,
                  'applicationDbReads':0,'hostSeconds':time.monotonic()-began,'appActivated':False,
                  'scope':'Captured source-only prototype. Static multi-via-way no-turns ban from->ANY via entry,regardless of source member order;this conservatively prevents completion and still excludes legal exits. Missing essential legs use complete PRE-closure graph only. Every other closure contribution/single-via history/source cost/flag/turn remains. All old arrays/fixtures/82 optima reproduced;all old physical arcs/prices/history paths preserved;all finite paths independently source geometry/price/node/via-node/single-via and raw multi-entry replay. No national layout/83ETA/maps/app admission or cost fit/place exception. HostRSS/deadline are not cgroup/CPU/swap/cloud memory/latency.'}
        save('report.json',report)
        print(json.dumps({k:report[k] for k in ('status','candidateFinite','candidateStillUnreachable','previousFailuresRecovered','previousFiniteImproved','multiViaRulesConverted','oldPhysicalArcs','newPhysicalArcs','remainingClosedWays','hostSeconds')}))
    except BaseException as error:
        save('failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began})
        raise


if __name__ == '__main__':
    main()

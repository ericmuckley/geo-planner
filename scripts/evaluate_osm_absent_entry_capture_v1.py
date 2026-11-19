"""Captured absent-member no-turn graph/source proof; use PYTHONPATH=scripts:routing."""
import argparse
from array import array
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_entry_graph_v1 import plan_entries, QueryGraph
from coarse_osm_absent_entry_v1 import plan_entries as absent_plan
from coarse_osm_packed_capture_v1 import ARC, encode, TURN, WAY
from coarse_osm_conditional_graph_v1 import augment
from evaluate_osm_conditional_capture_v1 import sha, unpack24, packed_arcs, arc_dict, SourceReplay

REPO=Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    assert sha(REPO / args.plan) == args.pin
    plan = json.loads((REPO / args.plan).read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-absent-entry-graph-capture-v1'
    assert plan['maxOwnedBytes'] == 67108864 and plan['hostSeconds'] == 600
    assert plan['controlsPassed'] == 20 and plan['expectedPreArcs'] == 79118
    assert plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes'] + plan['maxOwnedBytes'] < 72*1024**3
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
        original_fields, original_fixtures, _ = encode(ids, xy, anchors, flags, geometry, ways, raw_arcs, old_closed, turns, cases)
        original_assets = json.loads((REPO / plan['originalPacked']/'artifacts.json').read_bytes())
        for name, raw in original_fields.items():
            pin = original_assets['routing/'+name]
            assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256']
        assert original_fixtures == json.loads((REPO / plan['originalPacked']/'query-fixtures.json').read_bytes())
        def routing(candidate_ways, candidate_arcs, resolve=plan_entries):
            proposal=resolve(elements,[arc_dict(a,candidate_ways) for a in candidate_arcs])
            assert proposal['oldClosed']==old_closed
            fields,fixtures,counts=encode(ids,xy,anchors,flags,geometry,candidate_ways,candidate_arcs,proposal['closed'],turns,cases)
            active=packed_arcs(candidate_arcs,candidate_ways,proposal['closed'])
            index={tuple(a[:6]):i for i,a in enumerate(active)}
            extra={(index[tuple(candidate_arcs[a][:6])],index[tuple(candidate_arcs[b][:6])]) for a,b in proposal['pairs'] if tuple(candidate_arcs[a][:6]) in index and tuple(candidate_arcs[b][:6]) in index}
            existing=unpack24(fields['forbidden-turns.u24'])
            forbidden=sorted(set(zip(existing[::2],existing[1::2]))|extra)
            fields['forbidden-turns.u24']=b''.join(n.to_bytes(3,'little') for pair in forbidden for n in pair)
            return fields,fixtures,counts,active,index,proposal,extra,forbidden
        baseline_fields, baseline_fixtures, _, old_active, _, old_proposal, _, baseline_forbidden = routing(ways,raw_arcs)
        entry=REPO/plan['entryBaseline'];entry_report=json.loads((entry/'report.json').read_bytes())
        entry_assets=json.loads((entry/'artifacts.json').read_bytes())
        assert entry_report['candidateFinite']==74 and len(entry_report['rows'])==82
        for name,raw in baseline_fields.items():
            pin=entry_assets['routing/'+name]
            assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Frozen entry baseline byte identity'
        for row,fixture in zip(entry_report['rows'],baseline_fixtures):fixture['expectedTicks']=row['candidateTicks']
        assert baseline_fixtures==json.loads((entry/'query-fixtures.json').read_bytes())
        records=json.loads((REPO/plan['conditionalRecords']).read_bytes())['records'];assert len(records)==109
        ways,raw_arcs,changed=augment(ids,xy,anchors,geometry,ways,raw_arcs,records,check)
        assert len(changed)==108
        baseline_fields,baseline_fixtures,_,old_active,_,old_proposal,_,baseline_forbidden=routing(ways,raw_arcs)
        current=REPO/plan['conditionalBaseline']
        current_report=json.loads((current/'report.json').read_bytes())
        current_assets=json.loads((current/'artifacts.json').read_bytes())
        assert current_report['candidateFinite']==77 and len(current_report['rows'])==82
        assert len(raw_arcs)==plan['expectedPreArcs']
        for name,raw in baseline_fields.items():
            pin=current_assets['routing/'+name]
            assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Frozen conditional baseline byte identity'
        for row,fixture in zip(current_report['rows'],baseline_fixtures):fixture['expectedTicks']=row['candidateTicks']
        assert baseline_fixtures==json.loads((current/'query-fixtures.json').read_bytes())
        def resolve_absent(elements, arcs):
            return absent_plan(elements,arcs,plan['expectedPreArcs'])
        fields,fixtures,counts,active,index,proposal,extra,forbidden=routing(ways,raw_arcs,resolve_absent)
        assert proposal['closed']<=old_proposal['closed'] and proposal['pairs']==old_proposal['pairs']
        assert counts['arcs']==plan['expectedNewArcs']

        baseline=QueryGraph([arc_dict(a,ways) for a in old_active],flags,baseline_forbidden)
        candidate=QueryGraph([arc_dict(a,ways) for a in active],flags,forbidden)
        # Prove the full baseline directed graph/turn set is preserved, not only
        # its82 sampled queries. Added prohibitions touch no old allowed pair.
        mapped = {i: index[tuple(a[:6])] for i, a in enumerate(old_active)}
        for i, a in enumerate(old_active):
            for j in baseline.outgoing[a[1]]:
                if baseline.delay(i, j) is not None:
                    assert candidate.delay(mapped[i], mapped[j]) == baseline.delay(i, j)
        replay = SourceReplay(ids, xy, anchors, geometry, ways, active, elements, proposal['closed'], proposal['converted'])
        rows, recovered, improved, finite = [], 0, 0, 0
        for ordinal, (old, new) in enumerate(zip(baseline_fixtures, fixtures)):
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
        report = {'status': 'captured_absent_member_graph_experiment_complete', 'recipeSha256': args.pin,
                  'originalCases': 82, 'originalUnreachable': 14, 'entryBaselineFinite':74,'entryBaselineUnreachable':8,'conditionalBaselineFinite':77,'conditionalBaselineUnreachable':5,'allConditionalArraysReproduced':True,'allConditionalOptimaReproduced':True,'allOriginalArraysReproduced':True,'allEntryArraysReproduced':True,'allEntryOptimaReproduced':True,'inheritedConditionalChangesReproduced':changed,'inheritedConditionalPreArcsReproduced':sum(r['newPreClosureArcs'] for r in changed),'addedPreClosureArcs':0,'newlyAvailablePostClosureArcs':len(active)-len(old_active),'inactiveNarrowStaticNoTurns':len(proposal['inactive']),
                  'allBaselineAllowedTransitionsPreserved': True, 'candidateFinite': finite,
                  'previousFailuresRecovered': recovered, 'previousFiniteImproved': improved,
                  'candidateStillUnreachable': 82-finite, 'convertedRelations': len(proposal['converted']),
                  'fallbackRelations': len(proposal['fallback']), 'activeEntryPairs': len(extra),
                  'candidateArcs': counts['arcs'], 'candidateForbiddenPairs': len(forbidden),
                  'payloadBytes': sum(p['bytes'] for p in assets.values()), 'rows': rows,
                  'routingQueries':164,'smallRoutingEncodings':4,'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'providerRequests': 0, 'applicationDbReads': 0,
                  'hostSeconds': time.monotonic()-began, 'nationalPolicyChanged': False, 'appActivated': False,
                  'scope':'New small routing arrays from closed captured facts; original/entry/conditional graph bytes and fixtures reproduce, all82 conditional optima and every old allowed transition retained. Only omit narrow static no-turn closure contributions when an essential way has zero COMPLETE PRE-relation-closure arcs; every other contributor/conditional/only/unknown case unchanged. No speed/default/access/coordinate rule or fit. Every finite path independently native-geometry/price/raw-restriction replays. No raw source/PBF/native constructor/SQLite/provider/application DB. Captured feasibility only, not83 ORS/35 Valhalla ETA/national/app admission. Host RSS/deadline, no cgroup/CPU/swap/cloud claim.'}
        save('report.json', report)
        print(json.dumps({k:report[k] for k in ['status','candidateFinite','candidateStillUnreachable','previousFailuresRecovered','previousFiniteImproved','candidateArcs','candidateForbiddenPairs','newlyAvailablePostClosureArcs','inactiveNarrowStaticNoTurns','hostSeconds']}))
    except Exception as error:
        save('failure.json', {'status': 'captured_conditional_experiment_stopped', 'error': repr(error), 'hostSeconds': time.monotonic()-began})
        raise


if __name__ == '__main__':
    main()

"""Recompute the closed finer candidate gates; no model, provider or large asset reads."""
import json
import math

from verify_conditional_node_candidate_v1 import recompute_gates, summary
from verify_entry_runtime_v1 import stage
from verify_finer_display_capacity_pilot_v2 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    plan = load(HERE/'finer-reused-display-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin, name
    closed = load(HERE/'finer-reused-display-v1-closed-v1.json')
    mirror = HERE/'finer-reused-display-v1-raw-v1'
    for name, asset in closed['roster'].items():
        if not asset['ignoredLargeAsset']:
            assert (mirror/name).stat().st_size == asset['bytes'] and sha(mirror/name) == asset['sha256']
    assert (mirror/'execution-plan.json').read_bytes() == (HERE/'finer-reused-display-plan-v1.json').read_bytes()
    total = result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < plan['maxOwnedBytes']
    assert 64500000000+total+104857600 < 72*1024**3
    if closed['terminalRecord'] == 'failure.json':
        stopped = load(mirror/'failure.json')
        assert stopped['error'] == closed['terminalStatus']
        return {**result, 'status':'finer_candidate_stop_preserved_without_accuracy_score',
                'registeredClosedRoots':412, 'newUniqueClosedAllocationBytes':total,
                'newFinerAccuracyScore':False,'finerCandidateFailure':stopped['error'],
                'partialFinerMapsRetained':sum(n.endswith('.geojson') for n in closed['roster']),
                'accuracyOrAppAccepted':False}
    report = stage('finer-reused-display-v1')
    assert report['recipeSha256'] == sha(HERE/'finer-reused-display-plan-v1.json')
    assert report['status'] == 'all58_finer_reused_display_candidate_complete'
    assert report['isAccuracyCandidate'] and report['higherResolutionEvaluated']
    assert not report['candidateAdmitted'] and not report['frozenLocalGridOrMapsReused']
    assert not report['endpointCollectionsRecomputed'] and report['endpointCollectionsReusedByIdentity']
    old = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    prior = {r['id']:r for r in old['rows']}
    rows = report['rows']; by_id = {r['id']:r for r in rows}
    assert len(rows) == len(by_id) == report['originalCases'] == 83 and set(prior) == set(by_id)
    assert report['valhallaCases'] == sum(r['valhallaMinutes'] is not None for r in rows) == 35
    for row in rows:
        for key in ['set','origin','destination','budgetMinutes','referenceMinutes','valhallaMinutes','baseline']:
            assert row[key] == prior[row['id']][key], (row['id'],key)
        point = row['candidate']['pointMinutes']; baseline = row['baseline']['pointMinutes']
        expected = None if point is None or baseline is None else abs(point-row['referenceMinutes'])-abs(baseline-row['referenceMinutes'])
        assert row['absoluteErrorChangeMinutes'] is None if expected is None else math.isclose(row['absoluteErrorChangeMinutes'],expected,rel_tol=0,abs_tol=1e-10)
        shaded = row['candidate']['predictedReachable']
        expected_class = ('ambiguous' if abs(row['referenceMinutes']-row['budgetMinutes']) <= 5 else 'correct' if shaded == (row['referenceMinutes'] < row['budgetMinutes']) else 'falseReachable' if shaded else 'missedReachable')
        assert row['candidate']['classification'] == expected_class
    for name, selected in [('overall',rows), *[(s,[r for r in rows if r['set'] == s]) for s in ['original','regional','frontier']]]:
        recorded = report['overall'] if name == 'overall' else report['sets'][name]
        for model in ['baseline','candidate']:
            for metric, value in summary(selected,model).items():
                assert recorded[model][metric] is None if value is None else math.isclose(recorded[model][metric],value,rel_tol=0,abs_tol=1e-10)
    gates = recompute_gates(rows)
    assert len(gates) == 19 and gates == report['gates']
    assert report['numericalGatesPassed'] == all(gates.values())
    for name in ['original','regional']:
        selected = [r for r in rows if r['set'] == name]
        for model in ['baseline','candidate']:
            for metric,value in summary(selected,model,'valhallaMinutes').items():
                recorded = report['valhallaSensitivity'][name][model][metric]
                assert recorded is None if value is None else math.isclose(recorded,value,rel_tol=0,abs_tol=1e-10)
    assert report['frontierClassificationsAllCases'] == {
        label:sum(r['set'] == 'frontier' and r['candidate']['classification'] == label for r in rows)
        for label in ['correct','falseReachable','missedReachable','ambiguous']}
    assert report['origins'] == report['diagnosticDisplays'] == len(report['phases']) == 21
    assert report['productionDisplays'] == 37 and report['displays'] == len(report['results']) == 58
    assert report['diagnosticPointCases'] == 83
    outputs = []; displays = []; public = {}; timings = {}
    finer = 0
    for i, (phase, before) in enumerate(zip(report['phases'],old['phases'])):
        assert phase['origin'] == before['origin'] and phase['accessInput'] == before['accessInput']
        assert [p['minutes'] for p in phase['productions']] == [p['minutes'] for p in before['productions']]
        specs = [(900,phase['diagnostic'],before['diagnostic']), *[(p['minutes'],p,b) for p,b in zip(phase['productions'],before['productions'])]]
        for minutes, row, old_display in specs:
            assert row['originIndex'] == i and row['minutes'] == minutes
            assert row['diagnostic'] == (minutes == 900)
            assert row['fieldStats'] == old_display['fieldStats']
            assert 5000 <= row['frame']['step'] <= old_display['frame']['step']
            finer += row['frame']['step'] < old_display['frame']['step']
            assert row['stats']['initialSeedCells'] <= row['stats']['maximumHeapEntries'] <= 1000000
            assert row['maxObservedQueryArrayBuffers'] <= row['stats']['maximumBackingBufferBytes'] <= 67108864
            assert row['stats']['seedPhaseDeclaredBytes'] == row['stats']['fillPhaseDeclaredBytes'] == row['stats']['maximumBackingBufferBytes']
            assert row['afterReleaseArrayBuffers'] == report['afterLoad']['arrayBuffers']
            retries = row['stats']['retries']; assert len(retries) <= 8
            steps = [round(r['stepDegrees']*1e6) for r in retries]+[row['frame']['step']]
            for a,b in zip(steps,steps[1:]):
                assert b == min(25000,math.ceil(a*1.25))
            for retry in retries:
                assert retry['finiteSeedCells'] == 1000001
            output = row['output']; asset = closed['roster'][output['filename']]
            assert output['filename'] == old_display['output']['filename']
            assert all(output[k] == asset[k] for k in ['bytes','sha256']) and output['bytes'] <= 3000000
            assert row['stats']['jsonBytes'] == output['bytes']
            outputs.append(output); displays.append(row)
            if minutes == 900:
                assert set(row['timings']) == set(old_display['timings'])
                for key,timing in row['timings'].items():
                    assert timing['roadTicks'] == old_display['timings'][key]['roadTicks']
                    assert by_id[key]['candidate']['pointMinutes'] == (None if timing['ticks'] is None else timing['ticks']/480)
                    timings[key] = timing
            else:
                for sample in rows:
                    if [sample['origin']['lon'],sample['origin']['lat']] == phase['origin'] and sample['budgetMinutes'] == minutes:
                        public[sample['id']] = row
    assert len(outputs) == len({o['filename'] for o in outputs}) == 58
    assert displays == report['results'] and len(timings) == len(public) == 83
    observed = report['productionPointObservations']
    assert len(observed) == len({o['id'] for o in observed}) == 83 and {o['id'] for o in observed} == set(by_id)
    for obs in observed:
        sample = by_id[obs['id']]; display = public[obs['id']]; f = display['frame']
        assert obs['originIndex'] == display['originIndex'] and obs['minutes'] == sample['budgetMinutes']
        assert obs['shaded'] == sample['candidate']['predictedReachable']
        for name in ['pointOnMask','cellCovered','shaded']:
            assert type(obs[name]) is bool
        if obs['cell'] < 0:
            assert obs['cellCenter'] is obs['centerOnMask'] is obs['localSeconds'] is None
        else:
            assert obs['cell'] < f['width']*f['height'] and type(obs['centerOnMask']) is bool
            x = obs['cell'] % f['width']; y = obs['cell']//f['width']
            expected = [(f['west']+(x+0.5)*f['step'])/1e6,(f['south']+(y+0.5)*f['step'])/1e6]
            assert all(math.isclose(a,b,rel_tol=0,abs_tol=1e-12) for a,b in zip(obs['cellCenter'],expected))
        assert obs['localSeconds'] is None or 0 <= obs['localSeconds'] <= obs['minutes']*60
    assert report['providerRequests'] == 0
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers']
    assert report['retainedBackingBytes'] == report['heldBackingBytes'] == report['afterLoad']['arrayBuffers']-report['baseline']['arrayBuffers']
    assert report['retainedBackingGatePassed'] == (report['retainedBackingBytes'] <= 162238546)
    assert report['hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC'] < plan['hostSeconds']*1000
    return {**result, 'status':'all83_finer_candidate_original_gates_independently_recomputed',
            'registeredClosedRoots':412,'newUniqueClosedAllocationBytes':total,
            'newFinerAccuracyScore':True,
            'meanAbsoluteMinutes':report['overall']['candidate']['meanAbsoluteMinutes'],
            'previousRoadGridMeanAbsoluteMinutes':old['overall']['candidate']['meanAbsoluteMinutes'],
            'v9MeanAbsoluteMinutes':report['overall']['baseline']['meanAbsoluteMinutes'],
            'failedOriginalGates':sorted(k for k,v in gates.items() if not v),
            'all83Finite':gates['all83Finite'],'all58MapsFresh':True,
            'finerFrames':finer,'maximumFinerCells':max(r['frame']['width']*r['frame']['height'] for r in displays),
            'publicPointObservations':83,
            'dryPointsWithClosedFinerDisplayCenters':[o['id'] for o in observed if o['pointOnMask'] and o['centerOnMask'] is False],
            'pointEstimatesChangedVsOldGrid':sum(r['candidate']['pointMinutes'] != prior[r['id']]['candidate']['pointMinutes'] for r in rows),
            'retainedBackingBytes':report['retainedBackingBytes'],
            'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))

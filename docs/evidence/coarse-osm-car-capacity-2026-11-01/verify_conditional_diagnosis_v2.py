"""Portable all83 exact paths, corrected source annotation and cached-route diagnosis."""
import json
from verify_conditional_deltas_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    paths = stage('conditional-paths')
    assert paths['paths'] == paths['newRoadSearches'] == 83
    assert paths['reusedRoadPaths'] == paths['unavailable'] == paths['providerRequests'] == 0
    assert paths['afterLoad']['arrayBuffers'] == paths['afterQueries']['arrayBuffers'] == 157524723
    expected = {r['id']: r['candidate']['pointMinutes'] for r in load(HERE/'conditional-evaluation-raw-v1/report.json')['rows']}
    assert len(paths['rows']) == len(expected) == 83
    for row in paths['rows']:
        assert sum(row['components'].values()) == row['sumTicks']
        assert abs(row['sumTicks']/480-expected[row['id']]) < 1e-10
        assert row['afterReleaseArrayBuffers'] == 157524723
        assert row['searchStats']['offlineSearchBackingBytes'] <= 134217728
    frozen = {tuple(p['origin']): p['diagnostic']['output']['sha256'] for p in load(HERE/'conditional-evaluation-raw-v1/report.json')['phases']}
    assert len(paths['phases']) == 21
    for phase in paths['phases']:
        assert phase['outputSha256'] == frozen[tuple(phase['origin'])]
        assert phase['traceStats']['maximumBackingBufferBytes'] <= 134217728
    failed = load(HERE/'conditional-attributes-run-closed-v1.json')
    assert failed['terminalRecord'] == 'failure.json'
    raw = HERE/'conditional-attributes-run-raw-v1'
    for name, pin in failed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (raw/name).stat().st_size == pin['bytes'] and sha(raw/name) == pin['sha256']
    plan = load(raw/'execution-plan.json')
    for name, pin in plan['inputs'].items():
        if name.startswith(('scripts/', 'docs/')):
            assert sha(REPO/name) == pin
    assert load(raw/'cleanup.json')['independentInspectAbsent'] and load(raw/'run-summary.json')['exitCode'] == 2
    assert 'AssertionError' in load(raw/'failure.json')['error']
    assert stage('conditional-attributes-v2-controls', True)['controls'] == {'tests': 9, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    attributes = stage('conditional-attributes-v2-run', True)
    assert attributes['paths'] == 83 and attributes['unavailable'] == 0 and attributes['selectedArcs'] == 45119
    assert (attributes['waysChecked'], attributes['preArcMappingsChecked'], attributes['retainedArcMappingsChecked']) == (4227238, 9878318, 9744462)
    for row, path in zip(attributes['rows'], paths['rows']):
        assert row['id'] == path['id'] and row['roadTicks'] == path['components']['roadTravelTicks']
        assert row['taggedTicks'] + row['defaultTicks'] == row['roadTicks']
    plan = load(HERE/'conditional-path-findings-plan-v1.json')
    findings = load(HERE/'conditional-path-findings-v1.json')
    assert findings['recipeSha256'] == sha(HERE/'conditional-path-findings-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if name.startswith(('scripts/', 'docs/')):
            assert sha(REPO/name) == pin
    assert len(findings['rows']) == 83 and findings['unavailable'] == []
    assert findings['sourceSpeedAttributeUniqueKnownArcs'] == 45119 and findings['sourceSpeedAttributeUniqueUnknownArcs'] == 0
    assert findings['sourceSpeedTickTotals'] == {'explicitTicks': 12970162, 'defaultTicks': 1866947, 'unknownTicks': 0}
    assert findings['providerRequests'] == findings['modelQueries'] == 0 and not findings['policyChanged']
    total = result['newUniqueClosedAllocationBytes']
    for prefix in ('conditional-paths', 'conditional-attributes-run', 'conditional-attributes-v2-controls', 'conditional-attributes-v2-run'):
        total += load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == 6354694144
    return {**result, 'conditionalAll83PathsAnd21FrozenMapShasExact': True,
            'conditionalAll45119PathArcsSourceAnnotated': True, 'conditionalSourceAttributeUnknownArcs': 0,
            'uniqueClosedRoots': 204, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

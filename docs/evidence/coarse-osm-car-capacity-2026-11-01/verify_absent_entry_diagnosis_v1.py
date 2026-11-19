"""Portable complete paths/source/geometry and single fixed-speed sensitivity."""
import json
from statistics import mean

from verify_absent_entry_evaluation_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    paths = stage('absent-entry-paths')
    assert paths['paths'] == paths['newRoadSearches'] == 83
    assert paths['reusedRoadPaths'] == paths['unavailable'] == paths['providerRequests'] == 0
    assert paths['afterLoad']['arrayBuffers'] == paths['afterQueries']['arrayBuffers'] == 157946504
    candidate = load(HERE/'absent-entry-evaluation-raw-v1/report.json')
    expected = {r['id']: r['candidate']['pointMinutes'] for r in candidate['rows']}
    assert len(paths['rows']) == len(expected) == 83
    assert sum(r['kind'] == 'road-foot' for r in paths['rows']) == 67
    for row in paths['rows']:
        assert sum(row['components'].values()) == row['sumTicks']
        assert abs(row['sumTicks']/480-expected[row['id']]) < 1e-10
        assert row['afterReleaseArrayBuffers'] == 157946504
        assert row['searchStats']['offlineSearchBackingBytes'] <= 134217728
    frozen = {tuple(p['origin']): p['diagnostic']['output']['sha256'] for p in candidate['phases']}
    assert len(paths['phases']) == 21
    for phase in paths['phases']:
        assert phase['outputSha256'] == frozen[tuple(phase['origin'])]
        assert phase['traceStats']['maximumBackingBufferBytes'] <= 134217728
    controls = dict(tests=9, successful=True, failures=0, errors=0, skips=0)
    assert stage('absent-entry-attributes-controls', True)['controls'] == controls
    failed = load(HERE/'absent-entry-attributes-run-closed-v1.json')
    assert failed['terminalRecord'] == 'failure.json'
    raw = HERE/'absent-entry-attributes-run-raw-v1'
    for name, pin in failed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (raw/name).stat().st_size == pin['bytes'] and sha(raw/name) == pin['sha256']
    for name, pin in load(raw/'execution-plan.json')['inputs'].items():
        if name.startswith(('scripts/', 'docs/')):
            assert sha(REPO/name) == pin
    assert load(raw/'cleanup.json')['independentInspectAbsent']
    assert load(raw/'run-summary.json')['exitCode'] == 2
    assert 'Entry path compressed identity' in load(raw/'failure.json')['error']
    assert 'arc-attributes.json.gz' not in failed['roster']
    assert stage('absent-entry-attributes-v2-controls', True)['controls'] == controls
    attributes = stage('absent-entry-attributes-v2-run', True)
    assert attributes['paths'] == 83 and attributes['unavailable'] == 0 and attributes['selectedArcs'] == 41384
    assert (attributes['waysChecked'], attributes['preArcMappingsChecked'], attributes['retainedArcMappingsChecked']) == (4227238, 9878318, 9807359)
    for row, path in zip(attributes['rows'], paths['rows'], strict=True):
        assert row['id'] == path['id'] and row['roadTicks'] == path['components']['roadTravelTicks']
        assert row['taggedTicks'] + row['defaultTicks'] == row['roadTicks']
    plan = load(HERE/'absent-entry-path-findings-plan-v1.json')
    findings = load(HERE/'absent-entry-path-findings-v1.json')
    assert findings['recipeSha256'] == sha(HERE/'absent-entry-path-findings-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if name.startswith(('scripts/', 'docs/')):
            assert sha(REPO/name) == pin
    assert len(findings['rows']) == 83 and findings['unavailable'] == []
    assert findings['sourceSpeedAttributeUniqueKnownArcs'] == 41384
    assert findings['sourceSpeedAttributeUniqueUnknownArcs'] == 0
    assert findings['sourceSpeedTickTotals'] == dict(explicitTicks=12735645, defaultTicks=1537547, unknownTicks=0)
    assert findings['providerRequests'] == findings['modelQueries'] == 0 and not findings['policyChanged']
    plan = load(HERE/'absent-entry-tagged90-fixed-path-plan-v1.json')
    sensitivity = load(HERE/'absent-entry-tagged90-fixed-path-screen-v1.json')
    assert sensitivity['recipeSha256'] == sha(HERE/'absent-entry-tagged90-fixed-path-plan-v1.json')
    assert plan['taggedSpeedRatio'] == [9, 10] and plan['defaultSpeedRatio'] == [1, 1]
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin
    source = {r['id']: r for r in attributes['rows']}
    assert len(sensitivity['rows']) == 83
    for row in sensitivity['rows']:
        assert not row['unavailable'] and row['currentMinutes'] == expected[row['id']]
        assert row['fixedPathSensitivityMinutes'] == row['currentMinutes'] + source[row['id']]['taggedTicks']/(480*9)
    actual = mean(abs(r['fixedPathSensitivityMinutes']-r['referenceMinutes']) for r in sensitivity['rows'])
    assert abs(actual - 14.43662037037037) < 1e-10
    assert abs(sensitivity['same83']['fixedPathSensitivityMaeMinutes']-actual) < 1e-10
    assert sensitivity['newRoutingQueries'] == sensitivity['newMaps'] == sensitivity['providerRequests'] == 0
    assert not sensitivity['policyActivated'] and not sensitivity['isCandidateEvaluation'] and not sensitivity['originalGatesChanged']
    total = result['newUniqueClosedAllocationBytes']
    for name in ('paths', 'attributes-controls', 'attributes-run', 'attributes-v2-controls', 'attributes-v2-run'):
        total += load(HERE/f'absent-entry-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6823071744
    return {**result, 'absentMemberAll83PathsAnd21MapShasExact': True,
            'absentMemberAll41384PathArcsSourceAnnotated': True,
            'absentMemberSourceAttributeUnknownArcs': 0,
            'absentMemberExternalTagged90FixedPathMeanAbsoluteMinutes': actual,
            'absentMemberTagged90IsRoutingCandidate': False,
            'uniqueClosedRoots': 228, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

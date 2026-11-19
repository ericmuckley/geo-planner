"""Recheck current witness/source/geometry receipts without large assets or queries."""
import json
import math

from verify_incomplete_node_candidate_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    paths = stage('incomplete-node-paths')
    candidate = load(HERE / 'incomplete-node-evaluation-v2-raw-v1/report.json')
    by_id = {row['id']: row for row in candidate['rows']}
    assert paths['paths'] == paths['newRoadSearches'] == len(paths['rows']) == 83
    assert paths['unavailable'] == paths['reusedRoadPaths'] == paths['providerRequests'] == 0
    assert not paths['candidateAdmitted']
    assert paths['afterLoad']['arrayBuffers'] == paths['afterQueries']['arrayBuffers'] == 159854202
    for row in paths['rows']:
        assert sum(row['components'].values()) == row['sumTicks']
        assert math.isclose(row['sumTicks']/480, by_id[row['id']]['candidate']['pointMinutes'], abs_tol=1e-9)
        if row['searchStats']:
            assert row['searchStats']['offlineSearchBackingBytes'] <= 96 * 1024**2
    assert len(paths['phases']) == 21
    for phase, original in zip(paths['phases'], candidate['phases']):
        assert phase['origin'] == original['origin']
        assert phase['outputSha256'] == original['diagnostic']['output']['sha256']
        assert phase['fieldStats']['maximumBackingBufferBytes'] < 64 * 1024**2
        assert phase['traceStats']['productionAlgorithmBackingBufferBytes'] < 64 * 1024**2
    # Preserve the missing-mount stop independently of the successful correction.
    failed = load(HERE / 'incomplete-node-attributes-run-closed-v1.json')
    failed_root = HERE / 'incomplete-node-attributes-run-raw-v1'
    for name, pin in failed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (failed_root/name).stat().st_size == pin['bytes'] and sha(failed_root/name) == pin['sha256']
    assert failed['terminalRecord'] == 'failure.json'
    assert load(failed_root/'cleanup.json')['independentInspectAbsent']
    assert load(failed_root/'run-summary.json')['exitCode'] != 0
    old_plan = load(failed_root/'execution-plan.json')
    for name, pin in old_plan['inputs'].items():
        if name.startswith(('scripts/', 'docs/')):
            assert sha(REPO/name) == pin
    assert '/inputs/path-report.json' not in old_plan['mounts'].values()
    attributes = stage('incomplete-node-attributes-v2-run', True)
    assert (attributes['paths'], attributes['unavailable'], attributes['selectedArcs']) == (83, 0, 43889)
    assert (attributes['waysChecked'], attributes['preArcMappingsChecked'], attributes['retainedArcMappingsChecked']) == (4227238, 9882872, 9837848)
    assert attributes['sourcePbfReads'] == attributes['routingQueries'] == attributes['providerRequests'] == 0
    assert not attributes['policyFitOrChange'] and not attributes['appActivated']
    epoch = load(HERE/'incomplete-node-attributes-v2-run-plan-v1.json')
    witness = load(HERE/'incomplete-node-path-plan-v1.json')
    for key in ('coreManifestSha256', 'geometryManifestSha256'):
        assert epoch[key] == witness[key]
    assert '/inputs/path-report.json' in epoch['mounts'].values()
    assert len(set(epoch['mounts'].values())) == len(epoch['mounts'])
    plan = load(HERE/'incomplete-node-path-findings-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if name.startswith('data/'):
            assert name == 'data/coarse-quality/us-osm-tagged-timing-attributes-run-v1/arc-attributes.json.gz'
            assert pin == load(HERE/'tagged-timing-attributes-run-closed-v1.json')['roster']['arc-attributes.json.gz']['sha256']
        else:
            assert sha(REPO/name) == pin, name
    findings = load(HERE/'incomplete-node-path-findings-v1.json')
    assert findings['recipeSha256'] == sha(HERE/'incomplete-node-path-findings-plan-v1.json')
    assert len(findings['rows']) == 83 and not findings['unavailable']
    assert findings['sourceSpeedAttributeUniqueKnownArcs'] == 43889
    assert findings['sourceSpeedAttributeUniqueUnknownArcs'] == 0
    assert findings['sourceSpeedTickTotals'] == dict(explicitTicks=13787647, defaultTicks=1701440, unknownTicks=0)
    assert findings['providerRequests'] == findings['modelQueries'] == 0 and not findings['policyChanged']
    path_rows = {row['id']: row for row in paths['rows']}
    attr_rows = {row['id']: row for row in attributes['rows']}
    assert set(path_rows) == set(attr_rows) == {r['id'] for r in findings['rows']} == set(by_id)
    for row in findings['rows']:
        assert row['components'] == path_rows[row['id']]['components']
        assert math.isclose(row['candidateMinutes'], path_rows[row['id']]['sumTicks']/480, abs_tol=1e-9)
        assert math.isclose(row['signedMinutes'], row['candidateMinutes']-row['referenceMinutes'], abs_tol=1e-9)
        exposure = row['sourceSpeedExposure']
        assert sum(exposure[k] for k in ('explicitTicks', 'defaultTicks', 'unknownTicks')) == row['components']['roadTravelTicks']
        attr = attr_rows[row['id']]
        assert exposure['defaultTicks'] == attr['defaultTicks']
        assert exposure['explicitTicks'] == attr['taggedTicks']
    mean = sum(abs(r['signedMinutes']) for r in findings['rows'])/83
    assert math.isclose(mean, findings['overall']['meanAbsoluteErrorMinutes'], abs_tol=1e-10)
    assert math.isclose(mean, result['meanAbsoluteMinutes'], abs_tol=1e-10)
    total = result['newUniqueClosedAllocationBytes']
    for prefix in ('incomplete-node-paths', 'incomplete-node-attributes-run', 'incomplete-node-attributes-v2-run'):
        total += load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == plan['newClosedAllocationBytes'] == 10140217344
    assert plan['previousClosedRoots'] == 377
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    return {**result, 'status': 'incomplete_node_all83_current_winners_source_and_cached_geometry_audited',
            'registeredClosedRoots': 377, 'newUniqueClosedAllocationBytes': total,
            'all83CurrentWinnerSumsReproduced': True, 'all21DiagnosticMapHashesExact': True,
            'selectedSourceArcsKnown': 43889, 'selectedSourceArcsUnknown': 0,
            'ignoredAssetsReadOrProducerExecutions': 0, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

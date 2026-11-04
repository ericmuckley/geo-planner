"""Read small sealed records only: no model/path/source/provider/DB operation."""
import json
from verify_access_preview_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha
from verify_spatial_storage_v1 import host_closed


def verify():
    result = previous()
    mask = load(host_closed('mask-diagnostic')/'report.json')
    assert mask['inputs'] == 79 and mask['savedReferenceRequestsChecked'] == 83
    assert mask['savedReferenceRadiusMeters'] == 350 and len(mask['outsideMask']) == 2
    assert not mask['modelChanged'] and mask['providerRequests'] == 0
    unsupported = [r for r in mask['outsideMask'] if not r['originalSupported']]
    assert len(unsupported) == 1 and unsupported[0]['nearestModeledRoad']['distanceMeters'] > 939
    stopped = load(HERE/'access-path-diagnostic-closed-v1.json')
    assert stopped['terminalRecord'] == 'failure.json'
    assert len([n for n in stopped['roster'] if n.endswith('.json.gz')]) == 14
    failure = load(HERE/'access-path-diagnostic-raw-v1/failure.json')
    assert 'retained backing buffers' in failure['error'] and failure['providerRequests'] == 0
    for name, tests in [('road-witness-controls-v1.json', 10), ('road-witness-controls-v2.json', 11), ('local-witness-controls-v1.json', 12)]:
        controls = load(HERE/name)
        assert controls['successful'] and controls['tests'] == tests and controls['failures'] == controls['skips'] == 0
        for path, pin in controls['codeBindings'].items():
            assert sha(REPO/path) == pin
    root = host_closed('access-path-diagnostic-v2')
    paths = load(root/'report.json')
    assert paths['recipeSha256'] == sha(HERE/'access-path-diagnostic-plan-v2.json')
    assert (paths['paths'], paths['unavailable'], paths['reusedRoadPaths'], paths['newRoadSearches']) == (80, 3, 14, 66)
    assert len(paths['rows']) == 83 and len(paths['phases']) == 20
    assert paths['providerRequests'] == 0 and not paths['candidateAdmitted']
    candidate = load(HERE/'access-candidate-evaluation-raw-v1/report.json')
    timings = {k: v for p in candidate['phases'] if 'diagnostic' in p for k, v in p['diagnostic']['timings'].items()}
    expected = {tuple(p['origin']): p['diagnostic'] for p in candidate['phases'] if 'diagnostic' in p}
    baseline = paths['afterLoad']['arrayBuffers']
    for phase in paths['phases']:
        assert phase['outputSha256'] == expected[tuple(phase['origin'])]['output']['sha256']
        assert phase['afterTraceReleaseArrayBuffers'] <= baseline+1048576
        assert phase['traceStats']['maximumBackingBufferBytes'] <= 128*1024**2
    for row in paths['rows']:
        if 'unavailable' in row:
            assert row['id'] not in timings or timings[row['id']]['ticks'] is None
            continue
        assert sum(row['components'].values()) == row['sumTicks'] == timings[row['id']]['ticks']
        assert 0 <= row['components']['endpointRoundingTicks'] <= 7
        assert row['afterReleaseArrayBuffers'] <= baseline+1048576
        if row['searchStats']:
            assert row['searchStats']['offlineSearchBackingBytes'] == 84965440
    seal = load(HERE/'path-analysis-seal-v1.json')
    for path, pin in seal['records'].items():
        assert sha(REPO/path) == pin
    for name in ['saved-input-plan-v2.json', 'path-findings-plan-v1.json']:
        for path, pin in load(HERE/name)['bindings'].items():
            # Ignored country source inputs stay recorded, never reread by this portable proof.
            if not path.startswith('data/'):
                assert sha(REPO/path) == pin
    inputs = load(HERE/'saved-input-diagnostic-v2.json')
    assert len(inputs['inputs']) == 79 and len(inputs['references']) == 83
    assert inputs['systemMessages'] == {"Preference 'fastest' has been deprecated, using 'recommended'.": 83}
    assert inputs['providerRequests'] == 0 and not inputs['policyChanged']
    rejected = [r for r in inputs['inputs'] if not r['supported']]
    assert len(rejected) == 1 and rejected[0]['geography']['rawLakes'] == rejected[0]['geography']['simplifiedLakes'] == ['Salton Sea']
    findings = load(HERE/'path-findings-v1.json')
    assert findings['status'] == 'saved_path_geometry_cost_diagnosis_complete'
    assert len(findings['rows']) == 80 and len(findings['unavailable']) == 3
    assert abs(findings['overall']['meanAbsoluteErrorMinutes'] - 31.371151041666668) < 1e-10
    assert findings['providerRequests'] == findings['modelQueries'] == 0 and not findings['policyChanged']
    for row in findings['rows']:
        assert abs(sum(row['components'].values())/480-row['candidateMinutes']) < 1e-10
    return {**result, 'independentFiniteRoadLocalWitnesses': 80, 'unavailableCasesPreserved': 3,
            'frozenOutputIdentities': 20, 'sameMathRoadLifetimeControls': 11,
            'newUniqueClosedAllocationBytes': 2355331072, 'uniqueClosedRoots': 86,
            'accuracyOrAppAccepted': False,
            'reads': 'Small mirrors/bound code only; no source/ignored path asset/model search/render/browser/provider/DB.'}


if __name__ == '__main__':
    print(json.dumps(verify()))

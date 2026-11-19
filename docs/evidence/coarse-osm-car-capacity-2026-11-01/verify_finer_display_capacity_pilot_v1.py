"""Verify the closed finer-grid pressure pilot, retaining failures without a score."""
import json

from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha
from verify_reused_display_parity_v1 import verify as previous


def verify():
    result = previous()
    plan = load(HERE/'finer-display-capacity-pilot-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin, name
    candidate = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    peaks = [max(p['stats']['maximumHeapEntries'] for p in [phase['diagnostic'], *phase['productions']]) for phase in candidate['phases']]
    assert plan['originIndices'] == [peaks.index(max(peaks))] == [4]
    record = load(HERE/'finer-display-capacity-pilot-v1-closed-v1.json')
    mirror = HERE/'finer-display-capacity-pilot-v1-raw-v1'
    for name, asset in record['roster'].items():
        if not asset['ignoredLargeAsset']:
            assert (mirror/name).stat().st_size == asset['bytes'] and sha(mirror/name) == asset['sha256']
    assert (mirror/'execution-plan.json').read_bytes() == (HERE/'finer-display-capacity-pilot-plan-v1.json').read_bytes()
    stopped = record['terminalRecord'] == 'failure.json'
    if stopped:
        report = load(mirror/'failure.json')
        assert report['error'] == 'Error: local heap capacity'
        assert 'fillLocal' in report['stack'] and 'coarse_osm_display_grid_v1.ts:283' in report['stack']
        assert report['activeMinutes'] == 900 and report['immutableSeedingChecked']
        assert 0 < report['lastObservedQueryArrayBuffers'] <= 67108864
        assert report['observedQueryBuffers'] == 8 and report['queryBuffersReleased'] is False
        assert report['afterFailure']['arrayBuffers']-report['heldArrayBuffers'] == 2*5731903
        assert report['providerRequests'] == 0 and report['hostTotalMs'] < 900000
        capacity_passed = False
    else:
        report = stage('finer-display-capacity-pilot-v1')
        assert report['recipeSha256'] == sha(HERE/'finer-display-capacity-pilot-plan-v1.json')
        assert report['origins'] == 1 and report['originIndex'] == 4
        assert report['displays'] == len(report['results']) == 4
        assert not report['isAccuracyCandidate'] and report['higherResolutionEvaluated']
        phase = candidate['phases'][4]
        for row, old in zip(report['results'], [phase['diagnostic'], *phase['productions']]):
            assert row['frame']['step'] <= old['frame']['step']
            assert row['fieldStats'] == old['fieldStats']
            assert row['maxObservedQueryArrayBuffers'] <= row['stats']['maximumBackingBufferBytes'] <= 67108864
            assert row['afterReleaseArrayBuffers'] == report['afterLoad']['arrayBuffers']
            asset = record['roster'][row['output']['filename']]
            assert all(asset[k] == row['output'][k] for k in ['bytes','sha256'])
        assert report['providerRequests'] == 0
        assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers']
        capacity_passed = True
    assert record['usage']['conservativeAllocatedBytes'] < plan['maxOwnedBytes']
    total = result['newUniqueClosedAllocationBytes']+record['usage']['conservativeAllocatedBytes']
    assert 64500000000+total+104857600 < 72*1024**3
    return {**result, 'status':'finer_display_capacity_pilot_closed_and_verified',
            'registeredClosedRoots':409,'newUniqueClosedAllocationBytes':total,
            'finerPressurePilotPassed':capacity_passed,
            'finerExceptionCleanupPassed':False if stopped else True,
            'finerPressurePilotFailurePreserved':stopped,
            'newFinerAccuracyScore':False,'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))

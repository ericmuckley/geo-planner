"""Check the corrected closed resource pilot, without model or accuracy execution."""
import json

from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha
from verify_reused_display_parity_v2 import verify as previous


def verify():
    result = previous()
    plan = load(HERE/'finer-display-capacity-pilot-plan-v2.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin, name
    closed = load(HERE/'finer-display-capacity-pilot-v2-closed-v1.json')
    mirror = HERE/'finer-display-capacity-pilot-v2-raw-v1'
    for name, asset in closed['roster'].items():
        if not asset['ignoredLargeAsset']:
            assert (mirror/name).stat().st_size == asset['bytes'] and sha(mirror/name) == asset['sha256']
    assert (mirror/'execution-plan.json').read_bytes() == (HERE/'finer-display-capacity-pilot-plan-v2.json').read_bytes()
    failed = closed['terminalRecord'] == 'failure.json'
    if failed:
        report = load(mirror/'failure.json')
        assert report['error'] == closed['terminalStatus']
        assert report['providerRequests'] == 0
        cleanup_passed = report['queryBuffersReleased'] is True
        finer = None
    else:
        report = stage('finer-display-capacity-pilot-v2')
        assert report['recipeSha256'] == sha(HERE/'finer-display-capacity-pilot-plan-v2.json')
        assert report['origins'] == 1 and report['originIndex'] == 4
        assert report['displays'] == len(report['results']) == 4
        assert report['diagnosticPointCases'] == 6
        assert not report['isAccuracyCandidate'] and report['higherResolutionEvaluated']
        original = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')['phases'][4]
        specs = [(900, original['diagnostic']), *[(p['minutes'],p) for p in original['productions']]]
        finer = 0
        for row, (minutes, old) in zip(report['results'], specs):
            assert row['minutes'] == minutes
            assert row['fieldStats'] == old['fieldStats']
            assert 5000 <= row['frame']['step'] <= 25000
            finer += row['frame']['step'] < old['frame']['step']
            assert row['stats']['initialSeedCells'] <= row['stats']['maximumHeapEntries'] <= 1000000
            assert row['maxObservedQueryArrayBuffers'] <= row['stats']['maximumBackingBufferBytes'] <= 67108864
            assert row['stats']['seedPhaseDeclaredBytes'] <= 67108864
            assert row['stats']['fillPhaseDeclaredBytes'] <= 67108864
            for retry in row['stats']['retries']:
                assert retry['finiteSeedCells'] == 1000001
                assert 0.005 <= retry['stepDegrees'] <= 0.025
            assert row['afterReleaseArrayBuffers'] == report['afterLoad']['arrayBuffers']
            asset = closed['roster'][row['output']['filename']]
            assert all(asset[k] == row['output'][k] for k in ['bytes','sha256'])
            if minutes == 900:
                assert set(row['timings']) == set(old['timings'])
                for key, timing in row['timings'].items():
                    assert timing['roadTicks'] == old['timings'][key]['roadTicks']
        assert report['providerRequests'] == 0
        assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers']
        assert report['heldBackingBytes'] <= 162238546
        assert report['hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC'] < 900000
        cleanup_passed = True
    assert closed['usage']['conservativeAllocatedBytes'] < plan['maxOwnedBytes']
    total = result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert 64500000000+total+104857600 < 72*1024**3
    return {**result, 'status':'corrected_finer_display_capacity_receipts_verified',
            'registeredClosedRoots':411,'newUniqueClosedAllocationBytes':total,
            'correctedFinerCapacityPassed':not failed,
            'correctedFinerExceptionCleanupPassed':cleanup_passed,
            'correctedPilotFinerFrames':finer,
            'newFinerAccuracyScore':False,'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))

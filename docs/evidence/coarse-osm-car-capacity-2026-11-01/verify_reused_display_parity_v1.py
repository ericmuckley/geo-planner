"""Check closed same-resolution display parity, without queries or large assets."""
import json
import math

from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha
from verify_reused_display_pilot_v1 import verify as previous


def verify():
    result = previous()
    plan = load(HERE/'reused-display-parity-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin, name
    report = stage('reused-display-parity-v1')
    assert report['recipeSha256'] == sha(HERE/'reused-display-parity-plan-v1.json')
    candidate = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    specs = [(i, minutes, old) for i, phase in enumerate(candidate['phases'])
             for minutes, old in [(900,phase['diagnostic']), *[(p['minutes'],p) for p in phase['productions']]]]
    assert plan['originIndices'] == list(range(21))
    assert report['origins'] == 21 and report['displays'] == len(report['results']) == len(specs) == 58
    assert report['diagnosticPointCases'] == sum(len(p['diagnostic']['timings']) for p in candidate['phases']) == 83
    assert report['heldBackingBytes'] == report['afterLoad']['arrayBuffers']-report['baseline']['arrayBuffers'] <= 162238546
    assert report['afterQueries']['arrayBuffers'] == report['afterLoad']['arrayBuffers']
    closed = load(HERE/'reused-display-parity-v1-closed-v1.json')
    for row, (index, minutes, old) in zip(report['results'], specs):
        assert row['originIndex'] == index
        assert row['minutes'] == minutes and row['diagnostic'] == (minutes == 900)
        assert row['frame'] == old['frame'] and row['output'] == old['output']
        assert row['fieldStats'] == old['fieldStats']
        assert row['timings'] == (old['timings'] if minutes == 900 else {})
        for name in ['samples','activeSpans','settles','maximumHeapEntries','localCells','roadOnlyCells','selectedCells','edges','rings','vertices','jsonBytes','retries']:
            assert row['stats'][name] == old['stats'][name], name
        f = row['frame']; n = f['width']*f['height']
        masks = 4*math.ceil(n/8)+2*math.ceil(n/2)+2*f['width']+4*f['height']
        assert row['stats']['reusedLabelBytes'] >= masks
        assert row['stats']['reusedVertexBytes'] >= 8*1000000
        expected = old['fieldStats']['maximumBackingBufferBytes']+2*n+f['width']+f['height']+1+12*4096+64
        assert row['stats']['seedPhaseDeclaredBytes'] == row['stats']['fillPhaseDeclaredBytes'] == row['stats']['maximumBackingBufferBytes'] == expected <= 67108864
        assert 0 < row['maxObservedQueryArrayBuffers'] <= expected
        assert row['afterReleaseArrayBuffers'] == report['afterLoad']['arrayBuffers']
        asset = closed['roster'][row['output']['filename']]
        assert all(asset[k] == row['output'][k] for k in ['bytes','sha256'])
    assert report['providerRequests'] == 0
    assert not report['isAccuracyCandidate'] and not report['higherResolutionEvaluated']
    assert report['hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC'] < plan['hostSeconds']*1000
    assert closed['usage']['conservativeAllocatedBytes'] < plan['maxOwnedBytes']
    total = result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert 64500000000+total+104857600 < 72*1024**3
    return {**result, 'status':'all58_maps_and83_timings_reused_display_parity_verified',
            'registeredClosedRoots':408, 'newUniqueClosedAllocationBytes':total,
            'sameResolutionReusedMapsExact':58, 'sameResolutionDiagnosticComponentsExact':83,
            'observedReusedQueryBackingBelow64MiB':True,
            'reusedQueryBackingRestored':True,
            'reusedHigherResolutionEvaluated':False,
            'nationalReusedParityComplete':True}


if __name__ == '__main__':
    print(json.dumps(verify()))

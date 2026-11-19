"""Portable terminal-choice feasibility result and preserved lifetime stops."""
import json
from verify_conditional_diagnosis_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def stopped(prefix):
    record = load(HERE/(prefix+'-closed-v1.json'))
    raw = HERE/(prefix+'-raw-v1')
    assert record['terminalRecord'] == 'failure.json'
    for name, pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (raw/name).stat().st_size == pin['bytes'] and sha(raw/name) == pin['sha256']
    plan = load(raw/'execution-plan.json')
    for name, pin in plan['bindings'].items():
        if name.startswith(('scripts/', 'docs/')):
            assert sha(REPO/name) == pin
    assert 'retained backing buffers' in load(raw/'failure.json')['error']
    return record['usage']['conservativeAllocatedBytes']


def verify():
    result = previous()
    total = result['newUniqueClosedAllocationBytes'] + stopped('terminal-alternatives') + stopped('terminal-alternatives-v2')
    report = stage('terminal-alternatives-v3')
    assert report['originalCases'] == report['primaryRoadTimingsReproduced'] == 83 and report['valhallaCases'] == 35
    assert report['changedPointTimes'] == 28 and report['roadFinishesImproved'] == 33
    assert report['overall']['candidate']['pairedFinite'] == 83
    assert abs(report['overall']['candidate']['meanAbsoluteMinutes'] - 30.561380522088356) < 1e-10
    assert not report['numericalGatesPassed'] and not report['candidateAdmitted'] and report['providerRequests'] == 0
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers'] == 141923537
    assert report['heldCoreGeometryBackingBytes'] == 141845790
    original = {r['id']: r for r in load(HERE/'conditional-evaluation-raw-v1/report.json')['rows']}
    assert len(report['rows']) == len(report['comparisons']) == 83 and len(report['phases']) == 21
    for row in report['rows']:
        before = original[row['id']]
        for key in ['origin', 'destination', 'referenceMinutes', 'valhallaMinutes', 'budgetMinutes', 'baseline']:
            assert row[key] == before[key], key
        assert row['candidate']['classification'] == before['candidate']['classification']
    for row in report['comparisons']:
        assert row['pointTicks'] <= row['previousPointTicks']
        if row['previousRoadTicks'] is not None:
            assert row['bestRoadTicks'] <= row['previousRoadTicks']
    for i in range(1, 22):
        phase = load(HERE/f'terminal-alternatives-v3-raw-v1/origin-{i:02}.json')
        assert phase['afterReleaseArrayBuffers'] <= 141923537 + 1048576
        assert phase['fieldStats']['maximumBackingBufferBytes'] < 67108864
    total += load(HERE/'terminal-alternatives-v3-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6359228416
    return {**result, 'terminalChoicePrototypeAll83PrimaryTimingsReproduced': True,
            'terminalChoicePrototypeChangedPoints': 28, 'terminalChoicePrototypeMeanAbsoluteMinutes': 30.561380522088356,
            'terminalChoicePrototypeAll21FieldsReleased': True,
            'uniqueClosedRoots': 207, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

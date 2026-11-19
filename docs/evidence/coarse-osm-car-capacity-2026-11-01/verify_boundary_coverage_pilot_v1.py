"""Reconcile the closed coverage pilot; never reroute or read large source assets."""
import json

from verify_display_refinement_preview_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    plan = load(HERE / 'boundary-coverage-pilot-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO / name) == pin, name
    closed = load(HERE / 'boundary-coverage-pilot-v1-closed-v1.json')
    mirror = HERE / 'boundary-coverage-pilot-v1-raw-v1'
    for name, asset in closed['roster'].items():
        if not asset['ignoredLargeAsset']:
            assert (mirror / name).stat().st_size == asset['bytes']
            assert sha(mirror / name) == asset['sha256']
    assert (mirror / 'execution-plan.json').read_bytes() == (HERE / 'boundary-coverage-pilot-plan-v1.json').read_bytes()
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 413
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < plan['maxOwnedBytes']
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    base = {**result, 'registeredClosedRoots': 414, 'newUniqueClosedAllocationBytes': total,
            'boundaryWholeCellShoreAccuracyAccepted': False, 'newBoundaryAccuracyScore': False,
            'accuracyOrAppAccepted': False}
    if closed['terminalRecord'] == 'failure.json':
        stopped = load(mirror / 'failure.json')
        assert stopped['error'] == closed['terminalStatus']
        assert stopped['providerRequests'] == 0
        return {**base, 'status': 'boundary_coverage_pilot_stop_preserved',
                'boundaryPilotFailure': stopped['error'],
                'boundaryPilotQueryBuffersReleased': stopped['queryBuffersReleased']}
    report = stage('boundary-coverage-pilot-v1')
    assert report['recipeSha256'] == sha(HERE / 'boundary-coverage-pilot-plan-v1.json')
    assert report['status'] == 'highest_saved_finer_queue_pressure_paid_boundary_pilot_complete'
    assert not report['isAccuracyCandidate'] and report['wholeCellWaterPaintUnresolved']
    assert report['allFramesAndPointComponentsExactVsFinerCandidate']
    old = load(REPO / plan['candidate'])
    peaks = [max(row['stats']['maximumHeapEntries'] for row in [phase['diagnostic'], *phase['productions']])
             for phase in old['phases']]
    index = peaks.index(max(peaks))
    assert index == report['originIndex'] == plan['originIndices'][0] == 2
    phase = old['phases'][index]
    expected = [(900, phase['diagnostic']), *[(p['minutes'], p) for p in phase['productions']]]
    assert report['origins'] == 1 and report['displays'] == len(report['results']) == len(expected) == 4
    witnesses = water = uncertain = outside = points = 0
    for row, (minutes, before) in zip(report['results'], expected):
        assert row['minutes'] == minutes and row['diagnostic'] == (minutes == 900)
        assert row['frame'] == before['frame'] and row['fieldStats'] == before['fieldStats']
        assert row['stats']['maximumHeapEntries'] == before['stats']['maximumHeapEntries'] <= 1000000
        assert row['stats']['maximumBackingBufferBytes'] == before['stats']['maximumBackingBufferBytes'] <= 67108864
        assert 0 < row['maxObservedQueryArrayBuffers'] <= row['stats']['maximumBackingBufferBytes']
        assert row['afterReleaseArrayBuffers'] == report['afterLoad']['arrayBuffers']
        audit, coverage = row['witnessAudit'], row['boundary']
        assert audit['allNoncoverageGridHashesExact']
        n = coverage['addedCells']
        assert n == audit['witnessed'] == row['stats']['paidBoundaryCells']
        assert n <= coverage['adjacentToFiniteCenter'] <= coverage['closedUncoveredCells']
        assert audit['waterCenterCells'] + audit['uncertainCenterCells'] + audit['outsideWaterRasterCells'] <= n
        assert len(audit['certificateSha256']) == 64
        assert row['stats']['localCells'] == before['stats']['localCells']
        assert row['stats']['roadOnlyCells'] == before['stats']['roadOnlyCells']
        assert row['stats']['selectedCells'] == before['stats']['selectedCells'] + n
        output = row['output']
        asset = closed['roster'][output['filename']]
        assert all(output[k] == asset[k] for k in ['bytes', 'sha256'])
        assert output['bytes'] == row['stats']['jsonBytes'] <= 3000000
        if minutes == 900:
            assert row['timings'] == before['timings']
            points += len(row['timings'])
        else:
            assert row['timings'] == {}
        witnesses += n
        water += audit['waterCenterCells']
        uncertain += audit['uncertainCenterCells']
        outside += audit['outsideWaterRasterCells']
    assert report['diagnosticPointCases'] == points == 6
    assert report['heldBackingBytes'] == report['afterLoad']['arrayBuffers'] - report['baseline']['arrayBuffers'] <= 162238546
    assert report['afterQueries']['arrayBuffers'] == report['afterLoad']['arrayBuffers']
    assert report['providerRequests'] == 0
    assert report['hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC'] < plan['hostSeconds'] * 1000
    return {**base, 'status': 'four_boundary_pilot_maps_paid_witnesses_and_exact_point_parity_reconciled',
            'boundaryPilotFrames': 4, 'boundaryPilotPointComponentsExact': points,
            'boundaryPilotPaidWitnesses': witnesses, 'addedCellsWithSourceWaterCenters': water,
            'addedCellsWithSourceUncertainCenters': uncertain,
            'addedCellsWithCentersOutsideWaterRaster': outside,
            'boundaryPilotWholeHostMs': report['hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC']}


if __name__ == '__main__':
    print(json.dumps(verify()))

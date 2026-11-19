"""Portable full timing-candidate result, preserving every failed admission gate."""
import json

from verify_tagged_timing_runtime_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('tagged-timing-evaluation')
    assert report['status'] == 'completed_fixed_tagged_timing_full_candidate_screen'
    assert report['candidateModel'] == 'osm-car-tagged-static90-v1'
    assert not report['numericalGatesPassed'] and not report['candidateAdmitted']
    assert report['originalCases'] == len(report['rows']) == 83
    assert len({row['id'] for row in report['rows']}) == 83
    assert report['valhallaCases'] == 35
    assert report['origins'] == report['diagnosticDisplays'] == 21
    assert report['productionDisplays'] == 37 and not report['frozenLocalGridOrMapsReused']
    assert report['validatedInitialChoices'] == 10338
    assert report['waterPacketObservationsCompared'] == 1002
    assert report['unsupportedSourceCases'] == report['providerRequests'] == 0
    assert report['overall']['baseline']['meanAbsoluteMinutes'] == 29.257418754386766
    assert report['overall']['candidate']['meanAbsoluteMinutes'] == 13.910366465863454
    assert report['overall']['candidate']['pairedFinite'] == 83
    assert report['overall']['candidate']['pathSumsReconstructed'] == 0
    assert report['sets']['frontier']['candidate']['meanAbsoluteMinutes'] == 19.39054687500001
    failed = sorted(name for name, passed in report['gates'].items() if not passed)
    assert failed == sorted([
        'originalMean', 'originalP90', 'horizonP90', 'valhallaOriginalMean',
        'valhallaRegionalMean', 'frontierWorstRegression', 'olderWorstRegression',
        'all35OlderShaded',
    ])
    assert report['retainedBackingBytes'] == 159687884 and report['retainedBackingGatePassed']
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers']
    assert report['contextStates'] == 34179 and report['contextDataBackingBytes'] == 1786511
    closed = load(HERE/'tagged-timing-evaluation-closed-v1.json')
    outputs = [phase['diagnostic']['output'] for phase in report['phases']]
    outputs += [production['output'] for phase in report['phases'] for production in phase['productions']]
    assert len(outputs) == 58
    for output in outputs:
        pin = closed['roster'][output['filename']]
        assert pin['bytes'] == output['bytes'] and pin['sha256'] == output['sha256']
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert total == 9356029952
    return {**result, 'status': 'full_fresh_timing_candidate_improved_but_eight_original_gates_fail',
            'all83FiniteAnd58MapsFresh': True,
            'overallMeanAbsoluteMinutes': 13.910366465863454,
            'failedOriginalGates': failed, 'all166PathSumsOrSourceShoreAppGatesPassed': False,
            'uniqueClosedRoots': 319, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

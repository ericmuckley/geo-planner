"""Portable all-case failure and buffer proof; never rerun the candidate."""
import json
from verify_entry_runtime_v1 import stage, verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    access = stage('entry-access')
    assert (access['inputs'], access['supported'], access['totalConnections'], access['maximumConnections']) == (79, 78, 9897, 1835)
    assert access['originalSupportedInputsRetained'] == 78 and access['reusedEndpointCollections'] == 0
    report = stage('entry-evaluation')
    assert not report['numericalGatesPassed'] and not report['candidateAdmitted']
    assert len(report['rows']) == report['originalCases'] == 83 and report['valhallaCases'] == 35
    assert report['overall']['candidate']['pairedFinite'] == 80 and report['overall']['candidate']['unreached'] == 3
    assert report['commonFiniteComparison']['baseline']['meanAbsoluteMinutes'] == 30.0011693272841
    assert abs(report['commonFiniteComparison']['candidate']['meanAbsoluteMinutes']-33.7261875) < 1e-10
    assert report['productionDisplays'] == 36 and report['diagnosticDisplays'] == 20 and report['roadMonotonicComparisons'] == 75
    assert report['providerRequests'] == 0 and report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers'] == 141652517
    comparison = load(HERE/'entry-comparison-v1.json')
    for name, pin in comparison['sourceBindings'].items():
        assert sha(REPO/name) == pin
    assert (comparison['changed'], comparison['faster'], comparison['slower']) == (46, 43, 3)
    assert (comparison['absoluteErrorImproves'], comparison['absoluteErrorWorsens']) == (12, 34)
    assert comparison['fieldBackingMaxBytes'] == 50396646
    assert comparison['fieldPlusDisplayBackingMaxBytes'] == 58944715 < 67108864
    clarified = load(HERE/'access-field-v2-backing-clarification-v1.json')
    assert clarified['originalControlsSha256'] == sha(HERE/'access-field-v2-controls.json')
    assert clarified['resolvedSearchBackingBytes'] == 4*9703850+2*5731903+64*4096 == 50541350
    assert clarified['preClosureSearchBackingBytes'] == 4*9837326+2*5731903+64*4096 == 51075254
    assert clarified['resolvedSearchAndDisplayConservativeBoundBytes'] == 59089419
    assert clarified['preClosureSearchAndDisplayConservativeBoundBytes'] == 59623323
    assert not clarified['codeChanged'] and not clarified['accuracyOrScratchGateChanged']
    return {**result, 'newActualLoaderQueriesOrAccuracyMeasured': True,
            'latestCandidateSame80MaeMinutes': 33.7261875, 'priorCandidateSame80MaeMinutes': 31.371151041666668,
            'latestFieldBackingMaxBytes': 50396646, 'latestFieldAndDisplayBackingMaxBytes': 58944715,
            'allPriorPositiveRoadTotalsRetained': 75, 'latestNumericalGatesPassed': False,
            'newUniqueClosedAllocationBytes': 2840739840, 'uniqueClosedRoots': 107,
            'productionModelChanged': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

"""Portable complete/rejected all83 conditional candidate and saved shading proof."""
import json
import sys
from verify_conditional_attribute_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha

sys.path.insert(0, str(REPO/'scripts'))
from review_osm_water_candidate_v1 import review


def verify():
    result = previous()
    report = stage('conditional-evaluation')
    assert report['status'] == 'completed_fixed_conditional_source_candidate_screen'
    assert report['originalCases'] == 83 and report['valhallaCases'] == 35
    assert report['origins'] == report['diagnosticDisplays'] == 21 and report['productionDisplays'] == 37
    assert report['validatedInitialChoices'] == 10273 and report['waterPacketObservationsCompared'] == 1002
    assert report['roadMonotonicComparisons'] == 81 and report['roadArrivalRegressions'] == []
    assert report['overall']['candidate']['pairedFinite'] == 83 and report['overall']['candidate']['unreached'] == 0
    assert abs(report['overall']['candidate']['meanAbsoluteMinutes'] - 30.43812751004016) < 1e-10
    assert not report['numericalGatesPassed'] and not report['candidateAdmitted']
    assert report['retainedBackingBytes'] == 157446498 <= 162238546
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers'] == 157521418
    displays = [x for phase in report['phases'] for x in [phase['diagnostic'], *phase['productions']]]
    assert all(x['restorationChecked'] for x in displays)
    maximum = max(x['stats']['maximumBackingBufferBytes'] for x in displays)
    assert maximum < 67108864 and report['providerRequests'] == 0
    comparison = load(HERE/'conditional-candidate-comparison-v1.json')
    old = load(HERE/'water-country-evaluation-raw-v1/report.json')
    for key, value in review(old, report).items():
        assert comparison[key] == value, key
    assert comparison['producerSha256'] == sha(REPO/'scripts/review_osm_conditional_candidate_v1.py')
    assert comparison['comparisonHelperSha256'] == sha(REPO/'scripts/review_osm_water_candidate_v1.py')
    for name, pin in comparison['inputs'].items():
        assert sha(REPO/name) == pin
    shading = stage('conditional-shading')
    assert len(shading['rows']) == 83 and len(shading['maps']) == 37
    assert shading['pointDryButCellCenterWet'] == ['salton-city--bombay-beach']
    total = result['newUniqueClosedAllocationBytes']
    for prefix in ('conditional-evaluation', 'conditional-shading'):
        total += load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == 6344495104
    return {**result, 'conditionalCandidateAll83Finite': True,
            'conditionalCandidateAll83MeanAbsoluteMinutes': 30.43812751004016,
            'conditionalCandidateNumericallyRejected': True,
            'conditionalCandidateQueryBackingMaximumBytes': maximum,
            'uniqueClosedRoots': 200, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

"""Portable rejected all83 absent-member candidate and saved-map proof."""
import json
import sys

from verify_absent_entry_access_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha

sys.path.insert(0, str(REPO/'scripts'))
from review_osm_water_candidate_v1 import review
from analyze_osm_conditional_deltas_v1 import changes


def verify():
    result = previous()
    report = stage('absent-entry-evaluation')
    assert report['status'] == 'completed_fixed_absent_entry_candidate_screen'
    assert report['originalCases'] == 83 and report['valhallaCases'] == 35
    assert report['origins'] == report['diagnosticDisplays'] == 21 and report['productionDisplays'] == 37
    assert report['validatedInitialChoices'] == 10336 and report['waterPacketObservationsCompared'] == 1002
    assert report['roadMonotonicComparisons'] == 81 and report['roadArrivalRegressions'] == []
    assert report['overall']['candidate']['pairedFinite'] == 83 and report['overall']['candidate']['unreached'] == 0
    assert abs(report['overall']['candidate']['meanAbsoluteMinutes'] - 36.015481927710844) < 1e-10
    assert abs(report['overall']['baseline']['meanAbsoluteMinutes'] - 29.257418754386766) < 1e-10
    assert not report['numericalGatesPassed'] and not report['candidateAdmitted']
    assert report['gates']['all35OlderShaded'] and report['gates']['all83Finite']
    assert report['retainedBackingBytes'] == 157868131 <= 162238546
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers'] == 157943520
    displays = [x for phase in report['phases'] for x in [phase['diagnostic'], *phase['productions']]]
    assert all(x['restorationChecked'] for x in displays)
    maximum = max(x['stats']['maximumBackingBufferBytes'] for x in displays)
    assert maximum == 59671443 < 67108864 and report['providerRequests'] == 0
    old = load(HERE/'conditional-evaluation-raw-v1/report.json')
    comparison = load(HERE/'absent-entry-candidate-comparison-v1.json')
    for key, value in review(old, report).items():
        assert comparison[key] == value, key
    assert comparison['producerSha256'] == sha(REPO/'scripts/review_osm_absent_entry_candidate_v1.py')
    assert comparison['comparisonHelperSha256'] == sha(REPO/'scripts/review_osm_water_candidate_v1.py')
    deltas = load(HERE/'absent-entry-road-raster-deltas-v1.json')
    for key, value in changes(old, report).items():
        assert deltas[key] == value, key
    assert deltas['changedPointTimes'] == 54 and len(deltas['pointIncreases']) == 5
    assert deltas['casesWithChangedFrame'] == 83 and deltas['roadRegressions'] == []
    for record in (comparison, deltas):
        for name, pin in record['inputs'].items():
            assert sha(REPO/name) == pin
    assert deltas['producerSha256'] == sha(REPO/'scripts/analyze_osm_conditional_deltas_v1.py')
    shading = stage('absent-entry-shading')
    assert len(shading['rows']) == 83 and len(shading['maps']) == 37
    assert shading['pointDryButCellCenterWet'] == []
    assert shading['missedReachable'] == ['missoula-mt-600-outside']
    total = result['newUniqueClosedAllocationBytes']
    for name in ('evaluation', 'shading'):
        total += load(HERE/f'absent-entry-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6811967488
    return {**result, 'absentMemberCandidateAll83Finite': True,
            'absentMemberCandidateAll83MeanAbsoluteMinutes': 36.015481927710844,
            'absentMemberCandidateNumericallyRejected': True,
            'absentMemberCandidateAll35OlderShaded': True,
            'absentMemberCandidateQueryBackingMaximumBytes': maximum,
            'uniqueClosedRoots': 223, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

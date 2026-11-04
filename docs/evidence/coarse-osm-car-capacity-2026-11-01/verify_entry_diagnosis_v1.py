"""Portable all80 paths/source attributes and one fixed sensitivity proof."""
import json
from verify_entry_evaluation_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    paths = stage('entry-paths')
    assert paths['paths'] == paths['newRoadSearches'] == 80 and paths['reusedRoadPaths'] == 0
    assert paths['unavailable'] == 3 and len(paths['phases']) == 20
    candidate = load(HERE/'entry-evaluation-raw-v1/report.json')
    expected = {r['id']: r for r in candidate['rows']}
    for row in paths['rows']:
        if 'unavailable' not in row:
            assert abs(row['sumTicks']/480-expected[row['id']]['candidate']['pointMinutes']) < 1e-10
            assert sum(row['components'].values()) == row['sumTicks']
    output_pins = {p['diagnostic']['output']['sha256'] for p in candidate['phases'] if 'diagnostic' in p}
    assert {p['outputSha256'] for p in paths['phases']} == output_pins
    assert paths['afterLoad']['arrayBuffers'] == paths['afterQueries']['arrayBuffers']
    findings_plan = load(HERE/'entry-path-findings-plan-v1.json')
    for name, pin in findings_plan['bindings'].items():
        assert sha(REPO/name) == pin
    findings = load(HERE/'entry-path-findings-v1.json')
    assert findings['recipeSha256'] == sha(HERE/'entry-path-findings-plan-v1.json')
    assert len(findings['rows']) == 80 and len(findings['unavailable']) == 3
    assert abs(findings['overall']['meanAbsoluteErrorMinutes']-33.7261875) < 1e-10
    assert stage('entry-attributes-controls', True)['controls'] == {'tests': 7, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    attributes = stage('entry-attributes-run', True)
    assert attributes['selectedArcs'] == 44488 and len(attributes['rows']) == 80
    assert attributes['preArcMappingsChecked'] == 9837326 and attributes['retainedArcMappingsChecked'] == 9703850
    for row in attributes['rows']:
        assert row['defaultTicks']+row['taggedTicks'] == sum(g['ticks'] for g in row['groups'].values()) == row['roadTicks']
        assert row['candidateMinutes'] == expected[row['id']]['candidate']['pointMinutes']
    sensitivity_plan = load(HERE/'tagged90-fixed-path-plan-v1.json')
    for name, pin in sensitivity_plan['bindings'].items():
        assert sha(REPO/name) == pin
    sensitivity = load(HERE/'tagged90-fixed-path-screen-v1.json')
    assert sensitivity['recipeSha256'] == sha(HERE/'tagged90-fixed-path-plan-v1.json')
    assert not sensitivity['isCandidateEvaluation'] and not sensitivity['policyActivated']
    assert len(sensitivity['rows']) == 83 and abs(sensitivity['same80']['fixedPathSensitivityMaeMinutes']-29.93985069444445) < 1e-10
    return {**result, 'latestIndependentPathSums': 80, 'latestUnavailableCasesPreserved': 3,
            'latestPathSourceAttributeArcs': 44488, 'sourceAttributeLinuxControls': 7,
            'newUniqueClosedAllocationBytes': 2849484800, 'uniqueClosedRoots': 110,
            'fixedPathSensitivityIsRoutingCandidate': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

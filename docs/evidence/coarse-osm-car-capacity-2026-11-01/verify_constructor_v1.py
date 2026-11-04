"""Portable constructor qualification and preserved captured-preparation stops."""
import json

from verify_cost_math_v1 import verify as cost_math
from verify_preparation_v1 import HERE, closed, load, sha


def verify():
    cost_math()
    root, _ = closed('graph', 'build', 'v1', 0)
    binary = load(root/'result.json')
    assert binary['artifactSha256'] == '96f23e4b81646ec824a30ca1ccc1763664184bc2ae5f3a4e1c42ebcdb1f9d30e'
    assert binary['artifactBytes'] == 2083552
    root, _ = closed('graph', 'controls', 'v1', 0)
    assert load(root/'controls.json') == {'tests': 83, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    root, _ = closed('graph-capture', 'run', 'v1', 2)
    assert load(root/'writer-controls.json')['successful']
    assert load(root/'worker-failure.json')['error'] == 'Captured constructor unchanged references/native points/anchors'
    review = load(HERE/'graph-capture-stop-review-v1.json')
    assert review['failedWorkerRecordSha256'] == sha(root/'worker-failure.json')
    assert (review['sourceDefinedAnchors'], review['oldOnlyAnchors'], review['newOnlyAnchors']) == (46881, 6791, 0)
    assert review['allRemovedAnchorsHaveNoCarControlOrReversal']
    assert review['actualCountryPbfReads'] == review['capturedJsonlConversionsInFailedAttempt'] == review['actualGeneratedCapturedPbfReadsInFailedAttempt'] == 0
    root, _ = closed('graph-capture', 'run', 'v2', 2)
    assert load(root/'writer-controls.json') == {'tests': 6, 'successful': False, 'failures': 0, 'errors': 3, 'skips': 0}
    assert 'coarse_osm_car_payload_v1' in (root/'worker.log').read_text()
    scope = load(HERE/'graph-capture-native-partition-scope-v2.json')
    assert (scope['anchors'], scope['physicalSegments'], scope['preClosureArcs'], scope['postClosureArcs']) == (46881, 52282, 78811, 75137)
    assert scope['allOriginalDirectionalQueries'] == 82 and scope['allOriginalCasesAndNativePointsRetained']
    return {'targetLinuxConstructorControls': 83, 'preservedCapturedPreparationStops': 2,
            'originalSourceDefinedAnchorScope': 46881, 'all6791RemovedValidationCutsHaveFlag0': True,
            'capturedV3State': 'Separate actual terminal/owner records; never replay the existing root.',
            'countryArtifactBuilt': False, 'reads': 'Small closed mirrors and repository code only.'}


if __name__ == '__main__':
    print(json.dumps(verify()))

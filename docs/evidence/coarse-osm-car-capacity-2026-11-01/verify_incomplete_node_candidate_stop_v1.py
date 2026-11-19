"""Verify the preserved wall-clock stop; never execute the failed producer."""
import json

from verify_incomplete_node_runtime_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    record = load(HERE / 'incomplete-node-evaluation-closed-v1.json')
    assert record['terminalRecord'] == 'failure.json' and 'report.json' not in record['roster']
    root = HERE / 'incomplete-node-evaluation-raw-v1'
    for name, pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert sha(root / name) == pin['sha256']
    plan = load(root / 'execution-plan.json')
    for name, pin in plan['bindings'].items():
        if name.startswith(('scripts/', 'routing/', 'docs/')):
            assert sha(REPO / name) == pin
    failure = load(root / 'failure.json')
    assert 'Access candidate host deadline' in failure['error']
    assert failure['hostMs'] >= plan['hostSeconds'] * 1000 == 3600000
    assert len([n for n in record['roster'] if n.endswith('.geojson')]) == 35
    assert len([n for n in record['roster'] if n.startswith('origin-') and n.endswith('.json')]) == 9
    review = load(HERE / 'incomplete-node-candidate-stop-review-v1.json')
    assert review['failureSha256'] == record['roster']['failure.json']['sha256']
    assert review['completedOrigins'] == 9 and review['writtenMapFiles'] == 35
    assert not review['partialMapsReusableAsCandidateInputs'] and not review['sourcePolicyOrAccuracyGatesChanged']
    total = result['newUniqueClosedAllocationBytes'] + record['usage']['conservativeAllocatedBytes']
    assert total == 10107920384
    return {**result, 'status': 'incomplete_node_candidate_deadline_stop_preserved_no_complete_new_score',
            'registeredClosedRoots': 373, 'newUniqueClosedAllocationBytes': total,
            'stoppedRunCompletedOrigins': 9, 'stoppedRunMapFiles': 35,
            'nextFullCandidateScorePending': True,
            'scoreScope': 'The reported 12.614347-minute score belongs to the preceding completed conditional-junction model, not this stopped run.',
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

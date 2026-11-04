"""Portable path diagnosis plus proposed restriction-shape qualification."""
import json
from verify_path_diagnosis_v1 import verify as paths
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = paths()
    seal = load(HERE/'restriction-entry-seal-v1.json')
    for path, pin in seal['records'].items():
        assert sha(REPO/path) == pin
    plan = load(HERE/'restriction-entry-plan-v1.json')
    for path, pin in plan['bindings'].items():
        if not path.startswith('data/'):
            assert sha(REPO/path) == pin
    controls = load(HERE/'restriction-entry-controls-v1.json')
    assert controls['tests'] == 7 and controls['successful'] and controls['prohibitedGeneratedPaths'] == 400
    assert controls['failures'] == controls['skips'] == 0
    inventory = load(HERE/'restriction-entry-inventory-v1.json')
    assert inventory['recipeSha256'] == sha(HERE/'restriction-entry-plan-v1.json')
    assert inventory['sourceRelations'] == 4900
    assert inventory['originalStatuses'] == {'via-node': 4078, 'closed-unsupported': 819, 'non-car': 3}
    assert inventory['candidateShapes'] == len(inventory['entryCandidateShapes']) == 461
    assert len({r['identity'] for r in inventory['entryCandidateShapes']}) == 461
    assert inventory['unchangedFallbackRelations'] == 358
    assert inventory['sourcePbfReads'] == inventory['modelQueries'] == 0 and not inventory['policyActivated']
    return {**result, 'conservativeRestrictionControls': 7, 'candidateRelationShapes': 461,
            'actualEntryArcResolutionOrRoutingTested': False, 'modelPolicyChanged': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

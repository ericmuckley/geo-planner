"""Portable complete captured absent-member inventory, source paths and TS equality."""
import json
from verify_terminal_alternatives_v3 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    inventory = stage('absent-entry-inventory')
    assert (inventory['relationsChecked'], inventory['waysChecked'], inventory['completePreRelationClosureArcs']) == (4900, 28995, 79118)
    assert inventory['inactiveNarrowStaticNoTurns'] == 165 and len(inventory['inactive']) == 165
    assert len(inventory['newlyOpenedPresentWayIds']) == 271
    assert inventory['previousActiveArcs'] == 76722 and inventory['newActiveArcs'] == 77274 and inventory['existingEntryPairsExact']
    assert inventory['routingQueries'] == inventory['providerRequests'] == inventory['sourcePbfReads'] == 0
    stopped = load(HERE/'absent-entry-preimport-stop-v1.json')
    assert stopped['outputRootAbsentAtStop'] and stopped['inputBindingOrSourceFactReads'] == 0
    report = stage('absent-entry-graph-capture')
    assert report['allOriginalArraysReproduced'] and report['allEntryArraysReproduced'] and report['allConditionalArraysReproduced']
    assert report['allConditionalOptimaReproduced'] and report['allBaselineAllowedTransitionsPreserved']
    assert (report['candidateFinite'], report['candidateStillUnreachable'], report['previousFailuresRecovered'], report['previousFiniteImproved']) == (81, 1, 4, 10)
    assert report['candidateArcs'] == 77274 and report['candidateForbiddenPairs'] == 2694
    assert report['newlyAvailablePostClosureArcs'] == 552 and report['addedPreClosureArcs'] == 0
    assert report['inactiveNarrowStaticNoTurns'] == 165 and len(report['rows']) == 82
    assert sum(r['sourceReplayed'] for r in report['rows']) == 81
    assert report['providerRequests'] == report['sourcePbfReads'] == report['applicationDbReads'] == 0
    runtime = load(HERE/'absent-entry-graph-runtime-v1.json')
    plan = load(HERE/'absent-entry-graph-runtime-plan-v1.json')
    assert runtime['recipeSha256'] == sha(HERE/'absent-entry-graph-runtime-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if name.startswith(('scripts/', 'docs/')):
            assert sha(REPO/name) == pin
    assert runtime['finite'] == 81 and runtime['unreachable'] == 1 and len(runtime['checks']) == 82
    assert [c['ticks'] for c in runtime['checks']] == [r['candidateTicks'] for r in report['rows']]
    assert not runtime['nationalOrAppQualified'] and not report['appActivated']
    total = result['newUniqueClosedAllocationBytes']
    for prefix in ('absent-entry-inventory', 'absent-entry-graph-capture'):
        total += load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == 6363758592
    return {**result, 'absentMemberCapturedFinite': 81, 'absentMemberCapturedFailuresRecovered': 4,
            'absentMemberAll81FinitePathsSourceReplayed': True, 'absentMemberAll82TypeScriptCostsExact': True,
            'uniqueClosedRoots': 209, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

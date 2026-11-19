"""Portable bounded turn-context graph/optimum/raw-source witness proof."""
import json

from verify_absent_entry_diagnosis_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('context-turns-capture')
    assert report['status'] == 'captured_static_via_way_context_and_source_replay_complete'
    assert report['originalCases'] == 82 and len(report['rows']) == 82
    assert report['baselineFinite'] == report['candidateFinite'] == 81
    assert report['candidateStillUnreachable'] == 1 and report['previousFailuresRecovered'] == 0
    assert report['previousFiniteImproved'] == 1
    assert report['allAbsentMemberArraysAndFixturesReproduced'] and report['all82BaselineOptimaReproduced']
    assert report['allBaselineAllowedTransitionsPreserved'] and report['allowedOrdinaryTransitionsChecked'] == 145620
    assert report['preArcs'] == 79118 and report['activeArcs'] == 77274 and report['addedOrRepricedArcs'] == 0
    assert report['contextRules'] == 295 and report['contextPrefixGroups'] == 292
    assert report['maximumPossibleCapturedSearchStates'] == 77803
    assert report['supportedTurnPairsRetained'] == 2463 and report['previousEntryPairs'] == 276
    assert report['unchangedClosedWays'] == 618 and report['unchangedFallbackRelations'] == 359
    assert report['unchangedInactiveMissingMemberRules'] == 165
    assert sum(row['sourceReplayed'] for row in report['rows']) == 81
    assert all(row['candidateTicks'] is not None and row['candidateTicks'] <= row['baselineTicks']
               for row in report['rows'] if row['baselineTicks'] is not None)
    assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['providerRequests'] == report['applicationDbReads'] == 0
    assert not report['nationalPolicyChanged'] and not report['runtimeArtifactBuilt'] and not report['appActivated']
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'context-turns-capture-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6825242624
    return {**result, 'contextTurnCapturedAll82OptimaReproduced': True,
            'contextTurnCapturedAll81FinitePathsSourceReplayed': True,
            'contextTurnCapturedPreviousFiniteImproved': 1,
            'contextTurnCapturedExtraStateUpperBound': 529,
            'uniqueClosedRoots': 229, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

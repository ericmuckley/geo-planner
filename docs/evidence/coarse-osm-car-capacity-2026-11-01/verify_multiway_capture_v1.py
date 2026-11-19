"""Portable saved metadata/multi-via captured proof, without producer replay."""
import json

from verify_restriction_shapes_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    fallback=stage('restriction-fallbacks',False)
    assert fallback['status']=='saved_static_fallback_signatures_complete'
    assert len(fallback['sources'][0]['otherStaticFallbackSignatures'])==469
    assert len(fallback['sources'][1]['otherStaticFallbackSignatures'])==42
    report=stage('multiway-entry-capture',False)
    assert report['status']=='captured_multi_via_entry_and_independent_source_replay_complete'
    assert report['originalCases']==82 and report['baselineFinite']==report['candidateFinite']==81
    assert report['candidateStillUnreachable']==1 and report['previousFiniteImproved']==1
    assert report['oldPhysicalArcs']==77274 and report['newPhysicalArcs']==77429
    assert report['oldPhysicalArcsAndPricesExact'] and report['allOldAllowedHistoryPathsPreserved']
    assert report['oldAllowedPhysicalTransitionsChecked']==145847
    assert report['oldContextRulesUnchanged']==295
    assert report['multiViaRulesConverted']==34 and report['multiViaInactiveMissingMemberRules']==17
    assert report['activeMultiViaEntryPairs']==report['completeMultiViaPreEntryPairs']==17
    assert report['remainingClosedWays']==506 and report['remainingFallbackRelations']==325
    assert report['sourcePbfReads']==report['nativeConstructorExecutions']==report['providerRequests']==report['applicationDbReads']==0
    assert len(report['rows'])==82
    assert all(r['sourceReplayed']==(r['candidateTicks'] is not None) for r in report['rows'])
    assert all(r['baselineTicks'] is None or r['candidateTicks'] <= r['baselineTicks'] for r in report['rows'])
    total=result['newUniqueClosedAllocationBytes']
    for name in ('restriction-fallbacks','multiway-entry-capture'):
        total+=load(HERE/f'{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==6890295296
    return {**result,'multiViaCapturedAll82OldOptimaReproduced':True,
            'multiViaCapturedAll81FinitePathsSourceReplayed':True,
            'multiViaCapturedRestoredPhysicalArcs':155,
            'uniqueClosedRoots':239,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

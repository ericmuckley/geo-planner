"""Portable complete captured packed/paid/history cost consumer proof."""
import json
from verify_tagged_timing_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('tagged-timing-routing-capture')
    assert report['status']=='complete_captured_tagged_timing_packed_history_paid_routing_source_replay_passed'
    assert (report['originalCases'],report['baselineFinite'],report['candidateFinite'],report['candidateUnavailable'])==(82,81,81,1)
    assert report['costsIncreased']==74 and report['costsUnchanged']==7
    assert report['unchangedPhysicalPackedFields']==8 and report['physicalArcs']==77459 and report['preArcsChecked']==79148
    assert report['singleViaContextRules']==295 and report['closedWays']==506 and report['nodeFlagsChanged']==0
    assert report['allOldOptimaReproduced'] and report['allNewFinitePathsSourceReplayed'] and report['allPaidEndpointDomainsAndNondecreasingPricesChecked']
    assert report['routingQueries']==164 and report['sourcePbfReads']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['originalLegalSpeedSourceModified'] and not report['countryCostOrRuntimeBuilt'] and not report['accuracyOrAppAccepted']
    assert len(report['rows'])==82
    for row in report['rows']:
        assert (row['baselineTicks'] is None)==(row['candidateTicks'] is None)
        assert row['sourceReplayed']==(row['candidateTicks'] is not None)
        if row['candidateTicks'] is not None:assert row['candidateTicks']>=row['baselineTicks']
    log=(HERE/'tagged-timing-routing-controls-v1.txt').read_text();assert 'Ran 72 tests' in log and 'OK' in log and 'skipped' not in log
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'tagged-timing-routing-capture-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==8391122944
    return {**result,'status':'complete_captured_tagged_timing_packed_paid_history_routing_passed',
            'capturedTimingAll82QueriesRetained':True,'capturedTimingAll81FinitePathsSourceReplayed':True,
            'uniqueClosedRoots':302,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

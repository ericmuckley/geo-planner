"""Portable complete national multi-via entry metadata/source-join proof."""
import json

from verify_multiway_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    assert stage('multiway-country-controls',True)['controls']==dict(tests=46,successful=True,failures=0,errors=0,skips=0)
    report=stage('multiway-country-run',True)
    assert report['status']=='complete_multi_via_country_metadata_and_independent_join_audit_passed'
    assert (report['waysChecked'],report['preArcsCheckedTwice'],report['sourceUnsupportedRelationsChecked'])==(4227238,9878318,70376)
    assert report['oldSingleViaDecisionsRetained']==46533 and report['oldClosureUnionReproduced']
    assert (report['oldEntryPairsRetained'],report['newMultiEntryPairs'],report['combinedEntryPairs'])==(22964,2599,25327)
    assert (report['multiViaRules'],report['resolvedMultiViaRules'],report['inactiveMissingMemberMultiRules'],report['noJoinMultiFallbackRules'])==(3569,2623,932,14)
    assert (report['oldClosureIds'],report['newClosureIds'])==(40259,29657)
    assert (report['oldPostArcs'],report['proposedPostArcs'])==(9807359,9822101)
    assert report['oldAllowedPathsPreservedByClosureSubsetAndNewEntryWaysPreviouslyClosed']
    assert not report['sourceCostsFlagsOrPreArcsChanged']
    assert report['selectedPreArcRecordsPerAudit']==12526
    assert report['sourcePbfReads']==report['coordinatesRead']==report['routingQueries']==0
    total=result['newUniqueClosedAllocationBytes']
    for name in ('controls','run'):
        total+=load(HERE/f'multiway-country-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==6893383680
    return {**result,'multiViaNationalMetadataSourceJoinsAudited':True,
            'multiViaNationalProposedRestoredArcs':14742,
            'uniqueClosedRoots':241,'newUniqueClosedAllocationBytes':total,
            'multiViaNationalGraphOrAccuracyQualified':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

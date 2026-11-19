"""Portable new-ID context/static-ban records and independently decoded wire proof."""
import json

from verify_multiway_storage_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    assert stage('multiway-context-controls',True)['controls']==dict(tests=22,successful=True,failures=0,errors=0,skips=0)
    report=stage('multiway-context-run',True)
    assert report['status']=='multiway_static_bans_and_single_via_context_records_source_audited'
    assert (report['contextStates'],report['prohibitedExitArcRecords'],report['activeTriggerPairs'])==(34101,22582,22567)
    assert report['contextPrefixGroups']==22946 and report['retainedArcsMapped']==9822101
    assert (report['supportedSourceTurnPairs'],report['retainedStaticForbiddenPairs'],report['activeMultiEntryPairs'])==(235151,237620,2541)
    assert report['multiPreEntryPairs']==2599 and report['multiEntryPairsDroppedByOtherClosures']==58
    assert report['independentMultiEntryCsrMappingsChecked']==4998
    assert report['staticForbiddenBytes']==1425720 and report['contextRuntimeBackingBytes']==1784491
    assert report['finalForbiddenUnionPairsChecked']==257888
    proof=report['independentAudit']
    assert (proof['allContextStatesSourceMapped'],proof['allProhibitedExitArcRecordsChecked'],proof['allActiveEntryTriggerPairsChecked'])==(34101,22582,22567)
    assert proof['allRetainedStaticForbiddenPairsChecked']==237620 and proof['oldFinalTurnUnionExact']
    pack=stage('multiway-context-wire',False);audit=stage('multiway-context-wire-audit',False)
    assert pack['coreRawBytes']==129483002 and pack['contextRawBytes']==1784491
    assert audit['status']=='independent_complete_multiway_context_wire_bytes_passed'
    assert audit['copiedCoreFieldsByteIdentical']==12
    assert audit['replacementCoreBytesIndependentlyDecoded']==1425720
    assert audit['contextFieldsIndependentlyDecoded']==6 and audit['contextBytesIndependentlyCompared']==1784491
    assert audit['combinedCoreAndContextCompressedBytes']==46720807
    total=result['newUniqueClosedAllocationBytes']
    for name in ('multiway-context-controls','multiway-context-run','multiway-context-wire','multiway-context-wire-audit'):
        total+=load(HERE/f'{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7366422528
    return {**result,'multiViaNew34101HistoryStatesAndStaticBansSourceAudited':True,
            'multiViaNewContextWireAllChangedBytesIndependentlyDecoded':True,
            'uniqueClosedRoots':254,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

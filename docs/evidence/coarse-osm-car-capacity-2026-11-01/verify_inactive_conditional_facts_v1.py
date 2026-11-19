"""Current fixed-profile inactive-turn source facts, no large inputs or queries."""
import hashlib
import json
import struct

from verify_current_way_exclusions_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();plan=load(HERE/'inactive-conditional-inventory-plan-v1.json')
    stages={
        'metadata':('conditional-node-turns-inventory','candidate-metadata.json.gz'),
        'sourcePorts':('conditional-node-ports-run','source-port-descriptors.json.gz'),
        'oldClosures':('source-gap-closures-v2','closure-evidence.json.gz'),
        'currentExclusions':('current-way-exclusions','current-exclusions.json.gz'),
        'currentClosureIds':('conditional-node-facts-v2-run','cost-facts/closures-0000.bin')}
    data={plan[key]:load(HERE/(prefix+'-closed-v1.json'))['roster'][file]['sha256']for key,(prefix,file)in stages.items()}
    for name,pin in plan['bindings'].items():
        assert (data.get(name)==pin if name.startswith('data/')else sha(REPO/name)==pin),name
    projected=load(HERE/'inactive-conditional-inventory-v1.json')
    assert projected['recipeSha256']==sha(HERE/'inactive-conditional-inventory-plan-v1.json')
    assert (projected['metadataRules'],projected['representedRules'],projected['inactiveRules'],projected['fallbackRules'])==(7480,1331,6149,0)
    assert (projected['currentGlobalClosedWays'],projected['proposedGlobalClosedWays'],projected['proposedGlobalReopenedWays'],projected['proposedBaseEligibleMajorReopenedWays'])==(27421,16968,10453,4175)
    assert projected['allIndependentUnconvertedContributorUnionsExact'] and not projected['nativeCompilerExecuted'] and not projected['sourcePolicyActivated']
    assert projected['sourcePbfReads']==projected['modelQueries']==projected['providerRequests']==0
    controls=stage('inactive-conditional-facts-controls',True)
    assert controls['controls']==dict(tests=78,successful=True,failures=0,errors=0,skips=0)
    note=load(HERE/'inactive-conditional-controls-count-note-v1.json')
    assert note['scopeTextForecast']==79 and note['requiredByUsedCode']==note['actualTests']==78 and not note['admissionOrAccuracyGateChanged']
    captured=stage('inactive-conditional-facts-capture',True)
    assert captured['convertedRelations']==209 and captured['inactiveRelations']==109 and captured['representedConditionalRules']==100
    assert captured['newFinalClosedWays']==154 and captured['inactiveOutsideLocalMetadata']==7271
    assert captured['independentNegativeAndPositivePortAudit']['allCandidateSourceDescriptorsIndependentlyReplayed']==7480
    assert captured['compiler']['physicalFieldsCopiedExactly']
    assert captured['compiler']['independentCompleteSourceAndEntryAudit']['baseFields']['sourceTurnRecordsChecked']==4178
    national=stage('inactive-conditional-facts-run',True)
    assert national['allOriginalUnsupportedRelations']==70376 and national['convertedRelations']==7480
    assert national['inactiveRelations']==6149 and national['representedConditionalRules']==1331 and national['inactiveOutsideLocalMetadata']==0
    assert national['originalFinalClosedWays']==29657 and national['newFinalClosedWays']==16968
    assert national['sharedClosedWaysRetained']==440 and national['everyIndependentUnconvertedContributorRetained']
    ports=national['independentNegativeAndPositivePortAudit']
    assert ports['allCandidateSourceDescriptorsIndependentlyReplayed']==7480 and ports['secondSourcePreArcsChecked']==9882872
    assert ports['representedRules']==1331 and ports['inactiveRules']==6149 and ports['fallbackRules']==0
    assert national['turnAudit']==dict(oldSourceTurnsByteExact=409178,newAllStateJunctionBans=1331,allSourceTurnsIndependentlyCompared=410509)
    assert national['newFinalPostArcs']==9853365 and national['allPreArcRetentionMappingsCounted']==9882872
    assert national['nativeFlagAudit']['allVertexFlagsIndependentlyCompared']==5731903
    assert national['nativeFlagAudit']['changedVertices']==5714 and national['allOtherPhysicalSourceFactsUnchanged']
    old=load(HERE/'conditional-node-facts-v2-run-raw-v1/report.json')
    for name in ('turns','flags'):
        assert national['assets']['cost-facts/'+name+'-0000.bin']==old['assets']['cost-facts/'+name+'-0000.bin']
    proposed=projected['proposedGlobalClosureIds'];assert len(proposed)==16968 and proposed==sorted(set(proposed),key=int)
    raw=b''.join(struct.pack('<Q',int(i))for i in proposed)
    artifact=national['assets']['cost-facts/closures-0000.bin']
    assert artifact==dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    for report in (captured,national):
        assert report['sourcePbfReads']==report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==report['applicationDbReads']==0
        assert not report['newTimingOrAccuracyQualified'] and not report['appActivated']
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('inactive-conditional-facts-controls','inactive-conditional-facts-capture','inactive-conditional-facts-run'):
        total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==10210148352 and 64500000000+total+104857600<72*1024**3
    return {**result,'status':'inactive_conditional_source_facts_and_captured_native_oracle_qualified',
            'registeredClosedRoots':386,'newUniqueClosedAllocationBytes':total,
            'inactiveConditionalRulesSourceQualified':6149,'representedConditionalBansPreserved':1331,
            'currentNewGraphArcsBeforeConstruction':9853365,'newFullCandidateScorePending':True,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

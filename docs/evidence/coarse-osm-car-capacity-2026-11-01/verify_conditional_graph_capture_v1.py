"""Portable captured conditional graph/runtime proof; never rerun producers."""
import json
from verify_conditional_native_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();controls=load(HERE/'conditional-graph-controls-v1.json')
    assert controls['tests']==20 and controls['successful'] and controls['failures']==controls['errors']==controls['skips']==0
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items():
        if not name.startswith('data/'):assert sha(REPO/name)==pin,name
    report=stage('conditional-graph-capture')
    assert report['status']=='captured_conditional_speed_graph_experiment_complete'
    assert report['allOriginalArraysReproduced'] and report['allEntryArraysReproduced'] and report['allEntryOptimaReproduced']
    assert report['allBaselineAllowedTransitionsPreserved']
    assert report['originalCases']==82 and report['originalUnreachable']==14 and report['entryBaselineFinite']==74 and report['entryBaselineUnreachable']==8
    assert len(report['changedWays'])==108 and report['addedPreClosureArcs']==307
    assert [report[k] for k in ('candidateFinite','previousFailuresRecovered','previousFiniteImproved','candidateStillUnreachable')]==[77,3,1,5]
    assert [report[k] for k in ('convertedRelations','fallbackRelations','activeEntryPairs','candidateArcs','candidateForbiddenPairs','payloadBytes')]==[295,524,271,76722,2673,1038945]
    assert not report['nationalPolicyChanged'] and not report['appActivated']
    for key in ('sourcePbfReads','sourceConstructorExecutions','providerRequests','applicationDbReads'):assert report[key]==0
    runtime=load(HERE/'conditional-graph-runtime-v1.json');plan=load(HERE/'conditional-graph-runtime-plan-v1.json')
    assert runtime['recipeSha256']==sha(HERE/'conditional-graph-runtime-plan-v1.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin
    assert len(runtime['checks'])==len(report['rows'])==82 and runtime['finite']==77 and runtime['unreachable']==5
    for row,check in zip(report['rows'],runtime['checks']):
        assert row['index']==check['index'] and row['candidateTicks']==check['ticks']
        if row['baselineTicks'] is not None:assert row['candidateTicks'] is not None and row['candidateTicks']<=row['baselineTicks']
        assert row['sourceReplayed']==(row['candidateTicks'] is not None)
    allocation=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-graph-capture-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert allocation==5395804160
    return {**result,'conditionalGraphControls':20,'conditionalGraphIndependentQueriesExact':82,
            'conditionalGraphFiniteSourceReplayed':77,'conditionalGraphPreviousFailuresRecovered':3,
            'conditionalGraphPreviousFiniteImproved':1,'conditionalGraphRemainingFailures':5,
            'uniqueClosedRoots':173,'newUniqueClosedAllocationBytes':allocation,'nationalPolicyOrEtaAccepted':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

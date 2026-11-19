"""Completed corrected candidate and source closure receipts; no ignored assets or queries."""
import json
import math

from verify_passable_node_runtime_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous()
    ways=stage('source-gap-way-tags')
    assert ways['allSelectedSourceWays']==ways['sourceCacheWayQueries']==52743
    assert ways['rawWaysKnown']==616 and ways['rawWaysUnknown']==52127
    assert ways['knownSelectionClassCounts']=={'base-ineligible':249,'base-eligible-fallback-closed':367}
    stopped=load(HERE/'source-gap-closures-closed-v1.json')
    assert stopped['terminalRecord']=='failure.json'
    for name,pin in stopped['roster'].items():
        if not pin['ignoredLargeAsset']:assert sha(HERE/'source-gap-closures-raw-v1'/name)==pin['sha256']
    review=load(HERE/'source-gap-closures-v1-stop-review.json')
    assert review['cachedAllFinalClosedWays']==370 and review['cachedBaseEligibleFinalClosedWays']==367
    assert review['cachedBaseIneligibleAlsoFinalClosedWays']==3 and review['full29657ClosureUnionCheckPassedBeforeSubgroupGuard']
    assert not review['sourceOrModelChanged'] and not review['evidenceOutputCreated']
    closures=stage('source-gap-closures-v2')
    assert closures['allRawUnsupportedRelations']==70376 and closures['allCurrentSingleDecisions']==46533
    assert closures['allCurrentMultiDecisions']==3569 and closures['allFinalClosedWaysAttributed']==29657
    assert closures['cachedClosedWays']==370 and closures['cachedBaseEligibleClosedWays']==367
    assert closures['uniqueWayCategoriesCanOverlap'] and not closures['sourcePermissionsOrPricesChanged']
    report=stage('passable-node-evaluation')
    assert report['recipeSha256']==sha(HERE/'passable-node-candidate-plan-v1.json')
    rows=report['rows'];assert len(rows)==report['originalCases']==83 and report['valhallaCases']==35
    old=load(HERE/'tagged-timing-evaluation-raw-v1/report.json');prior={r['id']:r for r in old['rows']}
    for row in rows:
        for key in ('set','origin','destination','budgetMinutes','referenceMinutes','valhallaMinutes','baseline'):
            assert row[key]==prior[row['id']][key],(row['id'],key)
        assert row['candidate']['pointMinutes'] is not None
    for name,selected in [('overall',rows),('original',[r for r in rows if r['set']=='original']),('regional',[r for r in rows if r['set']=='regional']),('frontier',[r for r in rows if r['set']=='frontier'])]:
        stats=report['overall'] if name=='overall' else report['sets'][name]
        for model in ('baseline','candidate'):
            mean=math.fsum(abs(r[model]['pointMinutes']-r['referenceMinutes']) for r in selected)/len(selected)
            assert math.isclose(mean,stats[model]['meanAbsoluteMinutes'],rel_tol=0,abs_tol=1e-10)
    assert math.isclose(report['overall']['candidate']['meanAbsoluteMinutes'],12.614347389558226,abs_tol=1e-12)
    assert not report['numericalGatesPassed'] and not report['candidateAdmitted']
    failed=sorted(key for key,value in report['gates'].items() if not value)
    assert failed==sorted(['originalMean','originalP90','valhallaOriginalMean','valhallaRegionalMean','frontierWorstRegression','olderWorstRegression','all35OlderShaded'])
    assert report['gates']['horizonP90'] and not report['frozenLocalGridOrMapsReused']
    assert report['everyEndpointRecomputedAndByteIdenticalToPriorTiming']
    assert report['productionDisplays']==37 and report['diagnosticDisplays']==21 and report['origins']==21
    assert report['roadArrivalsCompared']==82 and not report['roadArrivalTimeIncreases']
    assert report['retainedBackingBytes']==159687884 and report['retainedBackingGatePassed']
    assert report['afterLoad']['arrayBuffers']==report['afterQueries']['arrayBuffers']
    assert report['providerRequests']==0 and report['validatedInitialChoices']==10338
    closed=load(HERE/'passable-node-evaluation-closed-v1.json');maps=[]
    for phase in report['phases']:
        assert phase['diagnostic']['restorationChecked']
        for output in [phase['diagnostic']['output'],*[p['output'] for p in phase['productions']]]:
            assert all(closed['roster'][output['filename']][key]==output[key] for key in ('bytes','sha256'))
            maps.append(output['filename'])
    assert len(maps)==len(set(maps))==58
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('source-gap-way-tags','source-gap-closures','source-gap-closures-v2','passable-node-evaluation'):
        total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==9483894784
    return {'status':'corrected_full_candidate_complete_original_gates_retained',
            'registeredClosedRoots':344,'newUniqueClosedAllocationBytes':total,
            'all83Finite':True,'all58MapsFresh':True,'meanAbsoluteMinutes':12.614347389558226,
            'v9MeanAbsoluteMinutes':29.257418754386766,'previousTimingCandidateMeanAbsoluteMinutes':13.910366465863454,
            'failedOriginalGates':failed,'allFinalWayClosuresAttributed':29657,
            'legacyRootErrorFields':'Unused inherited benchmark properties; current statistics recompute from nested candidate.pointMinutes.',
            'ignoredAssetsReadOrProducerExecutions':0,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

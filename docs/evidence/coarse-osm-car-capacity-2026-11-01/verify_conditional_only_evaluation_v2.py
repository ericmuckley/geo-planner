"""Recompute all original numerical gates from the completed new candidate rows."""
import json
import math

from verify_conditional_only_runtime_v1 import verify as previous
from verify_conditional_node_candidate_v1 import summary, recompute_gates
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result=previous();report=stage('conditional-only-evaluation-v2')
    assert report['recipeSha256']==sha(HERE/'conditional-only-evaluation-plan-v2.json')
    assert report['candidateModel']=='osm-car-tagged-static90-conditional-only-v1'
    rows=report['rows'];old=load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    prior={r['id']:r for r in old['rows']}
    assert len(rows)==report['originalCases']==83 and report['valhallaCases']==35
    assert len({r['id']for r in rows})==83 and set(prior)=={r['id']for r in rows}
    for row in rows:
        for key in ('set','origin','destination','budgetMinutes','referenceMinutes','valhallaMinutes','baseline'):
            assert row[key]==prior[row['id']][key],(row['id'],key)
        prediction=row['candidate']['pointMinutes'];baseline=row['baseline']['pointMinutes']
        expected=None if prediction is None or baseline is None else abs(prediction-row['referenceMinutes'])-abs(baseline-row['referenceMinutes'])
        assert row['absoluteErrorChangeMinutes'] is None if expected is None else math.isclose(row['absoluteErrorChangeMinutes'],expected,rel_tol=0,abs_tol=1e-10)
        shaded=row['candidate']['predictedReachable']
        classification=('ambiguous'if abs(row['referenceMinutes']-row['budgetMinutes'])<=5 else 'correct'if shaded==(row['referenceMinutes']<row['budgetMinutes'])else 'falseReachable'if shaded else 'missedReachable')
        assert row['candidate']['classification']==classification
    for name,selected in [('overall',rows),*[(s,[r for r in rows if r['set']==s])for s in ('original','regional','frontier')]]:
        recorded=report['overall']if name=='overall'else report['sets'][name]
        for model in ('baseline','candidate'):
            for metric,value in summary(selected,model).items():
                assert recorded[model][metric] is None if value is None else math.isclose(value,recorded[model][metric],rel_tol=0,abs_tol=1e-10)
    gates=recompute_gates(rows)
    assert gates==report['gates'] and all(gates.values())==report['numericalGatesPassed']
    assert not report['candidateAdmitted'] and not report['frozenLocalGridOrMapsReused']
    assert report['everyEndpointRecomputed'] and report['validatedInitialChoices']==10422
    assert report['resumedCompletedOrigins']==['origin-01','origin-02','origin-03'] and report['resumedMaps']==12
    checkpoint=load(HERE/'conditional-only-evaluation-closed-v1.json')
    assert checkpoint['terminalRecord']=='failure.json'
    prior_stop=load(HERE/'conditional-only-evaluation-raw-v1/failure.json')
    assert prior_stop['status']=='interrupted_without_terminal_report'
    for index, stem in enumerate(report['resumedCompletedOrigins']):
        before=load(HERE/'conditional-only-evaluation-raw-v1'/f'{stem}.json')
        after=report['phases'][index]
        assert all(before[key]==after[key] for key in ('origin','initialChoices','accessInput','diagnostic','productions'))
        for output in [before['diagnostic']['output'], *[v['output'] for v in before['productions']]]:
            assert checkpoint['roster'][output['filename']]['sha256']==output['sha256']
    assert report['productionDisplays']==37 and report['diagnosticDisplays']==report['origins']==21
    assert report['contextStates']==34256 and report['contextDataBackingBytes']==1790787
    assert report['providerRequests']==0 and report['waterPacketObservationsCompared']==1002
    assert report['afterLoad']['arrayBuffers']==report['afterQueries']['arrayBuffers']
    assert report['retainedBackingGatePassed']==(report['retainedBackingBytes']<=162238546)
    prior_road={key:timing['roadTicks']for phase in old['phases']for key,timing in phase['diagnostic']['timings'].items()}
    increases=[];compared=0
    record=load(HERE/'conditional-only-evaluation-v2-closed-v1.json');maps=[]
    for phase in report['phases']:
        assert phase['diagnostic']['restorationChecked']
        for key,timing in phase['diagnostic']['timings'].items():
            before=prior_road[key];now=timing['roadTicks']
            if before is not None:
                compared+=1
                if now is None or now>before:increases.append((key,before,now))
        for output in [phase['diagnostic']['output'],*[p['output']for p in phase['productions']]]:
            assert all(record['roster'][output['filename']][k]==output[k]for k in ('bytes','sha256'))
            maps.append(output['filename'])
    assert compared==report['roadArrivalsCompared']
    assert sorted(increases)==sorted((r['id'],r['previous'],r['current'])for r in report['roadArrivalTimeIncreases'])
    assert len(maps)==len(set(maps))==58
    total=result['newUniqueClosedAllocationBytes']+checkpoint['usage']['conservativeAllocatedBytes']+record['usage']['conservativeAllocatedBytes']
    assert 64500000000+total+104857600<72*1024**3
    return {'status':'mandatory_turn_full_candidate_original_gates_independently_recomputed',
            'registeredClosedRoots':436,'newUniqueClosedAllocationBytes':total,
            'meanAbsoluteMinutes':report['overall']['candidate']['meanAbsoluteMinutes'],
            'previousCompleteCandidateMeanAbsoluteMinutes':old['overall']['candidate']['meanAbsoluteMinutes'],
            'v9MeanAbsoluteMinutes':report['overall']['baseline']['meanAbsoluteMinutes'],
            'failedOriginalGates':sorted(k for k,v in gates.items()if not v),
            'all83Finite':gates['all83Finite'],'all58CandidateMapsVerified':True,'resumedMaps':12,
            'retainedBackingBytes':report['retainedBackingBytes'],'retainedBackingComponentGatePassed':report['retainedBackingGatePassed'],
            'roadArrivalTimeIncreasesRetained':len(increases),
            'pointEstimatesChangedVsPrior':sum(r['candidate']['pointMinutes']!=prior[r['id']]['candidate']['pointMinutes']for r in rows),
            'classifications':{label:sum(r['candidate']['classification']==label for r in rows)for label in ('correct','falseReachable','missedReachable','ambiguous')},
            'newFullCandidateScorePending':False,
            'ignoredAssetsReadOrProducerExecutions':0,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

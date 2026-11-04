"""Portable numerical rejection/source-buffer proof; no country query replay."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_origin_access_v3 import verify as access


def verify():
    access()
    control=load(HERE/'access-field-display-controls-v1.json')
    assert control['tests']==12 and control['successful'] and control['failures']==control['skips']==0
    assert control['generatedOriginalFieldMinComparisons']==4800
    assert control['consoleSha256']==sha(HERE/'access-field-display-controls-v1.txt')
    assert control['fieldDesignSha256']==sha(HERE/'access-road-field-design-v1.json')
    assert control['evaluationDesignSha256']==sha(HERE/'access-evaluation-design-v1.json')
    for name,pin in control['codeBindings'].items():assert sha(REPO/name)==pin,name
    root=host_closed('access-candidate-evaluation');report=load(root/'report.json');plan=load(root/'execution-plan.json')
    assert report['status']=='completed_fixed_initial_access_candidate_screen' and not report['numericalGatesPassed'] and not report['candidateAdmitted']
    assert (report['originalCases'],report['valhallaCases'],report['origins'])==(83,35,21)
    assert (report['diagnosticDisplays'],report['productionDisplays'],report['unsupportedSourceCases'],report['roadMonotonicComparisons'])==(20,36,2,71)
    old=load(REPO/plan['baseline']);rows=report['rows'];assert len(rows)==83
    assert sorted(row['id'] for row in rows)==sorted(row['id'] for row in old['rows'])
    for row in rows:
        original=next(value for value in old['rows'] if value['id']==row['id'])
        assert row['baseline']==original['candidate'] and row['referenceMinutes']==original['referenceMinutes'] and row['valhallaMinutes']==original['valhallaMinutes']
        assert row['candidate']['pathComponents'] is None
        if row['estimateFailure'] is not None:assert row['candidate']['pointMinutes'] is None and not row['candidate']['predictedReachable']
    assert report['overall']['candidate']['pairedFinite']==80 and sum(row['candidate']['pointMinutes'] is None for row in rows)==3
    assert abs(report['overall']['candidate']['meanAbsoluteMinutes']-31.371151041666668)<1e-10
    common=report['commonFiniteComparison'];assert common['cases']==80
    assert abs(common['baseline']['meanAbsoluteMinutes']-30.0011693272841)<1e-10
    assert not report['gates']['overallMean'] and not report['gates']['all83Finite'] and not report['gates']['all35OlderShaded']
    max_backing=0;baseline=report['afterLoad']['arrayBuffers']
    for phase in report['phases']:
        if 'diagnostic' not in phase:
            assert phase['sourceConnectionFailure']=='outside-geography-mask' and not phase['estimateProduced'];continue
        choices=phase['initialChoices'];assert choices<=4096
        for result in [phase['diagnostic'],*phase['productions']]:
            assert result['fieldStats']['seedBackingBufferBytes']==choices*64 and result['fieldStats']['starts']==choices
            assert result['fieldStats']['maximumBackingBufferBytes']==57946526+choices*64
            assert result['fieldStats']['returnedBackingBufferBytes']==49946526+choices*64
            assert result['stats']['maximumBackingBufferBytes']==66494595+choices*64<=66756739<67108864
            assert result['restorationChecked'] and result['output']['bytes']==result['stats']['jsonBytes']<=3000000
            max_backing=max(max_backing,result['stats']['maximumBackingBufferBytes'])
        assert phase['afterDiagnosticRelease']['arrayBuffers']<=baseline+1048576
    assert max_backing==66609411 and report['afterQueries']['arrayBuffers']<=baseline+1048576
    assert report['providerRequests']==0 and len(report['pending'])==2
    closed=load(HERE/'access-candidate-evaluation-closed-v1.json')
    return {'allCasesRetained':83,'finite':80,'unreachedShorelineCases':3,'same80CaseMae':{'v9':30.0011693272841,'candidate':31.371151041666668},
            'initialFieldAndDisplayBackingMaxBytes':66609411,'qualifiedRoadTotalsRetainedOrImproved':71,
            'numericalGatesPassed':False,'fullPathOrAppAdmission':False,
            'newUniqueClosedAllocationBytes':2326794240+closed['usage']['conservativeAllocatedBytes'],
            'reads':'Small bound code/mirrored evidence only; no graph/PBF/native/Docker/provider/DB/output replay.'}


if __name__=='__main__':print(json.dumps(verify()))

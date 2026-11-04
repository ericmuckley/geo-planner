"""Portable failed-candidate proof; no routing/graph/output/provider replay."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_filled_display_v1 import verify as display


def verify():
    display()
    for version,tests in [('v1',6),('v2',2)]:
        control=load(HERE/f'display-timing-controls-{version}.json')
        assert control['tests']==tests and control['successful'] and control['failures']==control['skips']==0
        assert control['consoleSha256']==sha(HERE/f'display-timing-controls-{version}.txt')
        design='display-timing-design-v1.json' if version=='v1' else 'display-timing-continuation-design-v2.json'
        assert control['designSha256']==sha(HERE/design)
        for name,pin in control['codeBindings'].items():assert sha(REPO/name)==pin,name
    closed=load(HERE/'display-timing-evaluation-closed-v1.json');prior=HERE/'display-timing-evaluation-raw-v1'
    assert closed['terminalRecord']=='failure.json'
    for name,pin in closed['roster'].items():
        if pin['ignoredLargeAsset']:continue
        assert (prior/name).stat().st_size==pin['bytes'] and sha(prior/name)==pin['sha256'],name
    failure=load(prior/'failure.json');assert 'Source connection failed' in failure['error']
    oldplan=load(prior/'execution-plan.json')
    for name,pin in oldplan['bindings'].items():assert sha(REPO/name)==pin,name
    root=host_closed('display-timing-evaluation','v2');report=load(root/'report.json');plan=load(root/'execution-plan.json')
    assert report['status']=='completed_fixed_numerical_and_shading_screen' and not report['numericalGatesPassed'] and not report['candidateAdmitted']
    assert (report['originalCases'],report['valhallaCases'],report['origins'])==(83,35,21)
    assert (report['reusedDiagnosticPhases'],report['reusedV1ProductionDisplays'],report['newDiagnosticPhases'],report['unsupportedSourceCases'])==(18,10,2,2)
    assert (report['reusedProductionDisplays'],report['newProductionDisplays'])==(24,2)
    baseline=load(REPO/plan['baseline']);rows=report['rows']
    assert len(rows)==83 and sorted(row['id'] for row in rows)==sorted(row['id'] for row in baseline['rows'])
    for row in rows:
        old=next(old for old in baseline['rows'] if old['id']==row['id'])
        assert row['baseline']==old['candidate'] and row['referenceMinutes']==old['referenceMinutes'] and row['valhallaMinutes']==old['valhallaMinutes']
        assert row['candidate']['pathComponents'] is None
        if row['estimateFailure'] is not None:assert row['candidate']['pointMinutes'] is None and not row['candidate']['predictedReachable']
    assert sum(row['candidate']['pointMinutes'] is None for row in rows)==4
    assert sum(row['estimateFailure'] is not None for row in rows)==2
    assert report['overall']['candidate']['pairedFinite']==79 and report['overall']['candidate']['pathSumsReconstructed']==0
    assert abs(report['overall']['candidate']['meanAbsoluteMinutes']-40.81115506329114)<1e-10
    assert not report['gates']['all83Finite'] and not report['gates']['all35OlderShaded'] and not report['gates']['overallMean']
    for phase in report['phases']:
        if phase.get('reusedV1Record'):
            previous=load(REPO/phase['reusedV1Record']);assert phase['diagnostic']==previous['diagnostic']
        if 'diagnostic' in phase:assert phase['afterDiagnosticRelease']['arrayBuffers']<=report['afterLoad']['arrayBuffers']+1048576
    assert report['providerRequests']==0 and len(report['pending'])==3
    assert report['afterQueries']['arrayBuffers']<=report['afterLoad']['arrayBuffers']+1048576
    new=load(HERE/'display-timing-evaluation-closed-v2.json')
    return {'allCasesRetained':83,'finite':79,'unreached':4,'unsupportedSourceRows':2,
            'candidateFiniteOnlyMaeMinutes':40.81115506329114,'v9All83MaeMinutes':29.257418754386766,
            'candidateNumericalGatesPassed':False,'candidateAdmitted':False,'fullPathAndAppGatesPending':True,
            'closedAllocationBytes':2311897088+closed['usage']['conservativeAllocatedBytes']+new['usage']['conservativeAllocatedBytes'],
            'reads':'Small bound code/mirrored evidence only; no national graph/PBF/native/Docker/provider/DB/output replay.'}


if __name__=='__main__':print(json.dumps(verify()))

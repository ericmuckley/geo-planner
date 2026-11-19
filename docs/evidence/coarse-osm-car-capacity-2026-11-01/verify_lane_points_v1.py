"""Portable all83 lane point-proxy screen; map/accuracy admission stays false."""
import json

from verify_lane_runtime_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();access=stage('lane-access');report=stage('lane-points')
    assert access['inputs']==access['newEndpointCollections']==access['supported']==79
    assert access['reusedEndpointCollections']==access['unsupported']==access['maskOmissionAllowanceInputs']==0
    assert access['totalConnections']==10338 and access['maximumConnections']==1840 and access['originalSupportedInputsRetained']==78
    assert report['status']=='all83_lane_primary_finish_context_feasibility_complete'
    assert report['originalCases']==83 and report['valhallaCases']==35
    assert len(report['phases'])==21 and len(report['comparisons'])==len(report['rows'])==83
    assert report['roadArrivalRegressions']==0 and report['roadFinishesImproved']==30 and report['changedPointTimes']==26
    assert report['contextStates']==34179 and report['contextDataBackingBytes']==1786511
    assert report['maximumQueryBackingBytes']==51024802<67108864
    assert report['heldCoreGeometryContextsBackingBytes']==144085900
    assert report['afterLoad']['arrayBuffers']==report['afterQueries']['arrayBuffers']==144171169
    frozen=load(HERE/'absent-entry-evaluation-raw-v1/report.json')
    old_rows={r['id']:r for r in frozen['rows']};new_rows={r['id']:r for r in report['rows']}
    timings={k:v for p in frozen['phases'] for k,v in p['diagnostic']['timings'].items()}
    assert old_rows.keys()==new_rows.keys()==timings.keys()
    road_finite=0
    for row in report['comparisons']:
        key=row['id'];saved=timings[key];new=new_rows[key];old=old_rows[key]
        assert row['previousRoadTicks']==saved['roadTicks'] and row['previousPointTicks']==saved['ticks']
        assert row['frozenLocalGridTicks']==saved['localGridTicks']
        point=min(v for v in (row['bestRoadTicks'],saved['localGridTicks']) if v is not None)
        assert row['pointTicks']==point and new['candidate']['pointMinutes']==point/480
        assert new['baseline']==old['baseline'] and new['candidate']['predictedReachable']==old['candidate']['predictedReachable']==row['frozenPublicShaded']
        for field in ('origin','destination','referenceMinutes','valhallaMinutes','budgetMinutes','set'):assert new[field]==old[field]
        road_finite+=row['bestRoadTicks'] is not None
    assert road_finite==82
    prior=load(HERE/'multiway-points-raw-v1/report.json');prior_by_id={r['id']:r for r in prior['comparisons']}
    paired=report['comparisonWithPreviousPrototype'];assert paired['cases']==83
    assert (paired['roadArrivalsImproved'],paired['roadArrivalsRegressed'],paired['pointTimesChanged'])==(18,0,15)
    current={r['id']:r for r in report['comparisons']}
    for row in paired['comparisons']:
        key=row['id'];before=prior_by_id[key];after=current[key]
        assert row==dict(id=key,previousRoadTicks=before['bestRoadTicks'],roadTicks=after['bestRoadTicks'],previousPointTicks=before['pointTicks'],pointTicks=after['pointTicks'])
        assert before['frozenLocalGridTicks']==after['frozenLocalGridTicks']
    assert report['overall']['candidate']['pairedFinite']==83 and report['overall']['candidate']['meanAbsoluteMinutes']==36.743468875502
    assert prior['overall']['candidate']['meanAbsoluteMinutes']==36.51196787148596
    assert report['overall']['baseline']['meanAbsoluteMinutes']==29.257418754386766
    assert not report['candidateAdmitted'] and not report['numericalGatesPassed'] and report['providerRequests']==0
    assert report['overall']['candidate']['pathSumsReconstructed']==0
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('lane-access','lane-points'):total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==8370069504
    return {**result,'status':'lane_all83_point_proxy_screen_complete_accuracy_rejected',
            'laneAll79FreshEndpointChoicesChecked':True,'laneAll83PointComparisonsComplete':True,
            'laneComparedWithPreviousPrototype':dict(roadImprovements=18,roadRegressions=0,changedPointTimes=15),
            'lanePointProxyMeanAbsoluteMinutes':36.743468875502,'laneRoadFinite':82,
            'laneMapsRerendered':False,'laneQueryOrAccuracyMeasured':True,
            'uniqueClosedRoots':295,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

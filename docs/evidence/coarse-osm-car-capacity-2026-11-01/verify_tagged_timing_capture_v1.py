"""Portable current diagnosis plus exact captured timing prototype; no replay."""
import json
from statistics import mean

from verify_lane_diagnosis_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    plan=load(HERE/'lane-tagged90-fixed-road-plan-v1.json');screen=load(HERE/'lane-tagged90-fixed-road-screen-v1.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    assert screen['recipeSha256']==sha(HERE/'lane-tagged90-fixed-road-plan-v1.json')
    assert plan['taggedSpeedRatio']==[9,10] and plan['defaultSpeedRatio']==[1,1]
    assert len(screen['rows'])==83 and not screen['isCandidateEvaluation'] and not screen['policyActivated']
    assert not screen['allNecessaryMeanGatesPass'] and not any(screen['necessaryMeanGatesOnly'].values())
    source={r['id']:r for r in load(HERE/'lane-primary-road-findings-v1.json')['rows']}
    for row in screen['rows']:
        if row['roadUnavailable']:
            assert row['id'] not in source and row['fixedRoadSensitivityMinutes'] is None
        else:
            original=source[row['id']]
            assert row['currentRoadMinutes']==original['candidateMinutes']
            assert row['taggedTimeAddedMinutes']==original['sourceSpeedExposure']['explicitTicks']/9/480
            assert row['fixedRoadSensitivityMinutes']==(sum(original['components'].values())+original['sourceSpeedExposure']['explicitTicks']/9)/480
        assert row['fixedPointSensitivityMinutes']==min(v for v in (row['fixedRoadSensitivityMinutes'],row['frozenLocalGridMinutes']) if v is not None)
    finite=[r for r in screen['rows'] if not r['roadUnavailable']]
    assert len(finite)==82 and mean(abs(r['fixedRoadSensitivityMinutes']-r['referenceMinutes']) for r in finite)==14.771480352303522
    assert sum(r['frozenLocalGridMinutes'] is not None and r['frozenLocalGridMinutes']<r['fixedRoadSensitivityMinutes'] for r in finite)==77
    assert screen['overall']['fixedPointSensitivityMaeMinutes']==34.80463966979028
    failed=load(HERE/'tagged-timing-controls-closed-v1.json');root=HERE/'tagged-timing-controls-raw-v1'
    assert failed['terminalRecord']=='failure.json' and 'controls.json' not in failed['roster']
    for name,pin in failed['roster'].items():
        if not pin['ignoredLargeAsset']:assert sha(root/name)==pin['sha256']
    assert 'coarse_osm_car_codec_v1' in load(root/'failure.json')['error'] and load(root/'run-summary.json')['exitCode']==2
    assert load(root/'cleanup.json')['removed'] and load(root/'cleanup.json')['independentInspectAbsent']
    for name,pin in load(root/'execution-plan.json')['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    controls=stage('tagged-timing-controls-v2',True)
    assert controls['controls']==dict(tests=24,successful=True,failures=0,errors=0,skips=0)
    capture=stage('tagged-timing-capture',True)
    assert capture['status']=='complete_captured_tagged_timing_native_and_independent_python_prices_passed'
    assert capture['sourceCounts']==dict(ids=143560,xy=287120,anchors=46881,flags=46881,geometry=177956,ways=28995,arcs=79148)
    assert capture['changedEstimatedWayRows']==14504
    assert capture['pricing']==dict(arcsChecked=79148,costsChanged=38709,defaultArcsChecked=40439,primitiveOccurrences=225775,nativeBatches=2)
    assert capture['everyOldAndNewMacroPricePythonAudited']==79148 and capture['derivedFactBytes']==3507457
    assert capture['allPhysicalArcDescriptorsAndOrderExact'] and capture['allDirectionsDefaultsRolesAndFlagsExact']
    assert not capture['originalLegalSpeedSourceFactsModified'] and capture['nodeFlagsChanged']==0
    assert capture['sourcePbfReads']==capture['sourceConstructorExecutions']==capture['routingQueries']==capture['providerRequests']==capture['applicationDbReads']==0
    assert not capture['countryCostFactsBuilt'] and not capture['runtimeGraphBuilt'] and not capture['accuracyOrAppAccepted']
    for prefix in ('tagged-timing-controls','tagged-timing-controls-v2','tagged-timing-capture'):total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==8387796992 and 64500000000+total+104857600+805306368+268435456<72*1024**3
    return {**result,'status':'exact_captured_tagged_timing_prototype_and_original_failure_preserved',
            'taggedTimingActualLinuxControls':24,'capturedAll79148OldAndNewPricesIndependentlyAudited':True,
            'originalLegalSpeedFactsPreserved':True,'frozenLocalGridSensitivityCannotQualifyGlobalCosts':True,
            'taggedTimingCountryCostsOrGraphBuilt':False,'uniqueClosedRoots':301,
            'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

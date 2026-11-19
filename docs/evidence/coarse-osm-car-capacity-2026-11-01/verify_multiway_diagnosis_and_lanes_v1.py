"""Read-only composed diagnosis/lane proof; no model or source producer replay."""
import json
import math

from verify_entry_runtime_v1 import stage
from verify_multiway_road_paths_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous()
    controls=stage('multiway-road-attributes-controls',True)
    assert controls['controls']=={'tests':9,'successful':True,'failures':0,'errors':0,'skips':0}
    attributes=stage('multiway-road-attributes-run',True)
    assert (attributes['paths'],attributes['unavailable'],attributes['selectedArcs'])==(82,1,41282)
    assert (attributes['waysChecked'],attributes['preArcMappingsChecked'],attributes['retainedArcMappingsChecked'])==(4227238,9878318,9822101)
    assert attributes['sourcePbfReads']==attributes['routingQueries']==attributes['providerRequests']==0
    review=load(HERE/'multiway-road-attributes-identity-review-v1.json')
    assert sha(REPO/review['recipe'])==review['recipeSha256']=='40c59c2cecbc93786db3bf0f7dcc654ee7ae33751453b155a97753326858bf95'
    annotation_plan=load(REPO/review['recipe'])
    controller=REPO/'scripts/run_osm_multiway_road_attributes_v1.py'
    assert sha(controller)==review['controllerSha256']
    assert 'coreManifestSha256' not in controller.read_text() and 'geometryManifestSha256' not in controller.read_text()
    for label in ('Core','Geometry'):
        assert review['unusedCopied'+label+'ManifestSha256']==annotation_plan[label.lower()+'ManifestSha256']
    sources=[('data/coarse-quality/us-osm-multiway-graph-run-v1/base-routing/offsets.u24','multiway-graph-run','base-routing/offsets.u24'),
             ('data/coarse-quality/us-osm-multiway-derived-spatial-v1/routing/old-arc-to-new.u32','multiway-derived-spatial','routing/old-arc-to-new.u32'),
             ('data/coarse-quality/us-osm-multiway-country-run-v1/resolved/closures-0000.bin','multiway-country-run','resolved/closures-0000.bin'),
             ('docs/evidence/coarse-osm-car-capacity-2026-11-01/multiway-road-paths-raw-v1/report.json','multiway-road-paths','report.json')]
    for name,prefix,key in sources:
        pin=load(HERE/(prefix+'-closed-v1.json'))['roster'][key]['sha256']
        assert review['actualInputFilesChecked'][name]==annotation_plan['inputs'][name]==pin
    query=load(HERE/'multiway-context-wire-raw-v1/core/manifest.json')
    base=load(HERE/'multiway-codec-core-raw-v1/manifest.json')
    assert sum(key!='routing/forbidden-turns.u24' and value==base['fields'][key] for key,value in query['fields'].items())==review['physicalCoreFieldsByteIdentical']==12
    path_plan=load(HERE/'multiway-road-paths-plan-v1.json')
    assert review['coreManifestSha256']==path_plan['coreManifestSha256']==sha(HERE/'multiway-context-wire-raw-v1/core/manifest.json')
    assert review['geometryManifestSha256']==path_plan['geometryManifestSha256']==sha(HERE/'multiway-codec-geometry-raw-v1/manifest.json')
    assert not review['recipeOrSourceMeasurementRewritten'] and not review['sourceOrProducerReplayed']
    findings_plan=load(HERE/'multiway-primary-road-findings-plan-v1.json')
    assert sha(HERE/'multiway-primary-road-findings-plan-v1.json')=='81bcb828e57ffec40763a4227bb99988ff16af5bbdc3b6f7041eccd744ca618d'
    for name,pin in findings_plan['bindings'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    findings=load(HERE/'multiway-primary-road-findings-v1.json')
    assert findings['recipeSha256']==sha(HERE/'multiway-primary-road-findings-plan-v1.json')
    assert len(findings['rows'])==82 and len(findings['unavailable'])==1
    road={r['id']:r['primaryRoadTicks'] for r in load(HERE/'multiway-road-paths-raw-v1/report.json')['rows']}
    for row in findings['rows']:assert row['candidateMinutes']==road[row['id']]/480
    assert findings['unavailable'][0]['id']=='astoria-or-600-outside' and road[findings['unavailable'][0]['id']] is None
    assert findings['sourceSpeedAttributeUniqueKnownArcs']==41282 and findings['sourceSpeedAttributeUniqueUnknownArcs']==0
    assert math.isclose(sum(abs(r['signedMinutes']) for r in findings['rows'])/82,findings['overall']['meanAbsoluteErrorMinutes'])
    metadata=stage('lane-metadata-capture')
    assert metadata['majorWayRowsClassified']==28995 and metadata['laneRejectedWays']==32
    classified=stage('explicit-lanes-capture')
    assert classified['majorWaysCompared']==28995 and classified['counts']['oldEligibleRetainedExactly']==28718
    assert classified['counts']['newEligible']==28 and classified['counts']['after/lane-access']==4
    records=load(HERE/'explicit-lanes-capture-raw-v1/lane-records.json')
    assert sha(HERE/'explicit-lanes-capture-raw-v1/lane-records.json')==classified['recordsSha256']
    assert len(records)==32 and sum(r['eligibilityGained'] for r in records)==28
    graph=stage('explicit-lanes-graph-capture')
    assert graph['originalCases']==82 and graph['candidateFinite']==81 and graph['candidateStillUnreachable']==1
    assert graph['newPreClosureArcs']==30 and graph['oldPhysicalArcsRetained']==graph['oldPhysicalArcs']==77429
    assert graph['newPhysicalArcs']==77459 and graph['oldAllowedPhysicalTransitionsRemoved']==0
    assert graph['oldAllowedPhysicalTransitionsChecked']==146184
    assert graph['oldSupportedTurnPairs']==graph['supportedSourceTurnPairs']==2481
    assert graph['oldContextRules']==graph['newContextRules']==295 and graph['oldClosedWays']==graph['newClosedWays']==506
    assert graph['previousFiniteImproved']==1 and graph['previousFiniteRegressed']==graph['previousFailuresRecovered']==0
    old=load(HERE/'multiway-entry-capture-raw-v1/report.json')['rows']
    for before,after in zip(old,graph['rows'],strict=True):
        assert before['candidateTicks']==after['baselineTicks']
        assert before['sourceNodeIds']==after['sourceNodeIds'] and before['windowId']==after['windowId']
        assert after['sourceReplayed']==(after['candidateTicks'] is not None)
    total=result['newUniqueClosedAllocationBytes']+sum(load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes'] for prefix in ('multiway-road-attributes-controls','multiway-road-attributes-run','lane-metadata-capture','explicit-lanes-capture','explicit-lanes-graph-capture'))
    assert total==7384236032
    assert 64500000000+total+104857600+67108864+268435456<72*1024**3
    return {'status':'completed_multiway_diagnosis_and_captured_lane_proof_passed',
            'previousSmallRecordProofChainPassed':True,'newPrimaryRoadSourceAndCachedGeometryDiagnosisComplete':True,
            'capturedExplicitLaneOldEligiblePoliciesRetainedExactly':28718,'capturedExplicitLaneWaysAdmitted':28,
            'capturedExplicitLaneDirectedSegmentsRestored':30,'uniqueClosedRoots':262,
            'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

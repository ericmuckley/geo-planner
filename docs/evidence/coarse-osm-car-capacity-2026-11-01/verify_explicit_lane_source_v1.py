"""Completed national lane metadata proof; small closed records/code only."""
import json

from verify_entry_runtime_v1 import stage
from verify_explicit_lane_census_controls_v1 import verify as previous
from verify_preparation_v1 import HERE, load, sha


def verify():
    result=previous();report=stage('explicit-lane-source-run-v1',True)
    assert report['status']=='complete_national_explicit_lane_metadata_census_passed'
    c=report['explicitLanes'];audit=report['independentChangedTagAudit']
    assert (c['nodes'],c['ways'],c['relations'])==(1606229364,162688797,1624265)
    assert c['allNodeFlagsExact']==c['nodes'] and c['changedNodeFlags']==0
    assert c['majorWays']==c['allMajorWayPoliciesCompared']==4227238 and c['majorReferences']==48163649
    assert c['oldEligibleWays']==c['oldEligibleWaysExact']==4190263
    assert c['newlyEligibleWays']==c['changedRecords']==3292 and c['newEligibleWays']==4193555
    assert c['laneRejectedWays']==11379 and c['laneFallbackWays']==8087
    assert c['newLaneWaysWithSpeedConditional']==0 and c['newLaneWaysWithoutSpeedConditional']==3292
    assert c['oldBlockedNodes']==c['newBlockedNodes']==3347881
    baseline=load(HERE/'conditional-source-run-v2-raw-v1/report.json')['conditional']
    for i in range(10):assert c['oldWayReason'+str(i)]==baseline['newWayReason'+str(i)]
    for i in (1,2,3,4,5,7,8,9):assert c['newWayReason'+str(i)]==c['oldWayReason'+str(i)]
    assert audit['allOldPositiveDecisionsRetained'] and audit['counts']['ways']==3292
    assert audit['bytes']==c['changedEncodedBytes']==1552816
    assert audit['counts']['tagUtf8Bytes']==c['changedTagUtf8Bytes']==1049344
    closed=load(HERE/'explicit-lane-source-run-v1-closed-v1.json')
    assert closed['roster']['changed-lane-tags.bin']['sha256']==audit['sha256']=='4bf02b067e59aa7ed992b42fadc7178620aa2cf048975a31a91d26fb91d45536'
    receipt=load(HERE/'explicit-lane-source-run-v1-raw-v1/receipt.json')
    assert receipt['nativeEof'] and receipt['visits']==1770542426
    assert receipt['counts']=={'node':1606229364,'way':162688797,'relation':1624265}
    assert receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    assert receipt['pythonProjectionFrames']==0
    assert receipt['sourceIdentity']['sourceSha256']=='1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
    assert receipt['sourceIdentity']['sourceMd5']=='c5abaec55e724255277f22fb97941e5a'
    assert receipt['sourceIdentity']['framingBytesRead']==receipt['postSourceHashBytes']==12229320016
    assert receipt['knownGuardReadBytes']==24458640032
    plan=HERE/'explicit-lane-source-run-plan-v1.json'
    assert sha(plan)=='50caeb33d2be64ace8f50584125db1b0f18bf2cf561878690a2acef0a8749709'
    assert report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['coordinatesOrGeometryRetained'] and not report['appActivated']
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==7403225088
    return {**result,'laneNationalMetadataCompleted':True,'laneNationalNewlyEligibleMajorWays':3292,
            'laneNationalExistingEligiblePoliciesRetainedExactly':4190263,'laneNationalFallbackWays':8087,
            'uniqueClosedRoots':269,'newUniqueClosedAllocationBytes':total,
            'laneNationalGraphBuilt':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

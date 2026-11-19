"""Portable complete corrected national conditional census; no source replay."""
import json
from verify_conditional_overlay_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-source-run-v2',True);root=HERE/'conditional-source-run-v2-raw-v1'
    assert report['status']=='complete_national_conditional_metadata_census_passed'
    receipt=load(root/'receipt.json');checkpoint=load(root/'source-census.json');c=report['conditional']
    assert checkpoint['receipt']==receipt and checkpoint['conditional']==c
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames']==0 and receipt['visits']==1770542426
    assert receipt['counts']=={'node':1606229364,'way':162688797,'relation':1624265}
    assert receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    source=receipt['sourceIdentity'];assert source['sourceSha256']=='1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff' and source['sourceMd5']=='c5abaec55e724255277f22fb97941e5a'
    assert source['framingBytesRead']==receipt['postSourceHashBytes']==12229320016 and source['frames']==221321
    assert c['complete']==1 and c['majorWays']==4227238 and c['majorReferences']==48163649
    assert c['oldEligibleWays']==c['oldEligibleWaysExact']==4173977 and c['newEligibleWays']==4190263
    assert c['oldUnblockedNodes']==c['oldUnblockedNodesExact']==1602881481
    assert c['newlyEligibleWays']==16286 and c['changedNodeFlags']==2 and c['changedRecords']==16288
    assert c['newSpeedConditionalWays']==5767 and c['newNonCarScopedWays']==10519
    assert c['majorWaysWithSpeedConditional']==6365 and c['speedConditionalStillExcludedWays']==598
    audit=report['independentChangedTagAudit'];assert audit['status']=='all_changed_source_tags_independently_reclassified'
    assert audit['counts']=={'nodes':2,'ways':16286,'speedWays':5767,'scopeWays':10519,'tagUtf8Bytes':4878831}
    assert audit['bytes']==c['changedEncodedBytes']==6997511 and audit['sha256']=='4472c6bd0cf4e826e86b860fc89d9b6fef06fd4a4c5a7e72aa899da970725f11'
    record=load(HERE/'conditional-source-run-v2-closed-v1.json');pin=record['roster']['changed-tags.bin'];assert pin['bytes']==audit['bytes'] and pin['sha256']==audit['sha256']
    assert report['sourcePbfScans']==1 and report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['coordinatesOrGeometryRetained'] and not report['maskOrModelChanged'] and not report['appActivated']
    allocation=result['newUniqueClosedAllocationBytes']+record['usage']['conservativeAllocatedBytes'];assert allocation==5425143808
    return {**result,'conditionalNationalMetadataMeasured':True,'conditionalNationalNewlyEligibleWays':16286,
            'conditionalNationalChangedSourceNodes':2,'conditionalNationalChangedTagsIndependentlyReclassified':16288,
            'conditionalNationalGraphOrEtaAccepted':False,'uniqueClosedRoots':180,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

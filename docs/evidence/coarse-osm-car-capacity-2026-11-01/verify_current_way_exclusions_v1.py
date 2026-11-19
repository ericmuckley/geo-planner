"""Portable current exclusion/contributor/corridor receipts, no ignored asset reads."""
import json
import math

from verify_selected_way_tags_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();report=stage('current-way-exclusions')
    assert report['knownOriginalWayTags']==report['sourceSelectedWays']==52743 and report['unknownOriginalWayTags']==0
    assert report['oldGlobalClosureIds']==29657 and report['currentGlobalClosureIds']==27421
    assert report['convertedRelationContributors']==1331 and report['allCurrentClosureContributorUnionsExact']
    assert report['categories']=={'base-eligible-fallback-closed':16824,'base-ineligible':33683,'retained-now':2236}
    assert sum(report['baseReasons'].values())==33683 and report['baseReasons']['lane-access']==8087
    assert report['laneShapes']=={'access-or-mixed-vectors':8084,'only-oneway-vectors':3}
    assert report['sourcePbfReads']==report['modelQueries']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['policyChanged'] and not report['appActivated']
    closed=load(HERE/'current-way-exclusions-closed-v1.json')
    artifact=report['artifact'];assert all(closed['roster'][artifact['file']][k]==artifact[k]for k in ('bytes','sha256'))
    plan=load(HERE/'current-exclusion-corridors-plan-v1.json')
    data={
        'data/coarse-quality/us-osm-source-gap-geometry-run-v1/geometries.jsonl.gz':load(HERE/'source-gap-geometry-run-closed-v1.json')['roster']['geometries.jsonl.gz']['sha256'],
        closed['root']+'/'+artifact['file']:artifact['sha256']}
    for name,pin in plan['bindings'].items():
        assert (data.get(name)==pin if name.startswith('data/') else sha(REPO/name)==pin),name
    corridors=load(HERE/'current-exclusion-corridors-v1.json')
    assert corridors['recipeSha256']==sha(HERE/'current-exclusion-corridors-plan-v1.json')
    assert corridors['allCasesRetained']==len(corridors['rows'])==83
    assert len({r['id']for r in corridors['rows']})==83
    assert corridors['sourceInventoryWays']==52743 and corridors['sourceInventoryReferences']==449987
    assert corridors['currentExcludedMajorWays']==50507 and corridors['retainedOldSelectionWaysOmitted']==2236
    assert corridors['providerRequests']==corridors['modelQueries']==corridors['sourcePbfReads']==0
    assert not corridors['permissionOrPriceChanges'] and not corridors['appActivated']
    for field in ('referenceSampleKm','referenceOutsideWinner1Km'):
        assert math.isclose(sum(r[field]for r in corridors['rows']),corridors[field],abs_tol=1e-8)
    for key in ('0.1','0.25','1'):
        near=sum(r['outsideWinner1KmNearAnyExcludedKm'][key]for r in corridors['rows'])
        assert math.isclose(near,corridors['outsideWinner1KmNearAnyExcludedKm'][key],abs_tol=1e-8)
        assert math.isclose(near/corridors['referenceOutsideWinner1Km'],corridors['fractionOfOutsideWinner1KmNearAnyExcluded'][key],abs_tol=1e-10)
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==plan['newClosedAllocationBytes']==10175856640 and plan['previousClosedRoots']==383
    assert 64500000000+total+104857600<72*1024**3
    return {**result,'status':'all_current_major_way_exclusions_and_all83_corridors_audited',
            'registeredClosedRoots':383,'newUniqueClosedAllocationBytes':total,
            'currentExclusionMembershipInterpreted':True,'currentExcludedMajorWays':50507,
            'allCurrentClosureContributorUnionsExact':True,'all83CurrentReferenceCorridorsCompared':True,
            'sourcePassGuardEvidence':'Sealed control flow/failure location; original numeric source/native receipts missing, not fabricated',
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

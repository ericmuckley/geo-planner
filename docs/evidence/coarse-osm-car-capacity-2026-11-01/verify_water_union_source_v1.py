"""Portable complete water/member-way union measurement; no ignored reads."""
import json
from verify_water_union_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();report=stage('water-union-source-run',True)
    assert report['status']=='national_water_member_way_union_census_passed'
    receipt=load(HERE/'water-union-source-run-raw-v1/receipt.json')
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames']==0
    assert receipt['counts']=={'node':1606229364,'way':162688797,'relation':1624265}
    assert receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    assert receipt['sourceIdentity']['sourceSha256']=='1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
    old=load(HERE/'water-source-run-raw-v1/report.json')['water'];water=report['water']
    assert {k:water[k] for k in old}==old
    union=water['union']
    assert (union['unionWays'],union['unionReferences'],union['unionEncodedBytes'])==(2829193,104806243,1197794328)
    assert union['requestedMemberWays']==458255 and union['memberWaysFound']==458238 and union['missingMemberWays']==17
    assert union['memberOnlyWays']==454851 and union['memberOnlyReferences']==36792901
    assert union['unionWays']==union['taggedWays']+union['memberOnlyWays']
    assert union['unionReferences']==union['taggedReferences']+union['memberOnlyReferences']
    assert union['closedUnionWays']+union['openUnionWays']==union['unionWays']
    assert union['maximumUnionWayReferences']==2000 and union['complete']==1
    assert report['missingMemberWayIds']['count']==17 and report['missingMemberWayIds']['bytes']==136
    assert not report['coordinatesOrGeometryRetained'] and not report['maskOrModelChanged']
    return {**result,'waterUnionNationalCensusCompleted':True,'waterUnionWays':2829193,'waterUnionReferenceOccurrences':104806243,
            'waterMissingWayMembersPreserved':17,'newUniqueClosedAllocationBytes':2887090176,'uniqueClosedRoots':124,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

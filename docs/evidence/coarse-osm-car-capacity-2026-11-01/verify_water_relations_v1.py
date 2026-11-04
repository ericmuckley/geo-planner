"""Portable complete national water relation/member-ID proof; no ignored reads."""
import json
from verify_water_relations_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    report=stage('water-relations-run',True)
    assert report['status']=='national_water_relations_and_member_ids_passed'
    assert report['nativeCensusParity']
    scan=report['scan'];stored=report['stored'];audit=report['independentAudit']
    assert scan['relations']==1624265 and scan['headersVisited']==221321 and scan['waterRecordsSelected']==68734
    assert not scan['earlierNodeWayBodiesValidated'] and scan['nodeWayObjectsProjected']==0
    assert stored['counts']=={'relations':68734,'wayMembers':468608,'nodeMembers':254,'relationMembers':34,
                             'outerWayMembers':229170,'innerWayMembers':239283,'otherRoleWayMembers':155,
                             'multipolygons':68720,'otherTypes':14,'maxMembers':14759}
    assert stored['uniqueMemberWays']==audit['uniqueMemberWayIdsChecked']==458209
    assert stored['rawJsonBytes']==audit['rawJsonBytesChecked']==35664831
    assert stored['memberIndexBytes']==3665672 and stored['gzipBytes']==3250252
    assert audit['allSelectedRelationsChecked']==68734 and audit['allMemberOccurrencesChecked']==468896
    raw=HERE/'water-relations-run-raw-v1'
    before=load(raw/'source-before.json');after=load(raw/'source-after.json')
    assert all(before[k]==after[k] for k in ('bytes','sha256','md5','stat'))
    assert before['bytes']==12229320016 and before['sha256']=='1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
    assert not report['missingMemberWaysOrNestedRelationsResolved'] and not report['coordinatesOrGeometryRetained']
    return {**result,'waterRelationsPreserved':True,'uniqueWaterRelationMemberWays':458209,
            'waterRelationMemberOccurrencesIndependentlyChecked':468896,
            'newUniqueClosedAllocationBytes':2870341632,'uniqueClosedRoots':117,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

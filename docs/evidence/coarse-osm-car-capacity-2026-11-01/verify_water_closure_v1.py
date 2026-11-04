"""Portable source-derived water relation closure; preserves its source gap."""
import json
from verify_water_relations_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    controls=stage('water-closure-controls',True)
    assert controls['controls']=={'tests':34,'successful':True,'failures':0,'errors':0,'skips':0}
    report=stage('water-closure-run',True)
    closure=report['closure'];audit=report['independentAudit']
    assert report['status']=='national_water_relation_closure_measured'
    assert closure['rootRelations']==audit['allRootRelationsChecked']==68734
    assert closure['descendantRelations']==audit['allDescendantsChecked']==17
    assert closure['descendantMembers']==audit['allDescendantMemberOccurrencesChecked']==59
    assert closure['uniqueWayIds']==audit['allUniqueWayIdsChecked']==458255
    assert len(closure['rounds'])==2 and closure['sourceAbsentRelationIds']==[21607544]
    assert not closure['referenceClosureComplete'] and closure['acyclic']
    assert closure['depthLimitedRelationIds']==closure['cycleBackEdges']==[]
    assert [s['recordsSelected'] for s in report['scans']]==[17,0]
    assert all(s['relations']==1624265 and s['headersVisited']==221321 and s['nodeWayObjectsProjected']==0 for s in report['scans'])
    raw=HERE/'water-closure-run-raw-v1'
    before=load(raw/'source-before.json');after=load(raw/'source-after.json')
    assert all(before[k]==after[k] for k in ('bytes','sha256','md5','stat'))
    assert before['bytes']==12229320016 and before['sha256']=='1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
    assert not report['coordinatesOrGeometryRetained'] and not report['maskOrModelChanged']
    return {**result,'waterNestedRelationLinuxControls':34,'waterAdditionalDescendantsPreserved':17,
            'waterSourceAbsentRelationsPreserved':1,'waterCompleteRelationMemberWayIds':458255,
            'waterReferenceClosureComplete':False,'newUniqueClosedAllocationBytes':2876903424,'uniqueClosedRoots':119,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

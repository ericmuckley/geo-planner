"""Portable saved source-gap dependency facts; no ignored metadata reads."""
import json
from verify_water_references_controls_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();plan=load(HERE/'water-source-gap-plan-v1.json')
    report=load(HERE/'water-source-gap-dependencies-v1.json')
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','docs/')):assert sha(REPO/name)==pin
    parents=[('roots','water-relations-run-raw-v1/report.json','water-relations.jsonl.gz'),
             ('descendants','water-closure-run-raw-v1/report.json','water-relations.jsonl.gz')]
    for key,parent,name in parents:assert plan['inputs'][plan[key]]==load(HERE/parent)['outputs'][name]['sha256']
    assert plan['inputs'][plan['missingWays']]==load(HERE/'water-union-source-run-raw-v1/report.json')['missingMemberWayIds']['sha256']
    assert report['recipeSha256']==sha(HERE/'water-source-gap-plan-v1.json')
    assert report['status']=='saved_water_source_gap_dependencies_complete'
    assert (report['rootRelations'],report['additionalRelations'])==(68734,17)
    assert len(report['sourceMissingWayIds'])==17 and report['sourceMissingRelationIds']==[21607544]
    assert report['directRootSourceGapCount']==0
    assert report['rootsDependingOnMissingWays']==report['rootsDependingOnMissingRelations']==report['rootsDependingOnAnyKnownSourceGap']==1
    assert len(report['affectedRootsAndReasonBits'])==1 and report['affectedRootsAndReasonBits'][0][1]==3
    assert {k:sum(v.values()) for k,v in report['memberRoleCounts'].items()}=={'way':468665,'node':254,'relation':36}
    assert not report['eligibilityPolygonOrGeographicImpactEstablished'] and not report['nodeCoordinatesAudited']
    return {**result,'waterSourceGapDependencyControls':4,'waterRootsDependingOnKnownSourceGaps':1,
            'waterSourceGapGeographicImpactOrPolygonEligibilityEstablished':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

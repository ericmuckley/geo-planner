"""Portable complete national graph/source audit and metadata preservation proof."""
import json

from verify_lane_restrictions_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    assert stage('lane-graph-controls',True)['controls']==dict(tests=38,successful=True,failures=0,errors=0,skips=0)
    report=stage('lane-graph-run',True)
    assert report['status']=='lane_national_graph_and_independent_complete_audit_passed'
    assert report['augmentationCounts']==[25398,235258,24947,451,258059,9826630]
    proof=report['independentAudit']
    assert proof['allPreArcMappingsChecked']==9882872 and proof['finalForbiddenPairsChecked']==258059
    assert proof['baseFields']['directedCostsAndPhysicalReversesChecked']==9826630
    assert proof['baseFields']['sourceTurnRecordsChecked']==409178
    assert proof['closureSubsetExact'] and proof['newEntryPairsOnlyTouchOriginallyClosedArcs'] and proof['oldAllowedTransitionsPreserved']
    assert report['finalPayloadBytes']==129290987
    assert report['sourcePbfReads']==report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==0
    total=result['newUniqueClosedAllocationBytes']
    for name in ('controls','run'):
        total+=load(HERE/f'lane-graph-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==8026193920
    return {**result,'laneNationalAll9826630ArcSourceCostsAudited':True,
            'laneNationalAll258059ConservativeTurnPairsAudited':True,
            'uniqueClosedRoots':282,'newUniqueClosedAllocationBytes':total,
            'laneNationalGraphBuilt':True,'laneRuntimeAndAccuracyQualified':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

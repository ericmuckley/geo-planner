"""Portable complete national graph/source audit and metadata preservation proof."""
import json

from verify_multiway_country_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    assert stage('multiway-graph-controls',True)['controls']==dict(tests=38,successful=True,failures=0,errors=0,skips=0)
    report=stage('multiway-graph-run',True)
    assert report['status']=='multiway_national_graph_and_independent_complete_audit_passed'
    assert report['augmentationCounts']==[25327,235151,24876,451,257888,9822101]
    proof=report['independentAudit']
    assert proof['allPreArcMappingsChecked']==9878318 and proof['finalForbiddenPairsChecked']==257888
    assert proof['baseFields']['directedCostsAndPhysicalReversesChecked']==9822101
    assert proof['baseFields']['sourceTurnRecordsChecked']==409178
    assert proof['closureSubsetExact'] and proof['newEntryPairsOnlyTouchOriginallyClosedArcs'] and proof['oldAllowedTransitionsPreserved']
    assert report['finalPayloadBytes']==129262787
    assert report['sourcePbfReads']==report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==0
    total=result['newUniqueClosedAllocationBytes']
    for name in ('controls','run'):
        total+=load(HERE/f'multiway-graph-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7026860032
    return {**result,'multiViaNationalAll9822101ArcSourceCostsAudited':True,
            'multiViaNationalAll257888ConservativeTurnPairsAudited':True,
            'uniqueClosedRoots':243,'newUniqueClosedAllocationBytes':total,
            'multiViaNationalGraphOrAccuracyQualified':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

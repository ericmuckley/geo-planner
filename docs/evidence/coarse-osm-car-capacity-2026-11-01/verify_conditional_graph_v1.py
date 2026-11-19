"""Portable full packed conditional graph/source audit; no producer replay."""
import json
from verify_conditional_graph_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-graph-run',True)
    assert report['status']=='conditional_national_graph_and_independent_complete_audit_passed'
    base=report['basePackedResult'];assert (base['vertices'],base['preClosureArcs'],base['postClosureArcs'])==(5731903,9878318,9744462)
    assert base['costOverflowEntries']==2 and base['reverseOverflowEntries']==0
    assert report['augmentationCounts']==[22964,232480,19619,3345,250228,9744462]
    proof=report['independentAudit'];assert proof['allPreArcMappingsChecked']==9878318 and proof['finalForbiddenPairsChecked']==250228
    assert proof['oldAllowedTransitionsPreserved'] and proof['newEntryPairsOnlyTouchOriginallyClosedArcs']
    assert proof['baseFields']['directedCostsAndPhysicalReversesChecked']==9744462
    assert report['finalPayloadBytes']==128750993 and report['routingQueries']==report['sourcePbfReads']==report['sourceConstructorExecutions']==0
    assert not report['spatialOrPaidGeometryOrCodecBuilt'] and not report['appActivated']
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-graph-run-closed-v1.json')['usage']['conservativeAllocatedBytes'];assert total==6034694144
    return {**result,'conditionalPackedGraphBuilt':True,'conditionalPackedGraphAllArcsAudited':9744462,
            'conditionalPackedGraphAllTurnPairsAudited':250228,'conditionalPackedGraphPayloadBytes':128750993,
            'uniqueClosedRoots':189,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

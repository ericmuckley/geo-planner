"""Current graph/spatial receipts; no graph asset reads or producer execution."""
import json

from verify_inactive_conditional_facts_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();graph=stage('inactive-conditional-graph-run',True)
    assert graph['basePackedResult']['postClosureArcs']==9853365
    assert graph['basePackedResult']['sourceTurnRecords']==410509
    assert graph['conditionalJunctionBansAdded']==1331 and graph['inactiveSourceRulesOmitted']==6149
    assert graph['comparisonParentPostArcs']==9837848
    audit=graph['independentAudit']
    assert audit['allPreArcMappingsChecked']==9882872 and audit['finalForbiddenPairsChecked']==259967
    assert audit['baseFields']['directedCostsAndPhysicalReversesChecked']==9853365
    assert audit['baseFields']['sourceTurnRecordsChecked']==410509 and audit['baseFields']['forbiddenTurnPairsChecked']==237138
    assert audit['oldAllowedTransitionsPreserved'] and audit['closureSubsetExact']
    assert graph['finalPayloadBytes']==129462845 and not graph['appActivated']
    spatial=stage('inactive-conditional-derived-spatial',True)
    assert spatial['nativeResult']['vertices']==5731903 and spatial['nativeResult']['arcs']==9853365
    assert spatial['nativeResult']['forbiddenTurnPairs']==259967
    assert not spatial['appActivated'] and not spatial['accuracyQualified']
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('inactive-conditional-graph-run','inactive-conditional-derived-spatial'):
        total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==10536194048 and 64500000000+total+104857600<72*1024**3
    return {**result,'status':'inactive_conditional_national_graph_and_fresh_spatial_all_fields_audited',
            'registeredClosedRoots':388,'newUniqueClosedAllocationBytes':total,
            'freshNationalGraphArcs':9853365,'additionalDirectedSegmentsVsCurrentModel':15517,
            'freshFinalForbiddenPairs':259967,'freshGeometryContextStorageAndQueriesPending':True,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

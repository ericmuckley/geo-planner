"""Portable complete saved-way endpoint/native-ID chain evidence, no geometry claim."""
import json
from verify_water_endpoints_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-endpoints-run',True)
    assert report['status']=='national_water_endpoint_and_relation_chain_diagnosis_complete'
    captured=report['captured'];audit=report['independentEndpointAudit']
    assert captured['sourceWayRecords']==audit['allSavedSourceWaysDecoded']==2829193
    assert captured['sourceReferenceOccurrences']==audit['allSavedSourceReferencesDecoded']==104806243
    assert captured['sourceRawGpfBytes']==1209111100
    assert captured['memberWayIds']==audit['allMemberEndpointRowsChecked']==458255
    assert captured['foundMemberWays']==458238 and len(captured['missingMemberWayIds'])==17
    assert report['rootStatusCounts']=={
        'explicit_role_degree2_closed_chains':68652,'duplicate_way_member_occurrence':3,
        'native_endpoint_topology_requires_geometry_or_missing_closure':46,
        'nested_relation_roles_need_geometry_policy':18,'not_direct_multipolygon':14,
        'way_role_requires_explicit_policy':1}
    assert report['additionalStatusCounts']=={'not_direct_multipolygon':1,'explicit_role_degree2_closed_chains':16}
    assert report['allRelationDiagnosticsReopened']==68751
    assert report['explicitRoleChainMemberOccurrencesIndependentlyReplayed']==467295
    assert report['compressedBytes']==6586531
    assert not report['sourcePbfReads'] and not report['coordinatesExamined']
    assert not report['polygonValidityEstablished'] and not report['maskOrModelChanged']
    return {**result,'waterNationalEndpointDiagnosisCompleted':True,
            'waterExplicitRoleClosedChainRoots':68652,'waterOtherRootCasesRetained':82,
            'newUniqueClosedAllocationBytes':4292411392,'uniqueClosedRoots':136,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

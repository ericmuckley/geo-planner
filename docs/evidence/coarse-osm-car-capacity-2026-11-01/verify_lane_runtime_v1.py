"""Portable lane spatial/geometry/storage/history proof; no large asset reads."""
import json
import re

from verify_lane_graph_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    assert stage('lane-derived-controls',True)['controls']==dict(tests=37,successful=True,failures=0,errors=0,skips=0)
    spatial=stage('lane-derived-spatial',True)
    assert spatial['nativeResult']['arcs']==spatial['independentAudit']['directedArcsCostsPhysicalReversesChecked']==9826630
    assert spatial['independentAudit']['forbiddenTurnPairsChecked']==258059 and spatial['independentAudit']['spatialCellsChecked']==56970
    geometry=stage('lane-derived-geometry',True);g=geometry['independentAudit']
    assert (g['physicalSpansChecked'],g['directedSourceCostsChecked'],g['interiorPositionsChecked'],g['longSpansChecked'])==(6586963,9826630,695702,533417)
    assert g['runtimeBytes']==geometry['nativeResult']['runtimeBytes']==11560158
    assert g['maximumDiscardedSourcePointErrorMeters']<=100 and g['maximumDiscardedSourceTimeErrorMs']<=10000
    for kind,fields,raw,compressed in [('core',13,129632810,46272129),('geometry',7,11560158,7955992)]:
        packed=stage('lane-codec-'+kind);audit=stage('lane-codec-audit-'+kind)
        assert packed['fields']==audit['fields']==fields
        assert packed['rawBytes']==audit['bytesIndependentlyDecodedAndCompared']==raw
        assert packed['compressedBytes']==audit['compressedBytes']==compressed
        assert audit['nativeProducerExecutions']==audit['routingQueries']==0
    assert stage('lane-context-controls',True)['controls']==dict(tests=22,successful=True,failures=0,errors=0,skips=0)
    context=stage('lane-context-run',True);a=context['independentAudit']
    assert (context['completePreArcsMapped'],context['retainedArcsMapped'])==(9882872,9826630)
    assert (context['contextStates'],context['prohibitedExitArcRecords'],context['activeTriggerPairs'])==(34179,22643,22628)
    assert context['contextRuntimeBackingBytes']==1786511 and context['additionalQueryLabelBytes']==136716
    assert context['supportedSourceTurnPairs']==235258 and context['multiPreEntryPairs']==2614
    assert context['retainedStaticForbiddenPairs']==237741 and context['finalForbiddenUnionPairsChecked']==258059
    assert a['oldFinalTurnUnionExact'] and a['allContextStatesSourceMapped']==34179 and a['allActiveEntryTriggerPairsChecked']==22628
    assert context['routingQueries']==0 and context['requiresTurnContextSearch']
    wire=stage('lane-context-wire');audit=stage('lane-context-wire-audit')
    assert wire['copiedCoreFieldsByteIdentical']==audit['copiedCoreFieldsByteIdentical']==12 and wire['replacedCoreFields']==1
    assert wire['contextRawBytes']==audit['contextBytesIndependentlyCompared']==1786511
    assert audit['contextFieldsIndependentlyDecoded']==6 and audit['replacementCoreBytesIndependentlyDecoded']==1426446
    assert wire['combinedCoreAndContextCompressedBytes']==audit['combinedCoreAndContextCompressedBytes']==46729321
    for filename,count in [('lane-access-controls-v1.txt',20),('lane-context-runtime-controls-v1.txt',14)]:
        log=(HERE/filename).read_text()
        for label,value in [('tests',count),('pass',count),('fail',0),('skipped',0),('cancelled',0)]:assert re.search(r'\b'+label+' '+str(value)+r'\b',log)
    prefixes=['lane-derived-controls','lane-derived-spatial','lane-derived-geometry','lane-codec-core','lane-codec-geometry',
              'lane-codec-audit-core','lane-codec-audit-geometry','lane-context-controls','lane-context-run','lane-context-wire','lane-context-wire-audit']
    for prefix in prefixes:total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==8365862912 and 64500000000+total+104857600+536870912<72*1024**3
    return {**result,'status':'complete_lane_spatial_geometry_storage_context_source_proofs_passed',
            'laneSpatialAndPaidGeometrySourceAudited':True,'laneAllRawStorageBytesIndependentlyCompared':141192968,
            'laneCoreGeometryCompressedBytes':54228121,'laneContextStatesSourceAudited':34179,
            'laneContextWireBytesIndependentlyCompared':True,'laneAccessGeographyControls':20,'laneRuntimeContextControls':14,
            'uniqueClosedRoots':293,'newUniqueClosedAllocationBytes':total,'laneQueryOrAccuracyMeasured':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

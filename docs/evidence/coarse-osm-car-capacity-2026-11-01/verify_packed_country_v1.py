"""Portable full national packed encoding and independent every-field audit proof."""
import json
from verify_preparation_v1 import closed, load


def verify():
    root,_=closed('packed-country','controls','v1',0)
    assert load(root/'controls.json')=={'tests':12,'successful':True,'failures':0,'errors':0,'skips':0}
    assert load(root/'result.json')['directedCostsAndPhysicalReversesChecked']==75137
    root,_=closed('packed-country','run','v1',0);result=load(root/'result.json')
    assert (result['vertices'],result['postClosureArcs'],result['forbiddenTurnPairs'],result['payloadBytes'])==(5731903,9620680,224675,127854983)
    assert result['costOverflowEntries']==2 and result['reverseOverflowEntries']==0 and result['maximumOutDegree']==21
    assert not result['snappingAndGeographyBuilt'] and not result['etaQualified'] and not result['vercelQualified'] and not result['modelChanged']
    artifacts=load(root/'artifacts.json');assert len(artifacts)==11 and sum(row['bytes'] for row in artifacts.values())==127854983
    root,_=closed('packed-country','audit','v1',0);audit=load(root/'result.json')
    assert audit['status']=='independent_complete_packed_routing_audit_passed'
    assert (audit['verticesChecked'],audit['directedCostsAndPhysicalReversesChecked'],audit['sourceTurnRecordsChecked'],audit['forbiddenTurnPairsChecked'])==(5731903,9620680,409178,224675)
    assert audit['sourcePbfReads']==audit['nativeLibraryExecutions']==audit['sourceConstructorExecutions']==audit['networkRequests']==audit['applicationDbReads']==0
    return {'allNationalPackedVerticesChecked':5731903,'allNationalDirectedCostsAndReversesChecked':9620680,
            'allForbiddenTurnPairsChecked':224675,'payloadBytes':127854983,'appOrEtaQualified':False,
            'reads':'Small mirrored records and bound code only; no ignored graph/source/native/worker/provider/application DB.'}


if __name__=='__main__':print(json.dumps(verify()))

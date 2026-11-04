"""Portable saved-shore, exact geography and coarse connection proof."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_paid_positions_v1 import verify as positions


def verify():
    positions()
    shore=load(host_closed('origin-shore-screen')/'report.json')
    assert shore['origins']==56 and shore['originOnMask']==shore['footOnMask']==shore['continuousMaskLand']==55
    geo=host_closed('car-geography');manifest=load(geo/'manifest.json')
    assert manifest['rawBytes']==586274 and manifest['compressedBytes']==197528
    plan=load(HERE/'car-geography-independent-plan-v1.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    independent=load(HERE/'car-geography-independent-v1.json')
    assert independent['recipeSha256']==sha(HERE/'car-geography-independent-plan-v1.json')
    assert independent['manifestSha256']==sha(geo/'manifest.json') and independent['status']=='independent_complete_unchanged_geography_equality_passed'
    assert independent['points']==27784 and independent['rings']==312 and independent['producerExecutions']==0
    controls=load(HERE/'origin-connection-controls-v1.json')
    for name,pin in controls['codeBindings'].items():assert sha(REPO/name)==pin,name
    assert controls['tests']==6 and controls['successful'] and controls['failures']==controls['skips']==0
    assert controls['consoleSha256']==sha(HERE/'origin-connection-controls-v1.txt') and controls['designSha256']==sha(HERE/'origin-connection-design-v1.json')
    result=load(host_closed('origin-connections-profile')/'report.json')
    assert result['status']=='host_all_saved_origin_connections_passed' and result['origins']==len(result['rows'])==56
    assert result['strictMaskConnections']==55 and result['modeledRoadMaskAllowances']==1
    assert result['combinedCompressedDataBytes']==53952814 and result['coreAndGeometryBackingBufferBytes']==140869261
    for row in result['rows']:
        connection=row['connection'];assert 0<=connection['connectorTicks']<=345600
        if connection['connectorMeters']>0:assert connection['connectorTicks']>0
        if not row['strictMaskConnection']:assert connection['kind']=='modeled-road' and connection['snap']['distanceMeters']<=1
    assert not result['modelChanged']
    return {'allSavedInputConnections':56,'strictContinuousMaskConnections':55,'explicitOnModeledRoadMaskAllowances':1,
            'combinedCompressedDataBytes':53952814,'hostLoadAndFirstConnectionMsIncludingGc':result['hostFirstLoadAndConnectionMsIncludingGc'],
            'prototypeProcessHeapAndArrayBufferBytes':result['prototypeProcessManagedBytes'],
            'actualShoreOrEtaOrAppQualified':False,
            'reads':'Small mirrored records and bound code only; no large graph/source/native/Docker/provider/DB.'}


if __name__=='__main__':print(json.dumps(verify()))

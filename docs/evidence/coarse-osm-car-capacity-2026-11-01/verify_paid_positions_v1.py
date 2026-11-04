"""Portable paid-position software qualification; no graph or producer execution."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_geometric_snap_v1 import verify as geometric


def verify():
    geometric()
    controls=load(HERE/'paid-position-controls-v1.json')
    for name,pin in controls['codeBindings'].items():assert sha(REPO/name)==pin,name
    assert controls['tests']==8 and controls['successful'] and controls['failures']==controls['skips']==0
    assert controls['consoleSha256']==sha(HERE/'paid-position-controls-v1.txt')
    assert controls['designSha256']==sha(HERE/'paid-position-design-v1.json')
    report=load(host_closed('paid-positions-profile')/'report.json')
    assert report['status']=='host_national_paid_position_software_checks_passed'
    assert report['draws']==len(report['rows'])==32 and report['endpointComparisons']==report['interiorQueries']==64
    assert report['retainedDataBackingBufferBytes']==140869261
    for row in report['rows']:
        assert len(row['checks'])==2
        for check in row['checks']:
            assert check['endpoint']['ticks']==check['endpointReference']['ticks']
            if check['forward']:assert check['interior']['ticks'] is not None and check['interior']['ticks']>0
    assert [query['ticks'] for query in report['originalQueries']]==[296763,256312,None,None]
    assert not report['modelChanged']
    return {'seededUnfilteredPhysicalSpans':32,'exactEndpointComparisons':64,'paidInteriorQueries':64,
            'originalNationalQueriesPreserved':4,'retainedDataBackingBufferBytes':140869261,
            'hostSoftwareQualificationMs':report['hostTotalMs'],
            'originConnectorOrEtaOrAppQualified':False,
            'reads':'Small mirrored records and bound code only; no large graph/source/native/Docker/provider/DB.'}


if __name__=='__main__':print(json.dumps(verify()))

"""Portable nearest-modeled-road proof from closed small records only."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_paid_geometry_v1 import verify as paid


def verify():
    paid()
    controls=load(HERE/'geometric-snap-controls-v1.json')
    for name,pin in controls['codeBindings'].items():assert sha(REPO/name)==pin,name
    assert controls['tests']==8 and controls['successful'] and controls['failures']==controls['skips']==0
    assert controls['consoleSha256']==sha(HERE/'geometric-snap-controls-v1.txt')
    assert controls['designSha256']==sha(HERE/'geometric-snap-design-v1.json')
    root=host_closed('geometric-snap-profile');report=load(root/'report.json');plan=load(root/'execution-plan.json')
    assert report['status']=='host_national_geometric_snap_profile_and_complete_first_origin_scan_passed'
    assert report['origins']==len(report['queries'])==len(plan['origins'])==56 and report['sourceRequests']==48
    assert report['retainedDataBackingBufferBytes']==140869261 and report['combinedCompressedBytes']==53755286
    for query,expected in zip(report['queries'],plan['origins']):
        assert query['coordinate']==expected['coordinate'] and query['stats']['longSpansExamined']==529205
        assert 0<=query['snap']['forwardProgress']<=1 and 0<=query['snap']['backwardProgress']<=1
    complete=report['completeEnumeration'];first=report['queries'][0]['snap']
    assert complete['physicalSpans']==6408084 and complete['segments']==7098552
    for key in ('canonicalArc','segment','distanceMeters','segmentFraction'):assert first[key]==complete['result'][key]
    assert not report['modelChanged']
    times=sorted(query['snapMs'] for query in report['queries'])
    return {'savedEndpointsProfiled':56,'generatedExhaustiveQueries':500,'independentSphericalControls':2000,
            'firstOriginCompleteCountrySpanEnumeration':6408084,'hostSnapMsRange':[times[0],times[-1]],
            'hostLoadAndFirstSnapMsIncludingGc':report['hostFirstLoadAndSnapMsIncludingGc'],
            'legalOriginConnectionOrEtaOrAppQualified':False,
            'reads':'Small mirrored records and bound code only; no large graph/source/native/Docker/provider/DB.'}


if __name__=='__main__':print(json.dumps(verify()))

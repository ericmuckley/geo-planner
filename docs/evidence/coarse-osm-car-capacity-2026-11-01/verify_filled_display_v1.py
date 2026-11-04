"""Portable completed finer-display proof; never recomputes a national field."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_road_field_v3 import verify as fields


def verify():
    fields()
    control=load(HERE/'filled-display-controls-v1.json')
    assert control['tests']==8 and control['successful'] and control['failures']==control['skips']==0
    assert sha(HERE/'filled-display-controls-v1.txt')==control['consoleSha256']
    assert sha(HERE/'filled-display-design-v1.json')==control['designSha256']
    for name,pin in control['codeBindings'].items():assert sha(REPO/name)==pin,name
    root=host_closed('filled-display-profile');report=load(root/'report.json');plan=load(root/'execution-plan.json')
    assert report['status']=='host_national_filled_display_software_profile_passed'
    assert report['fieldsAndDisplays']==len(report['rows'])==32
    assert report['maximumDisplayBackingBufferBytes']==66494595<67108864
    assert plan['newClosedAllocationBytes']==2302255104
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes']<64*1024**3
    assert load(HERE/'filled-display-host-absence-v1.json')['owners']==[]
    baseline=report['afterLoad']['arrayBuffers'];local=0
    original=load(HERE/'road-field-profile-raw-v3/report.json')
    for row in report['rows']:
        old=next(value for value in original['rows'] if value['sourceId']==row['sourceId'] and value['minutes']==row['minutes'])
        assert row['fieldStats']==old['stats']
        assert row['fieldLabelsUnchanged'] and row['vertexSummariesRestored']
        assert row['afterRelease']['arrayBuffers']<=baseline+1048576
        assert row['frame']['width']*row['frame']['height']<=2500000
        assert 5000<=row['frame']['step']<=25000
        if row['minutes']==120:assert row['frame']['step']==5000
        stats=row['stats'];witness=row['witnesses']
        assert stats['maximumBackingBufferBytes']==66494595 and stats['borrowedVertexWorkspace']
        assert stats['samples']<=30000000 and stats['maximumHeapEntries']<=1000000 and stats['retries']==[]
        assert stats['edges']<=400000 and stats['rings']<=4096 and stats['vertices']<=100000
        assert stats['jsonBytes']==row['output']['bytes']<=3000000
        assert stats['localCells']==witness['localCells']==witness['roadSeeds']+witness['inputSeeds']+witness['exactParentLinks']
        local+=witness['exactParentLinks']
    assert report['afterQueries']['arrayBuffers']<=baseline+1048576
    closed=load(HERE/'filled-display-profile-closed-v1.json')
    ranges={str(h):{'stepDegrees':[min(row['frame']['step'] for row in report['rows'] if row['minutes']==h)/1e6,max(row['frame']['step'] for row in report['rows'] if row['minutes']==h)/1e6],
                   'displayMs':[min(row['stats']['displayMs'] for row in report['rows'] if row['minutes']==h),max(row['stats']['displayMs'] for row in report['rows'] if row['minutes']==h)]} for h in plan['horizonsMinutes']}
    return {'fieldsAndFilledDisplays':32,'exactLocalParentSums':local,'maximumScratchBackingBytes':66494595,
            'hostLoadConnectionFirstFieldDisplayMsIncludingValidationWriteAndGc':report['hostFirstLoadConnectionFieldDisplayMsIncludingGc'],
            'ranges':ranges,'newUniqueClosedAllocationBytes':2302255104+closed['usage']['conservativeAllocatedBytes'],
            'etaOrCompleteAppQualified':False,'reads':'Small mirrored records/bound code only; no graph/PBF/native/Docker/provider/DB or output replay.'}


if __name__=='__main__':print(json.dumps(verify()))

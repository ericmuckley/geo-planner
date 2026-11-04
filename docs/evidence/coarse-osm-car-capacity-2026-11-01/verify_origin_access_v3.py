"""Portable initial-access component proof, preserving capacity failure evidence."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_display_timing_v2 import verify as prior_candidate


def verify():
    prior_candidate()
    for version,tests in [('v2',6),('v3',7)]:
        control=load(HERE/f'origin-access-controls-{version}.json')
        assert control['tests']==tests and control['successful'] and control['failures']==control['skips']==0
        assert control['generatedExhaustiveInputs']==100 and control['consoleSha256']==sha(HERE/f'origin-access-controls-{version}.txt')
        design='origin-access-design-v2.json' if version=='v2' else 'origin-access-capacity-design-v3.json'
        assert control['designSha256']==sha(HERE/design)
        for name,pin in control['codeBindings'].items():assert sha(REPO/name)==pin,name
    failed=load(HERE/'origin-access-profile-closed-v2.json');oldroot=HERE/'origin-access-profile-raw-v2'
    assert failed['terminalRecord']=='failure.json'
    for name,pin in failed['roster'].items():
        if pin['ignoredLargeAsset']:continue
        assert sha(oldroot/name)==pin['sha256'] and (oldroot/name).stat().st_size==pin['bytes']
    assert 'connection cap exceeded' in load(oldroot/'failure.json')['error']
    oldplan=load(oldroot/'execution-plan.json')
    for name,pin in oldplan['bindings'].items():assert sha(REPO/name)==pin,name
    root=host_closed('origin-access-profile','v3');report=load(root/'report.json');plan=load(root/'execution-plan.json')
    assert report['status']=='completed_all_endpoint_initial_access_profile'
    assert report['inputs']==len(report['rows'])==79
    assert (report['supported'],report['unsupported'],report['originalPrimaryConnectionsPreserved'])==(78,1,78)
    assert report['maskOmissionAllowanceInputs']==0 and sum(row['offMask'] for row in report['rows'])==2
    assert (report['reusedEndpointCollections'],report['newEndpointCollections'])==(56,23)
    assert report['maximumConnections']==1794<=4096 and report['totalConnections']==9804
    assert len(plan['reusedEndpoints'])==56
    for previous in plan['reusedEndpoints']:
        name=previous['path'].split('/')[-1];assert previous['sha256']==failed['roster'][name]['sha256']
    original=load(REPO/plan['originalConnections'])
    for row,old in zip(report['rows'],original,strict=True):
        assert row['coordinate']==old['coordinate'] and row['originalSupported']==(old['connection'] is not None)
        assert row['connections']<=4096 and row['connections']>0 if row['supported'] else row['connections']==0
        if row['originalSupported']:assert row['primaryPreserved']
    closed=load(HERE/'origin-access-profile-closed-v3.json')
    return {'inputs':79,'supported':78,'unsupportedRetained':1,'initialChoices':9804,'maximumChoices':1794,
            'originalPositiveConnectionsPreserved':78,'priorCollectionsReusedWithoutCollection':56,
            'newUniqueClosedAllocationBytes':2322522112+failed['usage']['conservativeAllocatedBytes']+closed['usage']['conservativeAllocatedBytes'],
            'multiSourceFieldOrEtaOrAppQualified':False,'reads':'Small bound code/mirrored records only; no graph/PBF/native/Docker/provider/DB or asset replay.'}


if __name__=='__main__':print(json.dumps(verify()))

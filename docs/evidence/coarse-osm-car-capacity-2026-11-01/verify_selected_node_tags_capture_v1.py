"""Saved selected-tag qualification receipts; no ignored assets or source execution."""
import json

from verify_blocked_node_causes_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def build_stage(kind):
    prefix='selected-node-tags-'+kind
    closed=load(HERE/(prefix+'-closed-v1.json'))
    root=HERE/(prefix+'-raw-v1')
    for name,pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']:
            path=root/name
            assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256'],name
    plan=load(root/'execution-plan.json')
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    final=load(root/'container-result.json')
    assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
    assert load(root/'run-summary.json')['exitCode']==0 and load(root/'cleanup.json')['independentInspectAbsent']
    metrics=load(root/'metrics.json')
    assert metrics['memory.swap.max']=='0' and int(metrics['memory.peak'])<=4294967296
    assert 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
    assert load(HERE/(prefix+'-cleanup-v1.json'))['independentlyAbsent']
    return load(root/'result.json'),closed


def verify():
    result=previous()
    binary,build=build_stage('build')
    controls,tested=build_stage('controls')
    assert binary['artifactBytes']==2007120 and binary['artifactSha256']=='cb4874aa8dc32fee758ac57b273711ee0e69abf120c70edf4be127fd1cd335d9'
    assert {key:controls[key] for key in ('tests','successful','failures','errors','skips')}==dict(tests=35,successful=True,failures=0,errors=0,skips=0)
    captured=stage('selected-node-tags-source-capture-v1',True)
    assert captured['selectedTags']['requestedNodes']==captured['selectedTags']['selectedRecords']==97
    assert captured['causeCounts']=={'restriction-only':16,'base-node':81}
    assert captured['allCached97OriginalTagsExact'] and captured['sourcePbfScans']==0 and not captured['unknownRawNodeIds']
    assert not captured['sourcePermissionsOrPricesChanged'] and not captured['appActivated']
    raw=HERE/'selected-node-tags-source-capture-v1-raw-v1'
    assert load(raw/'audit-controls.json')==dict(tests=7,successful=True,failures=0,errors=0,skips=0)
    receipt=load(raw/'receipt.json')
    assert receipt['nativeEof'] and receipt['counts']=={'node':97} and receipt['pythonProjectionFrames']==0
    closed=load(HERE/'selected-node-tags-source-capture-v1-closed-v1.json')
    for name,pin in captured['artifacts'].items():
        assert all(closed['roster'][name][key]==pin[key] for key in ('bytes','sha256'))
    total=result['newUniqueClosedAllocationBytes']+sum(c['usage']['conservativeAllocatedBytes'] for c in (build,tested,closed))
    assert total==9390870528
    return {**result,'status':'selected_original_tag_collector_qualified_full_cached_parity_passed',
            'nativeCollectorLinuxTests':35,'independentTagAuditAndReaderControls':7,
            'cachedOriginalNodeTagsExactlyReplayed':97,'nationalOriginalTagsMeasured':False,
            'registeredClosedRoots':334,'newUniqueClosedAllocationBytes':total,
            'ignoredAssetsReadOrProducerExecutions':0,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

"""Saved full-source tag-reader qualification; no large source/artifact reads."""
import json

from verify_default_timing_screen_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def build_stage(kind):
    prefix='selected-way-tags-'+kind;closed=load(HERE/(prefix+'-closed-v1.json'));root=HERE/(prefix+'-raw-v1')
    for name,pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    plan=load(root/'execution-plan.json')
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    final=load(root/'container-result.json')
    assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
    assert load(root/'run-summary.json')['exitCode']==0 and load(root/'cleanup.json')['independentInspectAbsent']
    assert load(HERE/(prefix+'-cleanup-v1.json'))['independentlyAbsent']
    metrics=load(root/'metrics.json')
    assert metrics['memory.swap.max']=='0' and int(metrics['memory.peak'])<=4294967296
    assert 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
    return load(root/'result.json'),closed


def verify():
    result=previous();binary,built=build_stage('build');controls,tested=build_stage('controls')
    assert binary['artifactBytes']==2007096 and binary['artifactSha256']=='0b84387ebb9875f1b86c4e0a9be450618246635b1023cad45784144b666873a7'
    assert {k:controls[k]for k in ('tests','successful','failures','errors','skips')}==dict(tests=35,successful=True,failures=0,errors=0,skips=0)
    prefix='selected-way-tags-source-capture-v1'
    captured=stage(prefix,True);captured_closed=load(HERE/(prefix+'-closed-v1.json'))
    assert captured['selectedTags']['requestedWays']==captured['selectedTags']['selectedRecords']==616
    assert captured['allCached616OriginalTagsExact'] and captured['sourcePbfScans']==0
    assert load(HERE/(prefix+'-raw-v1/audit-controls.json'))==dict(tests=8,successful=True,failures=0,errors=0,skips=0)
    receipt=load(HERE/(prefix+'-raw-v1/receipt.json'))
    assert receipt['nativeEof'] and receipt['counts']=={'way':616} and receipt['pythonProjectionFrames']==0
    failed=load(HERE/'selected-way-tags-source-run-v1-closed-v1.json')
    failed_root=HERE/'selected-way-tags-source-run-v1-raw-v1'
    assert failed['terminalRecord']=='failure.json' and 'receipt.json' not in failed['roster']
    for name,pin in failed['roster'].items():
        if not pin['ignoredLargeAsset']:assert sha(failed_root/name)==pin['sha256']
    original=load(failed_root/'execution-plan.json')
    for name,pin in original['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    assert load(failed_root/'failure.json')['error']=="PilotError('Selected original way output stable')"
    assert load(failed_root/'cleanup.json')['independentInspectAbsent']
    assert load(failed_root/'run-summary.json')['exitCode']==2
    report=stage('selected-way-tags-audit-v2')
    audited=load(HERE/'selected-way-tags-audit-v2-closed-v1.json')
    assert report['selectedTags']==dict(requestedWays=52743,selectedRecords=52743,encodedBytes=19386808,tagUtf8Bytes=12977728)
    assert report['allCached616OriginalTagsExact'] and not report['unknownRawWayIds']
    assert report['sourcePbfScans']==report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['originalNumericSourceReceiptPersisted'] and not report['sourcePermissionsOrPricesChanged']
    assert report['savedBinary']['sha256']==failed['roster']['original-way-tags.bin']['sha256']
    assert report['causeCounts']=={'lane-access':8087,'access':14582,'conditional-or-way-restriction':9555,'None':19060,'area-ford-driveway-parking':582,'unsupported-oneway':576,'unsupported-speed':298,'directional-access':3}
    review=load(HERE/'selected-way-tags-source-stop-review-v1.json')
    assert not review['originalNumericSourceReceiptPersisted'] and not review['sourceReplayRequired']
    for name,pin in report['artifacts'].items():
        assert all(audited['roster'][name][key]==pin[key]for key in ('bytes','sha256'))
    stopped=load(HERE/'selected-way-tags-capture-preinput-stop-v1.json')
    assert not stopped['workerCreated'] and not stopped['outputRootCreated'] and not stopped['recipeChanged']
    total=result['newUniqueClosedAllocationBytes']+sum(c['usage']['conservativeAllocatedBytes']for c in (built,tested,captured_closed,failed,audited))
    assert 64500000000+total+104857600<72*1024**3
    return {**result,'status':'all52743_original_excluded_major_way_tags_source_audited',
            'registeredClosedRoots':382,'newUniqueClosedAllocationBytes':total,
            'nativeWayReaderLinuxControls':35,'independentWayAuditControls':8,'correctedStabilityAuditControls':10,
            'knownOriginalSelectedWayTags':52743,'unknownOriginalSelectedWayTags':0,
            'all616CachedOriginalWayTagsExact':True,'ignoredAssetsReadOrProducerExecutions':0,
            'currentExclusionMembershipInterpreted':False,'sourcePassGuardEvidence':'Sealed control flow/failure location; original numeric source/native receipts missing, not fabricated','accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))

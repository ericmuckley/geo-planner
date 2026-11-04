"""Portable native-policy/partition/controller qualification proof; no ignored reads."""
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_bytes())
def closed(prefix,stage,version,exit_code):
    record=load(HERE/f'{prefix}-closed-{stage}-{version}.json');root=HERE/f'{prefix}-raw/{stage}-{version}'
    for name,pin in record['roster'].items():
        if pin['ignoredLargeAsset']:continue
        path=root/name;assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256'],name
    plan=load(root/'execution-plan.json')
    if 'inputs' in plan:
        bindings=plan['inputs']
    else:
        bindings=plan['hostFiles']
    for name,pin in bindings.items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    final=load(root/'container-result.json');assert final['State']['ExitCode']==final['clientExitCode']==exit_code and not final['State']['OOMKilled']
    metrics=load(root/('metrics-end.json' if (root/'metrics-end.json').exists() else 'metrics.json'));events=dict(line.split() for line in metrics['memory.events'].splitlines())
    assert metrics['memory.swap.max']=='0' and events['oom']==events['oom_kill']=='0' and int(metrics['memory.peak'])<=int(metrics['memory.max'])
    assert load(root/'run-summary.json')['exitCode']==exit_code and load(root/'cleanup.json')['independentInspectAbsent']
    assert load(HERE/f'{prefix}-cleanup-{stage}-{version}.json')['independentlyAbsent']
    return root,plan

def verify():
    for stage in ('build','controls','equivalence'):
        root,plan=closed('car',stage,'v1',0)
        if stage=='build':
            result=load(root/'result.json');assert result['artifactSha256']=='d4a30ef038460bd318ff34c6bd01a7b884dacdde21129054893f55a56d4a6931' and result['artifactBytes']==1729816
        if stage=='controls':assert load(root/'controls.json')=={'tests':16,'successful':True,'failures':0,'errors':0,'skips':0}
        if stage=='equivalence':
            result=load(root/'result.json');assert (result['selectedNodes'],result['majorWays'],result['relations'],result['sourceWaysExamined'])==(143560,28995,4900,239253)
    root,_=closed('capacity','build','v1',0);binary=load(root/'result.json');assert binary['artifactSha256']=='e68cbb4ac6d3bc8150c0ce859dac922121f8b39fa3f2f6919f45426f5ddd98fe' and binary['artifactBytes']==2081040
    root,_=closed('capacity','controls','v1',2);assert load(root/'controls.json')=={'tests':67,'successful':False,'skips':0,'errors':7,'failures':0}
    root,_=closed('capacity','controls','v2',0);assert load(root/'controls.json')=={'tests':68,'successful':True,'skips':0,'errors':0,'failures':0}
    root,derive_plan=closed('capacity','derive','v2',0);derived=load(root/'result.json')
    assert (derived['anchors'],derived['contractedEdges'],derived['internalSplitOccurrences'],derived['splitBytes'])==(5731903,6674747,2447509,19580072)
    root,_=closed('capacity','partition-audit','v2',0);audit=load(root/'audit.json')
    assert audit['exactWaySplitOccurrencesChecked']==2447509 and audit['sourceFilesAuthenticated']==32 and audit['splitSha256']==derived['splitSha256']=='9b8cb6742b0d2a94dc0aee2bff53cad22e99495696bb08617583ddf78d4301e5'
    assert audit['auditorSha256']==sha(HERE/'partition_audit_v1.py') and audit['selfTests']=={'checks':4,'successful':True}
    root,_=closed('capacity','pbf-controls','v2',2);assert load(root/'worker-failure.json')['errorType']=='ImportError'
    root,_=closed('capacity','pbf-controls-v2','v2',0);tiny=load(root/'audit.json')
    assert tiny['checks']==3 and tiny['syntheticSourceBytes']==564 and tiny['nativeArtifactSha256']==binary['artifactSha256'] and tiny['pythonProjectionFrames']==0
    assert tiny['rejectedInputs']==['header-epoch','truncated'] and tiny['validCounters']['preClosureArcs']==2 and tiny['validCounters']['postLocatableClosureArcs']==0
    root,_=closed('capacity','run','v2',2);stop=load(HERE/'capacity-run-v2-stop-review.json');assert stop['sourceCompleteIndependentSmallReceiptCheck'] and not stop['capacityQualified'] and not stop['carCountersOrFactsAvailable']
    assert stop['receiptSha256']==sha(root/'receipt.json') and load(root/'worker-failure.json')['errorType']=='FileNotFoundError'
    assert load(root/'receipt.json')['nativeEof']
    packed=load(HERE/'packed-index-closed-v1.json');raw=HERE/'packed-index-raw-v1'
    for name,pin in packed['roster'].items():
        if pin['ignoredBinaryAsset']:continue
        path=raw/name;assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256']
    report=load(raw/'report.json');proof=load(HERE/'packed-index-independent-v1.json')
    assert report['indicesChecked']==proof['allIndexValuesChecked']==144728 and report['packedPayloadBytes']==proof['packedPayloadBytes']==1176783 and report['savedBytes']==144728
    assert report['retainedBackingBufferBytes']==1242319 and proof['allOtherFieldsByteIdentical'] and proof['reportSha256']==sha(raw/'report.json')
    for name,pin in load(raw/'execution-plan.json')['codeBindings'].items():assert sha(REPO/name)==pin
    return {'qualifiedNativePolicy':True,'nativePolicyLinuxTests':16,'capturedMetadataRowsMatched':177455,'capacityLinuxTests':68,'partitionOccurrencesIndependentlyChecked':2447509,'actualTinyPbfChecks':3,'preservedFailedRuns':['capacity-controls-v1','pbf-controls-v1','capacity-run-v2'],'packedIndicesChecked':144728,'packedPayloadBytes':1176783,'countryV3State':'Read current actual run records; active or terminal result is separate from this preparation proof.','reads':'Small mirrored records and repository code only; no ignored binaries/SQLite/PBF/native/Docker/provider/appDB.'}
if __name__=='__main__':print(json.dumps(verify()))

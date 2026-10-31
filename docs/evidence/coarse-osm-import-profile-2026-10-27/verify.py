"""Saved offline profile proof. No Docker, network, native scan or producer replay."""
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import statistics
import sys

folder=Path(__file__).resolve().parent
repo=folder.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def bindings(mapping,root):
    for name,digest in mapping.items(): assert sha(root/name)==digest,name

manifest=load(folder/'sha256.json')
assert set(manifest)=={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name!='sha256.json'}
bindings(manifest,folder)
parent=repo/load(folder/'parent-proof.json')['path']
assert sha(parent/'sha256.json')==load(folder/'parent-proof.json')['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()): runpy.run_path(str(parent/'verify.py'),run_name='__main__')
one=load(folder/'execution-plan.json');two=load(folder/'correction-plan-v2.json')
assert sha(folder/'execution-plan.json')=='85da7b36a24bea4bf5c3aa2f3705228b7d8448d372fe51317ae439e96e697373'
assert sha(folder/'correction-plan-v2.json')=='22d2160b410330f506df99b763d6277b9a658fdf4e362a39485f41da94687cc1'
assert one['phase']=='offline_import_profile_v1' and two['phase']=='offline_import_profile_v2'
assert len(one['inputs'])==223 and len(one['workerFiles'])==210 and len(two['inputs'])==242 and len(two['workerFiles'])==213
for key in ('caps','cases','extractConfig','source','sourceReadBounds','imageId','site','runtime','designHypothesis'):
    assert one[key]==two[key],key
for plan in (one,two): bindings({p:s for p,s in plan['inputs'].items() if not p.startswith('data/')},repo)
assert two['correction']['v1NativeObjectVisits']==0 and not two['correction']['sampleOrTimingRetune']
assert two['acceptance']['hostAndLinuxControls']==18 and two['caps']['minimumMedianSpeedup']==1.25
assert two['caps']['sourcePrefixBytes']==2097152 and two['caps']['sampleFrames']==9
assert len(two['extractConfig']['windows'])==21 and two['network']=='none'
checks=load(folder/'verification.json')
assert checks['hostV1ControlsPassed']==17 and checks['linuxV1ControlsFailed']==3
assert checks['hostV2ControlsPassed']==checks['linuxV2ControlsPassed']==18
assert checks['checkPassed197Files'] and checks['typecheckPassed'] and checks['buildPassed']
v1=folder/'v1';v2=folder/'v2'
assert load(v1/'controls.json')=={'tests':17,'successful':False,'failures':3,'errors':0}
assert load(v1/'failure.json')['error']=='Profile synthetic controls failed'
assert load(v1/'run-summary.json')['workerClientExitCode']==2
assert load(v2/'controls.json')=={'tests':18,'successful':True,'failures':0,'errors':0}
for version,root,code in (('v1',v1,2),('v2',v2,0)):
    final=load(root/'container-result.json')['State']
    assert final['ExitCode']==code and not final['OOMKilled'] and not final['Running']
    summary=load(root/'run-summary.json')
    assert summary['workerClientExitCode']==code and summary['hostSecondsIncludingHashAndCleanupBeforeSummary']<600
    assert not summary['networkRequests'] and not summary['wholeExtractionQualified'] and not summary['modelChanged']
    initial=load(root/'container-initial.json');limits=initial['Limits']
    assert limits=={'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{'/tmp':'rw,size=256m'}}
    assert all(not m['writable'] for m in initial['Mounts'] if m['destination']!='/work')
    assert {u['Name']:(u['Soft'],u['Hard']) for u in initial['Ulimits']}=={'core':(0,0),'fsize':(67108864,67108864)}
    guards=load(root/'resource-guards.json')
    assert guards['memory']=={'memoryMaxBytes':4294967296,'swapMaxBytes':0} and guards['tmpBytes']==268435456
    cleanup=load(root/'cleanup.json');independent=load(folder/(version+'-cleanup-audit.json'))
    assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent']
    assert cleanup['ownedContainer']==independent['ownedContainer']
    binding=load(root/'source-binding.json')
    assert binding['bytesHashedBeforeNativeWork']==two['source']['bytes']==12229320016
    assert binding['sha256']==two['source']['sha256'] and binding['md5']==two['source']['md5']
old=load(folder/'v1-output.json');new=load(folder/'v2-output.json')
assert old['files']==13 and old['totalBytes']==83801 and old['nativeObjectVisits']==old['sourcePrefixBytesRead']==0
assert not any(n.endswith(('.pbf','.sqlite')) for n in old['roster'])
assert new['files']==47 and new['totalBytes']==14545627
sample=load(v2/'sample.json');prefix=load(folder/'independent-prefix-audit.json')
assert sample['sampleBytes']==sample['sourcePrefixBytesRead']==377536 and sample['frames']==9
assert sample['sampleSha256']==sample['framing']['sourceSha256']==prefix['sampleSha256']=='8c27122ee2321a320cf33c1f8c678fdd3041fee16621984380e768d4746d38b8'
assert sample['framing']['publisherStateUtc']==two['source']['publisherStateUtc']
assert prefix['sampleMatchesPreservedSourcePrefix'] and prefix['sourcePrefixBytesCompared']==377536 and not prefix['nativeReplay']
result=load(v2/'result.json');cases=result['cases']
assert len(cases)==len(two['cases'])==10 and result['nativeObjectVisits']==640000
for row,case in zip(cases,two['cases']):
    assert [row[k] for k in ('name','mode','implementation','profiled')]==case
    assert row['counts']=={'node':64000} and row['projectedRecordsSha256']==cases[0]['projectedRecordsSha256']
    assert row==load(v2/row['name']/'result.json')
    if row['mode']!='projection': assert row['passes']==[{'label':'profile-index','status':'eof','counts':{'node':64000}}]
    if row['mode']=='index': assert row['indexBytes']==1748992 and row['indexSha256']=='766e482dbd226e8b54126ac8dbd5e102f23d746d7d2bb497f5b02628fa768fec'
plain={kind:[r['secondsIncludingProjectionValidationHashAndIndexAsApplicable'] for r in cases if r['implementation']==kind and not r['profiled']] for kind in ('reference','candidate')}
assert all(len(t)==3 and all(math.isfinite(v) and v>0 for v in t) for t in plain.values())
medians={kind:statistics.median(t) for kind,t in plain.items()}
assert medians==result['medianIndexSeconds'] and medians['reference']/medians['candidate']==result['medianSpeedup']>=1.25
assert result['performanceGatePassed'] and result['equivalentPrefixRecordsAndIndexes'] and result['workerSecondsBeforeSummary']<300
assert not any(result[k] for k in ('wholeSourceEof','wholeExtractionQualified','sourceFeasibilityQualified','usableAttributesQualified','modelChanged','networkRequests'))
for case,expected in (('reference-profile',320000),('candidate-profile',64000)):
    rows=load(v2/case/'profile.json')['topCumulative']
    assert next(r['calls'] for r in rows if r['function']=='utc' and r['file'].endswith('/coarse_osm_records.py'))==expected
    assert next(r['calls'] for r in rows if r['function']=='<built-in method strptime>')==expected
execution=load(folder/'execution-result.json')
assert execution['nativeObjectVisits']==640000 and execution['recordAndIndexHashesMatch']
assert execution['referenceStrptimeCallsInProfiledIndexCase']==320000 and execution['candidateStrptimeCallsInProfiledIndexCase']==64000
assert execution['medianSpeedup']==result['medianSpeedup'] and not execution['wholeExtractionQualified'] and not execution['modelChanged']
local='--local-assets' in sys.argv
if local:
    bindings(two['inputs'],repo)
    for version,inventory in (('v1',old),('v2',new)):
        root=repo/inventory['root'];assert set(inventory['roster'])=={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        for name,record in inventory['roster'].items():
            path=root/name
            assert not path.is_symlink() and path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],name
            if (folder/version/name).is_file(): assert sha(folder/version/name)==record['sha256']
    with (repo/two['source']['path']).open('rb') as stream: raw=stream.read(sample['sampleBytes'])
    assert raw==(repo/new['root']/'prefix.osm.pbf').read_bytes()
print(json.dumps({'recordFiles':len(manifest),'producerFiles':213,'priorSealedRuns':40,'bindingsValid':True,'localAssetsChecked':local,
    'failedV1Files':13,'closedV2Files':47,'hostAndLinuxCorrectedControls':18,'sampleFrames':9,'sampleBytes':377536,
    'nodesPerCase':64000,'nativeObjectVisits':640000,'medianSpeedup':result['medianSpeedup'],'fractionLessIndexTime':1-medians['candidate']/medians['reference'],
    'sourceRequests':0,'ownedRemovalsIndependentlyConfirmed':True,'wholeExtractionQualified':False,'v9Unchanged':True},indent=2))

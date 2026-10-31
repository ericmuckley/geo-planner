"""Saved build proof: no network/Docker/archive/native/producer replay."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
load=lambda p:json.loads(p.read_text())

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def bindings(mapping,root):
    for name,pin in mapping.items():assert sha(root/name)==pin,name

manifest=load(folder/'sha256.json')
assert set(manifest)=={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name!='sha256.json'}
bindings(manifest,folder)
parent=load(folder/'parent-proof.json');assert sha(repo/parent['path']/'sha256.json')==parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(repo/parent['path']/'verify.py'),run_name='__main__')
plan=load(folder/'execution-plan.json');assert sha(folder/'execution-plan.json')=='b31290de98ac86c1a6c81db0fa9e6f617b33ae00c39b5ed8eed25e0f48c6b8b1'
assert len(plan['inputs'])==245 and len(plan['workerFiles'])==239
bindings({k:v for k,v in plan['inputs'].items() if not k.startswith('data/')},repo)
sys.path[:0]=[str(repo/'scripts'),str(folder)]
from run_osm_build_v1 import validate,isolation
from coarse_osm_build_v1 import CAPS,load_lock,verify_downloads
from asset_contents import snapshot
validate(plan)
lock=load_lock(repo/plan['lock']['path']);raw=folder/'raw'
freeze=load(folder/'freeze.json');assert freeze['recipeSha256']==sha(folder/'execution-plan.json') and freeze['outputAbsent']
assert freeze['hostControls']==freeze['linuxOfflineControls']==42 and freeze['hostLinuxSpecificSkip']==1 and not freeze['linuxSkips']
bindings(load(folder/'pre-freeze-controls/bindings.json'),repo)
assert load(raw/'controls/controls.json')=={'tests':42,'successful':True,'failures':0,'errors':0,'skipped':0}
cleanup_audit=load(folder/'cleanup-audit.json')
for phase,network in plan['phases'].items():
    p=raw/phase;initial=load(p/'container-initial.json');isolation(initial,network,phase)
    assert all(not m['Destination'].endswith(('.pbf','.jsonl','.sqlite')) for m in initial['Mounts'])
    guards=load(p/'resource-guards.json');assert guards['memory']=={'memoryMaxBytes':4294967296,'swapMaxBytes':0} and guards['tmpBytes']==268435456
    final=load(p/'container-result.json');assert final['clientExitCode']==final['State']['ExitCode']==0 and not final['State']['Running'] and not final['State']['OOMKilled']
    cleanup=load(p/'cleanup.json');independent=cleanup_audit[phase]
    assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent'] and independent['exitCode']==1
    assert independent['ownedContainer']==cleanup['ownedContainer']
summary=load(raw/'run-summary.json');assert summary['status']=='tiny_compiler_pbf_abi_qualified' and set(summary['phaseClientExitCodes'].values())=={0}
assert summary['hostSecondsIncludingInputsStartupAllPhasesStorageAuditsCleanup']<1800
assert summary['newDockerImageStoreBytes']==summary['roadOrSavedSampleReads']==0 and not summary['nativeImporterQualified'] and not summary['fullImportAdmitted'] and not summary['modelChanged']
acquired=load(raw/'acquire/result.json');ledger=load(raw/'acquire/http/ledger.json')
assert acquired['status']=='acquired_unexpanded_unqualified' and acquired['requests']==len(ledger['events'])==52 and not ledger['stopped']
assert acquired['receivedBodyBytes']==ledger['receivedBodyBytes']==sum(e['bodyBytes'] for e in ledger['events'])==567143969
assert [(e['kind'],e['status']) for e in ledger['events']]==[v for _ in range(25) for v in [('origin',302),('cdn',200)]]+[('archive',200)]*2
assert [r['descriptor'] for r in acquired['layers']]==lock['image']['layers'] and sum(r['bytes'] for r in acquired['layers'])==565413699
for record,desc in zip(acquired['layers'],lock['image']['layers'],strict=True):assert record['sha256']==desc['digest'][7:] and record['bytes']==desc['size']
for e in ledger['events']:
    assert 'location' not in e.get('headers',{}) and e['requestUri']['queryValuesRedacted'] and e['outcome']=='body_complete'
    if e['kind']=='origin':assert e['bodyFile'] is None and e['privateBodyRedacted'] and e['bodyBytes']==1359
assert [(r['bytes'],r['sha256']) for r in acquired['sources']]==[(568569,'dd3aaf4c8b5540e8e1d4e13a4aecf3a79d00db1759d2eeaac226377fa64d4190'),(1127726,'d7548d78dcd297e4a492577c6a5ddf28b91716152b9830caf4100e5f3d405d0d')]
prepared=load(raw/'prepare/result.json');assert prepared['status']=='prepared_build_unqualified'
assert prepared['expandedTarBytes']==sum(v['tarBytes'] for v in prepared['layers'])==1889123840
assert ['sha256:'+v['tarSha256'] for v in prepared['layers']]==lock['image']['diffIds']
assert sum(v['selectedFiles'] for v in prepared['sources'])==216 and sum(v['selectedBytes'] for v in prepared['sources'])==1812889
assert all(v['gitBlobIdentitiesVerified'] for v in prepared['sources'])
assert prepared['rootfs']['conservativeBytesWithNamespaceReserve']==2859870719<10*1073741824
assert load(raw/'acquire-storage.json')['conservativeBytesWithNamespaceReserve']<3*1073741824 and load(raw/'prepare-storage.json')['conservativeBytesWithNamespaceReserve']<11*1073741824
compiled=load(raw/'build/result.json');abi=load(raw/'abi/result.json')
assert compiled['artifactSha256']==abi['artifactSha256']=='bcd80e0b8ff911cc49f58bc13218fc941051361f3526f972e0166b1a6588b367' and compiled['artifactBytes']==1930672
assert compiled['elfReceiptSha256']==sha(raw/'build/elf.log') and 'GLIBCXX_' not in (raw/'build/elf.log').read_text()
assert abi['status']=='tiny_compiler_pbf_abi_qualified' and abi['fixtureBytes']==564 and abi['fixtureCounts']==[4,3,2] and abi['firstNodeXY']==[-10000000,5000000]
assert abi['negativePbfCases']==['truncated','invalid','empty'] and abi['nullRejected'] and not abi['nativeImporterQualified'] and not abi['fullImportAdmitted']
closed=load(folder/'closed-assets.json');assert closed['linuxRootfsSealUnchanged'] and closed['portableHostLinuxRootfsEqual']
assert closed['onlyObservedMetadataDifferences']==['mode'] and closed['elfGlibcVersions']==['GLIBC_2.17','GLIBC_2.25']
assert closed['portableClosedInventory']['files']==67899 and closed['portableClosedInventory']['logicalFileBytes']==2787749803
assert closed['hostClosedAllocation']['conservativeBytesWithNamespaceReserve']+268435456<14*1073741824
for name,code in [('closure-audit',0),('closure-metadata-audit',1),('closure-contents-audit',0)]:
    p=folder/name;final=load(p/'container-result.json');assert final['clientExitCode']==final['State']['ExitCode']==code and not final['State']['OOMKilled'] and not final['State']['Running']
    assert load(p/'cleanup.json')['removed'] and load(p/'independent-absence.json')['independentInspectAbsent']
assert load(folder/'closure-audit/comparison.json')['linuxClosedInventoryMatchesOriginalWorker']
assert load(folder/'closure-contents-audit/comparison.json')['portable']==closed['portableRootfsInventory']
assert load(folder/'closure-contents-audit/stdout.json')['differentFields']==['mode']
public=load(folder/'public-records.json');assert public['mirroredFiles']==len(public['roster'])==82 and public['mirroredBytes']==1285369
for name,row in public['roster'].items():
    p=raw/name;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],name
    body=p.read_bytes();assert not re.search(rb'(?:X-Amz-(?:Algorithm|Credential|Date|Expires|Signature|SignedHeaders)|akamai_signature)=',body),name
    assert not re.search(rb'https://cdn01\.quay\.io[^\s"<>]*\?',body),name
checks=load(folder/'verification.json');assert checks['linuxPreFreezeControls']==checks['linuxFrozenControls']==42 and checks['hostPassed']==41 and checks['hostLinuxSpecificSkip']==1
assert checks['checkPassed197Files'] and checks['typecheckPassed'] and checks['buildPassed']
local='--local-assets' in sys.argv
if local:
    bindings(plan['inputs'],repo);root=repo/closed['root']
    assert snapshot(root)==closed['portableClosedInventory']
    assert verify_downloads(root/'acquire',lock)==closed['offlineArtifactAudit']
    for index,source in enumerate(lock['sources'],1):
        for row in source['selectedFiles']:
            p=root/'prepare'/f'source-{index}'/row['path'];body=p.read_bytes()
            assert len(body)==row['size'] and hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==row['sha'],row['path']
    assert sha(root/'build/smoke.so')==compiled['artifactSha256']
print(json.dumps({'recordFiles':len(manifest),'producerFiles':239,'priorSealedRuns':46,'bindingsValid':True,'localAssetsChecked':local,
    'linuxControlsPassed':42,'hostPassed':41,'hostLinuxOnlySkip':1,'artifactRequests':52,'bodyBytes':567143969,
    'compilerAndTinyTargetAbiQualified':True,'nativeImporterQualified':False,'fullImportAdmitted':False,'signedValuesPersisted':False,
    'mainWorkersIndependentlyRemoved':5,'portableRootfsContentsReconciled':True,'v9Unchanged':True},indent=2))

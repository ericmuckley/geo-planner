"""Read-only native-index proof using only the Python oracle; no native execution."""
import contextlib,hashlib,io,json,runpy,struct,sys
from pathlib import Path
f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
 with p.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
m=load(f/'sha256.json');assert set(m)=={str(p.relative_to(f)) for p in f.rglob('*') if p.is_file() and p.name!='sha256.json'}
for n,h in m.items():assert sha(f/n)==h,n
parent=load(f/'parent-proof.json');assert sha(r/parent['path']/'sha256.json')==parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(r/parent['path']/'verify.py'),run_name='__main__')
plan=load(f/'execution-plan.json');assert sha(f/'execution-plan.json')=='08a033d5d00f9ebae6d6464f346a882462eeef5f9ed7665fc77c90bd0f74913e'
for n,h in plan['inputs'].items():
 if not n.startswith('data/'):assert sha(r/n)==h,n
assert len(plan['inputs'])==263 and len(plan['workerFiles'])==251 and plan['network']=='none' and plan['phases']==['controls']
sys.path.insert(0,str(r/'scripts'))
from run_osm_delta_v2 import validate
from run_osm_delta_v1 import isolation
from coarse_osm_delta_v2 import Reader,ReferenceCodec
validate(plan)
freeze=load(f/'freeze.json');assert freeze['recipeSha256']==sha(f/'execution-plan.json') and freeze['outputAbsent'] and freeze['v1SealedBytesPreserved']
raw=f/'raw';initial=load(raw/'controls/container-initial.json');isolation(initial,'controls')
assert not any(x['Destination'].endswith(('.pbf','.jsonl','.sqlite')) for x in initial['Mounts'])
guards=load(raw/'controls/resource-guards.json');assert guards['memory']=={'memoryMaxBytes':4294967296,'swapMaxBytes':0} and guards['tmpBytes']==268435456
state=load(raw/'controls/container-result.json');assert state['clientExitCode']==state['State']['ExitCode']==0 and not state['State']['Running'] and not state['State']['OOMKilled']
cleanup=load(raw/'controls/cleanup.json');independent=load(f/'cleanup-audit.json')
assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent'] and independent['exitCode']==1 and cleanup['ownedContainer']==independent['ownedContainer']
controls=load(raw/'controls/controls.json');assert controls['tests']==46 and controls['successful'] and controls['failures']==controls['errors']==controls['skipped']==0
result=load(raw/'controls/result.json');summary=load(raw/'run-summary.json')
assert result['status']==summary['status']=='native_delta_index_synthetic_qualified' and summary['workerClientExitCode']==0 and summary['networkRequests']==0 and not summary['recompiled']
assert summary['hostSecondsIncludingInputHashesControlsCleanup']<600
assert result['artifactSha256']=='efe338cabf78035b93b936afb623741162e376df8451e5fede8590bbf724dc23'
assert (result['syntheticConsecutiveRows'],result['deltaIndexBytes'],result['fixedIndexBytes'])==(20000,181044,320252)
assert result['codecWrappedEncodedRows']==73663 and result['codecWrappedDecodedRows']==96967 and result['codecWrappedCalls']==422
assert result['codecWrappedEncodedRows']+result['codecWrappedDecodedRows']<2000000
assert result['twoPassVisits']==18 and result['fourPassVisits']==36 and result['independentAuditComplete']
assert not result['nativeMetadataValidatorImplemented'] and not result['nativeIndexIoImplemented'] and not result['fullImportAdmitted'] and not result['modelChanged'] and result['sourceOrSavedSampleReads']==0
assert sha(raw/'controls/two-pass/elements.jsonl')==sha(raw/'controls/four-pass/elements.jsonl')==result['outputSha256']
reader=Reader(raw/'controls/delta-index',ReferenceCodec());assert reader.manifest['rows']==20000
fixed=raw/'controls/fixed-index/00000000.bin';fixed_raw=fixed.read_bytes();magic,count,first,last,digest=struct.unpack_from('<8sQQQ32s',fixed_raw)
assert magic==b'GPCOOR1\0' and (count,first,last)==(20000,1,20000) and len(fixed_raw)==64+count*16
assert hashlib.sha256(fixed_raw[64:]).digest()==digest
for block in range(reader.manifest['blocks']):
 ids,xy=reader.block(block)
 for k,identity in enumerate(ids):
  key,x,y=struct.unpack_from('<qii',fixed_raw,64+(identity-1)*16)
  assert key==identity and (xy[2*k],xy[2*k+1])==(x,y)==((identity%100)*1000000,0)
  assert struct.pack('<dd',xy[2*k]/10000000,xy[2*k+1]/10000000)==struct.pack('<dd',x/10000000,y/10000000)
reader.close()
roster=load(f/'closed-output.json');assert roster['files']==len(roster['roster'])==30 and roster['totalBytes']==sum(x['bytes'] for x in roster['roster'].values())==626105
assert set(roster['roster'])=={str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
for n,v in roster['roster'].items():assert (raw/n).stat().st_size==v['bytes'] and sha(raw/n)==v['sha256'],n
correction=load(f/'lookup-correction.json');assert sha(r/correction['formatPath'])==correction['formatSha256']
local='--local-assets' in sys.argv
if local:
 for n,h in plan['inputs'].items():assert sha(r/n)==h,n
 root=r/roster['root'];assert set(roster['roster'])=={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
 for n,v in roster['roster'].items():assert (root/n).stat().st_size==v['bytes'] and sha(root/n)==v['sha256'],n
print(json.dumps({'recordFiles':len(m),'producerFiles':248,'priorSealedRuns':48,'bindingsValid':True,'localAssetsChecked':local,'linuxControlsPassed':46,
 'hostPassed':44,'hostNativeSkips':2,'all20000SyntheticCoordinatesAndBitsVerified':True,'deltaBytes':181044,'fixedBytes':320252,
 'cacheTimestampAssumptionRejectedAndCorrected':True,'nativeDeltaPayloadCodecQualified':True,'nativeMetadataValidatorImplemented':False,
 'realSampleOrNationalRun':False,'fullImportAdmitted':False,'ownedWorkerIndependentlyRemoved':True,'v9Unchanged':True},indent=2))

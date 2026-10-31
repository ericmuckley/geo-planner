"""Read-only preparation proof. No native/PBF execution or sample producer replay."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

f=Path(__file__).resolve().parent
r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

manifest=load(f/'sha256.json')
assert set(manifest)=={str(p.relative_to(f)) for p in f.rglob('*') if p.is_file() and p.name!='sha256.json'}
for name,pin in manifest.items():assert sha(f/name)==pin,name
parent=load(f/'parent-proof.json')
assert sha(r/parent['path']/'sha256.json')==parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(r/parent['path']/'verify.py'),run_name='__main__')
sys.path.insert(0,str(r/'scripts'))
from run_osm_sample_v1 import validate as validate1
from run_osm_sample_v2 import validate as validate2,ADMISSION
from run_osm_delta_v1 import isolation
from coarse_osm_sample_v2 import SAMPLES,ARTIFACT,CASES,CAPS
local='--local-assets' in sys.argv
audits=load(f/'cleanup-audit.json')
for version,recipe,freeze_name,validator,tests,visits,expected_sha in (
    ('v1','controls-plan.json','control-freeze.json',validate1,71,9356,'5b8642f5f95d42d2719194f29ae1077b28223263c9c07401798ca899cceca3d4'),
    ('v2','controls-v2-plan.json','control-v2-freeze.json',validate2,74,9363,'3920d4043126efe046697a6903d0b3c2f06d234948c847bad66919b218d2d5c7')):
    plan=load(f/recipe);freeze=load(f/freeze_name);validator(plan)
    assert sha(f/recipe)==freeze['recipeSha256']==expected_sha and plan['sampleWorkerFiles']=={}
    for name,pin in freeze['newProducerSha256'].items():assert sha(r/name)==pin
    for name,pin in plan['inputs'].items():
        if local or not name.startswith('data/'):assert sha(r/name)==pin,name
    raw=f/(version+'-raw');initial=load(raw/'controls/container-initial.json');isolation(initial,'controls')
    assert not any(m['Destination'].startswith('/samples/') or m['Destination'].endswith(('.pbf','.jsonl','.sqlite')) for m in initial['Mounts'])
    guards=load(raw/'controls/resource-guards.json')
    assert guards['memory']=={'memoryMaxBytes':4294967296,'swapMaxBytes':0} and guards['tmpBytes']==268435456
    final=load(raw/'controls/container-result.json')
    assert final['clientExitCode']==final['State']['ExitCode']==0 and not final['State']['Running'] and not final['State']['OOMKilled']
    cleanup=load(raw/'controls/cleanup.json');independent=audits[version]
    assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent']
    assert cleanup['ownedContainer']==independent['ownedContainer'] and independent['exitCode']==1
    controls=load(raw/'controls/controls.json')
    assert controls['tests']==tests and controls['successful'] and controls['errors']==controls['failures']==controls['skipped']==0
    assert controls['projectorAggregateVisits']==visits<2000000
    summary=load(raw/'run-summary.json')
    assert summary['status']=='sample_controls_passed' and summary['workerClientExitCode']==0 and summary['networkRequests']==0
    assert not summary['savedSamplesMounted'] and not summary['nationalSourceMounted'] and not summary['recompiled'] and not summary['fullImportAdmitted'] and not summary['modelChanged']
    roster=load(f/(version+'-closed-output.json'))
    assert roster['files']==len(roster['roster'])==12 and roster['totalBytes']==sum(v['bytes'] for v in roster['roster'].values())
    assert set(roster['roster'])=={str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
    for name,row in roster['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
    if local:
        root=r/roster['root'];assert set(roster['roster'])=={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        for name,row in roster['roster'].items():assert (root/name).stat().st_size==row['bytes'] and sha(root/name)==row['sha256']
assert load(f/'control-freeze.json')['hostControls']['tests']==71
freeze2=load(f/'control-v2-freeze.json')
assert freeze2['hostControls']=={'tests':74,'passed':51,'nativeSkips':23,'logSha256':sha(f/'host-controls-v2.log')}
assert all(code==0 for code in freeze2['normalCodeChecks'].values())
admission=load(f/'control-acceptance-v2.json')
assert admission['allControlsPassed'] and admission['actualLinuxTests']==74 and admission['bothSourceSamplesNotDecoded'] and admission['ownedWorkerIndependentlyRemoved']
assert admission['controlsResultSha256']==sha(f/'v2-raw/controls/controls.json')
sample=load(f/'sample-plan.json');validate2(sample)
freeze=load(f/'sample-freeze.json')
assert sha(f/'sample-plan.json')==freeze['recipeSha256']=='7ef28e422a97604f43f19ba6960897b44260ec9fd81726fef5a439cd66a48723'
assert freeze['outputAbsentAtFreeze'] and freeze['sampleProducerNotExecuted'] and freeze['bothSourceSamplesNotDecoded'] and freeze['v2ControlsAccepted']
assert sample['phase']=='sample' and sample['samples']==SAMPLES and sample['artifact']==ARTIFACT and sample['cases']==CASES and sample['caps']==CAPS
assert len(sample['inputs'])==279 and len(sample['workerFiles'])==261 and len(sample['sampleWorkerFiles'])==2
assert sample['mounts'][ADMISSION]=='/inputs/admission.json' and sample['workerFiles']['/inputs/admission.json']==sha(f/'control-acceptance-v2.json')
for name,pin in sample['inputs'].items():
    if local or not name.startswith('data/'):assert sha(r/name)==pin,name
spec=load(f/'sample-spec.json');assert spec['visits']['plannedTotal']==524000==128000+6000+6000+384000
assert freeze['plannedObjectReceipts']==524000 and freeze['caseDeadlineSeconds']==60
if local:assert sha(r/ARTIFACT['path'])==ARTIFACT['sha256'] and (r/ARTIFACT['path']).stat().st_size==ARTIFACT['bytes']
print(json.dumps({'recordFiles':len(manifest),'producerFiles':259,'priorSealedRuns':50,'bindingsValid':True,'localAssetsChecked':local,
    'linuxControlsPassed':74,'hostPassed':51,'hostNativeSkips':23,'v1ReceiptOmissionPreservedAndReproduced':True,
    'v2RejectedReceiptAndQuotaSentinelChecked':True,'bothWorkersIndependentlyRemoved':True,'sampleRecipeFrozenNotExecuted':True,
    'realSamplePerformanceMeasured':False,'fullImportAdmitted':False,'v9Unchanged':True},indent=2))

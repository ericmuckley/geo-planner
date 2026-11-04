"""Saved disk-capture controller proof; no national/native/producer execution."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_qualification_v15.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_disk_capture_v1 import validate,isolation,check_receipt,output_ledger
from coarse_osm_disk_resources_v1 import RETAINED,OWNED_LIMIT,TMP,TOTAL,WRITABLE_WORST_CASE,QUALIFICATION_RESERVATION
plan=load(folder/'disk-capture-plan-controls-v1.json');validate(plan)
freeze=load(folder/'disk-capture-freeze-controls-v1.json');assert sha(folder/'disk-capture-plan-controls-v1.json')==freeze['sha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
closed=load(folder/'disk-capture-closed-controls-v1.json');raw=folder/'disk-capture-raw/controls-v1'
assert closed['files']==len(closed['roster'])==28 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==213827
for name,row in closed['roster'].items():assert not row['ignoredLargeAsset'] and (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
assert closed['closerSha256']==sha(repo/'scripts/close_osm_disk_capture_v1.py')
assert load(folder/'disk-capture-cleanup-controls-v1.json')['independentlyAbsent']
isolation(load(raw/'container-initial.json'));result=load(raw/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
c=load(raw/'controls.json');assert c=={'tests':16,'successful':True,'skips':0,'failures':0,'errors':0}
s=load(raw/'extraction-result.json');assert s['status']=='passed_disk_selected_extraction_prototype' and s['independentAuditComplete']
assert s['scanObjectVisits']==18 and s['retainedElements']==4 and s['windowOccurrences']==8 and s['extractBytes']==1470
for r in s['nativeReceipts']:check_receipt(r,plan)
assert len(s['nativeReceipts'])==2 and len(s['selectedStores'])==2
for report,label in zip(s['selectedStores'],['primary','audit']):
    assert report['sealed'] and report['closed'] and report['integrityOk'] and report['objects']==report['unique']==4 and report['occurrences']==8
    assert sha(raw/('extract/'+label+'-selected.sqlite'))==report['databaseSha256']
output=raw/'extract/elements.jsonl';assert sha(output)==s['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
assert output.read_bytes()==(folder/'qualification-raw/v15/controls/four-pass-reference/elements.jsonl').read_bytes()
assert output_ledger(output,load(raw/'proposal.json')['windows'])==load(raw/'window-ledger.json') if (raw/'proposal.json').exists() else output_ledger(output,[{'id':'a'},{'id':'b'}])==load(raw/'window-ledger.json')
for label in ('all-highway-primary-selection-cells','all-highway-independent-materialization-cells'):
    actual={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in (raw/'extract'/label).iterdir()}
    assert actual==plan['expectedBank'] and sum(r['bytes'] for r in actual.values())==581
views=load(raw/'fine-revalidation.json');assert len(views)==2 and all(v['nodeRowsCompared']==4 and v['wholeFileVerificationPasses']==1 for v in views)
r=load(raw/'result.json');assert r['sourcePasses']==2 and r['sourceObjects']==18 and r['rawAcquiredFileCaptureComplete'] and not r['nationalRawAcquiredFileCaptureComplete']
assert RETAINED+OWNED_LIMIT+TMP==TOTAL==64*1024**3 and WRITABLE_WORST_CASE<OWNED_LIMIT
assert sum(load(folder/f'qualification-closed-v{v}.json')['usage']['conservativeAllocatedBytes'] for v in [14,15])+closed['usage']['conservativeAllocatedBytes']<QUALIFICATION_RESERVATION
metrics=load(raw/'metrics-end.json');assert metrics['retainedReservationBytes']==RETAINED and metrics['latest']['cgroup']['memory.swap.max']=='0' and 'oom_kill 0' in metrics['latest']['cgroup']['memory.events']
assert load(raw/'run-summary.json')['status']=='passed_full_road_capture'
print(json.dumps({'diskCaptureLinuxControls':16,'skips':0,'exactOutputAndIndependentAudit':True,'fineInputPreserved':True,'bankBytesEach':581,'selectedDatabasesSealedAndClosed':True,'workerAbsent':True,'nationalSourceRead':False,'nationalCaptureQualified':False},indent=2))

"""Saved transient-budget qualification proof; no native/Docker/national reads."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
previous=sys.argv
try:
    sys.argv=[str(f/'verify_qualification.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=previous
sys.path.insert(0,str(r/'scripts'))
from run_osm_country_screen_v8 import validate,isolation
plan=load(f/'qualification-plan-v8.json');validate(plan)
assert sha(f/'qualification-plan-v8.json')==load(f/'qualification-freeze-v8.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(r/name)==pin,name
raw=f/'qualification-raw/v8';closed=load(f/'qualification-closed-v8.json')
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
isolation(load(raw/'controls/container-initial.json'),'controls')
state=load(raw/'controls/container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'controls/cleanup.json')['removed'] and load(raw/'controls/cleanup.json')['independentInspectAbsent']
assert load(f/'cleanup-audit-v8.json')['independentAbsent']
controls=load(raw/'controls/controls.json');assert controls['tests']==260 and controls['successful'] and controls['errors']==controls['failures']==controls['skipped']==0
assert len(plan['testIds'])==len(set(plan['testIds']))==260
memory=load(raw/'controls/transient-memory-proof.json')
assert memory==[{'liveBatchConservativeHeapPeakBytes':78079432,'liveBatchHeapLimitBytes':134217728,'retainedElements':0,'scanObjectVisits':65544}]
new=raw/'controls/full-prototype';old=f/'qualification-raw/v7/controls/full-prototype'
assert (new/'elements.jsonl').read_bytes()==(old/'elements.jsonl').read_bytes()
proof=load(raw/'controls/full-prototype-proof.json');assert proof['newState']['independentAuditComplete'] and proof['newState']['scanObjectVisits']==18
assert proof['newState']['liveBatchHeapLimitBytes']==134217728 and proof['proposal']['proposedCaps']['singleNormalizedElementBytes']==1048576
assert proof['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
assert sha(raw/'controls/full-fixture.osm')==sha(f/'qualification-raw/v7/controls/full-fixture.osm')
print(json.dumps({'completePrototypeAndTransientBudgetQualified':True,'actualLinuxTests':260,'skips':0,'validLargeBatchConservativeHeapBytes':78079432,
                  'selectedRecordBudgetUnchanged':True,'workerAbsent':True,'nationalSourceRead':False},indent=2))

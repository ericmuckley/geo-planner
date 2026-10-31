"""Saved typed-lookup control proof; no native, Docker, national source reads."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct
import sys

f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
parent=f.parent/'coarse-osm-way-batch-2026-10-30'
assert sha(parent/'sha256.json')=='f43b43173e5f667b6b19d525c0a0833c4a8f804bca6a26447c20fc9ead64ca83'
previous=sys.argv
try:
    sys.argv=[str(parent/'verify_closed.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=previous
sys.path.insert(0,str(r/'scripts'))
from run_osm_lookup_v3 import validate,isolation
plan=load(f/'controls-plan.json');validate(plan)
assert sha(f/'controls-plan.json')==load(f/'controls-freeze.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(r/name)==pin,name
closed=load(f/'controls-closed.json');raw=f/'controls-raw'
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
assert (raw/'execution-plan.json').read_bytes()==(f/'controls-plan.json').read_bytes()
isolation(load(raw/'container-initial.json'),'controls')
state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
assert load(f/'controls-cleanup-audit.json')['independentAbsent']
assert load(raw/'controls.json')=={'tests':6,'successful':True,'skips':0}
fields=load(parent/'qualification-raw/controls/reference-fields.json');coords={row['id']:(row['lon'],row['lat']) for row in fields if row['type']=='node'}
keys=[identity for row in fields if row['type']=='way' for identity in row['nodes']]
bits=b''.join(struct.pack('<dd',*coords[key]) for key in keys);proof=load(raw/'positive.json')
assert [row['kind'] for row in proof]==['old','new'] and all(row['references']==400 and row['coordinateBitsSha256']==hashlib.sha256(bits).hexdigest() for row in proof)
assert proof[0]['statistics']==proof[1]['statistics'] and load(raw/'result.json')['status']=='lookup_controls_passed'
correction=load(f/'parent-link-check-correction.json');assert correction['actualCheckOutput']==1304 and load(parent/'verification.json')['relativeLinks']==1306
print(json.dumps({'lookupQualificationVerified':True,'actualLinuxTests':6,'skips':0,'all400NativeCoordinateBitsVerified':True,'workerAbsent':True,'nationalPbfRead':False},indent=2))

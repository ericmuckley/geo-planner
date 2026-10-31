"""Saved controller/fixture proof only; no native, Docker or national reads."""
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
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(f/'verify_qualification.py'),run_name='__main__')
sys.path.insert(0,str(r/'scripts'))
from run_osm_way_batch_v2 import validate,WITNESS
from run_osm_country_screen_v4 import isolation
for version,closed in load(f/'controller-closed.json').items():
    raw=f/'controller-raw'/version
    for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
    suffix='-v2' if version=='v2' else ''
    path=f/f'controller-qualification-plan{suffix}.json';plan=load(path)
    assert sha(path)==load(f/f'controller-qualification-freeze{suffix}.json')['recipeSha256']
    for name,pin in plan['inputs'].items():
        if not name.startswith('data/'):assert sha(r/name)==pin
    assert (raw/'execution-plan.json').read_bytes()==path.read_bytes()
    isolation(load(raw/'container-initial.json'),'controls')
    state=load(raw/'container-result.json');expected=2 if version=='v1' else 0
    assert state['State']['ExitCode']==state['clientExitCode']==expected and not state['State']['OOMKilled']
    assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
    if version=='v1':
        assert not load(raw/'controls.json')['successful'] and 'IndexError' in (raw/'worker.log').read_text()
        assert load(raw/'worker-failure.json')['lastNativeReceipt'] is None
        continue
    validate(plan)
    assert load(raw/'controls.json')=={'tests':7,'successful':True,'skips':0}
    result=load(raw/'result.json');case=load(raw/'source-and-lookup.json');audit=load(raw/'independent-audit.json')
    assert result['status']=='passed_bounded_way_batch' and result['ways']==200 and result['references']==400 and result['batches']==1
    receipt=case['receipt'];assert receipt['nativeEof'] and receipt['visits']==500 and receipt['semanticSha256']==plan['expectedSemantic']
    assert receipt['batchWays']==receipt['deliveredBatchWays']==200 and receipt['batchReferences']==receipt['deliveredBatchReferences']==400
    fields=load(f/'qualification-raw/controls/reference-fields.json');ways=[row for row in fields if row['type']=='way']
    coords={row['id']:(row['lon'],row['lat']) for row in fields if row['type']=='node'}
    keys=[identity for row in ways for identity in row['nodes']]
    expected=b''.join(WITNESS.pack(identity,*coords[identity]) for identity in keys)
    ledger=load(raw/'ledger.json');actual=(raw/'witness'/ledger[0]['file']).read_bytes()
    assert actual==expected and ledger[0]['references']==400 and hashlib.sha256(actual).hexdigest()==ledger[0]['witnessSha256']
    assert audit['references']==400 and audit['orderedWitnessSha256']==hashlib.sha256(actual).hexdigest()
    from coarse_osm_records import canonical
    assert case['selectedFieldsSha256']==hashlib.sha256(b''.join(canonical(row)+b'\n' for row in ways)).hexdigest()
    assert not result['wholeRoadExtractionQualified'] and not result['modelChanged']
assert all(row['independentAbsent'] for row in load(f/'controller-cleanup-audit.json'))
print(json.dumps({'controllerQualificationVerified':True,'actualLinuxTests':7,'all200WayFieldsAnd400CoordinateOccurrencesVerified':True,'priorFailurePreserved':True,'workersAbsent':True,'nationalSourceRead':False},indent=2))

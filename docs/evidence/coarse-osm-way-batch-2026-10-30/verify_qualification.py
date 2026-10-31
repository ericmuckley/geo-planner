"""Saved batching qualification proof; no native/Docker/national reads."""
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
parent=f.parent/'coarse-osm-country-exec-2026-10-30'
assert sha(parent/'sha256.json')=='3cf6a309323e830fb0227e092e8d332e44684bdf8ddae250e485dc4bf827ad69'
previous=sys.argv
try:
    sys.argv=[str(parent/'verify_closed.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=previous
sys.path.insert(0,str(r/'scripts'))
from run_osm_country_screen_v5 import validate,isolation
from coarse_osm_country_wire_v4 import reference_seal
from coarse_osm_compact_v1 import coordinate
from coarse_osm_delta_v2 import Reader,ReferenceCodec
from coarse_osm_country_screen_v4 import storage_decision
from coarse_osm_country_screen_v1 import XY,priority
plan=load(f/'qualification-plan.json');validate(plan)
assert sha(f/'qualification-plan.json')==load(f/'qualification-freeze.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(r/name)==pin,name
closed=load(f/'qualification-closed.json');raw=f/'qualification-raw'
for name,row in closed['roster'].items():
    if name.endswith('.so'):continue
    assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
for phase in ('build','controls'):
    isolation(load(raw/phase/'container-initial.json'),phase)
    state=load(raw/phase/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    assert load(raw/phase/'cleanup.json')['removed'] and load(raw/phase/'cleanup.json')['independentInspectAbsent']
assert all(row['independentAbsent'] for row in load(f/'cleanup-audit.json'))
controls=load(raw/'controls/controls.json');assert controls['tests']==206 and controls['successful'] and controls['failures']==controls['errors']==controls['skipped']==0
assert len(plan['testIds'])==len(set(plan['testIds']))==206
built=load(raw/'build/result.json');assert built['artifactBytes']==2003456 and built['artifactSha256']=='9c81c86e3605738430b1c8f9f762bce71830740e5c46737485371ef8c0561166'
assert sha(raw/'build/country-screen.cpp')==sha(r/'scripts/coarse_osm_country_screen_v5.cpp')==built['sourceSha256']
assert sha(raw/'build/delta.cpp')==sha(r/'scripts/coarse_osm_delta_v1.cpp')==built['deltaSourceSha256']
fields=load(raw/'controls/reference-fields.json')
assert fields==load(raw/'controls/projected-fields.json') and len(fields)==500
proof=load(raw/'controls/proof-receipt.json')
assert proof['nativeEof'] and proof['semanticSha256']==reference_seal(fields)
for kind in ('node','way'):
    rows=[row for row in fields if row['type']==kind];meta=proof['metadata'][kind]
    assert meta['count']==len(rows) and meta['minTimestamp']==min(row['timestamp'] for row in rows) and meta['maxTimestamp']==max(row['timestamp'] for row in rows)
    assert meta['maxTagUtf8Bytes']==max(sum(len(k.encode())+len(v.encode()) for k,v in row['tags'].items()) for row in rows)
    assert meta['maxTags']==max(len(row['tags']) for row in rows) and meta['maxVersion']==max(row['version'] for row in rows)
pipe=raw/'controls/two-pass';result=load(pipe/'result.json')
assert result['status']=='passed_bounded_country_screen_pipeline' and result['objectReceipts']==1000
assert result['storageDecision']==storage_decision(result['passes'][1]) and result['storageDecision']['passed']
a,b=result['passes'];assert a['globalManifest']==b['globalManifest'] and a['mapping']==b['mapping']
assert a['receipt']['metadata']==b['receipt']['metadata']==proof['metadata']
assert a['receipt']['semanticSha256']==b['receipt']['semanticSha256']==proof['semanticSha256']
assert a['receipt']['pythonProjectionFrames']==b['receipt']['pythonProjectionFrames']==0
for name,stage in zip(('pass-a','pass-b'),(a,b)):
    assert stage['protectedSecondsIncludingReceiptClose']>=load(pipe/name/'phase-receipt.json')['dataAndSummaryCloseSeconds']
reader=Reader(pipe/'pass-b/probe',ReferenceCodec());actual=[]
for n in range(reader.manifest['blocks']):
    ids,xy=reader.block(n)
    actual.extend((i,xy[2*k],xy[2*k+1]) for k,i in enumerate(ids))
expected=[(row['id'],coordinate(row['lon'],180),coordinate(row['lat'],90)) for row in fields if row['type']=='node']
assert actual==expected and reader.bytes==a['logicalWholeIndexBytes']==b['logicalWholeIndexBytes']
reader.close()
witness=b''.join(XY.pack(*row) for row in expected)
assert witness==(pipe/'pass-b/source-witness.bin').read_bytes()
trace=load(pipe/'pass-a/way-trace.json');assert trace==load(pipe/'pass-b/way-trace.json')
ways=[row for row in fields if row['type']=='way']
chosen=sorted(enumerate(ways),key=lambda item:(priority(item[1]['id']),item[1]['id'],item[0]))[:128]
assert [row['wayID'] for row in trace]==[row['id'] for _,row in chosen]
keys=[v[0] for v in expected];coords={i:(x,y) for i,x,y in expected}
queries={'local':list(reversed(keys))+keys[:128],'spread':[keys[0],keys[0]],'way-refs':[i for row in trace for i in row['references']]}
for row in result['lookup']['runs']:
    values=queries[row['cohort']]
    bits=b''.join(struct.pack('<dd',coords[i][0]/10000000,coords[i][1]/10000000) for i in values)
    assert row['coordinateBitsSha256']==hashlib.sha256(bits).hexdigest() and row['occurrences']==len(values)
    assert row['authenticatedShardBytes']==(5782 if row['kind']=='cold-application' else 2891)
closed_receipt=load(pipe/'close-receipt.json')
assert closed_receipt['secondsThroughResultClose']>result['secondsBeforeResultClose']
assert closed_receipt['resourcesThroughResultClose']['latest']['work']['logicalBytes']>=sum(p.stat().st_size for p in pipe.rglob('*') if p.is_file() and p.name!='close-receipt.json')

actual=load(raw/'controls/batch-fields.json');expected=[row for row in fields if row['type']=='way'];assert actual==expected and len(actual)==200
batch=load(raw/'controls/batch-proof.json')
assert batch['nativeEof'] and batch['semanticSha256']==proof['semanticSha256'] and batch['pythonProjectionFrames']==0
assert batch['batchWays']==batch['deliveredBatchWays']==batch['eligibleHighwayWays']==200
assert batch['batchReferences']==batch['deliveredBatchReferences']==400 and batch['wayBatches']==batch['callbackEvents'][8]==1
keys=[identity for row in expected for identity in row['nodes']]
expected_xy={row['id']:(row['lon'],row['lat']) for row in fields if row['type']=='node'}
bits=b''.join(struct.pack('<dd',*expected_xy[key]) for key in keys)
lookup=load(raw/'controls/batch-lookups.json');assert lookup==[{'ways':200,'references':400,'coordinateBitsSha256':hashlib.sha256(bits).hexdigest()}]
print(json.dumps({'independentBatchQualificationProofPassed':True,'actualLinuxTests':206,'skips':0,'all200WayFieldsAnd400OrderedCoordinateBitsVerified':True,'priorNationalResultVerified':True,'nationalSourceRead':False},indent=2))

"""Saved V2/V3 qualification proof only; no Docker, native, PBF or national reads."""
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
parent=r/'docs/evidence/coarse-osm-country-helper-2026-10-30'
assert sha(parent/'sha256.json')=='8d87d30d07ec85029d84596a838b717cd029c46c9188db819d65f64565093cb3'
args=sys.argv
try:
    sys.argv=[str(parent/'verify.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=args
sys.path.insert(0,str(r/'scripts'))
from run_osm_country_screen_v3 import validate,isolation
from coarse_osm_projector_v1 import reference_seal
from coarse_osm_records import canonical
from coarse_osm_compact_v1 import coordinate
from coarse_osm_delta_v2 import Reader,ReferenceCodec
from coarse_osm_country_screen_v2 import storage_decision
from coarse_osm_country_screen_v1 import XY,priority
p=load(f/'qualification-plan-v3.json');validate(p)
assert sha(f/'qualification-plan-v3.json')==load(f/'qualification-freeze-v3.json')['recipeSha256']
for name,pin in p['inputs'].items():
    if not name.startswith('data/'):assert sha(r/name)==pin,name
closed=load(f/'qualification-closed.json')
for version,record in closed.items():
    raw=f/'qualification-raw'/version
    for name,row in record['roster'].items():
        if name.endswith('.so'):continue
        assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],(version,name)
    phases=('build','controls') if version=='v2' else ('controls',)
    for phase in phases:
        isolation(load(raw/phase/'container-initial.json'),phase)
        final=load(raw/phase/'container-result.json')
        expected=2 if version=='v2' and phase=='controls' else 0
        assert final['State']['ExitCode']==final['clientExitCode']==expected and not final['State']['OOMKilled'] and not final['State']['Running']
        clean=load(raw/phase/'cleanup.json');assert clean['removed'] and clean['independentInspectAbsent']
v2=f/'qualification-raw/v2';v3=f/'qualification-raw/v3'
assert load(v2/'run-summary.json')['status']=='stopped'
assert load(v2/'controls/controls.json')['tests']==135 and load(v2/'controls/controls.json')['successful']
assert load(v2/'controls/worker-failure.json')['errorType']=='ImportError'
assert 'binding' in load(v2/'controls/worker-failure.json')['error']
controls=load(v3/'controls/controls.json')
assert controls['tests']==137 and controls['successful'] and controls['failures']==controls['errors']==controls['skipped']==0
assert len(p['testIds'])==len(set(p['testIds']))==137
assert load(v3/'run-summary.json')['status']=='country_screen_synthetic_qualified'
assert load(v3/'run-summary.json')['phaseClientExitCodes']=={'controls':0}
absent=load(f/'cleanup-audit.json');assert absent['allIndependentlyAbsent'] and absent['exitCode']==1 and len(absent['ownedContainers'])==3
built=load(v2/'build/result.json')
assert built['artifactBytes']==2002920 and built['artifactSha256']=='56cb0ae4020e9ea04586ea72e1f71a2f6a943d83222dfa42d40a0a4f65a42c9a'
assert sha(v2/'build/country-screen.cpp')==sha(r/'scripts/coarse_osm_country_screen_v2.cpp')==built['sourceSha256']
assert sha(v2/'build/delta.cpp')==sha(r/'scripts/coarse_osm_delta_v1.cpp')==built['deltaSourceSha256']
fields=load(v3/'controls/reference-fields.json')
assert fields==load(v3/'controls/projected-fields.json') and len(fields)==500
proof=load(v3/'controls/proof-receipt.json')
assert proof['nativeEof'] and proof['semanticSha256']==reference_seal(fields)
for kind in ('node','way'):
    rows=[row for row in fields if row['type']==kind];meta=proof['metadata'][kind]
    assert meta['count']==len(rows) and meta['minTimestamp']==min(row['timestamp'] for row in rows) and meta['maxTimestamp']==max(row['timestamp'] for row in rows)
    assert meta['maxTagUtf8Bytes']==max(sum(len(k.encode())+len(v.encode()) for k,v in row['tags'].items()) for row in rows)
    assert meta['maxTags']==max(len(row['tags']) for row in rows) and meta['maxVersion']==max(row['version'] for row in rows)
pipe=v3/'controls/two-pass';result=load(pipe/'result.json')
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
print(json.dumps({'independentQualificationProofPassed':True,'actualTargetTests':137,'nativeSkips':0,'all500FieldsAnd300CoordinateRowsVerified':True,
                  'metadataAndCompletePassTimersVerified':True,'failedAttemptPreserved':True,'workersIndependentlyAbsent':True,'nationalDataRead':False},indent=2))

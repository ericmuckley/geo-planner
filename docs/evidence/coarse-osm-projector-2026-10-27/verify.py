"""Read-only synthetic projector proof; never loads native code or decodes PBF."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct
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
plan=load(f/'execution-plan.json')
assert sha(f/'execution-plan.json')=='43e4f0408efe3cb8308911f1b184db87a8cd322350f9051007ece526bc14bcea'
assert len(plan['inputs'])==267 and len(plan['workerFiles'])==254
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(r/name)==pin,name
sys.path.insert(0,str(r/'scripts'))
from run_osm_projector_v1 import validate,isolation,HEADERS
from coarse_osm_projector_v1 import field_frame,decode_frame,reference_seal
from coarse_osm_delta_v2 import Reader,ReferenceCodec
from coarse_osm_records import canonical,normalize
from coarse_osm_bulk_audit import crossing
validate(plan)
freeze=load(f/'freeze.json')
assert freeze['recipeSha256']==sha(f/'execution-plan.json') and freeze['formatSha256']==sha(f/'format-spec.json')
assert freeze['outputAbsent'] and freeze['compiledControlsNotYetExecuted'] and freeze['oldSealedCodeAndEvidenceUnchanged']
assert freeze['hostControls']=={'tests':62,'passed':46,'nativeSkips':16,'logSha256':sha(f/'host-controls.log')}
assert all(value==0 for value in freeze['normalCodeChecks'].values())
for name,pin in freeze['newProducerSha256'].items():assert sha(r/name)==pin
raw=f/'raw'
cleanup_audit=load(f/'cleanup-audit.json')
for phase in ('build','controls'):
    initial=load(raw/phase/'container-initial.json');isolation(initial,phase)
    assert not any(row['Destination'].endswith(('.pbf','.jsonl','.sqlite')) for row in initial['Mounts'])
    guards=load(raw/phase/'resource-guards.json')
    assert guards['memory']=={'memoryMaxBytes':4294967296,'swapMaxBytes':0} and guards['tmpBytes']==268435456
    state=load(raw/phase/'container-result.json')
    assert state['clientExitCode']==state['State']['ExitCode']==0 and not state['State']['Running'] and not state['State']['OOMKilled']
    cleanup=load(raw/phase/'cleanup.json');independent=cleanup_audit[phase]
    assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent']
    assert independent['exitCode']==1 and cleanup['ownedContainer']==independent['ownedContainer']
build=load(raw/'build/result.json');result=load(raw/'controls/result.json');summary=load(raw/'run-summary.json')
assert build['artifactSha256']==result['artifactSha256']=='9227bc577f3592f167d614329ecc25311c4f8505aa854d3121f9837073f75f26'
assert build['artifactBytes']==1935424 and build['elfSha256']==sha(raw/'build/elf.log')
assert sha(raw/'build/projector.cpp')==build['sourceSha256']==freeze['newProducerSha256']['scripts/coarse_osm_projector_v1.cpp']
assert sha(raw/'build/delta.cpp')==build['deltaSourceSha256']==sha(r/'scripts/coarse_osm_delta_v1.cpp')
assert set(build['needed'])<={'libz.so.1','libm.so.6','libpthread.so.0','libc.so.6','ld-linux-aarch64.so.1'}
controls=load(raw/'controls/controls.json')
assert controls['tests']==62 and controls['successful'] and controls['failures']==controls['errors']==controls['skipped']==0
assert controls['projectorAggregateVisits']==9249 and result['projectorAggregateVisits']==9276<2000000
assert result['status']==summary['status']=='native_projector_synthetic_qualified'
assert summary['phaseClientExitCodes']=={'build':0,'controls':0} and summary['hostSecondsIncludingInputAssetHashesBuildControlsCleanup']<600
assert summary['networkRequests']==summary['sourceOrSavedSampleReads']==0 and not summary['modelChanged'] and not summary['fullImportAdmitted']
assert result['nativeMetadataValidatorImplemented'] and not result['nativeIndexIoImplemented']
rows=load(raw/'controls/reference-fields.json')
assert rows==load(raw/'controls/projected-fields.json') and len(rows)==9
for row in rows:
    projected=decode_frame(field_frame(row))
    assert canonical(projected)==canonical(row)
    if row['type']=='node':assert struct.pack('<dd',projected['lon'],projected['lat'])==struct.pack('<dd',row['lon'],row['lat'])
semantic=reference_seal(rows)
assert semantic=='04630ed15b3eb0925917fb1d4dcabb51991d3cfe65eee84bc5a76b7652b9ed81'
receipts=[result['fullFieldProof'],*result['fastReceipts']]
assert [v['projectedFrames'] for v in receipts]==[9,5,7]
for receipt in receipts:
    assert receipt['counts']=={'node':4,'way':3,'relation':2} and receipt['visits']==9 and receipt['nativeEof'] and not receipt['error']
    assert receipt['blocks']==1 and receipt['fallbacks']==0 and receipt['semanticBytes']==930 and receipt['semanticSha256']==semantic
    assert receipt['sourceIdentity']['sourceSha256']==sha(raw/'controls/fixture.pbf') and receipt['sourceIdentity']['framingBytesRead']==564
    assert receipt['pythonProjectionFrames']==receipt['projectedFrames']
state=load(raw/'controls/two-pass/state.json')
assert state['nativeProjectionSyntheticQualified'] and state['independentAuditComplete'] and not state['wholeExtractionQualified']
assert result['twoPassVisits']==state['scanObjectVisits']==18 and result['fourPassVisits']==36
assert all(p['status']=='eof' and p['counts']==receipts[0]['counts'] for p in state['passes'])
index=Reader(raw/'controls/two-pass/audit-index',ReferenceCodec())
nodes={v['id']:v for v in rows if v['type']=='node'}
assert index.manifest['rows']==len(nodes)==4
for identity,node in nodes.items():assert struct.pack('<dd',*index.points([identity])[0])==struct.pack('<dd',node['lon'],node['lat'])
index.close()
# Independently derive window membership with the frozen audit intersection routine.
proposal=load(raw/'controls/synthetic-proposal.json');snapshot=proposal['source']['proposedPublisherReplicationStateUtc']
members={w['id']:set() for w in proposal['windows']};objects={(v['type'],v['id']):v for v in rows}
for way in rows:
    if way['type']!='way' or 'highway' not in way['tags']:continue
    points=[[nodes[i]['lon'],nodes[i]['lat']] for i in way['nodes']]
    for window in proposal['windows']:
        if crossing(points,window['bbox']):members[window['id']].update([('way',way['id']),*[('node',i) for i in way['nodes']]])
for relation in rows:
    if relation['type']!='relation' or relation['tags'].get('type')!='restriction':continue
    linked={(m['type'],m['ref']) for m in relation['members'] if m['type'] in ('node','way')}
    for window,keys in members.items():
        if not keys.isdisjoint(linked):keys.add(('relation',relation['id']))
selected=set().union(*members.values());expected=bytearray()
for key in sorted(selected):
    element=normalize(objects[key],snapshot,1048576)
    record={'publisherStateUtc':snapshot,'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),'windowIds':[w for w in members if key in members[w]]}
    if key[0]=='way':record['geometryDependencySha256']=hashlib.sha256(canonical([snapshot,[normalize(nodes[i],snapshot,1048576) for i in element['nodes']]])).hexdigest()
    expected.extend(canonical(record)+b'\n')
assert bytes(expected)==(raw/'controls/two-pass/elements.jsonl').read_bytes()==(raw/'controls/four-pass/elements.jsonl').read_bytes()
assert hashlib.sha256(expected).hexdigest()==result['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
roster=load(f/'closed-output.json')
assert roster['files']==len(roster['roster'])==46 and roster['totalBytes']==sum(v['bytes'] for v in roster['roster'].values())==3159367
assert roster['mirroredFiles']==len(roster['mirroredRoster'])==45 and roster['mirroredBytes']==1223943
assert set(roster['mirroredRoster'])==set(roster['roster'])-{'build/projector.so'}=={str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
for name,value in roster['mirroredRoster'].items():assert (raw/name).stat().st_size==value['bytes'] and sha(raw/name)==value['sha256'],name
local='--local-assets' in sys.argv
if local:
    for name,pin in plan['inputs'].items():assert sha(r/name)==pin,name
    root=r/roster['root']
    assert set(roster['roster'])=={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    for name,value in roster['roster'].items():assert (root/name).stat().st_size==value['bytes'] and sha(root/name)==value['sha256'],name
    asset=runpy.run_path(str(r/'docs/evidence/coarse-osm-native-build-2026-10-27/asset_contents.py'))['snapshot']
    assert asset(r/plan['rootfs']['path'])==plan['rootfs']['portable']
    for name,path in HEADERS.items():assert asset(r/path)==plan['headers'][name]['portable']
print(json.dumps({'recordFiles':len(manifest),'producerFiles':253,'priorSealedRuns':49,'bindingsValid':True,'localAssetsChecked':local,
    'linuxControlsPassed':62,'hostPassed':46,'hostNativeSkips':16,'fullFieldsAndCoordinateBitsVerified':True,'independentSelectedOutputVerified':True,
    'nativeMetadataProjectorSyntheticQualified':True,'nativeIndexIoImplemented':False,'realSampleOrNationalRun':False,
    'fullImportAdmitted':False,'bothWorkersIndependentlyRemoved':True,'v9Unchanged':True},indent=2))

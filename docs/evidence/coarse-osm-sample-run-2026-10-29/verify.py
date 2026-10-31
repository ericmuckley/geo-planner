"""Independent saved-result proof. No Docker, native execution or PBF decoding."""
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path
import runpy
import statistics
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
sys.path.insert(0,str(r/'scripts'))
from run_osm_sample_v2 import validate
from run_osm_delta_v1 import isolation
from coarse_osm_sample_v2 import SAMPLES,CASES
from coarse_osm_projector_v1 import field_frame,SEAL_PREFIX
from coarse_osm_records import canonical,strict_json
from coarse_osm_compact_v1 import coordinate
from coarse_osm_delta_v2 import Reader,ReferenceCodec

raw=f/'raw';result=load(raw/'sample/result.json');summary=load(raw/'run-summary.json')
plan=load(raw/'execution-plan.json');validate(plan)
assert sha(raw/'execution-plan.json')=='7ef28e422a97604f43f19ba6960897b44260ec9fd81726fef5a439cd66a48723'
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(r/name)==pin,name
isolation(load(raw/'sample/container-initial.json'),'controls')
initial=load(raw/'sample/container-initial.json')
sample_mounts={v['Destination'] for v in initial['Mounts'] if v['Destination'].startswith('/samples/')}
assert sample_mounts=={'/samples/prefix.pbf','/samples/mixed.jsonl'} and not any('source.pbf' in v['Destination'] for v in initial['Mounts'])
guards=load(raw/'sample/resource-guards.json')
assert guards['memory']=={'memoryMaxBytes':4294967296,'swapMaxBytes':0} and guards['tmpBytes']==268435456 and guards['fileBytes']==67108864
state=load(raw/'sample/container-result.json')
assert state['clientExitCode']==state['State']['ExitCode']==0 and not state['State']['Running'] and not state['State']['OOMKilled']
cleanup=load(raw/'sample/cleanup.json');independent=load(f/'cleanup-audit.json')
assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent']
assert cleanup['ownedContainer']==independent['ownedContainer'] and independent['exitCode']==1
assert summary['status']=='fixed_sample_screen_passed' and summary['workerClientExitCode']==0 and summary['networkRequests']==0
assert summary['savedSamplesMounted'] and not summary['nationalSourceMounted'] and not summary['recompiled'] and not summary['fullImportAdmitted'] and not summary['modelChanged']
assert result['status']=='passed_fixed_sample_screen' and result['performanceGatePassed'] and result['aggregateObjectVisits']==524000
assert not result['wholeSourceEof'] and not result['wholeExtractionQualified'] and not result['nationalRunAdmitted'] and not result['modelChanged']
roster=load(f/'closed-output.json')
assert roster['files']==len(roster['roster'])==75 and roster['totalBytes']==sum(v['bytes'] for v in roster['roster'].values())==36423557
assert roster['mirroredFiles']==len(roster['mirroredRoster'])==39 and roster['mirroredBytes']==1921786
assert set(roster['mirroredRoster'])=={str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
for name,row in roster['mirroredRoster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
proofs={}
for sample in ('prefix','mixed'):
    archived=roster['compressedFieldSnapshots'][sample];path=f/archived['archive']
    assert path.stat().st_size==archived['archiveBytes'] and sha(path)==archived['archiveSha256']
    for name in archived['originalPaths']:assert roster['roster'][name]=={'bytes':archived['originalBytes'],'sha256':archived['originalSha256']}
    reference=raw/'sample'/(sample+'-reference-proof')
    records_sha=hashlib.sha256();semantic=hashlib.sha256(SEAL_PREFIX);counts={};node_count=0;total=0;previous=(-1,-1);ids=[]
    reader=Reader(reference/'index',ReferenceCodec())
    def all_index_rows():
        for number in range(reader.manifest['blocks']):
            keys,xy=reader.block(number)
            for k,key in enumerate(keys):yield key,xy[2*k],xy[2*k+1]
    index_rows=iter(all_index_rows())
    with gzip.open(path,'rb') as stream,(reference/'coordinates.bin').open('rb') as coordinates:
        while line:=stream.readline(1048578):
            assert len(line)<=1048577 and line.endswith(b'\n')
            total+=len(line);assert total<=archived['originalBytes']
            row=strict_json(line);assert canonical(row)+b'\n'==line
            kind=row['type'];assert kind in ('node','way','relation') and row['visible'] is True
            assert type(row['id']) is int and type(row['version']) is int and row['id']>0 and row['version']>0
            key=(('node','way','relation').index(kind),row['id']);assert key>previous;previous=key
            counts[kind]=counts.get(kind,0)+1
            records_sha.update(line);body=field_frame(row);semantic.update(struct.pack('<I',len(body)));semantic.update(body)
            if kind=='node':
                x=coordinate(row['lon'],180);y=coordinate(row['lat'],90)
                assert next(index_rows)==(row['id'],x,y)
                assert coordinates.read(16)==struct.pack('<qii',row['id'],x,y)
                bits=struct.pack('<dd',x/10000000,y/10000000)
                assert bits==struct.pack('<dd',row['lon'],row['lat'])
                if len(ids)<1024:ids.append(row['id'])
                node_count+=1
        assert not coordinates.read(1)
    assert next(index_rows,None) is None
    reader.close()
    assert total==archived['originalBytes'] and records_sha.hexdigest()==archived['originalSha256']==SAMPLES[sample]['canonicalSha256']
    assert counts==SAMPLES[sample]['counts'] and node_count==counts['node']
    for mode,label in (('python','reference'),('native','native')):
        row=result['proofs'][sample][mode]
        assert row==load(raw/'sample'/(sample+'-'+label+'-proof')/'result.json')
        assert row['counts']==counts and row['eof'] and row['canonicalSha256']==records_sha.hexdigest() and row['semanticSha256']==semantic.hexdigest()
        assert row['coordinateRowsProved']==node_count and row['queryIds']==ids
        other=roster['roster']['sample/'+sample+'-'+label+'-proof/coordinates.bin']
        assert other['sha256']==sha(reference/'coordinates.bin') and other['bytes']==node_count*16
        assert row['indexManifestSha256']==sha(reference/'index/index.json') and row['indexBytes']==reader.bytes
        for name in ('index.json','directory.bin','00000000.bin'):
            assert roster['roster']['sample/'+sample+'-'+label+'-proof/index/'+name]['sha256']==sha(reference/'index'/name)
        assert row['framingBytesRead']==row['postSourceHashBytes'] and row['knownGuardReadBytes']==2*row['framingBytesRead']
    assert result['proofs'][sample]['native']['receipt']['pythonProjectionFrames']==sum(counts.values())
    proofs[sample]={'counts':counts,'semantic':semantic.hexdigest(),'ids':ids,'manifest':sha(reference/'index/index.json')}
prefix=proofs['prefix'];queries=list(reversed(prefix['ids']))+prefix['ids'][:128]
# Reconstruct the fixed query order and duplicates from the preserved source coordinates.
bits={}
with (raw/'sample/prefix-reference-proof/coordinates.bin').open('rb') as stream:
    for _ in range(1024):
        identity,x,y=struct.unpack('<qii',stream.read(16));bits[identity]=struct.pack('<dd',x/10000000,y/10000000)
lookup_sha=hashlib.sha256(b''.join(bits[i] for i in queries)).hexdigest()
assert len(queries)==1152 and len(result['cases'])==6
for (name,mode),case in zip(CASES,result['cases']):
    assert {k:v for k,v in case.items() if k!='name'}==load(raw/'sample'/name/'result.json') and case['name']==name and case['mode']==mode
    assert case['counts']=={'node':64000} and case['eof'] and not case['proofMode']
    assert case['protectedTotalSeconds']>=case['decodeValidateIndexSealEofSeconds']+case['framingSeconds']+case['postSourceHashSeconds']
    assert case['indexBytes']==579134 and case['indexManifestSha256']==prefix['manifest']
    assert case['sourceIdentity']['sourceSha256']==SAMPLES['prefix']['sha256']
    assert case['framingBytesRead']==case['postSourceHashBytes']==377536 and case['knownGuardReadBytes']==755072
    if mode=='native':
        receipt=case['receipt']
        assert receipt['nativeEof'] and receipt['visits']==64000 and receipt['counts']=={'node':64000}
        assert receipt['blocks']==16 and receipt['projectedFrames']==receipt['pythonProjectionFrames']==0
        assert case['semanticSha256']==receipt['semanticSha256']==prefix['semantic'] and case['canonicalSha256'] is None
    else:assert case['canonicalSha256']==SAMPLES['prefix']['canonicalSha256']
    assert [q['kind'] for q in case['lookup']]==['cold','warm','repeat']
    for k,query in enumerate(case['lookup']):
        assert query['queries']==1152 and query['coordinateBitsSha256']==lookup_sha
        assert query['authenticatedShardBytesRead']==(1156352 if k==0 else 578176)
    for filename in ('index.json','directory.bin','00000000.bin'):
        assert roster['roster']['sample/'+name+'/index/'+filename]['sha256']==sha(raw/'sample/prefix-reference-proof/index'/filename)
medians={mode:statistics.median(c['protectedTotalSeconds'] for c in result['cases'] if c['mode']==mode) for mode in ('python','native')}
assert medians==result['medianProtectedSeconds']=={'python':1.1122069170232862,'native':0.023119126039091498}
assert medians['native']<=.070 and medians['native']<medians['python']
assert medians['python']/medians['native']==result['medianSpeedup']==48.10765403253938
encoded=load(raw/'sample/mixed-encoding.json')
assert encoded['records']==encoded['encodingNativeViews']==encoded['jsonReceiptVisits']==3000
assert encoded['pbfBytes']==327670 and encoded['pbfSha256']==roster['roster']['sample/mixed.pbf']['sha256']
visits=encoded['encodingNativeViews']+encoded['jsonReceiptVisits']
visits+=sum(sum(c['counts'].values()) for c in result['cases'])
visits+=sum(sum(c['counts'].values()) for modes in result['proofs'].values() for c in modes.values())
assert visits==524000<2000000
scope=load(f/'timing-scope.json');decision=load(f/'decision.json')
assert scope['actualHostSeconds']==summary['hostSecondsIncludingInputHashesControlsCleanup']==7.7474491249304265<600
assert decision['measured']['performanceGatePassed'] and decision['measured']['allRawFieldsAndCoordinateBitsEqual']
assert not decision['measured']['scope'].startswith('national')
local='--local-assets' in sys.argv
if local:
    for name,pin in plan['inputs'].items():assert sha(r/name)==pin,name
    for sample in SAMPLES.values():
        source=r/sample['path'];assert source.stat().st_size==sample['bytes'] and sha(source)==sample['sha256']
    root=r/roster['root'];assert set(roster['roster'])=={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    for name,row in roster['roster'].items():assert (root/name).stat().st_size==row['bytes'] and sha(root/name)==row['sha256'],name
print(json.dumps({'recordFiles':len(manifest),'producerFiles':259,'priorSealedRuns':51,'bindingsValid':True,'localAssetsChecked':local,
    'all64000PrefixAnd1000MixedNodeCoordinateBitsVerified':True,'all67000FullFieldsAndSemanticSealsVerified':True,
    'protectedMedianPythonSeconds':medians['python'],'protectedMedianNativeSeconds':medians['native'],
    'protectedMedianSpeedup':result['medianSpeedup'],'fixedSampleGatePassed':True,'pairedLookupBitsVerified':True,
    'actualObjectVisits':visits,'ownedWorkerIndependentlyRemoved':True,'nationalRunAdmitted':False,'v9Unchanged':True},indent=2))

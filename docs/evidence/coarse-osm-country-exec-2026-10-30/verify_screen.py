"""Closed V4 screen proof. --local-assets additionally authenticates ignored probe bytes.

No Docker, native, national PBF reads, source producer or routing provider calls.
Portable proof checks saved complete receipts, sidecars, witnesses and lookup bits;
local proof derives the exact spread cohort from retained block headers as well.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct
import sys

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(f/'verify_v4.py'),run_name='__main__')
sys.path.insert(0,str(r/'scripts'))
from coarse_osm_records import canonical
from coarse_osm_delta_v1 import Reader,ReferenceCodec,DIRECTORY,ENTRY,BLOCK,block_fields
from coarse_osm_country_screen_v1 import XY,priority,RECEIPT_NAMES
from run_osm_country_screen_v4 import validate_screen,verify_admission,isolation
plan=load(f/'screen-plan-v4.json');validate_screen(plan);verify_admission(plan,load(f/'admission-v4.json'))
assert sha(f/'screen-plan-v4.json')==load(f/'screen-freeze-v4.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(r/name)==pin,name
closed=load(f/'screen-closed-v4.json');raw=f/'screen-raw-v4'
for name,row in closed['roster'].items():
    p=raw/name if row['mirrored'] else r/closed['root']/name
    if row['mirrored'] or args.local_assets:assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],name
assert (raw/'execution-plan.json').read_bytes()==(f/'screen-plan-v4.json').read_bytes()
isolation(load(raw/'container-initial.json'),'controls')
state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
assert load(f/'screen-cleanup-audit-v4.json')['independentAbsent']
assert load(raw/'run-summary.json')['status']=='country_screen_passed'
assert not load(raw/'run-summary.json')['fullImportAdmitted'] and not load(raw/'run-summary.json')['modelChanged']
source=plan['source'];binding=load(raw/'host-source-binding.json')
assert binding['bytesRead']==source['bytes'] and binding['sha256']==source['sha256'] and binding['md5']==source['md5']
pipe=raw/'screen';result=load(pipe/'result.json');a,b=result['passes']
assert result['status']=='passed_bounded_country_screen_pipeline' and result['objectReceipts']==3541084852
assert a['globalManifest']==b['globalManifest'] and a['mapping']==b['mapping']
assert all(a['receipt'][key]==b['receipt'][key] for key in RECEIPT_NAMES if 'Span' not in key and key!='witnessRows')
assert a['receipt']['metadata']==b['receipt']['metadata'] and a['receipt']['semanticSha256']==b['receipt']['semanticSha256']
for name,stage in zip(('pass-a','pass-b'),(a,b)):
    receipt=stage['receipt'];identity=receipt['sourceIdentity']
    assert receipt['nativeEof'] and receipt['counts']==source['counts'] and receipt['visits']==1770542426
    assert receipt['pythonProjectionFrames']==receipt['projectedFrames']==0 and not receipt['error']
    assert identity['sourceSha256']==source['sha256'] and identity['sourceMd5']==source['md5'] and identity['publisherStateUtc']==source['publisherState']
    assert identity['framingBytesRead']==receipt['postSourceHashBytes']==source['bytes'] and receipt['knownGuardReadBytes']==2*source['bytes']
    assert receipt['sourceEncodeRows']==receipt['sourceDecodeRows']==source['counts']['node'] and receipt['sourceCodecCalls']==784292
    assert receipt['blocks']==392146 and receipt['maxCopyBytes']<=4194304 and receipt['maxCanonicalUpperBytes']<=4194304
    assert stage['protectedSecondsIncludingReceiptClose']>=load(pipe/name/'phase-receipt.json')['dataAndSummaryCloseSeconds']
    assert stage['protectedSecondsIncludingReceiptClose']<=3000
    for kind,count in source['counts'].items():
        meta=receipt['metadata'][kind]
        assert meta['count']==count and '0001-'<=meta['minTimestamp']<=meta['maxTimestamp']<=source['publisherState']
    folder=pipe/name;manifest=stage['globalManifest'];directory=folder/'global-directory.bin'
    assert directory.stat().st_size==manifest['directory']['bytes'] and sha(directory)==manifest['directory']['sha256']
    # The whole national directory is present; national shard payloads are not.
    body=directory.read_bytes();head=DIRECTORY.unpack_from(body);table=body[DIRECTORY.size:]
    assert head[:7]==(b'GPDIR1\0\0',1,0,ENTRY.size,392146,1606229364,766)
    assert hashlib.sha256(table).digest()==head[7] and hashlib.sha256(canonical(manifest['shards'])).digest()==head[8]
    assert head[9]==b'\0'*24 and len(table)==392146*ENTRY.size
    assert manifest==load(folder/'global-catalog.json')
    assert sum(x['rows'] for x in manifest['shards'])==1606229364 and sum(x['blocks'] for x in manifest['shards'])==392146
    assert stage['logicalWholeIndexBytes']==sum(x['bytes'] for x in manifest['shards'])+len(body)+len(canonical(manifest))+1
    assert [x['source'] for x in stage['mapping']]==[0,109,218,327,437,546,655,765]
    assert stage['probeRows']==16588148
    for mapping in stage['mapping']:
        assert mapping['sourceDescriptor']==manifest['shards'][mapping['source']]
        assert mapping['miniDescriptor']['rows']==mapping['sourceDescriptor']['rows']
    offset=rows=previous=0
    for number,shard in enumerate(manifest['shards']):
        assert previous<shard['first']<=shard['last']
        position=128;count_rows=0
        for index in range(shard['blocks']):
            end,start,length,count,zero,selected,zero2=ENTRY.unpack_from(table,offset)
            assert previous<end<2**63 and start==position and zero==zero2==0 and selected==number and 0<count<=4096
            assert BLOCK.size+count*8+count-1<=length<=BLOCK.size+count*8+9*(count-1)
            previous=end;position+=length;count_rows+=count;offset+=ENTRY.size
        assert position==shard['bytes'] and count_rows==shard['rows'] and previous==shard['last']
    assert offset==len(table)
    mini=Reader(folder/'probe',ReferenceCodec(),index_limit=384*1024**2,catalog_limit=4*1024**2)
    assert mini.bytes==stage['probeBytes'] and mini.manifest['rows']==16588148 and mini.manifest['blocks']==4050
    assert mini.manifest['shards']==[mapping['miniDescriptor'] for mapping in stage['mapping']]
    ordinal=0
    for mapping in stage['mapping']:
        for local_index in range(mapping['sourceDescriptor']['blocks']):
            source_entry=ENTRY.unpack_from(table,(mapping['source']*512+local_index)*ENTRY.size)
            mini_entry=mini.entry(ordinal)
            assert mini_entry[:5]==source_entry[:5] and mini_entry[5]==mapping['mini'] and mini_entry[6]==source_entry[6]
            ordinal+=1
    mini.close()
# Independent margin arithmetic; no national physical allocation claim.
logical=b['logicalWholeIndexBytes'];reserve=12288*(766+3)+1048576;margined=(3*(logical+reserve)+1)//2
extra=(3*(35679872+b['globalManifest']['directory']['bytes']+4*1048576+3*4096)+1)//2
working=38811541607+margined+extra;decision=result['storageDecision']
assert decision['logicalIndexBytes']==logical and decision['filesystemReserveBytes']==reserve and decision['marginedIndexBytes']==margined
assert decision['marginedWorkingBytes']==working and decision['passed'] and margined<=24*1024**3 and working<=64*1024**3
assert not result['nationalPhysicalIndexAllocated'] and not result['wholeRoadExtractionQualified'] and not result['modelChanged']
assert load(pipe/'pass-a/way-trace.json')==load(pipe/'pass-b/way-trace.json')
trace=load(pipe/'pass-b/way-trace.json');assert len(trace)==128
order=[(x['priority'],x['wayID'],x['sourceWayOrdinal']) for x in trace];assert order==sorted(set(order))
assert all(x['priority']==priority(x['wayID']) and 2<=len(x['references'])<=1024 for x in trace)
witness=(pipe/'pass-b/source-witness.bin').read_bytes();coords={};previous=0
for identity,x,y in XY.iter_unpack(witness):
    assert previous<identity and -1800000000<=x<=1800000000 and -900000000<=y<=900000000
    previous=identity;coords[identity]=(x,y)
local=list(coords)[:1024];cohorts={'local':list(reversed(local))+local[:128],'way-refs':[identity for x in trace for identity in x['references']]}
assert len(witness)//XY.size==b['receipt']['witnessRows']
if args.local_assets:
    class WitnessCodec(ReferenceCodec):
        def __init__(self):self.seen={};self.rows=0;self.digest=hashlib.sha256()
        def decode(self,*arguments):
            values=super().decode(*arguments)
            for identity,x,y in values:
                self.digest.update(XY.pack(identity,x,y));self.rows+=1
                if identity in coords:
                    assert (x,y)==coords[identity];self.seen[identity]=(x,y)
            return values
    codec=WitnessCodec();root=r/closed['root']/'screen/pass-b/probe'
    reader=Reader(root,codec,index_limit=384*1024**2,catalog_limit=4*1024**2)
    spread=[]
    for mini,mapping in enumerate(b['mapping']):
        reader.validate_shard(mini)
        # Authenticated full-shard bytes; derive each selected source block's first ID.
        payload=reader.path(mini).read_bytes()
        for index in range(reader.starts[mini],reader.starts[mini]+reader.manifest['shards'][mini]['blocks']):
            end,start,size,count,_,_,_=reader.entry(index);n,first,last,_=block_fields(payload[start:start+size]);assert (n,last)==(count,end)
            spread.append((index-reader.starts[mini],mapping['source'],first))
    keys=[row[2] for row in sorted(spread)];cohorts['spread']=keys+keys[:128]
    assert codec.seen==coords and codec.rows==16588148 and codec.digest.hexdigest()==result['referenceAudit']['idXYRowsSha256']
    reader.close()
for row in result['lookup']['runs']:
    assert row['seconds']>=0 and row['authenticatedShardBytes']>=0
    if row['cohort'] not in cohorts:continue
    keys=cohorts[row['cohort']];bits=b''.join(struct.pack('<dd',coords[key][0]/10000000,coords[key][1]/10000000) for key in keys)
    assert row['occurrences']==len(keys) and row['uniqueIds']==len(set(keys)) and row['coordinateBitsSha256']==hashlib.sha256(bits).hexdigest()
assert len(result['lookup']['runs'])==9 and result['lookup']['authenticatedShardBytes']<=4294967296
assert result['referenceAudit']['rows']==16588148
close=load(pipe/'close-receipt.json');assert close['secondsThroughResultClose']>result['secondsBeforeResultClose']
metrics=load(raw/'metrics-end.json');assert int(metrics['latest']['cgroup']['memory.peak'])<=4294967296
assert 'oom 0\n' in metrics['latest']['cgroup']['memory.events'] and 'oom_kill 0\n' in metrics['latest']['cgroup']['memory.events']
assert metrics['observedWorkPeaks']['conservativeAllocatedBytes']<768*1024**2
print(json.dumps({'nationalClosedReceiptsSidecarsWitnessesVerified':True,'localProbeAndAllCohortsVerified':args.local_assets,'fullNationalIndexAllocated':False,'nationalSourceReadByProof':False},indent=2))

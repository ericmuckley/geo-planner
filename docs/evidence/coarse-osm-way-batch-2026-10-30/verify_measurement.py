"""Closed batch receipts; --local-assets independently checks every coordinate.

Uses saved witnesses and eight retained shards only, never native code or the
national PBF. Local verification decodes the probe once, not once per query.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import struct
import sys

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(f/'verify_controller.py'),run_name='__main__')
sys.path.insert(0,str(r/'scripts'))
from run_osm_way_batch_v2 import validate,WITNESS
from coarse_osm_country_screen_v1 import RECEIPT_NAMES
from coarse_osm_delta_v1 import Reader,ReferenceCodec
from run_osm_country_screen_v4 import isolation
plan=load(f/'measurement-plan-v2.json');validate(plan)
assert sha(f/'measurement-plan-v2.json')==load(f/'measurement-freeze-v2.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/') or args.local_assets:assert sha(r/name)==pin,name
closed=load(f/'measurement-closed-v2.json');raw=f/'measurement-raw-v2'
for name,row in closed['roster'].items():
    p=raw/name if row['mirrored'] else r/closed['root']/name
    if row['mirrored'] or args.local_assets:assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],name
isolation(load(raw/'container-initial.json'),'controls')
state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
assert load(f/'measurement-cleanup-audit-v2.json')['independentAbsent']
case=load(raw/'source-and-lookup.json');receipt=case['receipt'];result=load(raw/'result.json');audit=load(raw/'independent-audit.json')
assert load(raw/'run-summary.json')['status']==result['status']=='passed_bounded_way_batch'
assert result['ways']==case['ways']==receipt['batchWays']==receipt['eligibleHighwayWays']==274570
assert result['references']==case['references']==receipt['batchReferences']==receipt['deliveredBatchReferences']
assert receipt['nativeEof'] and receipt['counts']==plan['source']['counts'] and receipt['visits']==1770542426
assert receipt['semanticSha256']==plan['expectedSemantic'] and not receipt['error'] and receipt['pythonProjectionFrames']==0
prior=load(f.parent/'coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/result.json')['passes'][0]['receipt']
assert all(receipt[key]==prior[key] for key in RECEIPT_NAMES if 'Span' not in key and key!='witnessRows')
assert receipt['metadata']==prior['metadata']
source=plan['source'];identity=receipt['sourceIdentity'];binding=load(raw/'host-source-binding.json')
assert identity['sourceSha256']==binding['sha256']==source['sha256'] and identity['sourceMd5']==binding['md5']==source['md5']
assert identity['framingBytesRead']==receipt['postSourceHashBytes']==binding['bytesRead']==source['bytes']
ledger=load(raw/'ledger.json');assert len(ledger)==result['batches']==receipt['wayBatches']<=plan['caps']['batches']
assert sum(row['ways'] for row in ledger)==result['ways'] and sum(row['references'] for row in ledger)==result['references']
previous=0
for index,row in enumerate(ledger):
    assert row['file']==f'{index:04d}.bin' and re.fullmatch(r'[0-9]{4}\.bin',row['file'])
    assert 0<row['ways']<=2048 and 2*row['ways']<=row['references']<=65536
    assert previous<row['firstWay']<=row['lastWay'];previous=row['lastWay']
    saved=closed['roster']['witness/'+row['file']]
    assert saved['bytes']==row['references']*WITNESS.size and saved['sha256']==row['witnessSha256']
assert case['authenticatedShardBytes']==sum(row['authenticatedShardBytes'] for row in ledger)<=plan['caps']['lookupBytes']
assert case['lookupSeconds']==sum(row['lookupSeconds'] for row in ledger)
assert case['decodedRows']<=plan['caps']['lookupRows'] and case['codecCalls']<=plan['caps']['codecCalls']
assert audit['references']==result['references'] and audit['authenticatedShardBytes']<=plan['caps']['lookupBytes']
assert audit['decodedRows']<=plan['caps']['lookupRows'] and audit['codecCalls']<=plan['caps']['codecCalls']
assert case['caseSecondsBeforeClose']<plan['caps']['caseSeconds'] and audit['seconds']<plan['caps']['auditSeconds']
assert not result['nationalPhysicalIndexAllocated'] and not result['wholeRoadExtractionQualified'] and not result['modelChanged']
metrics=load(raw/'metrics-end.json');cgroup=metrics['latest']['cgroup']
assert int(cgroup['memory.peak'])<=4294967296 and 'oom 0\n' in cgroup['memory.events'] and 'oom_kill 0\n' in cgroup['memory.events']
assert metrics['observedWorkPeaks']['conservativeAllocatedBytes']<=768*1024**2
if args.local_assets:
    witness_root=r/closed['root']/'witness';ordered=hashlib.sha256()
    for row in ledger:ordered.update((witness_root/row['file']).read_bytes())
    assert ordered.hexdigest()==audit['orderedWitnessSha256']
    # Keep at most one source shard's queried IDs in memory. Repeated IDs must
    # retain identical bits, then every occurrence is checked against that shard.
    probe=Reader(r/plan['probe'],ReferenceCodec(),index_limit=384*1024**2,catalog_limit=4*1024**2)
    occurrences=0
    for number,descriptor in enumerate(probe.manifest['shards']):
        wanted={};selected=0
        for row in ledger:
            body=(witness_root/row['file']).read_bytes()
            for identity,x,y in WITNESS.iter_unpack(body):
                if not descriptor['first']<=identity<=descriptor['last']:continue
                selected+=1;bits=struct.pack('<dd',x,y)
                assert identity not in wanted or wanted[identity]==bits
                wanted[identity]=bits
        assert len(wanted)<=descriptor['rows']
        class WitnessCodec(ReferenceCodec):
            def __init__(self):self.found=0
            def decode(self,*arguments):
                values=super().decode(*arguments)
                for identity,x,y in values:
                    if identity in wanted:
                        assert struct.pack('<dd',x/10000000,y/10000000)==wanted[identity]
                        self.found+=1
                return values
        codec=WitnessCodec();probe.codec=codec;probe.validate_shard(number)
        assert codec.found==len(wanted);occurrences+=selected
    assert occurrences==result['references'];probe.close()
print(json.dumps({'closedSourceBatchAndBudgetReceiptsVerified':True,'everyCoordinateOccurrenceIndependentlyVerified':args.local_assets,
                  'nationalPbfRead':False,'fullIndexOrModelAdmitted':False},indent=2))

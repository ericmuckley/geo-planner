"""Fixed-sample equivalence and profiling; no national source or model launcher."""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import statistics
import struct
import time

from coarse_osm_bulk_pbf import framing,stat_key
from coarse_osm_compact_v1 import coordinate
from coarse_osm_delta_v2 import Index,Reader,ReferenceCodec,Storage
from coarse_osm_native_lock_v1 import save
from coarse_osm_native_smoke import write_xml,STATE
from coarse_osm_projector_v1 import EncodedIndex,SEAL_PREFIX,field_frame,MAX_INPUT
from coarse_osm_records import canonical,strict_json
from coarse_osm_stream_v1 import NativeValidator,native_scan
from coarse_timing_input import digest,require,start_watchdog

CAPS={'hostSeconds':600,'workSeconds':570,'workerSeconds':300,'caseSeconds':60,
    'objectsPerCase':200000,'aggregateVisits':2000000,'workingBytesIncludingTmp':1073741824,
    'tmpBytes':268435456,'fileBytes':67108864,'indexBytes':33554432,'reportBytes':2097152}
CASES=[['pair-0-python','python'],['pair-0-native','native'],['pair-1-native','native'],
    ['pair-1-python','python'],['pair-2-python','python'],['pair-2-native','native']]
ARTIFACT={'path':'data/coarse-quality/us-osm-projector-v1/build/projector.so','bytes':1935424,
    'sha256':'9227bc577f3592f167d614329ecc25311c4f8505aa854d3121f9837073f75f26'}
SAMPLES={
    'prefix':{'path':'data/coarse-quality/us-osm-profile-v2/prefix.osm.pbf','bytes':377536,
        'sha256':'8c27122ee2321a320cf33c1f8c678fdd3041fee16621984380e768d4746d38b8',
        'counts':{'node':64000},'canonicalSha256':'e845926261ab0fc4d7c1d8a904e08bbde01fd9e063b582d6537fc4cdd0a957b7'},
    'mixed':{'path':'data/coarse-quality/us-osm-inventory-v3/scan/samples.jsonl','bytes':3304488,
        'sha256':'fd45e8844f790da058c708689548ee477382826d202ff06968d91db5ee1aee95',
        'counts':{'node':1000,'way':1000,'relation':1000},
        'canonicalSha256':'fd45e8844f790da058c708689548ee477382826d202ff06968d91db5ee1aee95'}}


class Visits:
    def __init__(self,limit=CAPS['aggregateVisits']):self.limit,self.total=limit,0
    def check(self,pending=0):require(self.total+pending<=self.limit,'Sample aggregate object visits')
    def add(self,count=1):self.check(count);self.total+=count


@contextmanager
def case_deadline(seconds=CAPS['caseSeconds']):
    # A separate process kills this worker even if C++ never returns to Python.
    watchdog=start_watchdog(seconds)
    try:yield
    finally:
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def config(proposal):
    result=deepcopy(proposal)
    result['proposedCaps'].update(wallSeconds=CAPS['caseSeconds'],workingBytesIncludingTmp=CAPS['workingBytesIncludingTmp'],
        tmpBytes=CAPS['tmpBytes'],sqliteIndexBytesEach=CAPS['indexBytes'],scanNodesPerPass=CAPS['objectsPerCase'],
        scanWaysPerPass=CAPS['objectsPerCase'],scanRelationsPerPass=CAPS['objectsPerCase'],scanObjectVisitsTotal=CAPS['objectsPerCase'])
    return result


def source_start(path,caps,snapshot,check):
    path=Path(path)
    require(not path.is_symlink() and path.is_file() and path.stat().st_size<=MAX_INPUT,'Fixed sample source type/size')
    before=stat_key(path);began=time.monotonic();identity=framing(path,caps,snapshot,check)
    return before,identity,time.monotonic()-began


def source_end(path,before,identity,check):
    began=time.monotonic();check()
    require(digest(path)==identity['sourceSha256'] and stat_key(path)==before,'Fixed sample post-scan source drift')
    check();return {'postSourceHashSeconds':time.monotonic()-began,'postSourceHashBytes':before[2]}


def run_case(path,proposal,folder,*,engine,budget,mode,proof=False,expected=None,queries=(),source_sha=None):
    """Same V2 index, source guards and lookup policy on both sides of the pair."""
    require(mode in ('python','native') and (expected is None or mode=='native' and proof),'Sample case mode')
    folder=Path(folder);folder.mkdir();caps=proposal['proposedCaps'];snapshot=proposal['source']['proposedPublisherReplicationStateUtc']
    index=None;native=None;receipt=None;began=time.monotonic();counts=Counter();ids=[]
    if mode=='native':engine.last=None
    json_hash=hashlib.sha256();semantic=hashlib.sha256(SEAL_PREFIX);output_bytes=0;coordinate_rows=0
    def check():
        require(time.monotonic()-began<CAPS['caseSeconds'],'Sample case deadline')
        budget.check(engine.progress()['visits'] if mode=='native' else 0)
    try:
        with case_deadline():
            before,identity,framing_seconds=source_start(path,caps,snapshot,check)
            if source_sha is not None:require(identity['sourceSha256']==source_sha,'Fixed sample source SHA binding')
            storage=Storage(CAPS['indexBytes'],CAPS['fileBytes'])
            index=(EncodedIndex if mode=='native' else Index)(folder/'index',storage,codec=engine.codec,index_limit=CAPS['indexBytes'])
            # Proof files are separate from paired fast work and bounded per file.
            with (folder/'fields.jsonl').open('xb') as output,(folder/'coordinates.bin').open('xb') as coordinates:
                oracle=Path(expected).open('rb') if expected is not None else None
                def consume(raw,line=None):
                    nonlocal output_bytes,coordinate_rows
                    check();counts[raw['type']]+=1
                    if mode=='python':budget.add()
                    require(sum(counts.values())<=CAPS['objectsPerCase'],'Sample per-case receipts')
                    line=canonical(raw)+b'\n' if line is None else line
                    json_hash.update(line)
                    if proof:
                        output_bytes+=len(line);require(output_bytes<=CAPS['fileBytes'],'Sample proof-file cap');output.write(line)
                        if oracle is not None:require(oracle.readline(caps['singleNormalizedElementBytes']+2)==line,'Sample full-field oracle mismatch')
                        frame=field_frame(raw);semantic.update(struct.pack('<I',len(frame)));semantic.update(frame)
                    if raw['type']=='node':
                        if len(ids)<1024:ids.append(raw['id'])
                        if mode=='python':index.add(raw)
                        if proof:
                            coordinates.write(struct.pack('<qii',raw['id'],coordinate(raw['lon'],180),coordinate(raw['lat'],90)));coordinate_rows+=1
                loop=time.monotonic()
                try:
                    if mode=='native':
                        try:
                            receipt=engine._run(engine.pbf,[os.fsencode(path)],snapshot,caps,proof=proof,on_record=consume,
                                on_block=lambda body:index.append_encoded(body,engine.codec),check=check)
                        finally:
                            if engine.last is not None:budget.add(engine.last['visits'])
                        counts=Counter(receipt['counts'])
                    else:
                        native=NativeValidator(snapshot,caps['singleNormalizedElementBytes'],caps,consume);native_scan(path,native)
                    index.finish();loop_seconds=time.monotonic()-loop
                    post=source_end(path,before,identity,check)
                    if oracle is not None:require(not oracle.read(1),'Sample oracle has extra records')
                finally:
                    if oracle is not None:oracle.close()
            protected_seconds=time.monotonic()-began
            if proof:
                reader=Reader(index.root,ReferenceCodec());seen=0
                try:
                    with (folder/'coordinates.bin').open('rb') as stream:
                        for number in range(reader.manifest['blocks']):
                            keys,xy=reader.block(number)
                            for k,key in enumerate(keys):
                                require(stream.read(16)==struct.pack('<qii',key,xy[2*k],xy[2*k+1]),'Sample full-index coordinate mismatch');seen+=1
                        require(not stream.read(1) and seen==coordinate_rows,'Sample coordinate proof closure')
                finally:reader.close()
            lookup=[]
            if queries:
                index.reader.cache.clear();index.reader.format_verified.clear()
                for label in ('cold','warm','repeat'):
                    check();start=time.monotonic();loaded=index.reader.loaded_bytes;points=index.points(queries)
                    lookup.append({'kind':label,'seconds':time.monotonic()-start,'queries':len(queries),
                        'coordinateBitsSha256':hashlib.sha256(b''.join(struct.pack('<dd',*p) for p in points)).hexdigest(),
                        'authenticatedShardBytesRead':index.reader.loaded_bytes-loaded})
            result={'mode':mode,'proofMode':proof,'counts':dict(counts),'eof':receipt['nativeEof'] if receipt else native.eof,
                'decodeValidateIndexSealEofSeconds':loop_seconds,'framingSeconds':framing_seconds,**post,
                'protectedTotalSeconds':protected_seconds,'framingBytesRead':identity['framingBytesRead'],
                'knownGuardReadBytes':identity['framingBytesRead']+post['postSourceHashBytes'],
                'guardReadScope':'Framing/pre-hash+post-hash only; decoder/index/lookup reads are separate, never an all-IO total.',
                'sourceIdentity':identity,'canonicalSha256':json_hash.hexdigest() if mode=='python' or proof else None,
                'semanticSha256':receipt['semanticSha256'] if receipt else semantic.hexdigest() if proof else None,
                'semanticFormat':'geo-planner-projected-fields-v1','indexBytes':index.generated_bytes,
                'indexManifestSha256':digest(index.root/'index.json'),'lookup':lookup,
                'queryIds':ids if proof else [],'receipt':receipt,'coordinateRowsProved':coordinate_rows if proof else None}
            if receipt and proof:require(result['semanticSha256']==semantic.hexdigest(),'Sample native full-field semantic mismatch')
            require(result['eof'],'Sample missing normal EOF');save(folder/'result.json',result);return result
    except BaseException as error:
        save(folder/'partial-result.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],
            'counts':dict(counts),'nativeReceipt':engine.last if mode=='native' else None,'eof':False,'indexesTrusted':False})
        raise
    finally:
        if index is not None:index.close()


def encode_mixed(path,target,budget,expected_counts):
    """Round-trip precisely the saved raw fields; never fill missing dependencies."""
    import osmium
    rows=[]
    with case_deadline(),Path(path).open('rb') as stream:
        while line:=stream.readline(1048578):
            budget.add();require(len(line)<=1048577 and line.endswith(b'\n') and len(rows)<3000,'Mixed record/line bound')
            rows.append(strict_json(line))
        require(Counter(row['type'] for row in rows)==expected_counts,'Mixed input typed counts')
        xml=Path(target).with_suffix('.osm');write_xml(xml,rows)
        require(xml.stat().st_size<=CAPS['fileBytes'],'Mixed XML byte cap')
        header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE);header.set('generator','geo-planner-fixed-sample-v1')
        encoded=0
        with osmium.SimpleWriter(str(target),header=header,bufsz=65536) as writer:
            for obj in osmium.FileProcessor(str(xml)):budget.add();writer.add(obj);encoded+=1
        require(encoded==len(rows) and Path(target).stat().st_size<=MAX_INPUT,'Mixed encoding count/size')
    return {'records':len(rows),'encodingNativeViews':encoded,'jsonReceiptVisits':len(rows),'pbfBytes':Path(target).stat().st_size,
        'pbfSha256':digest(target),'scope':'Re-encoded first1000/type projected records, not original publisher PBF or dependency-complete roads.'}


def samples(plan,root,engine):
    root=Path(root);proposal=config(plan['extractConfig']);budget=Visits();proofs={};cases=[]
    # Decode only these fixed saved samples; no national input is mounted.
    mixed=encode_mixed('/samples/mixed.jsonl',root/'mixed.pbf',budget,SAMPLES['mixed']['counts']);save(root/'mixed-encoding.json',mixed)
    for name,path in (('prefix','/samples/prefix.pbf'),('mixed',root/'mixed.pbf')):
        source_sha=SAMPLES['prefix']['sha256'] if name=='prefix' else mixed['pbfSha256']
        reference=run_case(path,proposal,root/(name+'-reference-proof'),engine=engine,budget=budget,mode='python',proof=True,source_sha=source_sha)
        require(reference['counts']==SAMPLES[name]['counts'] and reference['canonicalSha256']==SAMPLES[name]['canonicalSha256'],'Fixed sample reference identity changed')
        actual=run_case(path,proposal,root/(name+'-native-proof'),engine=engine,budget=budget,mode='native',proof=True,
            expected=root/(name+'-reference-proof')/'fields.jsonl',source_sha=source_sha)
        require(actual['counts']==reference['counts'] and actual['canonicalSha256']==reference['canonicalSha256'] and actual['semanticSha256']==reference['semanticSha256'],'Fixed sample proof mismatch')
        proofs[name]={'python':reference,'native':actual}
    ids=proofs['prefix']['python']['queryIds'];queries=list(reversed(ids))+ids[:128]
    for name,mode in CASES:
        result=run_case('/samples/prefix.pbf',proposal,root/name,engine=engine,budget=budget,mode=mode,queries=queries,source_sha=SAMPLES['prefix']['sha256'])
        require(result['counts']==SAMPLES['prefix']['counts'],'Prefix pair count mismatch')
        require(result['indexManifestSha256']==proofs['prefix']['native']['indexManifestSha256']==proofs['prefix']['python']['indexManifestSha256'],'Paired full-index content mismatch')
        if mode=='native':require(result['semanticSha256']==proofs['prefix']['native']['semanticSha256'] and result['receipt']['pythonProjectionFrames']==0,'Fast prefix semantic/projection mismatch')
        else:require(result['canonicalSha256']==SAMPLES['prefix']['canonicalSha256'],'Reference prefix canonical mismatch')
        cases.append(dict(name=name,**result))
    require(len({row['coordinateBitsSha256'] for c in cases for row in c['lookup']})==1,'Paired lookup coordinate bits differ')
    require(len({c['indexBytes'] for c in cases})==1,'Same frozen format has different index sizes')
    medians={mode:statistics.median(c['protectedTotalSeconds'] for c in cases if c['mode']==mode) for mode in ('python','native')}
    passed=medians['native']<=.070 and medians['native']<medians['python']
    result={'status':'passed_fixed_sample_screen' if passed else 'equivalent_but_performance_gate_failed','proofs':proofs,'cases':cases,
        'medianProtectedSeconds':medians,'medianSpeedup':medians['python']/medians['native'],'performanceGatePassed':passed,
        'aggregateObjectVisits':budget.total,'wholeSourceEof':False,'wholeExtractionQualified':False,'nationalRunAdmitted':False,
        'modelChanged':False,'scope':'Fixed node-prefix validation/index and re-encoded mixed field equivalence; synthetic selected-output audit remains separate.'}
    save(root/'result.json',result);return 0 if passed else 2

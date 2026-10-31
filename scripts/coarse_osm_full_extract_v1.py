"""Two-pass controlled extraction prototype; national allocation launcher absent."""
from copy import deepcopy
import hashlib
from pathlib import Path
import time

from coarse_osm_bulk import Run,Selection,heap_size,records
from coarse_osm_bulk_audit import crossing
from coarse_osm_delta_v2 import Storage
from coarse_osm_lookup_v3 import Reader
from coarse_osm_projector_v1 import EncodedIndex
from coarse_osm_records import canonical,intersects
from coarse_osm_stream_v1 import Audit
from coarse_timing_input import digest,require


def primary_windows(points,windows):
    west=south=float('inf');east=north=-float('inf')
    for x,y in points:
        west=min(west,x);east=max(east,x);south=min(south,y);north=max(north,y)
    return [window for window in windows if not (east<window['bbox'][0] or west>window['bbox'][2] or north<window['bbox'][1] or south>window['bbox'][3])]


class BatchAudit(Audit):
    def way_with_points(self,raw,points):
        # Independently derive the conservative envelope; no primary hints/bbox.
        low_x=min(point[0] for point in points);high_x=max(point[0] for point in points)
        low_y=min(point[1] for point in points);high_y=max(point[1] for point in points)
        for window in self.proposal['windows']:
            left,bottom,right,top=window['bbox']
            if high_x<left or low_x>right or high_y<bottom or low_y>top:continue
            if crossing(points,window['bbox']):
                self.add(window['id'],('way',raw['id']))
                for identity in raw['nodes']:self.add(window['id'],('node',identity))
        if ('way',raw['id']) in self.keys:self.keep(raw)


def extract(path,proposal,root,*,engine,source=None,primary_hook=None,before_second=None,materialized_hook=None,
            check=lambda:None,storage=None,lookup_io=64*1024**2):
    run=Run(root,proposal);snapshot=proposal['source']['proposedPublisherReplicationStateUtc']
    run.state.update(publisherStateUtc=snapshot,counterScope='Recognized native source objects including rejected/cap+1; full count/seal only at normal EOF.')
    if storage is None:storage=Storage(run.caps['workingBytesIncludingTmp']-run.caps['tmpBytes']-8388608,64*1024**2)
    first=EncodedIndex(run.root/'primary-index',storage,codec=engine.codec,index_limit=run.caps['sqliteIndexBytesEach'])
    second=reader=None;receipts=[];primary=Selection(proposal['windows'],run);audit=None;last_sample=0.

    def phase_check():
        nonlocal last_sample
        check();run.check(storage=False)
        now=time.monotonic()
        if now-last_sample>=1:
            last_sample=now;run.check();run.checkpoint()

    def open_query(index):
        index.finish()
        return Reader(index.root,engine.codec,index_limit=run.caps['sqliteIndexBytesEach'],catalog_limit=16*1024**2,read_limit=lookup_io)

    def scan(index,label,consume,selected=(),on_record=None):
        nonlocal reader
        previous=run.state['scanObjectVisits'];stage={'label':label,'status':'running','counts':{}}
        run.state['passes'].append(stage);run.state['stage']=label;run.checkpoint();reader=None
        def receive_block(body):
            engine.codec.check_call();index.append_encoded(body,engine.codec)
        def receive_batch(rows):
            nonlocal reader
            require(heap_size(rows)<=run.caps['retainedNativeObjectBytes'],'Extraction live batch heap cap')
            if reader is None:reader=open_query(index)
            keys=[identity for row in rows for identity in row['nodes']]
            points=reader.points(keys)
            require(heap_size(rows)+heap_size(keys)+heap_size(points)<=run.caps['retainedNativeObjectBytes'],'Extraction live coordinate batch heap cap')
            cursor=0
            for raw in rows:
                end=cursor+len(raw['nodes']);consume(raw,points[cursor:end]);cursor=end
            require(cursor==len(points),'Extraction batch geometry closure')
            phase_check()
        def progress():
            current=engine.progress()
            if not engine.active and engine.last is not None:current={'counts':engine.last['counts'],'visits':engine.last['visits']}
            stage['counts']=current['counts'];run.state['scanObjectVisits']=previous+current['visits'];phase_check()
        caps=dict(run.caps,singleNormalizedElementBytes=4194304,scanObjectVisitsTotal=run.caps['scanObjectVisitsTotal']-previous)
        try:
            receipt=engine.scan(path,snapshot,caps,source=source,selected=selected,on_record=on_record,on_block=receive_block,
                                on_way_batch=receive_batch,batch_scope='all',
                                batch_caps={'ways':run.caps['scanWaysPerPass'],'references':5330986500096,'batches':1000000},check=progress)
            index.finish();stage.update(status='eof',counts=receipt['counts']);run.state['scanObjectVisits']=previous+receipt['visits']
            receipts.append(receipt);phase_check()
            return dict(authenticatedShardBytes=reader.loaded_bytes if reader else 0,hashAndFormatSeconds=reader.hash_seconds if reader else 0,
                        blockDecodeSeconds=reader.decode_seconds if reader else 0)
        except BaseException:
            if engine.last is not None:
                stage['counts']=engine.last['counts'];run.state['scanObjectVisits']=previous+engine.last['visits']
            raise
        finally:
            if reader is not None:reader.close();reader=None

    def choose(raw,points):
        for window in primary_windows(points,proposal['windows']):
            if intersects(points,window['bbox']):
                primary.add(window['id'],('way',raw['id']))
                for identity in raw['nodes']:primary.add(window['id'],('node',identity))
        if ('way',raw['id']) in primary.keys:
            # Full selected fields are materialized in pass B. A canonical digest
            # is sufficient to detect drift without retaining a third raw copy.
            primary.ways[raw['id']]=hashlib.sha256(canonical(raw)).hexdigest()
            run.charge(heap_size((raw['id'],primary.ways[raw['id']]))+256)

    try:
        primary_lookup=scan(first,'all-highway-primary-selection',choose)
        if primary_hook is not None:primary_hook(primary)
        if before_second is not None:before_second()
        audit=BatchAudit(proposal,run)
        second=EncodedIndex(run.root/'audit-index',storage,codec=engine.codec,index_limit=run.caps['sqliteIndexBytesEach'],replacing=first)
        def audit_way(raw,points):
            audit.way_with_points(raw,points)
            key=('way',raw['id'])
            if key in primary.keys:
                require(hashlib.sha256(canonical(raw)).hexdigest()==primary.ways[raw['id']],'Extraction primary way-field drift')
                primary.keep(raw)
        def materialize(raw):
            key=raw['type'],raw['id']
            if key[0]=='node':
                require(key in primary.keys,'Extraction unexpected selected node')
                audit.keep(raw);primary.keep(raw)
            else:
                audit.relation(raw)
                for window in primary.members:
                    if any((member['type'],member['ref']) in primary.members[window] and member['type'] in ('node','way') for member in raw['members']):primary.add(window,key)
                if key in primary.keys:primary.keep(raw)
        selected=sorted(identity for kind,identity in primary.keys if kind=='node')
        audit_lookup=scan(second,'all-highway-independent-materialization',audit_way,selected,materialize)
        require(receipts[0]['sourceIdentity']['sourceSha256']==receipts[1]['sourceIdentity']['sourceSha256'],'Extraction source byte drift')
        require(receipts[0]['semanticSha256']==receipts[1]['semanticSha256'],'Extraction whole-field semantic drift')
        require(all(row['nativeEof'] and row['counts']==receipts[0]['counts'] for row in receipts),'Extraction normal EOF/count drift')
        require(set(audit.objects)==audit.keys and set(primary.objects)==primary.keys,'Extraction independent materialization hint/dependency mismatch')
        if materialized_hook is not None:materialized_hook(primary)
        run.state['windowOccurrences']=primary.occurrences;output=run.root/'elements.jsonl'
        with output.open('xb') as stream:
            for row in records(primary,snapshot):
                encoded=canonical(row)+b'\n'
                require(len(encoded)<=run.caps['singleNormalizedElementBytes'] and run.state['extractBytes']+len(encoded)<=run.caps['normalizedExtractBytes'],'Extraction output cap')
                phase_check();stream.write(encoded);run.state['extractBytes']+=len(encoded);run.state['retainedElements']+=1
        audit.compare(output)
        run.state.update(status='passed_all_highway_extraction_prototype',independentAuditComplete=True,outputSha256=digest(output),
                         nativeReceipts=receipts,lookups=[primary_lookup,audit_lookup],coordinateStoragePeakBytes=storage.peak,
                         coordinateStorageLiveBytes=storage.live,nativeAllHighwaySyntheticQualified=True,wholeExtractionQualified=False,modelChanged=False)
    except BaseException as error:
        run.state.update(status='stopped',errorType=type(error).__name__,error=str(error),nativeReceipts=receipts,
                         lastNativeReceipt=engine.last,derivedIndexesTrusted=False,independentAuditComplete=False)
    finally:
        if reader is not None:reader.close()
        for index in (first,second):
            if index is not None:index.close()
    run.checkpoint();return run.state

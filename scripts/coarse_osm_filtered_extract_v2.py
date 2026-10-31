"""Two-pass conservative cell filtering; no national allocation launcher."""
from copy import deepcopy
import hashlib
from pathlib import Path
import time

from coarse_osm_bulk import Run,Selection,heap_size,records
from coarse_osm_bulk_audit import crossing
from coarse_osm_delta_v2 import Storage
from coarse_osm_lookup_v3 import Reader
from coarse_osm_projector_v1 import EncodedIndex,BLOCK_EVENT
from coarse_osm_window_bank_v2 import Writer as CellWriter,Bank,LIMIT as CELL_LIMIT
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
            check=lambda:None,storage=None,lookup_io=64*1024**2,live_batch_heap_bytes=128*1024**2,
            cell_codec,masker,expected_counts,bank_limit=CELL_LIMIT,index_factory=EncodedIndex):
    require(type(live_batch_heap_bytes) is int and 0<live_batch_heap_bytes<=128*1024**2,'Extraction transient heap limit')
    peak_batch_heap=0
    require(type(bank_limit) is int and 0<bank_limit<=CELL_LIMIT,'Extraction cell bank bound')
    require(set(expected_counts)=={'node','way','relation'} and all(type(v) is int and v>=0 for v in expected_counts.values()) and expected_counts['node']>0,'Extraction expected source counts')
    require(masker.grid.ids==cell_codec.cells.ids and masker.grid.boxes==cell_codec.cells.boxes and masker.grid.codes==cell_codec.cells.codes,'Extraction primary/audit query binding')
    cell_bank_peak=0;coarse_lookups=[]
    run=Run(root,proposal);snapshot=proposal['source']['proposedPublisherReplicationStateUtc']
    run.state.update(publisherStateUtc=snapshot,counterScope='Recognized native source objects including rejected/cap+1; full count/seal only at normal EOF.')
    if storage is None:storage=Storage(run.caps['workingBytesIncludingTmp']-run.caps['tmpBytes']-8388608,64*1024**2)
    first=index_factory(run.root/'primary-index',storage,codec=engine.codec,index_limit=run.caps['sqliteIndexBytesEach'])
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
        nonlocal reader,cell_bank_peak
        cell_reader=None;cell_writer=CellWriter(run.root/(label+'-cells'),storage,proposal['windows'],expected_counts['node'],limit=bank_limit)
        metrics={'examinedReferences':0,'fineReferences':0,'certifiedOutsideWays':0}
        previous=run.state['scanObjectVisits'];stage={'label':label,'status':'running','counts':{}}
        run.state['passes'].append(stage);run.state['stage']=label;run.checkpoint();reader=None
        def receive_block(body):
            engine.codec.check_call();index.append_encoded(body,engine.codec)
            count,first,last,size=BLOCK_EVENT.unpack_from(body)
            cell_writer.append(cell_codec.encode(body[BLOCK_EVENT.size:],count,first,last),cell_codec)
        def receive_batch(rows):
            nonlocal reader,cell_reader,peak_batch_heap,cell_bank_peak
            row_heap=heap_size(rows);peak_batch_heap=max(peak_batch_heap,row_heap)
            require(row_heap<=live_batch_heap_bytes,'Extraction live batch heap cap')
            if reader is None:
                reader=open_query(index);cell_writer.finish()
                cell_reader=Bank(cell_writer.root,cell_codec,proposal['windows'],expected_rows=expected_counts['node'],limit=bank_limit)
                cell_bank_peak=max(cell_bank_peak,cell_reader.loaded_bytes)
            keys=[identity for row in rows for identity in row['nodes']]
            cells=cell_reader.lookup(keys)
            flags=masker.masks(cells,[len(row['nodes']) for row in rows],audit=label=='all-highway-independent-materialization')
            needed=[identity for raw,mask in zip(rows,flags) if mask for identity in raw['nodes']]
            metrics['examinedReferences']+=len(keys);metrics['fineReferences']+=len(needed);metrics['certifiedOutsideWays']+=sum(mask==0 for mask in flags)
            points=reader.points(needed) if needed else []
            working_heap=row_heap+heap_size(keys)+heap_size(cells)+heap_size(flags)+heap_size(needed)+heap_size(points)
            peak_batch_heap=max(peak_batch_heap,working_heap)
            require(working_heap<=live_batch_heap_bytes,'Extraction live coordinate batch heap cap')
            cursor=0
            for raw,mask in zip(rows,flags):
                if not mask:continue
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
            index.finish();cell_writer.finish()
            if cell_reader is None:
                cell_reader=Bank(cell_writer.root,cell_codec,proposal['windows'],expected_rows=expected_counts['node'],limit=bank_limit)
                cell_bank_peak=max(cell_bank_peak,cell_reader.loaded_bytes)
            cell_reader.verify_files()
            require({kind:receipt['counts'].get(kind,0) for kind in expected_counts}==expected_counts,'Extraction expected whole source counts')
            coarse_lookups.append({'label':label,'bankBytes':cell_writer.stored_bytes,'bankBlocks':cell_writer.blocks,
                                   'codecRowsCumulative':cell_codec.rows,'codecCallsCumulative':cell_codec.calls,
                                   'maskReferencesCumulative':masker.references,'maskCallsCumulative':masker.calls,
                                   'queryBlocks':cell_reader.lookup_blocks if cell_reader else 0,**metrics})
            stage.update(status='eof',counts=receipt['counts']);run.state['scanObjectVisits']=previous+receipt['visits']
            receipts.append(receipt);phase_check()
            return dict(authenticatedShardBytes=reader.loaded_bytes if reader else 0,hashAndFormatSeconds=reader.hash_seconds if reader else 0,
                        blockDecodeSeconds=reader.decode_seconds if reader else 0)
        except BaseException:
            if engine.last is not None:
                stage['counts']=engine.last['counts'];run.state['scanObjectVisits']=previous+engine.last['visits']
            raise
        finally:
            if reader is not None:reader.close();reader=None
            if cell_reader is not None:cell_reader.close()

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
        second=index_factory(run.root/'audit-index',storage,codec=engine.codec,index_limit=run.caps['sqliteIndexBytesEach'],replacing=first)
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
        run.state.update(status='passed_cell_filtered_extraction_prototype',independentAuditComplete=True,outputSha256=digest(output),
                         nativeReceipts=receipts,lookups=[primary_lookup,audit_lookup],coordinateStoragePeakBytes=storage.peak,
                         coordinateStorageLiveBytes=storage.live,cellBankBytesPeak=cell_bank_peak,coarseLookups=coarse_lookups,liveBatchHeapLimitBytes=live_batch_heap_bytes,liveBatchConservativeHeapPeakBytes=peak_batch_heap,nativeCellFilteredSyntheticQualified=True,wholeExtractionQualified=False,modelChanged=False)
    except BaseException as error:
        run.state.update(status='stopped',errorType=type(error).__name__,error=str(error),nativeReceipts=receipts,
                         lastNativeReceipt=engine.last,derivedIndexesTrusted=False,independentAuditComplete=False)
    finally:
        if reader is not None:reader.close()
        for index in (first,second):
            if index is not None:index.close()
    run.checkpoint();return run.state

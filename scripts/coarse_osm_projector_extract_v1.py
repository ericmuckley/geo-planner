"""Synthetic native PBF two-pass integration; no national import launcher."""
from copy import deepcopy
import hashlib

from coarse_osm_bulk import Run,Selection,heap_size,records
from coarse_osm_stream_v1 import Audit
from coarse_osm_projector_v1 import EncodedIndex
from coarse_osm_delta_v1 import Storage
from coarse_osm_records import canonical,intersects,normalize
from coarse_timing_input import digest,require


def extract(path,proposal,root,*,engine,primary_hook=None,before_second=None):
    run=Run(root,proposal);snapshot=proposal['source']['proposedPublisherReplicationStateUtc'];run.state['publisherStateUtc']=snapshot
    storage=Storage(run.caps['workingBytesIncludingTmp']-run.caps['tmpBytes']-8388608,run.caps['sqliteIndexBytesEach'])
    first=EncodedIndex(run.root/'primary-index',storage,codec=engine.codec,index_limit=run.caps['sqliteIndexBytesEach']);second=None
    receipts=[];primary=Selection(proposal['windows'],run)
    def scan(label,index,on_record,selected=()):
        previous=run.state['scanObjectVisits'];record={'label':label,'status':'running','counts':{}};run.state['passes'].append(record);run.state['stage']=label;run.checkpoint()
        def check():
            progress=engine.progress();record['counts']=progress['counts'];run.state['scanObjectVisits']=previous+progress['visits']
            run.check()
            if progress['visits']%128==0:run.checkpoint()
        caps=dict(run.caps,scanObjectVisitsTotal=run.caps['scanObjectVisitsTotal']-previous)
        try:
            receipt=engine.scan(path,snapshot,caps,selected=selected,on_record=on_record,on_block=lambda data:index.append_encoded(data,engine.codec),check=check)
            record['counts']=receipt['counts'];run.state['scanObjectVisits']=previous+receipt['visits'];record['status']='eof';receipts.append(receipt)
        except BaseException:
            if engine.last is not None:
                record['counts']=engine.last['counts'];run.state['scanObjectVisits']=previous+engine.last['visits']
            raise
        index.finish();run.checkpoint()
    def primary_record(raw):
        require(raw['type']!='node','Fast primary unexpectedly projected a node')
        first.finish()
        if raw['type']=='way' and 'highway' in raw['tags']:
            normalize(raw,snapshot,run.caps['singleNormalizedElementBytes']);points=first.points(raw['nodes'])
            for window in proposal['windows']:
                if intersects(points,window['bbox']):
                    primary.add(window['id'],('way',raw['id']))
                    for identity in raw['nodes']:primary.add(window['id'],('node',identity))
            if ('way',raw['id']) in primary.keys:
                primary.ways[raw['id']]=deepcopy(raw);run.charge(heap_size((raw['id'],raw))+256)
    try:
        scan('native-primary-selection',first,primary_record)
        if primary_hook is not None:primary_hook(primary)
        if before_second is not None:before_second()
        audit=Audit(proposal,run)
        second=EncodedIndex(run.root/'audit-index',storage,codec=engine.codec,index_limit=run.caps['sqliteIndexBytesEach'],replacing=first)
        def audit_record(raw):
            key=raw['type'],raw['id']
            if key[0]=='node':
                if key in primary.keys:audit.keep(raw)
            else:second.finish()
            if key[0]=='way' and 'highway' in raw['tags']:audit.way(raw,second)
            if key[0]=='relation' and raw['tags'].get('type')=='restriction':
                audit.relation(raw)
                for window in primary.members:
                    if any((m['type'],m['ref']) in primary.members[window] and m['type'] in ('node','way') for m in raw['members']):primary.add(window,key)
            if key in primary.keys:
                if key[0]=='way':require(raw==primary.ways[raw['id']],'Native primary way drift')
                primary.keep(raw)
        scan('native-materialize-independent-audit',second,audit_record,sorted(i for kind,i in primary.keys if kind=='node'))
        require(receipts[0]['sourceIdentity']['sourceSha256']==receipts[1]['sourceIdentity']['sourceSha256'],'Native two-pass source bytes drift')
        require(receipts[0]['semanticSha256']==receipts[1]['semanticSha256'],'Native two-pass full-field semantic drift')
        require(set(audit.objects)==audit.keys and set(primary.objects)==primary.keys,'Native audit materialization hints')
        run.state['windowOccurrences']=primary.occurrences;output=run.root/'elements.jsonl'
        with output.open('xb') as stream:
            for row in records(primary,snapshot):
                line=canonical(row)+b'\n';require(len(line)<=run.caps['singleNormalizedElementBytes'] and run.state['extractBytes']+len(line)<=run.caps['normalizedExtractBytes'],'Native output byte cap')
                run.check();stream.write(line);run.state['extractBytes']+=len(line);run.state['retainedElements']+=1
        audit.compare(output)
        require(len(run.state['passes'])==2 and all(r['nativeEof'] and r['counts']==receipts[0]['counts'] for r in receipts),'Native EOF/count disagreement')
        run.state.update(status='passed_native_projector_synthetic',independentAuditComplete=True,outputSha256=digest(output),nativeReceipts=receipts,
            sourceSemanticHashes=[r['semanticSha256'] for r in receipts],semanticFormat='geo-planner-projected-fields-v1',
            coordinateStoragePeakBytes=storage.peak,coordinateStorageLiveBytes=storage.live,nativeProjectionSyntheticQualified=True,wholeExtractionQualified=False)
    except Exception as error:
        run.state.update(status='stopped',errorType=type(error).__name__,error=str(error)[:1000],nativeReceipts=receipts,independentAuditComplete=False,derivedIndexesTrusted=False)
    finally:
        first.close()
        if second is not None:second.close()
    run.checkpoint();return run.state

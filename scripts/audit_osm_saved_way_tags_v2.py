"""Audit a sealed complete CST1 output after its original metadata stability stop."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_conditional_records_v1 import read_records
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_osm_selected_way_tag_audit_v2 import audit

REPO=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(recipe,pin):
    began=time.monotonic();assert sha(recipe)==pin
    plan=json.loads(recipe.read_bytes());assert plan['output']=='data/coarse-quality/us-osm-selected-way-tags-audit-v2'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+104857600+67108864<72*1024**3
    for name,pin in plan['bindings'].items():
        assert not name.endswith(('.pbf','/001.bin','.sqlite')) and sha(REPO/name)==pin,name
    root=REPO/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<=1048576
        with (root/name).open('xb')as stream:stream.write(raw)
    def check():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        assert rss<536870912 and time.monotonic()-began<300 and owned_usage(root)['conservativeAllocatedBytes']<67108864
        return rss
    try:
        selection={};digest=hashlib.sha256();total=0
        with gzip.open(REPO/plan['selectionGeometry'],'rb')as stream:
            while raw:=stream.readline(4194305):
                assert len(raw)<=4194304 and raw.endswith(b'\n');total+=len(raw);digest.update(raw)
                row=json.loads(raw);identity=row['sourceWay'];assert identity not in selection
                selection[identity]={k:row[k]for k in ('sourceWay','storedSourceFlags','baseEligible','finalFallbackClosed')}
                if len(selection)%512==0:check()
        assert len(selection)==52743 and total==17291126 and digest.hexdigest()=='11c60bf7b56382d458260477ac81a33a01088e82ee79bd144ad30a29616a85d4'
        source=REPO/plan['savedTags'];identity=stat_key(source);number=tag_bytes=0
        for row in read_records(source):
            assert row['type']=='way';number+=1;tag_bytes+=sum(len(k.encode())+len(v.encode())for k,v in row['tags'].items())
        assert number==52743
        counters=dict(requestedWays=number,selectedRecords=number,encodedBytes=source.stat().st_size,tagUtf8Bytes=tag_bytes)
        result=audit(source,counters,selection,check)
        prior=json.loads(gzip.decompress((REPO/plan['previousCachedEvidence']).read_bytes()))
        assert len(prior['knownWays'])==616
        assert all(result['wayEvidence'][str(r['sourceWay'])]['rawTags']==r['rawTags'] for r in prior['knownWays'])
        assert stat_key(source)==identity and sha(source)==plan['bindings'][plan['savedTags']]
        raw=(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(raw)<=48*1048576
        packed=gzip.compress(raw,mtime=0);assert len(packed)<=16*1048576
        with (root/'way-evidence.json.gz').open('xb')as stream:stream.write(packed)
        save('report.json',dict(status='all52743_saved_original_way_tags_independently_audited_v2',recipeSha256=sha(recipe),
             selectedTags=counters,counterOrigin='Independent recount of sealed CST1; no invented persisted native counters.',
             causeCounts=result['currentBaseReasonCounts'],allCached616OriginalTagsExact=True,unknownRawWayIds=[],
             artifacts={'way-evidence.json.gz':dict(bytes=len(packed),sha256=hashlib.sha256(packed).hexdigest(),rawBytes=len(raw),rawSha256=hashlib.sha256(raw).hexdigest())},
             savedBinary=dict(path=plan['savedTags'],bytes=source.stat().st_size,sha256=plan['bindings'][plan['savedTags']]),
             sourcePbfScans=0,sourceConstructorExecutions=0,routingQueries=0,providerRequests=0,applicationDbReads=0,
             upstreamSourceGuardEvidence='Inferred from sealed original control flow and exact recorded failure location after guarded scan/native finish/all-record audit; original numeric source/native receipts were not persisted.',
             originalNumericSourceReceiptPersisted=False,sourcePermissionsOrPricesChanged=False,appActivated=False,
             hostSecondsIncludingBindingsRecountAndIndependentAudit=time.monotonic()-began,hostMaximumRssBytes=check(),
             scope=plan['scope']))
    except BaseException as error:
        save('failure.json',dict(status='saved_original_way_audit_stopped',error=repr(error)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recipe',type=Path);p.add_argument('pin');a=p.parse_args();run(a.recipe,a.pin)

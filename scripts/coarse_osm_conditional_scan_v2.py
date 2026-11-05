"""Bound source census followed by independent complete changed-tag replay."""
import hashlib
from pathlib import Path
import time
from coarse_osm_conditional_records_v1 import read_records
import coarse_osm_car_policy_v2 as old
import coarse_osm_car_conditional_speed_v1 as new
from coarse_timing_input import require


def audit(output,counters,check):
    output=Path(output);before=output.stat();identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
    with output.open('rb') as stream:before_sha=hashlib.file_digest(stream,'sha256').hexdigest()
    counts={'nodes':0,'ways':0,'speedWays':0,'scopeWays':0,'tagUtf8Bytes':0}
    for index,record in enumerate(read_records(output)):
        if index%256==0:check()
        tags=record['tags'];counts['tagUtf8Bytes']+=sum(len(k.encode())+len(v.encode()) for k,v in tags.items())
        if record['type']=='node':
            a,b=old.node_policy(tags),new.node_policy(tags)
            require(a['blocked'] and not b['blocked'] and a['signal']==b['signal'] and a['tagged']==b['tagged'],'Changed node independently opens only blocked bit')
            counts['nodes']+=1
        else:
            a,b=old.way_policy(tags),new.way_policy(tags)
            require(a.reason is not None and b.reason is None,'Changed major way independently newly eligible')
            counts['ways']+=1;counts['speedWays' if any(k in tags for k in new.SPEED_KEYS) else 'scopeWays']+=1
    require(counts['nodes']==counters['changedNodeFlags'] and counts['ways']==counters['newlyEligibleWays'],'All changed native records independently accounted')
    require(counts['speedWays']==counters['newSpeedConditionalWays'] and counts['scopeWays']==counters['newNonCarScopedWays'],'All new way categories independently accounted')
    require(counts['tagUtf8Bytes']==counters['changedTagUtf8Bytes'],'All changed raw tag bytes accounted')
    require(sum(counts[k] for k in ('nodes','ways'))==counters['changedRecords'],'Changed record count')
    require(before.st_size==counters['changedEncodedBytes'],'Changed output byte count')
    require(counters['oldEligibleWays']==counters['oldEligibleWaysExact'] and counters['oldUnblockedNodes']==counters['oldUnblockedNodesExact'],'All original positive decisions retained exactly')
    with output.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
    after=output.stat()
    require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==identity and pin==before_sha,'Changed record bytes/stat stable')
    check();return {'status':'all_changed_source_tags_independently_reclassified','counts':counts,'bytes':before.st_size,'sha256':pin,'allOldPositiveDecisionsRetained':True,'graphOrEtaAccepted':False}


def collect(engine,source_path,snapshot,caps,source,expected_counts,expected_semantic,output,check,checkpoint=lambda value:None):
    began=time.monotonic();engine.begin(output)
    try:
        receipt=engine.scan(source_path,snapshot,caps,source=source,check=check)
        require(receipt['nativeEof'] and receipt['counts']==expected_counts,'Conditional complete source counts')
        require(receipt['semanticSha256']==expected_semantic,'Conditional unchanged source semantic seal')
        require(receipt['pythonProjectionFrames']==0,'No Python ordinary source projections')
        counters=engine.finish()
        require({k:counters[k+'s'] for k in expected_counts}==expected_counts,'Conditional consumer/source full counts')
    finally:engine.release()
    source_seconds=time.monotonic()-began
    checkpoint({'receipt':receipt,'conditional':counters,'sourceValidationAndCensusSeconds':source_seconds})
    audit_began=time.monotonic();independent=audit(output,counters,check)
    return {'receipt':receipt,'conditional':counters,'independentChangedTagAudit':independent,'sourceValidationAndCensusSeconds':source_seconds,'changedTagAuditSeconds':time.monotonic()-audit_began}

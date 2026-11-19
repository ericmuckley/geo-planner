"""Authenticate the complete source and independently replay every lane change."""
import hashlib
from pathlib import Path
import time

from coarse_osm_car_conditional_speed_v1 import SPEED_KEYS, way_policy as previous
from coarse_osm_car_explicit_lanes_v1 import classify_way
from coarse_osm_conditional_records_v1 import read_records
from coarse_timing_input import require


def audit(output,counters,check):
    output=Path(output);before=output.stat()
    identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
    def sha():
        with output.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    before_sha=sha();counts={'ways':0,'withSpeedConditional':0,'withoutSpeedConditional':0,'tagUtf8Bytes':0}
    for index,record in enumerate(read_records(output)):
        if index%256==0:check()
        require(record['type']=='way','Lane eligibility cannot change node policy')
        tags=record['tags'];old=previous(tags);explanation=classify_way(tags);new=explanation['policy']
        require(old.reason=='lane-access' and new.reason is None,'Only explicit lane eligibility independently opens')
        require(explanation['explicitOrdinaryLaneIndices'] and explanation['acceptedLaneKeys'],'Common explicit ordinary lane')
        require((new.forward is None)!=(new.backward is None),'Static one-way lane direction')
        require(new==previous({key:value for key,value in tags.items() if key not in explanation['acceptedLaneKeys']}),'Unchanged scoped source prices and access')
        counts['ways']+=1;counts['withSpeedConditional' if any(k in tags for k in SPEED_KEYS) else 'withoutSpeedConditional']+=1
        counts['tagUtf8Bytes']+=sum(len(k.encode())+len(v.encode()) for k,v in tags.items())
    require(counts['ways']==counters['newlyEligibleWays']==counters['changedRecords'],'All changed ways accounted')
    require(counts['withSpeedConditional']==counters['newLaneWaysWithSpeedConditional'] and counts['withoutSpeedConditional']==counters['newLaneWaysWithoutSpeedConditional'],'All changed way categories accounted')
    require(counts['tagUtf8Bytes']==counters['changedTagUtf8Bytes'] and before.st_size==counters['changedEncodedBytes'],'All raw output bytes accounted')
    require(counters['changedNodeFlags']==0 and counters['allNodeFlagsExact']==counters['nodes'],'Every source node flag unchanged')
    require(counters['oldEligibleWays']==counters['oldEligibleWaysExact'] and counters['oldUnblockedNodes']==counters['oldUnblockedNodesExact'],'All original positives exact')
    require(counters['oldEligibleWays']+counters['unchangedExcludedMajorWaysExact']+counts['ways']==counters['allMajorWayPoliciesCompared']==counters['majorWays'],'Every major way decision accounted')
    require(counters['laneRejectedWays']==counters['laneFallbackWays']+counts['ways'],'Every lane fallback accounted')
    after=output.stat()
    require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==identity and sha()==before_sha,'Changed lane bytes/stat stable')
    check();return {'status':'all_changed_lane_tags_independently_reclassified','counts':counts,'bytes':before.st_size,
                    'sha256':before_sha,'allOldPositiveDecisionsRetained':True,'graphOrEtaAccepted':False}


def collect(engine,source_path,snapshot,caps,source,expected_counts,expected_semantic,output,check,checkpoint=lambda value:None):
    began=time.monotonic();engine.begin(output)
    try:
        receipt=engine.scan(source_path,snapshot,caps,source=source,check=check)
        require(receipt['nativeEof'] and receipt['counts']==expected_counts,'Lane complete source counts')
        require(receipt['semanticSha256']==expected_semantic,'Lane unchanged source semantic seal')
        require(receipt['pythonProjectionFrames']==0,'No Python ordinary source projections')
        counters=engine.finish()
        require({key:counters[key+'s'] for key in expected_counts}==expected_counts,'Lane consumer/source full counts')
    finally:engine.release()
    source_seconds=time.monotonic()-began
    checkpoint({'receipt':receipt,'explicitLanes':counters,'sourceValidationAndCensusSeconds':source_seconds})
    audit_began=time.monotonic();independent=audit(output,counters,check)
    return {'receipt':receipt,'explicitLanes':counters,'independentChangedTagAudit':independent,
            'sourceValidationAndCensusSeconds':source_seconds,'changedTagAuditSeconds':time.monotonic()-audit_began}

"""Independently join every selected raw tag with its stored blocking causes."""
from collections import Counter
import hashlib
from pathlib import Path
import time

from coarse_osm_blocked_node_causes_v1 import node_cause
from coarse_osm_conditional_records_v1 import read_records
from coarse_timing_input import require


def audit(output, counters, nodes, contributors, check):
    output=Path(output)
    before=output.stat()
    identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
    with output.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    expected=iter(sorted(nodes))
    evidence={}
    tag_bytes=0
    for index,record in enumerate(read_records(output)):
        if index%256==0:check()
        native_id=record['id']
        require(record['type']=='node' and native_id==next(expected,None),'Every selected raw node in exact source order')
        result=node_cause(native_id,nodes[native_id]['flags'],record,contributors.get(native_id,[]))
        require(result['sourceBlockingReconciled'] and result['sourceSignalReconciled'],'Every raw blocking/signal cause reconciles')
        evidence[str(native_id)]=result
        tag_bytes+=sum(len(k.encode())+len(v.encode()) for k,v in record['tags'].items())
    require(next(expected,None) is None,'No missing selected raw nodes')
    require(len(evidence)==counters['requestedNodes']==counters['selectedRecords']==len(nodes),'Complete selected denominator')
    require(tag_bytes==counters['tagUtf8Bytes'] and before.st_size==counters['encodedBytes'],'Complete selected output accounting')
    after=output.stat()
    with output.open('rb') as stream:
        second=hashlib.file_digest(stream,'sha256').hexdigest()
    require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==identity and digest==second,'Selected tag output stable')
    return {'status':'all_original_selected_tags_and_independent_causes_replayed','selectedNodes':len(nodes),
            'bytes':before.st_size,'sha256':digest,'tagUtf8Bytes':tag_bytes,
            'causeCounts':dict(Counter(row['cause'] for row in evidence.values())),
            'nodeEvidence':evidence,'unknownRawNodeIds':[],
            'sourcePermissionsOrPricesChanged':False,'routingOrAccuracyAccepted':False}


def collect(engine, path, snapshot, caps, source, expected_counts, semantic, output, nodes, contributors, check):
    began=time.monotonic()
    engine.begin(output,sorted(nodes))
    try:
        receipt=engine.scan(path,snapshot,caps,source=source,check=check)
        require(receipt['nativeEof'] and receipt['counts']==expected_counts,'Complete selected-source counts/EOF')
        require(receipt['semanticSha256']==semantic and receipt['pythonProjectionFrames']==0,'Unchanged complete source seal, zero ordinary Python projections')
        counters=engine.finish()
    finally:
        engine.release()
    source_seconds=time.monotonic()-began
    independent=audit(output,counters,nodes,contributors,check)
    return {'receipt':receipt,'selectedTags':counters,'independentTagAudit':independent,
            'sourceValidationAndCollectionSeconds':source_seconds,'collectionAndAuditSeconds':time.monotonic()-began}

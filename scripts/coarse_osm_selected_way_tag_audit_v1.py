"""Independently replay raw source eligibility for an entire selected way-ID set."""
from collections import Counter
import hashlib
from pathlib import Path
import time

from coarse_osm_conditional_records_v1 import read_records
from coarse_osm_source_gap_way_causes_v1 import way_cause
from coarse_timing_input import require


def audit(output, counters, selected, check):
    output = Path(output); before = output.stat()
    with output.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    expected = iter(sorted(selected)); evidence = {}; tag_bytes = 0
    for index, record in enumerate(read_records(output)):
        if index % 256 == 0: check()
        identity = record['id']
        require(record['type'] == 'way' and identity == next(expected, None), 'Every selected original way in exact source order')
        evidence[str(identity)] = way_cause(selected[identity], record)
        tag_bytes += sum(len(k.encode())+len(v.encode()) for k, v in record['tags'].items())
    require(next(expected, None) is None, 'No missing selected original ways')
    require(len(evidence) == counters['requestedWays'] == counters['selectedRecords'] == len(selected), 'Complete selected way denominator')
    require(tag_bytes == counters['tagUtf8Bytes'] and before.st_size == counters['encodedBytes'], 'Complete selected way output accounting')
    with output.open('rb') as stream: second = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(output.stat() == before and digest == second, 'Selected original way output stable')
    return dict(status='all_original_selected_way_tags_and_base_eligibility_replayed', selectedWays=len(selected),
                bytes=before.st_size, sha256=digest, tagUtf8Bytes=tag_bytes,
                currentBaseReasonCounts=dict(Counter(str(r['currentRawPolicy']['reason']) for r in evidence.values())),
                wayEvidence=evidence, unknownRawWayIds=[], sourcePermissionsOrPricesChanged=False, routingOrAccuracyAccepted=False)


def collect(engine, path, snapshot, caps, source, counts, semantic, output, selected, check):
    began = time.monotonic(); engine.begin(output, sorted(selected))
    try:
        receipt = engine.scan(path, snapshot, caps, source=source, check=check)
        require(receipt['nativeEof'] and receipt['counts'] == counts, 'Complete way source counts/EOF')
        require(receipt['semanticSha256'] == semantic and receipt['pythonProjectionFrames'] == 0, 'Unchanged complete source seal, zero ordinary Python projections')
        counters = engine.finish()
    finally: engine.release()
    source_seconds = time.monotonic()-began
    independent = audit(output, counters, selected, check)
    return dict(receipt=receipt, selectedTags=counters, independentTagAudit=independent,
                sourceValidationAndCollectionSeconds=source_seconds, collectionAndAuditSeconds=time.monotonic()-began)

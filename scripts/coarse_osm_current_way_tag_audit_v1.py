"""Audit every requested source tag record without changing permissions or prices."""
import hashlib
from pathlib import Path

from coarse_osm_backbone_v1 import MAJOR
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_conditional_records_v1 import read_records
from coarse_timing_input import require


def audit(output, counters, selected, cached, check):
    output = Path(output)
    require(0 < len(selected) <= 250000 and all(type(i) is int and 0 < i < 2**63 and role in MAJOR for i, role in selected.items()), 'Selected current way IDs/roles')
    require(set(cached) <= set(selected), 'Cached originals belong to the complete selection')
    before = stat_key(output)
    size = output.stat().st_size
    with output.open('rb') as stream:
        first = hashlib.file_digest(stream, 'sha256').hexdigest()
    expected = iter(sorted(selected))
    evidence = {}
    tag_bytes = 0
    for index, record in enumerate(read_records(output)):
        if index % 256 == 0:
            check()
        identity = record['id']
        require(record['type'] == 'way' and identity == next(expected, None), 'Every selected current way in source order')
        tags = record['tags']
        require(tags.get('highway') == selected[identity], 'Current source way role exact')
        if identity in cached:
            require(tags == cached[identity], 'Every cached original raw tag exact')
        evidence[str(identity)] = tags
        tag_bytes += sum(len(k.encode())+len(v.encode()) for k, v in tags.items())
    require(next(expected, None) is None, 'No missing selected current ways')
    require(len(evidence) == counters['requestedWays'] == counters['selectedRecords'] == len(selected), 'Complete selected current way denominator')
    require(tag_bytes == counters['tagUtf8Bytes'] and size == counters['encodedBytes'], 'Complete current way output accounting')
    with output.open('rb') as stream:
        second = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(stat_key(output) == before and first == second, 'Current way tag output stable')
    return {'selectedWays': len(evidence), 'cachedOriginalsChecked': len(cached), 'bytes': size,
            'sha256': first, 'tagUtf8Bytes': tag_bytes, 'wayTags': evidence,
            'unknownRawWayIds': [], 'sourcePermissionsOrPricesChanged': False}

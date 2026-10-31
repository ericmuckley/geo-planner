"""Versioned validation prototype: one node validation, strict faster UTC parsing.

The frozen native projector, counters, checkpoint cadence, caps and SQLite code
remain unchanged. This module is not used by a national extraction launcher.
"""
from collections import Counter
from datetime import datetime
import math
import re

from coarse_osm_bulk import ORDER
from coarse_osm_records import canonical, positive, utc as reference_utc
from coarse_timing_input import require


STAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')


def utc(value):
    require(isinstance(value, str) and STAMP.fullmatch(value), 'Invalid UTC timestamp')
    # strptime accepts some Unicode digits; retain that exact fallback behavior.
    if not value.isascii():
        return reference_utc(value)
    return datetime.fromisoformat(value[:-1])


def checked_records(reader, run, publisher_state, label):
    counts = Counter()
    last = (-1, -1)
    snapshot = None
    record = {'label': label, 'status': 'running', 'counts': {}}
    run.state['passes'].append(record)
    run.state['stage'] = label
    run.checkpoint()
    for raw in reader():
        run.check(storage=False)
        kind = raw.get('type', 'unknown') if isinstance(raw, dict) else 'unknown'
        counts[kind] += 1
        run.state['scanObjectVisits'] += 1
        record['counts'] = dict(counts)
        require(isinstance(raw, dict) and len(canonical(raw)) <= run.caps['singleNormalizedElementBytes'], 'Native record size/type')
        kind = raw.get('type')
        require(kind in ORDER and positive(raw.get('id')) and positive(raw.get('version')), 'Native identity')
        key = ORDER[kind], raw['id']
        require(key > last, 'Duplicate/out-of-order source identity')
        last = key
        require(raw.get('visible', True) is True, 'Native state/deletion drift')
        timestamp = utc(raw.get('timestamp'))
        if snapshot is None:
            snapshot = utc(publisher_state)
        require(timestamp <= snapshot, 'Native state/deletion drift')
        tags = raw.get('tags')
        require(tags is None or isinstance(tags, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items()), 'Native tags')
        if kind == 'node':
            # These are the remaining node-normalization checks. Identity,
            # visibility, size, tags and time were already checked above.
            require('tags' not in raw or isinstance(tags, dict), 'Invalid raw tags')
            require(all(type(raw.get(k)) in (int, float) and math.isfinite(raw[k]) for k in ('lat', 'lon')), 'Invalid node coordinates')
            require(-90 <= raw['lat'] <= 90 and -180 <= raw['lon'] <= 180, 'Node coordinates outside range')
        elif kind == 'way':
            require(isinstance(raw.get('nodes'), list) and len(raw['nodes']) >= 2 and all(positive(i) for i in raw['nodes']), 'Native way references')
        else:
            require(isinstance(raw.get('members'), list), 'Native relation members')
            for member in raw['members']:
                require(isinstance(member, dict) and member.get('type') in ORDER and positive(member.get('ref')) and isinstance(member.get('role'), str), 'Native typed member')
        require(counts[kind] <= run.caps[{'node': 'scanNodesPerPass', 'way': 'scanWaysPerPass', 'relation': 'scanRelationsPerPass'}[kind]], 'Upstream per-pass row cap')
        require(run.state['scanObjectVisits'] <= run.caps['scanObjectVisitsTotal'], 'Upstream visit cap')
        if run.state['scanObjectVisits'] % 128 == 0:
            run.check()
            run.checkpoint()
        yield raw
    run.check()
    record['status'] = 'eof'
    run.checkpoint()

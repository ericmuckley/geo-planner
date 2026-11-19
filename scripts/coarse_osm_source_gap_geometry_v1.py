"""Read-only inventory of every currently excluded major-way source geometry."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path


def selected_rows(ways, geometry, xy, closures, check=lambda: None):
    previous_id = end = 0
    assert len(xy) % 2 == 0
    for index in range(len(ways)):
        if index % 4096 == 0:
            check()
        identity, forward, backward, flags, following = ways[index]
        assert previous_id < identity and end <= following <= len(geometry)
        assert 0 <= flags < 2560 and (flags >> 4) & 15 < 10
        assert all(math.isfinite(value) and 0 <= value <= 160 for value in (forward, backward))
        assert bool(flags & 1) == (forward > 0) and bool(flags & 2) == (backward > 0)
        eligible = bool(flags & 3)
        assert bool(flags >> 8) != eligible
        closed = identity in closures
        if not eligible or closed:
            points = []
            for at in range(end, following):
                node = geometry[at]
                assert type(node) is int and 0 <= node < len(xy) // 2
                x, y = xy[2 * node], xy[2 * node + 1]
                assert type(x) is int and type(y) is int and abs(x) <= 1800000000 and abs(y) <= 900000000
                points.append([x, y])
            yield {'sourceWay': identity, 'sourceWayRow': index, 'storedSourceFlags': flags,
                   'baseEligible': eligible, 'finalFallbackClosed': closed, 'xyE7': points}
        end = following
        previous_id = identity
    assert end == len(geometry)


def capture(ways, geometry, xy, closures, output, check=lambda: None):
    assert all(type(value) is int and value > 0 for value in closures)
    output = Path(output)
    records = points = raw_bytes = 0
    digest = hashlib.sha256()
    reasons, matched_closures = Counter(), set()
    base_ineligible = eligible_closed = 0
    with output.open('xb') as file, gzip.GzipFile(fileobj=file, mode='wb', mtime=0) as stream:
        for row in selected_rows(ways, geometry, xy, closures, check):
            records += 1
            assert records <= 100000, 'Complete source-gap record limit; never truncate'
            points += len(row['xyE7'])
            if row['baseEligible']:
                eligible_closed += 1
            else:
                base_ineligible += 1
                reasons[row['storedSourceFlags'] >> 8] += 1
            if row['finalFallbackClosed']:
                matched_closures.add(row['sourceWay'])
            raw = (json.dumps(row, separators=(',', ':'))+'\n').encode()
            assert len(raw) <= 4194304, 'Complete source way record limit; never truncate'
            raw_bytes += len(raw)
            assert raw_bytes <= 512*1048576, 'Complete raw geometry budget; never truncate'
            digest.update(raw)
            stream.write(raw)
            if records % 256 == 0:
                check()
    assert output.stat().st_size <= 50331648
    audited = audit(ways, geometry, xy, closures, output, check)
    assert audited['recordsIndependentlyReplayed'] == records
    assert audited['sourceReferencesIndependentlyReplayed'] == points
    return {'selectedWays': records, 'selectedSourceReferences': points,
            'baseIneligibleMajorWays': base_ineligible, 'baseEligibleFinalClosedMajorWays': eligible_closed,
            'storedOriginalReasonCounts': dict(sorted(reasons.items())),
            'finalClosureIds': len(closures), 'finalClosureIdsMatchedToMajorWays': len(matched_closures),
            'finalClosureIdsOutsideMajorWayTable': len(closures - matched_closures),
            'independentAudit': audited,
            'artifact': {'file': output.name, 'bytes': output.stat().st_size,
                         'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                         'rawBytes': raw_bytes, 'rawSha256': digest.hexdigest()}}


def audit(ways, geometry, xy, closures, output, check=lambda: None):
    records = points = previous = 0
    with gzip.open(output, 'rb') as stream:
        for index in range(len(ways)):
            if index % 4096 == 0:
                check()
            identity, _, _, flags, following = ways[index]
            selected = flags & 3 == 0 or identity in closures
            if selected:
                raw = stream.readline(4194305)
                assert raw.endswith(b'\n') and len(raw) <= 4194304
                saved = json.loads(raw)
                assert set(saved) == {'sourceWay','sourceWayRow','storedSourceFlags','baseEligible','finalFallbackClosed','xyE7'}
                assert saved['sourceWay'] == identity and saved['sourceWayRow'] == index
                assert saved['storedSourceFlags'] == flags
                assert saved['baseEligible'] == bool(flags & 3)
                assert saved['finalFallbackClosed'] == (identity in closures)
                assert len(saved['xyE7']) == following-previous
                for offset, point in enumerate(saved['xyE7']):
                    source = geometry[previous+offset]
                    assert point == [xy[2*source], xy[2*source+1]]
                points += following-previous
                records += 1
            previous = following
        assert previous == len(geometry) and stream.read(1) == b''
    return {'status': 'independent_complete_excluded_major_way_geometry_replay_passed',
            'allWayRowsChecked': len(ways), 'recordsIndependentlyReplayed': records,
            'sourceReferencesIndependentlyReplayed': points, 'unselectedRowsOmittedExactly': True}

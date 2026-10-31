"""Independent raw-row, clipped-length and Census-weight reconciliation."""
import base64
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from coarse_backbone_paths import arc_geometry
from coarse_timing_input import json_bytes, require, usable_limit
from coarse_timing_parquet import decode_lines


def interval(a, b, box):
    lows, highs = [0.], [1.]
    for dim in (0, 1):
        delta = b[dim] - a[dim]
        if delta:
            bounds = sorted([(box[dim] - a[dim]) / delta, (box[dim + 2] - a[dim]) / delta])
            lows.append(bounds[0])
            highs.append(bounds[1])
        elif not box[dim] <= a[dim] <= box[dim + 2]:
            return None
    lo, hi = max(lows), min(highs)
    return (lo, hi) if hi > lo else None


def geometry_km(lines, box):
    total = []
    for line in lines:
        for a, b in zip(line, line[1:]):
            span = interval(a, b, box)
            if span:
                points = [[a[i] + t * (b[i] - a[i]) for i in (0, 1)] for t in span]
                x, y = points
                lat1, lat2 = math.radians(x[1]), math.radians(y[1])
                h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(y[0] - x[0]) / 2) ** 2
                total.append(12742 * math.asin(min(1, math.sqrt(h))))
    return math.fsum(total)


def close(a, b):
    require(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-8), 'Independent numeric reconciliation')


def reconcile(actual, expected):
    if isinstance(expected, dict):
        require(actual.keys() == expected.keys(), 'Independent dictionary keys')
        for key in expected:
            reconcile(actual[key], expected[key])
    elif isinstance(expected, (float, int)):
        close(actual, expected)
    else:
        require(actual == expected, 'Independent value reconciliation')


def audit(plan, output, proposal, data):
    windows = proposal['selection']['windows']
    report = json.loads((output.root / 'report.json').read_text())
    rows, field_counts, limit_counts, flags = {}, Counter(), Counter(), Counter()
    totals = defaultdict(Counter)
    class_totals = defaultdict(lambda: defaultdict(Counter))
    def accumulate(group, record, km):
        group['bboxCandidateRows'] += 1
        group['rowsWithClippedGeometry'] += km > 0
        group['clippedGeometryKm'] += km
        for prefix, key in [('limit', 'limit'), ('speedOnly', 'speedOnlyLimit')]:
            group[prefix + 'StatusCounts:' + record[key]['status']] += 1
            group[prefix + 'StatusGeometryKm:' + record[key]['status']] += km
        for flag in record['observations']:
            group['observationCounts:' + flag] += 1
            group['observationGeometryKm:' + flag] += km
    def check_group(actual, flat):
        require(actual['bboxCandidateRows'] == flat['bboxCandidateRows'], 'Window row denominator')
        require(actual['rowsWithClippedGeometry'] == flat['rowsWithClippedGeometry'], 'Geometry row denominator')
        close(actual['clippedGeometryKm'], flat['clippedGeometryKm'])
        for key in ['limitStatusCounts', 'limitStatusGeometryKm', 'speedOnlyStatusCounts', 'speedOnlyStatusGeometryKm', 'observationCounts', 'observationGeometryKm']:
            expected = {k.split(':', 1)[1]: v for k, v in flat.items() if k.startswith(key + ':')}
            reconcile(actual[key], expected)
    with Path('/cache/segments.jsonl').open('rb') as raw_stream, (output.root / 'rows.jsonl').open('rb') as ledger:
        for raw, encoded in itertools.zip_longest(raw_stream, ledger):
            output.check()
            require(raw is not None and encoded is not None, 'Retained ledger length')
            row, record = json.loads(raw), json.loads(encoded)
            key = row['id'], row['version']
            require(key not in rows and (record['id'], record['version']) == key, 'Retained ledger identities')
            require(record['rawLineSha256'] == hashlib.sha256(raw).hexdigest(), 'Raw retained line binding')
            fields = {k: v for k, v in row.items() if k != 'geometryWkbBase64'}
            raw_fields = json.dumps(fields, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            require(record['fieldsSha256'] == hashlib.sha256(raw_fields).hexdigest(), 'All raw scoped fields binding')
            require(record['geometryBase64Sha256'] == hashlib.sha256(row['geometryWkbBase64'].encode()).hexdigest(), 'Raw geometry binding')
            require(record['limit'] == usable_limit(row), 'Frozen scoped-rule classification')
            require(record['speedOnlyLimit'] == usable_limit({**row, 'access_restrictions': None}), 'Separate speed-only classification')
            field_counts.update(k for k, v in row.items() if v not in (None, [], {}))
            limit_counts.update([record['limit']['status']])
            flags.update(record['observations'])
            try:
                lines = decode_lines(base64.b64decode(row['geometryWkbBase64'], validate=True))
                require(record['geometryStatus'] == 'decoded', 'Geometry status')
            except (ValueError, RuntimeError):
                require(record['geometryStatus'] == 'malformed_geometry', 'Malformed geometry status')
                lines = []
            box = row['bbox']
            ids = [w['id'] for w in windows if box['xmin'] <= w['bbox'][2] and box['xmax'] >= w['bbox'][0] and box['ymin'] <= w['bbox'][3] and box['ymax'] >= w['bbox'][1]]
            require([m['windowId'] for m in record['memberships']] == ids, 'All window memberships')
            for member in record['memberships']:
                wid = member['windowId']
                window = next(w for w in windows if w['id'] == wid)
                km = geometry_km(lines, window['bbox'])
                close(km, member['clippedGeometryKm'])
                accumulate(totals[wid], record, km)
                accumulate(class_totals[wid][row['class']], record, km)
            rows[key] = {'class': row['class'], 'limit': record['limit'], 'windows': ids}
    require(len(rows) == plan['expectedRows'] == report['retainedUniqueRows'], 'All retained identities')
    reconcile(report['fieldNonemptyCounts'], dict(field_counts))
    reconcile(report['limitStatusCounts'], dict(limit_counts))
    reconcile(report['observationCounts'], dict(flags))
    require(len(report['windows']) == len(windows) == 21 and report['completedSourceWindows'] == 0 and not report['originalFeasibilityQualified'], 'Every source window stays incomplete')
    expected_arcs = {}
    grid = plan['grid']
    for window in windows:
        output.check()
        box, wid = window['bbox'], window['id']
        xs = [max(0, math.floor((box[0] - grid['bounds'][0]) / grid['step']) - 1), min(grid['width'], math.floor((box[2] - grid['bounds'][0]) / grid['step']) + 2)]
        ys = [max(0, math.floor((box[1] - grid['bounds'][1]) / grid['step']) - 1), min(grid['height'], math.floor((box[3] - grid['bounds'][1]) / grid['step']) + 2)]
        candidates = set()
        for i, cell in enumerate(data['cellIds']):
            y, x = divmod(cell, grid['width'])
            if xs[0] <= x < xs[1] and ys[0] <= y < ys[1]:
                candidates.update(data['cellArcs'][data['cellArcOffsets'][i]:data['cellArcOffsets'][i + 1]])
        for arc in candidates:
            points, cumulative = arc_geometry(data, arc)
            spans = []
            for i, (a, b) in enumerate(zip(points, points[1:])):
                clipped = interval(a, b, box)
                if clipped:
                    lo, hi = clipped
                    weight = (cumulative[i + 1] - cumulative[i]) * (hi - lo)
                    if weight > 0:
                        spans.append(([[a[d] + t * (b[d] - a[d]) for d in (0, 1)] for t in [lo, hi]], weight))
            if spans:
                expected_arcs[wid, arc] = spans
    match_totals = defaultdict(lambda: defaultdict(float))
    seen_matches = set()
    with (output.root / 'matches.jsonl').open() as stream:
        for line in stream:
            output.check()
            record = json.loads(line)
            key = record['windowId'], record['arc']
            require(key in expected_arcs and key not in seen_matches, 'Census arc/window roster')
            seen_matches.add(key)
            spans = expected_arcs[key]
            close(record['sourceKm'], math.fsum(s[1] for s in spans))
            require(len(spans) == len(record['sourceSpans']), 'Census span count')
            for (points, weight), saved in zip(spans, record['sourceSpans']):
                close(weight, saved[2])
                for a, b in zip(points, saved[:2]):
                    for x, y in zip(a, b): close(x, y)
            speed = str(int(data['arcSpeedKph'][record['arc']]))
            require(record['sourceClassKph'] == int(speed) and not record['sourceComplete'], 'Census class/source state')
            n = record['candidateCount']
            require(type(n) is int and n >= 0, 'Candidate count')
            expected_status = 'single_in_cache' if n == 1 else 'ambiguous_in_cache' if n > 1 else 'absent_in_cache'
            require(record['status'] == expected_status, 'Provisional candidate semantics')
            if n == 1:
                source = rows[record['overtureId'], record['version']]
                require(key[0] in source['windows'] and record['limit'] == source['limit'] and record['class'] == source['class'], 'Candidate cache/scoped identity')
                require(.8 - 1e-12 <= record['fraction'] <= 1, 'Frozen candidate fraction range')
                provisional = record['sourceKm'] * record['fraction'] if record['limitStatus'] == 'usable' else 0.
                require(record['limitStatus'] == source['limit']['status'], 'Candidate limit status')
                close(record['provisionalStaticLimitMatchedKm'], provisional)
            else:
                close(record['provisionalStaticLimitMatchedKm'], 0.)
            group = match_totals[key[0], speed]
            group['arcCount'] += 1
            group['sourceKm'] += record['sourceKm']
            group['cacheStatusCounts:' + record['status']] += 1
            group['cacheStatusSourceKm:' + record['status']] += record['sourceKm']
            group['provisionalStaticLimitMatchedKm'] += record['provisionalStaticLimitMatchedKm']
            if n == 1:
                group['singleCandidateLimitStatusSourceKm:' + record['limitStatus']] += record['sourceKm']
    require(seen_matches == expected_arcs.keys(), 'Complete Census denominator roster')
    for summary in report['windows']:
        wid = summary['id']
        require(summary['sourceStatus'] == 'incomplete_after_capture_stop', 'Incomplete source status')
        require(summary == json.loads((output.root / 'windows' / (wid + '.json')).read_text()), 'Window/report identity')
        check_group(summary['publisherTotals'], totals[wid])
        require(set(summary['publisherClasses']) == {r['class'] for r in rows.values()}, 'All observed publisher classes retained in each window')
        for role, group in summary['publisherClasses'].items():
            check_group(group, class_totals[wid][role])
        for speed, actual in summary['sourceClassesKph'].items():
            flat = match_totals[wid, speed]
            for key in ['arcCount', 'sourceKm', 'provisionalStaticLimitMatchedKm']:
                close(actual[key], flat[key])
            for key in ['cacheStatusCounts', 'cacheStatusSourceKm', 'singleCandidateLimitStatusSourceKm']:
                reconcile(actual[key], {k.split(':', 1)[1]: v for k, v in flat.items() if k.startswith(key + ':')})
    output.write('audit.json', json_bytes({'independentRawIdentityFieldGeometryAndSourceWeightAudit': True,
        'retainedRows': len(rows), 'windows': len(windows), 'censusArcWindowRecords': len(seen_matches),
        'completedSourceWindows': 0, 'originalFeasibilityQualified': False,
        'matchingAlgorithm': 'Shared frozen 25 m/80%/15 degree helper with synthetic fixtures; this audit independently checks identities, scoped classifications, lengths, every Census denominator and candidate accounting, not physical road identity or a second full geometric matcher.'}))

"""Independent sample-membership, weight, partition and scope accounting."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from analyze_timing_cache import prepare_row
from coarse_timing_input import json_bytes, require, usable_limit
from coarse_timing_parquet import MatchIndex


def close(actual, expected):
    if isinstance(expected, dict):
        require(actual.keys() == expected.keys(), 'Independent dictionary roster')
        for key in expected: close(actual[key], expected[key])
    elif type(expected) in (int, float):
        require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-8), 'Independent numeric accounting')
    else:
        require(actual == expected, 'Independent value accounting')


def great_circle(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))


def aligned(point, a, b, c, d):
    scale = math.cos(math.radians(sum(p[1] for p in (a, b, c, d)) / 4))
    x, y = ((b[0] - a[0]) * scale, b[1] - a[1]), ((d[0] - c[0]) * scale, d[1] - c[1])
    denominator = math.hypot(*x) * math.hypot(*y)
    if not denominator or math.degrees(math.acos(min(1, abs(x[0] * y[0] + x[1] * y[1]) / denominator))) > 15:
        return False
    scale = math.cos(math.radians(point[1]))
    vx, vy = (d[0] - c[0]) * scale, d[1] - c[1]
    length = vx * vx + vy * vy
    t = max(0, min(1, (((point[0] - c[0]) * scale) * vx + (point[1] - c[1]) * vy) / length)) if length else 0
    return great_circle(point, [c[0] + t * (d[0] - c[0]), c[1] + t * (d[1] - c[1])]) <= .025


def raw_values(value):
    stack = [('', value)]
    while stack:
        path, child = stack.pop()
        if isinstance(child, dict):
            stack.extend(((path + '.' if path else '') + k, v) for k, v in child.items())
        elif isinstance(child, list):
            stack.extend((path + '[]', v) for v in child)
        elif child is not None:
            yield path, json.dumps(child, sort_keys=True, separators=(',', ':'), allow_nan=False)


def summarize(records):
    counts, source, union, old = Counter(), defaultdict(float), defaultdict(float), Counter()
    for r in records:
        status = r['compatibilityStatus']
        counts[status] += 1; source[status] += r['sourceKm']; union[status] += r['unionAlignedKm']
        old[r['oldStatus']] += 1
    return {'arcCount': len(records), 'sourceKm': sum(r['sourceKm'] for r in records),
        'unionAlignedKm': sum(r['unionAlignedKm'] for r in records), 'statusCounts': counts,
        'statusSourceKm': source, 'statusUnionAlignedKm': union, 'oldStatusCounts': old,
        'provisionalEligibleMatchedKm': sum(r['provisionalEligibleMatchedKm'] for r in records)}


def audit(plan, output, paths):
    report = json.loads((output.root / 'report.json').read_text())
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    selected, identities, raw_counts = defaultdict(list), set(), {'speed': Counter(), 'access': Counter()}
    flags, values = {'speed': Counter(), 'access': Counter()}, {'speed': defaultdict(Counter), 'access': defaultdict(Counter)}
    limits, speed_only, ordinal_for = Counter(), Counter(), {}
    from analyze_timing_compatibility import scope_profile
    with Path(paths['segments']).open('rb') as raw_stream, (output.root / 'scopes.jsonl').open('rb') as scopes:
        for ordinal, (raw, encoded) in enumerate(itertools.zip_longest(raw_stream, scopes)):
            output.check()
            require(raw is not None and encoded is not None, 'Independent row roster')
            row, record = json.loads(raw), json.loads(encoded)
            key = row['id'], row['version']
            require(key not in identities and record['ordinal'] == ordinal and key == (record['id'], record['version']), 'Independent retained identity')
            identities.add(key); ordinal_for[key] = ordinal
            require(record['rawLineSha256'] == hashlib.sha256(raw).hexdigest(), 'Independent raw line checksum')
            fields = {k: v for k, v in row.items() if k != 'geometryWkbBase64'}
            require(record['fieldsSha256'] == hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest(), 'Independent raw field checksum')
            require(record['frozenLimit'] == usable_limit(row) and record['frozenSpeedOnlyLimit'] == usable_limit({**row, 'access_restrictions': None}), 'Frozen classifications changed')
            require(record['sourceRecordIds'] == [[s.get('provider'), s.get('record_id')] for s in row.get('sources') or []], 'Raw source record IDs')
            old, slim = prepare_row(row, windows)
            slim['_ordinal'] = ordinal
            require(record['memberships'] == old['memberships'], 'Retained publisher geometry denominator')
            for member in record['memberships']: selected[member['windowId']].append(slim)
            limits.update([record['frozenLimit']['status']]); speed_only.update([record['frozenSpeedOnlyLimit']['status']])
            for kind, field, saved in [('speed', 'speed_limits', 'rawSpeedLimits'), ('access', 'access_restrictions', 'rawAccessRestrictions')]:
                require(record[saved] == row.get(field), 'Raw scoped rules changed')
                present = row.get(field) is not None and row.get(field) != []
                raw_counts[kind]['presentRows' if present else 'missingRows'] += 1
                raw_counts[kind]['rawRuleCount'] += len(row[field]) if isinstance(row.get(field), list) else 0
                require(record['profiles'][kind] == scope_profile(row.get(field), kind), 'Tested scope profile changed')
                flags[kind].update(record['profiles'][kind]['flags'])
                for path, value in raw_values(row.get(field)): values[kind][path][value] += 1
    require(len(identities) == plan['expectedRows'] == report['retainedRows'], 'Full retained scope denominator')
    close(report['scopeCounts'], raw_counts); close(report['scopeFlagRowCounts'], flags); close(report['rawLeafValueCounts'], values)
    close(report['frozenLimitStatusCounts'], limits); close(report['frozenSpeedOnlyStatusCounts'], speed_only)
    require(report['frozenSpeedOnlyConflictingRows'] == speed_only.get('conflicting', 0), 'Conflicting scoped-limit denominator')
    old_report = json.loads(Path(paths['report']).read_text())
    require(report['publisherGeometryKm'] == {w['id']: w['publisherTotals']['clippedGeometryKm'] for w in old_report['windows']}, 'Publisher/Census geometry denominators stay separate')
    previous = defaultdict(list)
    with Path(paths['matches']).open('rb') as stream:
        for raw in stream:
            r = json.loads(raw); r['_hash'] = hashlib.sha256(raw).hexdigest(); previous[r['windowId']].append(r)
    records, all_records, cache_records, sample_count = defaultdict(list), [], [], 0
    with (output.root / 'support.jsonl').open() as stream:
        for window in windows:
            wid = window['id']; index = MatchIndex(selected[wid], window['bbox'])
            for old in previous[wid]:
                output.check()
                r = json.loads(next(stream))
                require((r['windowId'], r['arc']) == (wid, old['arc']) and r['savedMatchLineSha256'] == old['_hash'], 'Full saved source roster')
                require(r['oldStatus'] == old['status'] and r['sourceClassKph'] == old['sourceClassKph'], 'Saved classifications/classes changed')
                close(r['sourceKm'], sum(s[2] for s in old['sourceSpans']))
                close(r['provisionalEligibleMatchedKm'], old['provisionalStaticLimitMatchedKm'])
                position, supported, individual = 0, [], defaultdict(float)
                for si, (a, b, km) in enumerate(old['sourceSpans']):
                    count = max(1, math.ceil(great_circle(a, b) / .025))
                    for i in range(count):
                        output.check()
                        t = (i + .5) / count
                        point = [a[d] + t * (b[d] - a[d]) for d in (0, 1)]
                        found = {row for sid in index.bins.get((math.floor(point[0] / .01), math.floor(point[1] / .01)), [])
                                 for row, c, d in [index.segments[sid]] if aligned(point, a, b, c, d)}
                        sample = r['samples'][position]; position += 1; sample_count += 1
                        require(sample[:3] == [si, i, count], 'Independent sample roster')
                        close(sample[3], km / count)
                        require(sample[4] == sorted(index.rows[row]['_ordinal'] for row in found), 'Independent geometric sample memberships')
                        if found: supported.append(km / count)
                        for row in found: individual[row] += km / count
                require(position == len(r['samples']), 'Extra output samples')
                close(r['unionAlignedKm'], min(r['sourceKm'], math.fsum(supported)))
                close(r['maximumSingleFraction'], min(1, max(individual.values(), default=0) / r['sourceKm']))
                candidates = sorted(index.rows[row]['_ordinal'] for row, km in individual.items() if km / r['sourceKm'] >= .8 - 1e-12)
                require(candidates == r['candidateOrdinals'] and len(candidates) == old['candidateCount'], 'Independent candidate accounting')
                if len(candidates) == 1: require(candidates == [ordinal_for[old['overtureId'], old['version']]], 'Independent single identity')
                if old['status'] == 'absent_in_cache':
                    expected = 'no_aligned_cached_geometry' if not supported else 'union_aligned_without_single_candidate' if r['unionAlignedKm'] / r['sourceKm'] >= .8 - 1e-12 else 'partial_aligned_cached_geometry'
                else: expected = 'existing_' + old['status']
                require(r['compatibilityStatus'] == expected, 'Independent union partition')
                records[wid].append(r); all_records.append(r)
                if selected[wid]: cache_records.append(r)
        require(not stream.read().strip(), 'Extra source output records')
    require(len(all_records) == plan['expectedMatches'], 'All source arc/window records')
    close(report['allWindows'], summarize(all_records)); close(report['windowsWithCache'], summarize(cache_records))
    require(len(report['windows']) == len(windows) == plan['expectedWindows'], 'All incomplete windows')
    for w in report['windows']:
        wid = w['id']
        require(w['sourceStatus'] == 'incomplete_after_capture_stop' and w['cachedRows'] == len(selected[wid]), 'Incomplete cache state')
        close(w['totals'], summarize(records[wid]))
        for speed, summary in w['sourceClassesKph'].items(): close(summary, summarize([r for r in records[wid] if r['sourceClassKph'] == int(speed)]))
        require(w == json.loads((output.root / 'windows' / (wid + '.json')).read_text()), 'Window/report mismatch')
    require(report['completedSourceWindows'] == report['networkRequests'] == report['routingQueries'] == 0 and not report['originalFeasibilityQualified'], 'No coverage/runtime admission')
    output.write('audit.json', json_bytes({'independentIdentitySampleMembershipWeightPartitionAndScopeAccounting': True,
        'retainedRows': len(identities), 'sourceArcWindowRecords': len(all_records), 'samplesChecked': sample_count,
        'plannedWindows': len(windows), 'completedSourceWindows': 0, 'originalFeasibilityQualified': False,
        'method': 'Separate numeric distance/tangent/sample/partition and raw-field/value accounting. Shared sealed geometry decoder/binning/parser and tested new scope-profile function. No independent source completeness, physical road identity, connected chain or car-access proof.'}))

"""Diagnose partial-cache geometric support and raw scopes without routing."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from analyze_timing_cache import canonical, prepare_row
from coarse_path_features import distance_km, segment_distance_km
from coarse_timing_input import json_bytes, require
from coarse_timing_parquet import MatchIndex, angle_degrees, interpolate


STATUSES = ['no_aligned_cached_geometry', 'partial_aligned_cached_geometry',
            'union_aligned_without_single_candidate', 'existing_single_in_cache', 'existing_ambiguous_in_cache']


def present(value):
    return value not in (None, [], {})


def scope_profile(rules, kind):
    flags, intervals, maxima, access_types = set(), [], set(), set()
    if rules is None or rules == []:
        return {'present': False, 'ruleCount': 0, 'flags': ['missing']}
    if not isinstance(rules, list):
        return {'present': True, 'ruleCount': 0, 'flags': ['malformed_rules']}
    for rule in rules:
        if not isinstance(rule, dict):
            flags.add('malformed_rule')
            continue
        between = rule.get('between')
        if between is None:
            intervals.append((0., 1.))
        elif isinstance(between, list) and len(between) == 2 and all(type(x) in (float, int) and math.isfinite(x) for x in between) and 0 <= between[0] < between[1] <= 1:
            intervals.append(tuple(between))
            if between != [0, 1]: flags.add('partial_between')
        else:
            flags.add('malformed_between')
        when = rule.get('when')
        if when is not None and not isinstance(when, dict):
            flags.add('malformed_when')
        elif isinstance(when, dict):
            for key, value in when.items():
                if present(value):
                    flags.add('when_' + key)
                    if key != 'heading': flags.add('conditional_scope')
        if kind == 'speed':
            if rule.get('is_max_speed_variable') is not None and type(rule['is_max_speed_variable']) is not bool:
                flags.add('malformed_variable_flag')
            if rule.get('is_max_speed_variable'):
                flags.add('variable_speed')
            maximum = rule.get('max_speed')
            if maximum is None:
                flags.add('no_explicit_maximum')
            elif not isinstance(maximum, dict) or type(maximum.get('value')) not in (int, float) or not math.isfinite(maximum['value']) or maximum['value'] <= 0:
                flags.add('malformed_maximum')
            elif maximum.get('unit') not in ('mph', 'km/h'):
                flags.add('unsupported_unit')
            else:
                maxima.add(maximum['value'] * (1.609344 if maximum['unit'] == 'mph' else 1))
        elif isinstance(rule.get('access_type'), str):
            access_types.add(rule['access_type'])
        else:
            flags.add('malformed_access_type')
    if len(maxima) > 1: flags.add('multiple_maximum_values')
    if len(access_types) > 1: flags.add('multiple_access_types')
    if any(min(b, d) > max(a, c) for i, (a, b) in enumerate(intervals) for c, d in intervals[i + 1:]):
        flags.add('overlapping_between_intervals')
    return {'present': True, 'ruleCount': len(rules), 'flags': sorted(flags)}


def leaves(value, path=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, (path + '.' if path else '') + key)
    elif isinstance(value, list):
        for child in value:
            yield from leaves(child, path + '[]')
    elif value is not None:
        yield path, canonical(value).decode()


def union_status(old_status, source_km, union_km):
    if old_status != 'absent_in_cache':
        require(old_status in ('single_in_cache', 'ambiguous_in_cache'), 'Unknown saved candidate status')
        return 'existing_' + old_status
    if union_km == 0:
        return STATUSES[0]
    return STATUSES[2] if union_km / source_km >= .8 - 1e-12 else STATUSES[1]


def support(index, spans, check=lambda: None):
    covered, samples, supported = defaultdict(float), [], []
    for span_index, (a, b, km) in enumerate(spans):
        require(km > 0 and math.isfinite(km), 'Invalid source-span weight')
        count = max(1, math.ceil(distance_km(a, b) / .025))
        require(count <= 100000, 'Sample allocation cap')
        for i in range(count):
            check()
            point = interpolate(a, b, (i + .5) / count)
            found = set()
            for sid in index.bins.get((math.floor(point[0] / .01), math.floor(point[1] / .01)), []):
                row, c, d = index.segments[sid]
                if angle_degrees(a, b, c, d) <= 15 and segment_distance_km(point, c, d) <= .025:
                    found.add(row)
            weight = km / count
            if found: supported.append(weight)
            for row in found: covered[row] += weight
            samples.append([span_index, i, count, weight, sorted(index.rows[row]['_ordinal'] for row in found)])
    total = sum(s[2] for s in spans)
    candidates = [row for row, km in covered.items() if km / total >= .8 - 1e-12]
    return {'sourceKm': total, 'unionAlignedKm': min(total, math.fsum(supported)),
            'maximumSingleFraction': min(1., max(covered.values(), default=0.) / total),
            'candidateOrdinals': sorted(index.rows[row]['_ordinal'] for row in candidates), 'samples': samples}


def group():
    return {'arcCount': 0, 'sourceKm': 0., 'unionAlignedKm': 0., 'statusCounts': Counter(),
            'statusSourceKm': defaultdict(float), 'statusUnionAlignedKm': defaultdict(float),
            'oldStatusCounts': Counter(), 'provisionalEligibleMatchedKm': 0.}


def add_match(summary, record):
    summary['arcCount'] += 1
    for key in ['sourceKm', 'unionAlignedKm']: summary[key] += record[key]
    summary['statusCounts'][record['compatibilityStatus']] += 1
    summary['statusSourceKm'][record['compatibilityStatus']] += record['sourceKm']
    summary['statusUnionAlignedKm'][record['compatibilityStatus']] += record['unionAlignedKm']
    summary['oldStatusCounts'][record['oldStatus']] += 1
    summary['provisionalEligibleMatchedKm'] += record['provisionalEligibleMatchedKm']


def analyze(plan, output, paths):
    proposal = json.loads(Path(paths['proposal']).read_text())
    old_report = json.loads(Path(paths['report']).read_text())
    windows = proposal['selection']['windows']
    selected, keys, ordinals = defaultdict(list), set(), {}
    scope_counts = {'speed': Counter(), 'access': Counter()}
    flag_counts = {'speed': Counter(), 'access': Counter()}
    field_values = {'speed': defaultdict(Counter), 'access': defaultdict(Counter)}
    frozen_status, speed_only_status = Counter(), Counter()
    with Path(paths['segments']).open('rb') as raw_stream, Path(paths['rows']).open('rb') as saved_stream:
        for ordinal, (raw, previous) in enumerate(itertools.zip_longest(raw_stream, saved_stream)):
            output.check()
            require(raw is not None and previous is not None and max(len(raw), len(previous)) <= plan['maxLineBytes'], 'Retained row roster/allocation')
            row, saved = json.loads(raw), json.loads(previous)
            key = row['id'], row['version']
            require(key not in keys and ordinal < plan['expectedRows'], 'Duplicate/excess identity')
            keys.add(key); ordinals[key] = ordinal
            record, slim = prepare_row(row, windows)
            require(all(record[k] == saved[k] for k in record) and saved['rawLineSha256'] == hashlib.sha256(raw).hexdigest(), 'Saved raw row/classification/geometry binding')
            slim['_ordinal'] = ordinal
            for member in saved['memberships']: selected[member['windowId']].append(slim)
            scopes = {'speed': scope_profile(row.get('speed_limits'), 'speed'), 'access': scope_profile(row.get('access_restrictions'), 'access')}
            ledger = {'ordinal': ordinal, 'id': key[0], 'version': key[1], 'class': row['class'],
                'rawLineSha256': saved['rawLineSha256'], 'fieldsSha256': saved['fieldsSha256'],
                'frozenLimit': saved['limit'], 'frozenSpeedOnlyLimit': saved['speedOnlyLimit'],
                'sourceRecordIds': [[s.get('provider'), s.get('record_id')] for s in row.get('sources') or []],
                'rawSpeedLimits': row.get('speed_limits'), 'rawAccessRestrictions': row.get('access_restrictions'),
                'profiles': scopes, 'memberships': saved['memberships']}
            output.record('scopes.jsonl', ledger)
            frozen_status.update([saved['limit']['status']]); speed_only_status.update([saved['speedOnlyLimit']['status']])
            for kind, field in [('speed', 'speed_limits'), ('access', 'access_restrictions')]:
                profile = scopes[kind]
                scope_counts[kind]['presentRows' if profile['present'] else 'missingRows'] += 1
                scope_counts[kind]['rawRuleCount'] += profile['ruleCount']
                flag_counts[kind].update(profile['flags'])
                for path, value in leaves(row.get(field)): field_values[kind][path][value] += 1
    require(len(keys) == plan['expectedRows'], 'All retained rows required')
    require(dict(frozen_status) == old_report['limitStatusCounts'], 'Frozen limit outcome counts changed')
    require(scope_counts['speed']['presentRows'] == old_report['fieldNonemptyCounts']['speed_limits'] and
            scope_counts['access']['presentRows'] == old_report['fieldNonemptyCounts']['access_restrictions'], 'Raw field denominators changed')
    saved_matches = defaultdict(list)
    with Path(paths['matches']).open('rb') as stream:
        for raw in stream:
            match = json.loads(raw)
            match['_lineSha256'] = hashlib.sha256(raw).hexdigest()
            saved_matches[match['windowId']].append(match)
    summaries, all_summary, cache_summary = [], group(), group()
    for window in windows:
        wid = window['id']
        index = MatchIndex(selected[wid], window['bbox'])
        summary = {'id': wid, 'sourceStatus': 'incomplete_after_capture_stop', 'cachedRows': len(selected[wid]),
                   'totals': group(), 'sourceClassesKph': {str(s): group() for s in (85, 105)}}
        for saved in saved_matches[wid]:
            output.check()
            record = support(index, saved['sourceSpans'], output.check)
            require(len(record['candidateOrdinals']) == saved['candidateCount'], 'Frozen candidate count changed')
            if saved['candidateCount'] == 1:
                require(record['candidateOrdinals'] == [ordinals[saved['overtureId'], saved['version']]], 'Frozen single candidate changed')
            require(math.isclose(record['sourceKm'], saved['sourceKm'], abs_tol=1e-9), 'Frozen source weight changed')
            record.update(windowId=wid, arc=saved['arc'], sourceClassKph=saved['sourceClassKph'],
                savedMatchLineSha256=saved['_lineSha256'], oldStatus=saved['status'],
                provisionalEligibleMatchedKm=saved['provisionalStaticLimitMatchedKm'],
                compatibilityStatus=union_status(saved['status'], record['sourceKm'], record['unionAlignedKm']))
            output.record('support.jsonl', record)
            for destination in [summary['totals'], summary['sourceClassesKph'][str(saved['sourceClassKph'])], all_summary]:
                add_match(destination, record)
            if selected[wid]: add_match(cache_summary, record)
        summaries.append(summary)
        output.write('windows/' + wid + '.json', json_bytes(summary))
        print(json.dumps({'window': wid, 'sourceStatus': summary['sourceStatus'], 'cachedRows': len(selected[wid])}), flush=True)
    require(sum(s['totals']['arcCount'] for s in summaries) == plan['expectedMatches'] and len(windows) == plan['expectedWindows'], 'All source/window records required')
    report = {'retainedRows': len(keys), 'windows': summaries, 'allWindows': all_summary, 'windowsWithCache': cache_summary,
        'scopeCounts': scope_counts, 'scopeFlagRowCounts': flag_counts, 'rawLeafValueCounts': field_values,
        'frozenLimitStatusCounts': frozen_status, 'frozenSpeedOnlyStatusCounts': speed_only_status,
        'frozenSpeedOnlyConflictingRows': speed_only_status.get('conflicting', 0),
        'publisherGeometryKm': {w['id']: w['publisherTotals']['clippedGeometryKm'] for w in old_report['windows']},
        'completedSourceWindows': 0, 'originalFeasibilityQualified': False, 'networkRequests': 0, 'routingQueries': 0,
        'scope': 'Observed geometric unions and raw rule inventories only; no connected route, unique road identity, usable speed coverage, lower bound, national completeness or timing model. Original Census weights and single-segment classifications stay unchanged; all21 source windows incomplete. Natural Earth/base remains outside the Census denominator.'}
    output.write('report.json', json_bytes(report))


def run(plan, output):
    paths = plan['paths']
    analyze(plan, output, paths)
    from coarse_timing_compatibility_audit import audit
    audit(plan, output, paths)


if __name__ == '__main__':
    from offline_timing_runner import main
    main('docs/evidence/coarse-timing-compatibility-2026-10-26/execution-plan.json')

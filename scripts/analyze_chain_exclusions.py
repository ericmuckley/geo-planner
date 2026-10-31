"""Inventory frozen chain exclusions; never enumerate or revise matches."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from analyze_timing_cache import canonical
from coarse_timing_chains import progress, row_metadata, sample_points
from coarse_timing_input import json_bytes, require


DECLARED_REASONS = {'unsupported_road_role', 'unsupported_level_rules'}


def level_profile(rules):
    if rules is None or rules == []:
        return {'category': 'missing', 'valueCategory': 'missing', 'flags': [], 'ruleCount': 0, 'fieldNames': []}
    if not isinstance(rules, list):
        return {'category': 'malformed', 'valueCategory': 'unknown', 'flags': ['malformed'], 'ruleCount': 0, 'fieldNames': []}
    flags, fields, values, intervals = set(), set(), [], []
    bad_value = False
    for rule in rules:
        if not isinstance(rule, dict):
            flags.add('malformed'); bad_value = True
            continue
        fields.update(rule)
        if any(v not in (None, [], {}) for k, v in rule.items() if k not in {'value', 'between'}):
            flags.add('unsupported_fields')
        value = rule.get('value')
        if type(value) not in (int, float) or not math.isfinite(value):
            flags.add('malformed'); bad_value = True
        else:
            values.append(value)
        span = rule.get('between')
        if span is None:
            intervals.append((0., 1.))
        elif isinstance(span, list) and len(span) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in span) and 0 <= span[0] < span[1] <= 1:
            intervals.append(tuple(span))
            if span != [0, 1]: flags.add('partial_intervals')
        else:
            flags.add('malformed')
    if any(min(b, d) > max(a, c) for i, (a, b) in enumerate(intervals) for c, d in intervals[i + 1:]):
        flags.add('overlapping_intervals')
    distinct = set(values)
    value_category = 'unknown' if bad_value or not values else 'uniform_zero' if distinct == {0} else 'uniform_nonzero' if len(distinct) == 1 else 'mixed'
    category = next((c for c, flag in [('malformed', 'malformed'), ('unsupported_fields', 'unsupported_fields'),
                     ('partial', 'partial_intervals')] if flag in flags), value_category)
    return {'category': category, 'valueCategory': value_category, 'flags': sorted(flags),
            'ruleCount': len(rules), 'fieldNames': sorted(fields)}


def measurements(row, indices, points, box):
    endpoints = row['endpoints']
    if len(endpoints) != 2:
        return {'endpointDistancesKm': [], 'progressIntervals': [], 'insideWindow': None,
                'measuredProgress': 'unavailable_geometry', 'flags': ['unavailable_geometry'],
                'frozenProgressApplied': False, 'frozenProgressReason': None}
    inside = all(box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3] for p in endpoints)
    results = [progress(p, indices, points) for p in endpoints]
    intervals, distances = [r[0] for r in results], [r[1] for r in results]
    order = 'forward' if intervals[0][1] < intervals[1][0] else 'reverse' if intervals[1][1] < intervals[0][0] else 'overlap_or_tie'
    flags = []
    if not inside: flags.append('outside_window_endpoint')
    if max(distances) > .025: flags.append('endpoint_not_near_own_samples')
    if order == 'overlap_or_tie': flags.append('nonprogressing_or_tied_endpoints')
    applied = not row['baseReasons'] and inside
    reason = ('endpoint_not_near_own_samples' if max(distances) > .025 else
              'nonprogressing_or_tied_endpoints' if order == 'overlap_or_tie' else None) if applied else None
    return {'endpointDistancesKm': distances, 'progressIntervals': intervals, 'insideWindow': inside,
            'measuredProgress': order, 'flags': flags, 'frozenProgressApplied': applied, 'frozenProgressReason': reason}


def cohorts(record, cached_rows):
    names = ['all', 'with_cache' if cached_rows else 'empty_cache']
    if record['candidates']: names.append('candidate_bearing')
    elif cached_rows: names.append('without_candidate_with_cache')
    if record['supportsHypothesis']: names.append('formerly_absent_positive')
    if record['oldStatus'] == 'absent_in_cache': names.append('baseline_absent')
    return names


def overlap(indices, row, candidate_indices, candidate_ids, weights, has_candidates):
    if not has_candidates:
        return {'kind': 'no_candidate_record', 'sharedSampleCount': 0, 'sharedSampleIncidenceKm': 0., 'sharedEndpointIds': []}
    shared = sorted(set(indices) & candidate_indices)
    ids = sorted({v for v in row['endpointIds'] if v is not None} & candidate_ids)
    kind = 'sample_and_endpoint' if shared and ids else 'sample_only' if shared else 'endpoint_only' if ids else 'neither'
    return {'kind': kind, 'sharedSampleCount': len(shared),
            'sharedSampleIncidenceKm': math.fsum(weights[i] for i in shared), 'sharedEndpointIds': ids}


def aggregate(records):
    incidences = [i for r in records for i in r['excluded']]
    reasons, levels, values, combinations, overlaps, measured = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    unique_reasons, unique_levels = defaultdict(set), defaultdict(set)
    for item in incidences:
        ordinal = item['ordinal']
        for reason in item['frozenReasons']:
            reasons[reason] += 1; unique_reasons[reason].add(ordinal)
        levels[item['levelCategory']] += 1; unique_levels[item['levelCategory']].add(ordinal)
        values[item['levelValueCategory']] += 1
        combinations['|'.join(item['frozenReasons'])] += 1
        overlaps[item['candidateOverlap']['kind']] += 1
        measured.update(item['measurements']['flags'])
    return {'arcCount': len(records), 'sourceKm': math.fsum(r['sourceKm'] for r in records),
        'originalStatusCounts': dict(Counter(r['originalStatus'] for r in records)),
        'originalOldStatusCounts': dict(Counter(r['originalOldStatus'] for r in records)),
        'samples': sum(r['sampleCount'] for r in records), 'candidateChains': sum(r['candidateCount'] for r in records),
        'formerlyAbsentPositiveRecords': sum(r['originalSupportsHypothesis'] for r in records),
        'cappedRecords': sum(r['originalSearchCapped'] for r in records),
        'baselineProvisionalEligibleKm': math.fsum(r['baselineProvisionalEligibleKm'] for r in records),
        'excludedIncidences': len(incidences), 'uniqueExcludedPublisherIds': len({i['ordinal'] for i in incidences}),
        'reasonIncidences': reasons, 'reasonUniquePublisherIds': {k: len(v) for k, v in unique_reasons.items()},
        'reasonCombinationIncidences': combinations, 'levelCategoryIncidences': levels,
        'levelCategoryUniquePublisherIds': {k: len(v) for k, v in unique_levels.items()},
        'levelValueCategoryIncidences': values, 'candidateOverlapIncidences': overlaps,
        'sharedSampleIncidenceKm': math.fsum(i['candidateOverlap']['sharedSampleIncidenceKm'] for i in incidences),
        'declaredRoleLevelOnlyIncidences': sum(i['declaredRoleLevelOnly'] for i in incidences),
        'measuredFlagIncidences': measured}


def analyze(plan, output, paths):
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    prior = json.loads(Path(paths['previousReport']).read_text())
    metadata, profiles, identities = [], [], set()
    levels, value_categories, level_flags, limits = Counter(), Counter(), Counter(), Counter()
    scope_counts = Counter()
    with Path(paths['segments']).open('rb') as raw_stream, Path(paths['scopes']).open('rb') as scopes, Path(paths['rows']).open('rb') as old_rows:
        for ordinal, triple in enumerate(itertools.zip_longest(raw_stream, scopes, old_rows)):
            output.check()
            require(all(v is not None and len(v) <= plan['maxLineBytes'] for v in triple), 'Retained input roster/allocation')
            raw, scope_raw, meta_raw = triple
            row, scope, meta = json.loads(raw), json.loads(scope_raw), json.loads(meta_raw)
            key = row['id'], row['version']
            require(key not in identities and ordinal == meta['ordinal'] == scope['ordinal'] and ordinal < plan['expectedRows'], 'Retained identity/ordinal')
            require(hashlib.sha256(raw).hexdigest() == meta['rawLineSha256'] and meta == row_metadata(row, scope), 'Frozen raw metadata changed')
            identities.add(key)
            profile = level_profile(row.get('level_rules'))
            record = {'ordinal': ordinal, 'id': key[0], 'version': key[1], 'class': row['class'],
                'sourceLineSha256': meta['rawLineSha256'], 'metadataLineSha256': hashlib.sha256(meta_raw).hexdigest(),
                'scopesLineSha256': hashlib.sha256(scope_raw).hexdigest(), 'rawLevelRules': row.get('level_rules'),
                'profile': profile, 'frozenLimit': meta['frozenLimit'], 'frozenSpeedOnlyLimit': meta['frozenSpeedOnlyLimit'],
                'scopeRulesSha256': meta['scopeRulesSha256'], 'rawConnectorsSha256': hashlib.sha256(canonical(row.get('connectors'))).hexdigest(),
                'baseReasons': meta['baseReasons']}
            output.record('levels.jsonl', record)
            metadata.append(meta); profiles.append(profile)
            levels[profile['category']] += 1; value_categories[profile['valueCategory']] += 1; level_flags.update(profile['flags'])
            limits.update([meta['frozenLimit']['status']])
            scope_counts['speedRows'] += row.get('speed_limits') not in (None, [], {})
            scope_counts['accessRows'] += row.get('access_restrictions') not in (None, [], {})
    require(len(metadata) == plan['expectedRows'] and dict(limits) == prior['frozenLimitStatusCounts'] and dict(scope_counts) == prior['scopeRowCounts'], 'Full retained/scoped denominators')
    saved, supports = {}, {}
    for name, destination in [('matches', saved), ('support', supports)]:
        with Path(paths[name]).open('rb') as stream:
            for raw in stream:
                r = json.loads(raw); key = r['windowId'], r['arc']
                require(key not in destination, 'Duplicate source/sample record')
                destination[key] = (r, hashlib.sha256(raw).hexdigest())
    boxes = {w['id']: w['bbox'] for w in windows}
    cached = {w['id']: w['cachedRows'] for w in prior['windows']}
    records = []
    with Path(paths['chains']).open('rb') as stream:
        for raw in stream:
            output.check()
            chain = json.loads(raw); key = chain['windowId'], chain['arc']
            old, match_sha = saved.pop(key); support, support_sha = supports.pop(key)
            require(chain['savedSupportLineSha256'] == support_sha and support['savedMatchLineSha256'] == match_sha, 'Frozen chain/sample/source binding')
            points, weights = sample_points(old, support)
            aligned = defaultdict(list)
            for i, sample in enumerate(support['samples']):
                for ordinal in sample[4]: aligned[ordinal].append(i)
            node_ids = {n['ordinal'] for n in chain['nodes']}; excluded_ids = {r['ordinal'] for r in chain['excludedRows']}
            require(not node_ids & excluded_ids and node_ids | excluded_ids == aligned.keys(), 'Full aligned-row partition')
            members = {i for c in chain['candidates'] for i in c['rowOrdinals']}
            require(members <= node_ids, 'Frozen candidate member roster')
            candidate_indices = {i for ordinal in members for i in aligned[ordinal]}
            candidate_ids = {v for ordinal in members for v in metadata[ordinal]['endpointIds'] if v is not None}
            excluded = []
            for entry in chain['excludedRows']:
                ordinal = entry['ordinal']; meta = metadata[ordinal]; profile = profiles[ordinal]
                measured = measurements(meta, aligned[ordinal], points, boxes[key[0]])
                frozen = set(meta['baseReasons'])
                if measured['insideWindow'] is False: frozen.add('outside_window_endpoint')
                if measured['frozenProgressReason'] is not None: frozen.add(measured['frozenProgressReason'])
                require(sorted(frozen) == entry['reasons'], 'Frozen exclusions changed')
                excluded.append({'ordinal': ordinal, 'id': meta['id'], 'version': meta['version'],
                    'frozenReasons': entry['reasons'], 'levelCategory': profile['category'], 'levelValueCategory': profile['valueCategory'],
                    'declaredRoleLevelOnly': bool(frozen and frozen <= DECLARED_REASONS), 'measurements': measured,
                    'candidateOverlap': overlap(aligned[ordinal], meta, candidate_indices, candidate_ids, weights, bool(chain['candidates']))})
            record = {'windowId': key[0], 'arc': key[1], 'sourceClassKph': chain['sourceClassKph'], 'sourceKm': chain['sourceKm'],
                'sampleCount': len(points), 'chainLineSha256': hashlib.sha256(raw).hexdigest(),
                'originalStatus': chain['status'], 'originalOldStatus': chain['oldStatus'],
                'originalSupportsHypothesis': chain['supportsHypothesis'], 'originalSearchCapped': chain['searchCapped'],
                'candidateCount': len(chain['candidates']), 'candidateRowsSha256': hashlib.sha256(canonical([c['rowOrdinals'] for c in chain['candidates']])).hexdigest(),
                'baselineProvisionalEligibleKm': chain['baselineProvisionalEligibleKm'], 'cohorts': cohorts(chain, cached[key[0]]),
                'sourceStatus': 'incomplete_after_capture_stop', 'excluded': excluded}
            output.record('exclusions.jsonl', record); records.append(record)
    require(not saved and not supports and len(records) == plan['expectedMatches'] and sum(r['sampleCount'] for r in records) == plan['expectedSamples'], 'All source/sample records')
    total = aggregate(records)
    require(total['originalStatusCounts'] == prior['allWindows']['statusCounts'] and total['candidateChains'] == prior['allWindows']['candidateChains'] and
            total['formerlyAbsentPositiveRecords'] == prior['allWindows']['formerlyAbsentUncappedWithChain'] and total['cappedRecords'] == prior['allWindows']['cappedRecords'], 'Frozen matcher outcomes changed')
    require(math.isclose(total['sourceKm'], prior['allWindows']['sourceKm'], abs_tol=1e-8) and
            sum(r['candidateCount'] > 0 for r in records) == prior['allWindows']['recordsWithCandidates'], 'Frozen source/candidate denominators')
    summaries = []
    for window in windows:
        subset = [r for r in records if r['windowId'] == window['id']]
        result = {'id': window['id'], 'cachedRows': cached[window['id']], 'sourceStatus': 'incomplete_after_capture_stop',
            'totals': aggregate(subset), 'sourceClassesKph': {str(s): aggregate([r for r in subset if r['sourceClassKph'] == s]) for s in (85, 105)}}
        summaries.append(result); output.write('windows/' + window['id'] + '.json', json_bytes(result))
    names = ['all', 'with_cache', 'empty_cache', 'candidate_bearing', 'without_candidate_with_cache', 'formerly_absent_positive', 'baseline_absent']
    report = {'retainedRows': len(metadata), 'retainedLevelCategories': levels, 'retainedLevelValueCategories': value_categories,
        'retainedLevelFlagCounts': level_flags, 'scopeRowCounts': scope_counts, 'frozenLimitStatusCounts': limits,
        'cohorts': {name: aggregate([r for r in records if name in r['cohorts']]) for name in names}, 'windows': summaries,
        'publisherGeometryKm': prior['publisherGeometryKm'], 'candidateMemberParserOccurrences': dict(Counter(s for c in read_saved_candidates(paths['chains']) for s in c['memberParserStatuses'])),
        'completedSourceWindows': 0, 'originalFeasibilityQualified': False, 'matcherEnumerationsPerformed': 0, 'networkRequests': 0, 'routingQueries': 0,
        'scope': 'Overlapping cohorts/reasons and per-incidence sample overlaps are not additive road coverage. Unique counts identify retained publisher id/version pairs, not physical roads. Zero level is a raw value, not grade/access proof. All frozen outcomes/21 incomplete windows stay; no new joins, chains, parser or permission policy.'}
    output.write('report.json', json_bytes(report))


def read_saved_candidates(path):
    with Path(path).open() as stream:
        for raw in stream:
            yield from json.loads(raw)['candidates']


def run(plan, output):
    analyze(plan, output, plan['paths'])
    from coarse_chain_exclusions_audit import audit
    audit(plan, output, plan['paths'])


if __name__ == '__main__':
    from offline_timing_runner import main
    main('docs/evidence/coarse-chain-exclusions-2026-10-26/execution-plan.json')

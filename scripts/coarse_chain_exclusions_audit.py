"""Independent raw-level, measurement, overlap and denominator accounting."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from coarse_path_features import distance_km
from coarse_timing_chains import row_metadata, sample_points
from coarse_timing_compatibility_audit import close
from coarse_timing_input import json_bytes, require


def reference_level(rules):
    if rules is None or rules == []:
        return {'category': 'missing', 'valueCategory': 'missing', 'flags': [], 'ruleCount': 0, 'fieldNames': []}
    if not isinstance(rules, list):
        return {'category': 'malformed', 'valueCategory': 'unknown', 'flags': ['malformed'], 'ruleCount': 0, 'fieldNames': []}
    fields, spans, values, flags = set(), [], [], set()
    value_error = False
    for item in rules:
        if not isinstance(item, dict):
            value_error = True; flags.add('malformed'); continue
        fields |= item.keys()
        if any(k not in ('value', 'between') and item[k] not in (None, [], {}) for k in item): flags.add('unsupported_fields')
        value = item.get('value')
        if type(value) in (int, float) and math.isfinite(value): values.append(value)
        else: value_error = True; flags.add('malformed')
        span = item.get('between')
        if span is None: spans.append((0, 1))
        elif type(span) is list and len(span) == 2 and all(type(x) in (int, float) and math.isfinite(x) for x in span) and 0 <= span[0] < span[1] <= 1:
            spans.append(tuple(span))
            if span[0] != 0 or span[1] != 1: flags.add('partial_intervals')
        else: flags.add('malformed')
    for i in range(len(spans)):
        for j in range(i):
            if max(spans[i][0], spans[j][0]) < min(spans[i][1], spans[j][1]): flags.add('overlapping_intervals')
    if value_error or not values: value_category = 'unknown'
    elif all(v == 0 for v in values): value_category = 'uniform_zero'
    elif all(v == values[0] for v in values): value_category = 'uniform_nonzero'
    else: value_category = 'mixed'
    if 'malformed' in flags: category = 'malformed'
    elif 'unsupported_fields' in flags: category = 'unsupported_fields'
    elif 'partial_intervals' in flags: category = 'partial'
    else: category = value_category
    return {'category': category, 'valueCategory': value_category, 'flags': sorted(flags), 'ruleCount': len(rules), 'fieldNames': sorted(fields)}


def reference_measure(row, indices, points, box):
    if len(row['endpoints']) != 2:
        return {'endpointDistancesKm': [], 'progressIntervals': [], 'insideWindow': None,
                'measuredProgress': 'unavailable_geometry', 'flags': ['unavailable_geometry'], 'frozenProgressApplied': False, 'frozenProgressReason': None}
    inside = all(box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3] for p in row['endpoints'])
    bounds, distances = [], []
    for endpoint in row['endpoints']:
        by_index = {i: distance_km(endpoint, points[i]) for i in indices}
        nearest = min(by_index.values()); tied = [i for i in by_index if abs(by_index[i] - nearest) <= 1e-9]
        bounds.append([min(tied), max(tied)]); distances.append(nearest)
    if bounds[0][1] < bounds[1][0]: order = 'forward'
    elif bounds[1][1] < bounds[0][0]: order = 'reverse'
    else: order = 'overlap_or_tie'
    flags = []
    if not inside: flags.append('outside_window_endpoint')
    if any(d > .025 for d in distances): flags.append('endpoint_not_near_own_samples')
    if order == 'overlap_or_tie': flags.append('nonprogressing_or_tied_endpoints')
    applied = len(row['baseReasons']) == 0 and inside
    reason = None
    if applied:
        if any(d > .025 for d in distances): reason = 'endpoint_not_near_own_samples'
        elif order == 'overlap_or_tie': reason = 'nonprogressing_or_tied_endpoints'
    return {'endpointDistancesKm': distances, 'progressIntervals': bounds, 'insideWindow': inside,
            'measuredProgress': order, 'flags': flags, 'frozenProgressApplied': applied, 'frozenProgressReason': reason}


def reference_aggregate(records):
    reasons, combinations, levels, values, overlaps, measured = (Counter() for _ in range(6))
    by_reason, by_level, unique = defaultdict(set), defaultdict(set), set()
    count, declared = 0, 0
    for record in records:
        for row in record['excluded']:
            count += 1; ordinal = row['ordinal']; unique.add(ordinal)
            for reason in row['frozenReasons']: reasons[reason] += 1; by_reason[reason].add(ordinal)
            combinations['|'.join(row['frozenReasons'])] += 1
            levels[row['levelCategory']] += 1; by_level[row['levelCategory']].add(ordinal)
            values[row['levelValueCategory']] += 1
            overlaps[row['candidateOverlap']['kind']] += 1
            measured.update(row['measurements']['flags']); declared += row['declaredRoleLevelOnly']
    return {'arcCount': len(records), 'sourceKm': math.fsum(r['sourceKm'] for r in records),
        'originalStatusCounts': dict(Counter(r['originalStatus'] for r in records)), 'originalOldStatusCounts': dict(Counter(r['originalOldStatus'] for r in records)),
        'samples': sum(r['sampleCount'] for r in records), 'candidateChains': sum(r['candidateCount'] for r in records),
        'formerlyAbsentPositiveRecords': sum(r['originalSupportsHypothesis'] for r in records), 'cappedRecords': sum(r['originalSearchCapped'] for r in records),
        'baselineProvisionalEligibleKm': math.fsum(r['baselineProvisionalEligibleKm'] for r in records),
        'excludedIncidences': count, 'uniqueExcludedPublisherIds': len(unique), 'reasonIncidences': reasons,
        'reasonUniquePublisherIds': {k: len(v) for k, v in by_reason.items()}, 'reasonCombinationIncidences': combinations,
        'levelCategoryIncidences': levels, 'levelCategoryUniquePublisherIds': {k: len(v) for k, v in by_level.items()},
        'levelValueCategoryIncidences': values, 'candidateOverlapIncidences': overlaps,
        'sharedSampleIncidenceKm': math.fsum(i['candidateOverlap']['sharedSampleIncidenceKm'] for r in records for i in r['excluded']),
        'declaredRoleLevelOnlyIncidences': declared, 'measuredFlagIncidences': measured}


def audit(plan, output, paths):
    report = json.loads((output.root / 'report.json').read_text())
    prior = json.loads(Path(paths['previousReport']).read_text())
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    metadata, profiles, identities = [], [], set()
    levels, values, flags, limits, counts = (Counter() for _ in range(5))
    with Path(paths['segments']).open('rb') as source, Path(paths['scopes']).open('rb') as scopes, Path(paths['rows']).open('rb') as rows, (output.root / 'levels.jsonl').open('rb') as ledger:
        for ordinal, four in enumerate(itertools.zip_longest(source, scopes, rows, ledger)):
            output.check(); require(all(v is not None for v in four), 'Independent row roster')
            raw, scope_raw, meta_raw, encoded = four
            row, scope, meta, saved = (json.loads(v) for v in four)
            key = row['id'], row['version']; require(key not in identities, 'Independent retained identities'); identities.add(key)
            require(ordinal == saved['ordinal'] == meta['ordinal'] and (saved['id'], saved['version']) == key, 'Retained ordinal/id')
            require(saved['class'] == row['class'], 'Retained source class')
            require(saved['sourceLineSha256'] == hashlib.sha256(raw).hexdigest() == meta['rawLineSha256'], 'Raw source binding')
            require(saved['metadataLineSha256'] == hashlib.sha256(meta_raw).hexdigest() and saved['scopesLineSha256'] == hashlib.sha256(scope_raw).hexdigest(), 'Raw metadata/scope binding')
            require(meta == row_metadata(row, scope), 'Frozen metadata filtering changed')
            profile = reference_level(row.get('level_rules'))
            require(saved['rawLevelRules'] == row.get('level_rules') and saved['profile'] == profile, 'Independent raw level classification')
            require(saved['baseReasons'] == meta['baseReasons'] and saved['frozenLimit'] == meta['frozenLimit'] and saved['frozenSpeedOnlyLimit'] == meta['frozenSpeedOnlyLimit'], 'Frozen classifications changed')
            require(saved['scopeRulesSha256'] == meta['scopeRulesSha256'] and saved['rawConnectorsSha256'] == hashlib.sha256(json.dumps(row.get('connectors'), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest(), 'Raw rules/connectors remain bound')
            metadata.append(meta); profiles.append(profile)
            levels[profile['category']] += 1; values[profile['valueCategory']] += 1; flags.update(profile['flags']); limits.update([meta['frozenLimit']['status']])
            counts['speedRows'] += row.get('speed_limits') not in (None, [], {}); counts['accessRows'] += row.get('access_restrictions') not in (None, [], {})
    require(len(metadata) == plan['expectedRows'] == report['retainedRows'], 'All retained identities')
    close(report['retainedLevelCategories'], levels); close(report['retainedLevelValueCategories'], values); close(report['retainedLevelFlagCounts'], flags)
    close(report['frozenLimitStatusCounts'], limits); close(report['scopeRowCounts'], counts)
    cached = {w['id']: w['cachedRows'] for w in prior['windows']}; boxes = {w['id']: w['bbox'] for w in windows}
    matches, supports = {}, {}
    for field, target in [('matches', matches), ('support', supports)]:
        with Path(paths[field]).open() as stream:
            for raw in stream:
                r = json.loads(raw); target[r['windowId'], r['arc']] = r
    records, members = [], Counter()
    with Path(paths['chains']).open('rb') as old_stream, (output.root / 'exclusions.jsonl').open() as ledger:
        for raw, encoded in itertools.zip_longest(old_stream, ledger):
            output.check(); require(raw is not None and encoded is not None, 'All original arc records')
            chain, record = json.loads(raw), json.loads(encoded); key = chain['windowId'], chain['arc']
            require((record['windowId'], record['arc']) == key and record['chainLineSha256'] == hashlib.sha256(raw).hexdigest(), 'Frozen chain outcome binding')
            for field, original in [('originalStatus', 'status'), ('originalOldStatus', 'oldStatus'), ('originalSupportsHypothesis', 'supportsHypothesis'), ('originalSearchCapped', 'searchCapped'), ('sourceClassKph', 'sourceClassKph'), ('sourceKm', 'sourceKm'), ('baselineProvisionalEligibleKm', 'baselineProvisionalEligibleKm')]:
                require(record[field] == chain[original], 'Original source/outcome changed')
            candidate_rows = [c['rowOrdinals'] for c in chain['candidates']]
            require(record['candidateCount'] == len(candidate_rows) and record['candidateRowsSha256'] == hashlib.sha256(json.dumps(candidate_rows, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest(), 'All saved candidates retained')
            for c in chain['candidates']: members.update(c['memberParserStatuses'])
            points, weights = sample_points(matches.pop(key), supports[key]); support = supports.pop(key)
            require(record['sampleCount'] == len(points) and record['sourceStatus'] == 'incomplete_after_capture_stop', 'Original sample/cache denominator')
            membership = defaultdict(list)
            for i, sample in enumerate(support['samples']):
                for ordinal in sample[4]: membership[ordinal].append(i)
            candidate_ordinals = {i for path in candidate_rows for i in path}
            candidate_support = {i for ordinal in candidate_ordinals for i in membership[ordinal]}
            candidate_ids = {v for ordinal in candidate_ordinals for v in metadata[ordinal]['endpointIds'] if v is not None}
            require(len(record['excluded']) == len(chain['excludedRows']), 'Every excluded incidence')
            for saved, old in zip(record['excluded'], chain['excludedRows']):
                ordinal = old['ordinal']; meta, profile = metadata[ordinal], profiles[ordinal]
                require(saved['ordinal'] == ordinal and (saved['id'], saved['version']) == (meta['id'], meta['version']), 'Excluded identity')
                require(saved['frozenReasons'] == old['reasons'] and saved['levelCategory'] == profile['category'] and saved['levelValueCategory'] == profile['valueCategory'], 'Frozen reasons/raw levels')
                measured = reference_measure(meta, membership[ordinal], points, boxes[key[0]])
                close(saved['measurements'], measured)
                original = set(meta['baseReasons'])
                if measured['insideWindow'] is False: original.add('outside_window_endpoint')
                if measured['frozenProgressReason']: original.add(measured['frozenProgressReason'])
                require(sorted(original) == old['reasons'], 'Frozen reason precedence')
                require(saved['declaredRoleLevelOnly'] == bool(original and not original - {'unsupported_road_role', 'unsupported_level_rules'}), 'Declared role/level-only partition')
                shared = sorted(set(membership[ordinal]) & candidate_support)
                ids = sorted({v for v in meta['endpointIds'] if v is not None} & candidate_ids)
                if not candidate_rows: expected = {'kind': 'no_candidate_record', 'sharedSampleCount': 0, 'sharedSampleIncidenceKm': 0., 'sharedEndpointIds': []}
                else:
                    kind = 'sample_and_endpoint' if shared and ids else 'sample_only' if shared else 'endpoint_only' if ids else 'neither'
                    expected = {'kind': kind, 'sharedSampleCount': len(shared), 'sharedSampleIncidenceKm': math.fsum(weights[i] for i in shared), 'sharedEndpointIds': ids}
                close(saved['candidateOverlap'], expected)
            names = ['all', 'with_cache' if cached[key[0]] else 'empty_cache']
            if candidate_rows: names.append('candidate_bearing')
            elif cached[key[0]]: names.append('without_candidate_with_cache')
            if chain['supportsHypothesis']: names.append('formerly_absent_positive')
            if chain['oldStatus'] == 'absent_in_cache': names.append('baseline_absent')
            require(record['cohorts'] == names, 'Fixed overlapping cohort membership'); records.append(record)
    require(not matches and not supports and len(records) == plan['expectedMatches'] and sum(r['sampleCount'] for r in records) == plan['expectedSamples'], 'Full arc/sample rosters')
    require(set(report['cohorts']) == {'all', 'with_cache', 'empty_cache', 'candidate_bearing', 'without_candidate_with_cache', 'formerly_absent_positive', 'baseline_absent'}, 'All predeclared cohorts')
    for name, group in report['cohorts'].items(): close(group, reference_aggregate([r for r in records if name in r['cohorts']]))
    require(len(report['windows']) == len(windows) == plan['expectedWindows'], 'All incomplete windows')
    for w in report['windows']:
        subset = [r for r in records if r['windowId'] == w['id']]
        require(w['cachedRows'] == cached[w['id']] and w['sourceStatus'] == 'incomplete_after_capture_stop', 'Window cache state')
        close(w['totals'], reference_aggregate(subset))
        for speed, group in w['sourceClassesKph'].items(): close(group, reference_aggregate([r for r in subset if r['sourceClassKph'] == int(speed)]))
        require(w == json.loads((output.root / 'windows' / (w['id'] + '.json')).read_text()), 'Window/report identity')
    require(report['candidateMemberParserOccurrences'] == members and report['publisherGeometryKm'] == prior['publisherGeometryKm'], 'Preserved scope and separate geometry denominators')
    require(report['completedSourceWindows'] == report['matcherEnumerationsPerformed'] == report['networkRequests'] == report['routingQueries'] == 0 and not report['originalFeasibilityQualified'], 'No new matching/coverage/policy admission')
    output.write('audit.json', json_bytes({'independentRawLevelMeasurementOverlapCohortAndDenominatorAudit': True,
        'retainedRows': len(metadata), 'arcWindowRecords': len(records), 'samples': sum(r['sampleCount'] for r in records),
        'excludedIncidences': sum(len(r['excluded']) for r in records), 'plannedWindows': len(windows),
        'completedSourceWindows': 0, 'matcherEnumerationsPerformed': 0,
        'method': 'Separate raw-level classifier, endpoint/tie measurement, overlap/cohort/unique-ID counters. Shared sealed raw-metadata, source-sample and numeric primitives. No new node/adjacency/chain search or grade/access/physical-identity proof.'}))

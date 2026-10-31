"""Independent audit of additive declared-role reporting, without rematching."""
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path

from coarse_timing_input import json_bytes, require, usable_limit
from coarse_timing_compatibility_audit import close


def reference_scope(chain, cached):
    outside = [e for e in chain['excludedRows'] if 'unsupported_road_role' in e['reasons']]
    unresolved = [e for e in chain['excludedRows'] if 'unsupported_road_role' not in e['reasons']]
    n = len(chain['candidates'])
    if cached == 0: label = 'unmeasured_empty_cache'
    elif chain['searchCapped']: label = 'search_capped'
    elif len(unresolved) > 0: label = 'unresolved_in_role_with_candidates' if n > 0 else 'unresolved_in_role_without_candidates'
    elif n == 0: label = 'no_declared_role_chain'
    elif n == 1: label = 'single_declared_role_chain'
    else: label = 'multiple_declared_role_chains'
    exhaustive = cached > 0 and chain['searchCapped'] is False and len(unresolved) == 0
    return {'status': label, 'exhaustiveWithinDeclaredRoleScope': exhaustive,
        'declaredOutOfRoleRows': outside, 'unresolvedInRoleRows': unresolved, 'savedCandidateCount': n,
        'newlyExhaustiveCandidateRecord': bool(n > 0 and chain['status'] == 'unresolved_with_candidates' and
            chain['searchExhaustiveForDeclaredRows'] is False and exhaustive),
        'sourceComplete': False, 'physicalIdentityVerified': False, 'carAccessVerified': False}


def reference_summary(records):
    outside, unresolved = [], []
    for r in records:
        outside.extend(r['declaredRoleScope']['declaredOutOfRoleRows'])
        unresolved.extend(r['declaredRoleScope']['unresolvedInRoleRows'])
    new = [r for r in records if r['declaredRoleScope']['newlyExhaustiveCandidateRecord']]
    return {'arcCount': len(records), 'sourceKm': math.fsum(r['sourceKm'] for r in records),
        'samples': sum(r['reportingProvenance']['sampleCount'] for r in records),
        'originalStatusCounts': dict(Counter(r['status'] for r in records)),
        'originalExhaustiveRecords': len([r for r in records if r['searchExhaustiveForDeclaredRows']]),
        'originalCandidateChains': sum(len(r['candidates']) for r in records),
        'originalPositiveRecords': len([r for r in records if r['supportsHypothesis']]),
        'originalCappedRecords': len([r for r in records if r['searchCapped']]),
        'baselineProvisionalEligibleKm': math.fsum(r['baselineProvisionalEligibleKm'] for r in records),
        'roleScopedStatusCounts': dict(Counter(r['declaredRoleScope']['status'] for r in records)),
        'roleScopedExhaustiveRecords': len([r for r in records if r['declaredRoleScope']['exhaustiveWithinDeclaredRoleScope']]),
        'newlyExhaustiveCandidateRecords': len(new), 'newlyExhaustiveCandidateSourceKm': math.fsum(r['sourceKm'] for r in new),
        'declaredOutOfRoleIncidences': len(outside), 'unresolvedInRoleIncidences': len(unresolved),
        'uniqueOutOfRolePublisherIds': len({e['ordinal'] for e in outside}),
        'uniqueUnresolvedInRolePublisherIds': len({e['ordinal'] for e in unresolved}),
        'outOfRoleReasonIncidences': dict(Counter(reason for e in outside for reason in e['reasons'])),
        'unresolvedInRoleReasonIncidences': dict(Counter(reason for e in unresolved for reason in e['reasons']))}


def verify_weights(match, support):
    by_span = {}
    for sample in support['samples']:
        by_span.setdefault(sample[0], []).append(sample)
    require(set(by_span) == set(range(len(match['sourceSpans']))), 'Independent source-span roster')
    for i, (_, _, km) in enumerate(match['sourceSpans']):
        block = by_span[i]; n = len(block)
        require(n > 0 and math.isfinite(km) and km > 0, 'Positive original source weight')
        for j, sample in enumerate(block):
            require(sample[:3] == [i, j, n] and sample[4] == sorted(set(sample[4])), 'Independent saved sample/membership roster')
            close(sample[3], km / n)
    close(math.fsum(s[3] for s in support['samples']), match['sourceKm'])
    return len(support['samples'])


def audit(plan, output, paths):
    report = json.loads((output.root / 'report.json').read_text())
    previous = json.loads(Path(paths['previousReport']).read_text())
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    identities, metadata, limits, roles, levels, counts = set(), [], Counter(), Counter(), Counter(), Counter()
    with Path(paths['segments']).open('rb') as source, Path(paths['rows']).open('rb') as rows, Path(paths['levels']).open('rb') as inventory, (output.root / 'rows.jsonl').open() as ledger:
        for ordinal, four in enumerate(itertools.zip_longest(source, rows, inventory, ledger)):
            output.check(); require(all(v is not None for v in four), 'Every retained row required')
            raw, meta_raw, level_raw, encoded = four
            row, meta, level, saved = (json.loads(v) for v in four)
            key = row['id'], row['version']
            require(key not in identities and key == (saved['id'], saved['version']) == (meta['id'], meta['version']), 'Independent retained identity')
            identities.add(key); require(saved['ordinal'] == meta['ordinal'] == level['ordinal'] == ordinal, 'Fixed ordinals')
            require(saved['sourceLineSha256'] == hashlib.sha256(raw).hexdigest() == meta['rawLineSha256'] == level['sourceLineSha256'], 'Raw source hash')
            require(saved['metadataLineSha256'] == hashlib.sha256(meta_raw).hexdigest() == level['metadataLineSha256'] and
                    saved['levelInventoryLineSha256'] == hashlib.sha256(level_raw).hexdigest(), 'Frozen metadata/level hashes')
            limit = usable_limit(row); speed_only = usable_limit({**row, 'access_restrictions': None})
            require(saved['frozenLimit'] == meta['frozenLimit'] == level['frozenLimit'] == limit and
                    saved['frozenSpeedOnlyLimit'] == meta['frozenSpeedOnlyLimit'] == level['frozenSpeedOnlyLimit'] == speed_only, 'Unchanged parser/scope outcomes')
            require(saved['rawClass'] == row['class'] and saved['rawSubtype'] == row['subtype'], 'Raw role unchanged')
            require(saved['declaredUnsupportedRole'] == (limit['status'] == 'unsupported_road_role'), 'Frozen role membership')
            for value, field in [(row.get('level_rules'), 'rawLevelRulesSha256'), (row.get('connectors'), 'rawConnectorsSha256'),
                                 ([row.get('speed_limits'), row.get('access_restrictions')], 'scopeRulesSha256')]:
                digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                require(saved[field] == digest, 'Original raw rule/connector values retained')
            require(saved['originalLevelProfile'] == level['profile'], 'No new level interpretation')
            metadata.append(saved); limits[limit['status']] += 1; roles[row['class']] += 1; levels[level['profile']['category']] += 1
            counts['speedRows'] += row.get('speed_limits') not in (None, [], {}); counts['accessRows'] += row.get('access_restrictions') not in (None, [], {})
    require(len(metadata) == plan['expectedRows'] == report['retainedRows'], 'All publisher identities')
    close(report['rawRoleCounts'], roles); close(report['frozenLimitStatusCounts'], limits); close(report['scopeRowCounts'], counts); close(report['retainedLevelCategories'], levels)
    matches, supports = {}, {}
    for name, target in [('matches', matches), ('support', supports)]:
        with Path(paths[name]).open('rb') as stream:
            for raw in stream:
                r = json.loads(raw); target[r['windowId'], r['arc']] = (r, hashlib.sha256(raw).hexdigest())
    cached = {w['id']: w['cachedRows'] for w in previous['windows']}
    records, samples = [], 0
    with Path(paths['chains']).open('rb') as chains, Path(paths['exclusions']).open('rb') as exclusions, (output.root / 'role-scope.jsonl').open() as ledger:
        for raw, excluded_raw, encoded in itertools.zip_longest(chains, exclusions, ledger):
            output.check(); require(all(v is not None for v in (raw, excluded_raw, encoded)), 'All frozen chain records')
            chain, excluded, saved = json.loads(raw), json.loads(excluded_raw), json.loads(encoded)
            require({k: v for k, v in saved.items() if k not in {'declaredRoleScope', 'reportingProvenance'}} == chain and
                    set(saved) == set(chain) | {'declaredRoleScope', 'reportingProvenance'}, 'Every original field/candidate/status preserved')
            key = chain['windowId'], chain['arc']; p = saved['reportingProvenance']
            require(p['chainLineSha256'] == hashlib.sha256(raw).hexdigest() == excluded['chainLineSha256'] and
                    p['exclusionLineSha256'] == hashlib.sha256(excluded_raw).hexdigest(), 'Original chain/exclusion hashes')
            require(p['cohorts'] == excluded['cohorts'], 'Frozen overlapping cohorts')
            match, m_sha = matches.pop(key); support, s_sha = supports.pop(key)
            require(p['matchLineSha256'] == m_sha == support['savedMatchLineSha256'] and p['supportLineSha256'] == s_sha == chain['savedSupportLineSha256'], 'Original source/sample hashes')
            n = verify_weights(match, support); samples += n
            require(p['sampleCount'] == excluded['sampleCount'] == n, 'Every original sample')
            close(chain['sourceKm'], match['sourceKm']); require(chain['sourceClassKph'] == match['sourceClassKph'], 'Source class/weight unchanged')
            scope = reference_scope(chain, cached[key[0]])
            for name, value in scope.items(): close(saved['declaredRoleScope'][name], value)
            require(saved['declaredRoleScope']['scope'].startswith('Only the frozen supported-role candidate universe'), 'Scope limitations')
            partitions = saved['declaredRoleScope']['declaredOutOfRoleRows'] + saved['declaredRoleScope']['unresolvedInRoleRows']
            require(len(partitions) == len(chain['excludedRows']) and len({e['ordinal'] for e in partitions}) == len(partitions), 'Excluded partition is complete/disjoint')
            for e in partitions: require(('unsupported_road_role' in e['reasons']) == metadata[e['ordinal']]['declaredUnsupportedRole'], 'Role label cannot be reinterpreted')
            records.append(saved)
    require(not matches and not supports and len(records) == plan['expectedMatches'] and samples == plan['expectedSamples'], 'Full arc/sample roster')
    require(set(report['cohorts']) == set(previous['cohorts']), 'Every original cohort retained')
    for name, group in report['cohorts'].items(): close(group, reference_summary([r for r in records if name in r['reportingProvenance']['cohorts']]))
    require(len(report['windows']) == len(windows) == plan['expectedWindows'], 'All incomplete windows')
    for w in report['windows']:
        subset = [r for r in records if r['windowId'] == w['id']]
        require(w['sourceStatus'] == 'incomplete_after_capture_stop' and w['cachedRows'] == cached[w['id']], 'Source incompleteness retained')
        close(w['totals'], reference_summary(subset))
        for speed, group in w['sourceClassesKph'].items(): close(group, reference_summary([r for r in subset if r['sourceClassKph'] == int(speed)]))
        require(w == json.loads((output.root / 'windows' / (w['id'] + '.json')).read_text()), 'Window/report identity')
    positive = [r for r in records if r['declaredRoleScope']['newlyExhaustiveCandidateRecord']]
    require(report['reportingHypothesisSupported'] == bool(positive), 'Predeclared reporting decision')
    require(report['publisherGeometryKm'] == previous['publisherGeometryKm'] and report['completedSourceWindows'] == report['matcherEnumerationsPerformed'] == report['networkRequests'] == report['routingQueries'] == 0 and not report['originalFeasibilityQualified'], 'No physical/source/model admission')
    output.write('audit.json', json_bytes({'independentAdditiveRolePartitionOriginalFieldWeightAndOutcomeAudit': True,
        'retainedRows': len(metadata), 'arcWindowRecords': len(records), 'samples': samples, 'plannedWindows': len(windows),
        'newlyExhaustiveCandidateRecords': len(positive), 'reportingHypothesisSupported': bool(positive),
        'completedSourceWindows': 0, 'matcherEnumerationsPerformed': 0,
        'method': 'Separate role/cap/cache classification and aggregate counters; every original chain field equals its saved value, and all raw roles/scopes/sample weights remain bound. Shared sealed parser/hash primitives. No new geometry, graph, chain, physical identity or permission proof.'}))

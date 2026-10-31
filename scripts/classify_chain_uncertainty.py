"""Add declared-role reporting fields to frozen matches; never rematch."""
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path

from analyze_timing_cache import canonical
from coarse_timing_input import json_bytes, require, usable_limit


COHORTS = ['all', 'with_cache', 'empty_cache', 'candidate_bearing',
           'without_candidate_with_cache', 'formerly_absent_positive', 'baseline_absent']


def classify(chain, cached_rows):
    require(type(cached_rows) is int and cached_rows >= 0 and type(chain['searchCapped']) is bool and
            type(chain['searchExhaustiveForDeclaredRows']) is bool, 'Cache/cap/exhaustiveness types')
    outside, unresolved, seen = [], [], set()
    for excluded in chain['excludedRows']:
        require(excluded['ordinal'] not in seen and excluded['reasons'] and all(isinstance(r, str) and r for r in excluded['reasons']), 'Excluded row partition')
        seen.add(excluded['ordinal'])
        (outside if 'unsupported_road_role' in excluded['reasons'] else unresolved).append(excluded)
    count = len(chain['candidates'])
    exhaustive = bool(cached_rows and not chain['searchCapped'] and not unresolved)
    if not cached_rows: status = 'unmeasured_empty_cache'
    elif chain['searchCapped']: status = 'search_capped'
    elif unresolved: status = 'unresolved_in_role_with_candidates' if count else 'unresolved_in_role_without_candidates'
    elif count == 0: status = 'no_declared_role_chain'
    elif count == 1: status = 'single_declared_role_chain'
    else: status = 'multiple_declared_role_chains'
    newly_exhaustive = bool(chain['status'] == 'unresolved_with_candidates' and count and
                            not chain['searchExhaustiveForDeclaredRows'] and exhaustive)
    return {'status': status, 'exhaustiveWithinDeclaredRoleScope': exhaustive,
        'declaredOutOfRoleRows': outside, 'unresolvedInRoleRows': unresolved,
        'savedCandidateCount': count, 'newlyExhaustiveCandidateRecord': newly_exhaustive,
        'sourceComplete': False, 'physicalIdentityVerified': False, 'carAccessVerified': False,
        'scope': 'Only the frozen supported-role candidate universe; original status/graph unchanged. No physical/global uniqueness, usable-speed or completeness admission.'}


def samples_preserved(match, support):
    position = 0
    weights = []
    for si, (_, _, km) in enumerate(match['sourceSpans']):
        require(position < len(support['samples']), 'Missing source-span samples')
        count = support['samples'][position][2]
        require(type(count) is int and 0 < count <= 100000 and math.isfinite(km) and km > 0, 'Saved sample bounds')
        for i in range(count):
            sample = support['samples'][position]
            require(sample[:3] == [si, i, count] and math.isclose(sample[3], km / count, abs_tol=1e-10), 'Saved weight roster')
            require(sample[3] > 0 and sample[4] == sorted(set(sample[4])), 'Saved membership/weight validity')
            weights.append(sample[3]); position += 1
    require(position == len(support['samples']) and math.isclose(math.fsum(weights), match['sourceKm'], abs_tol=1e-8), 'Complete original source weights')
    return position


def summarize(records):
    scopes = [r['declaredRoleScope'] for r in records]
    outside = [e for s in scopes for e in s['declaredOutOfRoleRows']]
    unresolved = [e for s in scopes for e in s['unresolvedInRoleRows']]
    return {'arcCount': len(records), 'sourceKm': math.fsum(r['sourceKm'] for r in records),
        'samples': sum(r['reportingProvenance']['sampleCount'] for r in records),
        'originalStatusCounts': dict(Counter(r['status'] for r in records)),
        'originalExhaustiveRecords': sum(r['searchExhaustiveForDeclaredRows'] for r in records),
        'originalCandidateChains': sum(len(r['candidates']) for r in records),
        'originalPositiveRecords': sum(r['supportsHypothesis'] for r in records),
        'originalCappedRecords': sum(r['searchCapped'] for r in records),
        'baselineProvisionalEligibleKm': math.fsum(r['baselineProvisionalEligibleKm'] for r in records),
        'roleScopedStatusCounts': dict(Counter(s['status'] for s in scopes)),
        'roleScopedExhaustiveRecords': sum(s['exhaustiveWithinDeclaredRoleScope'] for s in scopes),
        'newlyExhaustiveCandidateRecords': sum(s['newlyExhaustiveCandidateRecord'] for s in scopes),
        'newlyExhaustiveCandidateSourceKm': math.fsum(r['sourceKm'] for r in records if r['declaredRoleScope']['newlyExhaustiveCandidateRecord']),
        'declaredOutOfRoleIncidences': len(outside), 'unresolvedInRoleIncidences': len(unresolved),
        'uniqueOutOfRolePublisherIds': len({e['ordinal'] for e in outside}),
        'uniqueUnresolvedInRolePublisherIds': len({e['ordinal'] for e in unresolved}),
        'outOfRoleReasonIncidences': dict(Counter(reason for e in outside for reason in e['reasons'])),
        'unresolvedInRoleReasonIncidences': dict(Counter(reason for e in unresolved for reason in e['reasons']))}


def analyze(plan, output, paths):
    previous = json.loads(Path(paths['previousReport']).read_text())
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    metadata, identities, roles, limits, scope_counts, levels = [], set(), Counter(), Counter(), Counter(), Counter()
    with Path(paths['segments']).open('rb') as source, Path(paths['rows']).open('rb') as rows, Path(paths['levels']).open('rb') as inventory:
        for ordinal, triple in enumerate(itertools.zip_longest(source, rows, inventory)):
            output.check()
            require(all(v is not None and len(v) <= plan['maxLineBytes'] for v in triple), 'All raw identities/metadata required')
            raw, meta_raw, level_raw = triple
            row, meta, level = (json.loads(v) for v in triple)
            key = row['id'], row['version']
            require(key not in identities and ordinal == meta['ordinal'] == level['ordinal'] and ordinal < plan['expectedRows'], 'Raw identity/ordinal')
            require(key == (meta['id'], meta['version']) == (level['id'], level['version']), 'Identity alignment')
            source_sha = hashlib.sha256(raw).hexdigest()
            require(source_sha == meta['rawLineSha256'] == level['sourceLineSha256'] and hashlib.sha256(meta_raw).hexdigest() == level['metadataLineSha256'], 'Frozen row hashes')
            fields = {k: v for k, v in row.items() if k != 'geometryWkbBase64'}
            require(meta['fieldsSha256'] == hashlib.sha256(canonical(fields)).hexdigest(), 'Raw property binding')
            limit, speed_only = usable_limit(row), usable_limit({**row, 'access_restrictions': None})
            require(meta['frozenLimit'] == level['frozenLimit'] == limit and meta['frozenSpeedOnlyLimit'] == level['frozenSpeedOnlyLimit'] == speed_only, 'Frozen parser unchanged')
            require(meta['rawLevelRules'] == level['rawLevelRules'] == row.get('level_rules') and meta['rawConnectors'] == row.get('connectors'), 'Raw level/connector values')
            require(meta['scopeRulesSha256'] == level['scopeRulesSha256'] == hashlib.sha256(canonical([row.get('speed_limits'), row.get('access_restrictions')])).hexdigest(), 'Raw speed/access scopes')
            require(level['rawConnectorsSha256'] == hashlib.sha256(canonical(row.get('connectors'))).hexdigest(), 'Raw connector hash')
            unsupported = limit['status'] == 'unsupported_road_role'
            record = {'ordinal': ordinal, 'id': key[0], 'version': key[1], 'rawClass': row['class'], 'rawSubtype': row['subtype'],
                'sourceLineSha256': source_sha, 'metadataLineSha256': hashlib.sha256(meta_raw).hexdigest(),
                'levelInventoryLineSha256': hashlib.sha256(level_raw).hexdigest(), 'frozenLimit': limit,
                'frozenSpeedOnlyLimit': speed_only, 'declaredUnsupportedRole': unsupported,
                'scopeRulesSha256': meta['scopeRulesSha256'], 'rawLevelRulesSha256': hashlib.sha256(canonical(row.get('level_rules'))).hexdigest(),
                'rawConnectorsSha256': level['rawConnectorsSha256'], 'originalLevelProfile': level['profile']}
            output.record('rows.jsonl', record)
            identities.add(key); metadata.append(record)
            roles[row['class']] += 1; limits[limit['status']] += 1; levels[level['profile']['category']] += 1
            scope_counts['speedRows'] += row.get('speed_limits') not in (None, [], {})
            scope_counts['accessRows'] += row.get('access_restrictions') not in (None, [], {})
    require(len(metadata) == plan['expectedRows'] and dict(limits) == previous['frozenLimitStatusCounts'] and
            dict(scope_counts) == previous['scopeRowCounts'] and dict(levels) == previous['retainedLevelCategories'], 'All frozen row/scope/level denominators')
    matches, supports = {}, {}
    for name, target in [('matches', matches), ('support', supports)]:
        with Path(paths[name]).open('rb') as stream:
            for raw in stream:
                r = json.loads(raw); key = r['windowId'], r['arc']
                require(key not in target, 'Duplicate saved source/sample record')
                target[key] = (r, hashlib.sha256(raw).hexdigest())
    cached = {w['id']: w['cachedRows'] for w in previous['windows']}
    records = []
    with Path(paths['chains']).open('rb') as chains, Path(paths['exclusions']).open('rb') as exclusions:
        for raw, exclusion_raw in itertools.zip_longest(chains, exclusions):
            output.check(); require(raw is not None and exclusion_raw is not None, 'All original chain/exclusion records')
            chain, excluded = json.loads(raw), json.loads(exclusion_raw); key = chain['windowId'], chain['arc']
            require((excluded['windowId'], excluded['arc']) == key and excluded['chainLineSha256'] == hashlib.sha256(raw).hexdigest(), 'Original chain binding')
            require(chain['sourceStatus'] == 'incomplete_after_capture_stop' and excluded['originalStatus'] == chain['status'] and
                    excluded['candidateCount'] == len(chain['candidates']), 'Frozen outcomes/cache state')
            require('declaredRoleScope' not in chain and 'reportingProvenance' not in chain, 'Reporting refuses overwrite')
            require([(e['ordinal'], e['frozenReasons']) for e in excluded['excluded']] == [(e['ordinal'], e['reasons']) for e in chain['excludedRows']], 'All frozen exclusions retained')
            for e in chain['excludedRows']:
                require(('unsupported_road_role' in e['reasons']) == metadata[e['ordinal']]['declaredUnsupportedRole'], 'Frozen role label agreement')
            match, match_sha = matches.pop(key); support, support_sha = supports.pop(key)
            require(chain['savedSupportLineSha256'] == support_sha and support['savedMatchLineSha256'] == match_sha and
                    match['sourceClassKph'] == chain['sourceClassKph'], 'Original samples/source classes')
            n = samples_preserved(match, support)
            require(n == excluded['sampleCount'] and math.isclose(chain['sourceKm'], match['sourceKm'], abs_tol=1e-8), 'Original source/sample weights')
            result = dict(chain)
            result['declaredRoleScope'] = classify(chain, cached[key[0]])
            result['reportingProvenance'] = {'chainLineSha256': hashlib.sha256(raw).hexdigest(), 'exclusionLineSha256': hashlib.sha256(exclusion_raw).hexdigest(),
                'matchLineSha256': match_sha, 'supportLineSha256': support_sha, 'sampleCount': n, 'cohorts': excluded['cohorts']}
            output.record('role-scope.jsonl', result); records.append(result)
    require(not matches and not supports and len(records) == plan['expectedMatches'] and
            sum(r['reportingProvenance']['sampleCount'] for r in records) == plan['expectedSamples'], 'Full arc/sample roster')
    groups = {name: summarize([r for r in records if name in r['reportingProvenance']['cohorts']]) for name in COHORTS}
    baseline = previous['cohorts']['all']; total = groups['all']
    require(total['originalStatusCounts'] == baseline['originalStatusCounts'] and total['originalCandidateChains'] == baseline['candidateChains'] and
            total['originalPositiveRecords'] == baseline['formerlyAbsentPositiveRecords'] and total['originalCappedRecords'] == baseline['cappedRecords'], 'Original matching outcomes changed')
    summaries = []
    for w in windows:
        subset = [r for r in records if r['windowId'] == w['id']]
        result = {'id': w['id'], 'cachedRows': cached[w['id']], 'sourceStatus': 'incomplete_after_capture_stop',
            'totals': summarize(subset), 'sourceClassesKph': {str(s): summarize([r for r in subset if r['sourceClassKph'] == s]) for s in (85, 105)}}
        summaries.append(result); output.write('windows/' + w['id'] + '.json', json_bytes(result))
    require(len(windows) == plan['expectedWindows'], 'All source windows required')
    report = {'retainedRows': len(metadata), 'rawRoleCounts': roles, 'frozenLimitStatusCounts': limits, 'scopeRowCounts': scope_counts,
        'retainedLevelCategories': levels, 'cohorts': groups, 'windows': summaries,
        'reportingHypothesisSupported': groups['candidate_bearing']['newlyExhaustiveCandidateRecords'] > 0,
        'publisherGeometryKm': previous['publisherGeometryKm'], 'completedSourceWindows': 0, 'originalFeasibilityQualified': False,
        'matcherEnumerationsPerformed': 0, 'networkRequests': 0, 'routingQueries': 0,
        'scope': 'Separate declared-role reporting fields only; all original chain fields/candidates/statuses preserved. All21 source windows incomplete. Scoped exhaustiveness is neither physical/global uniqueness nor access/usable-speed/ETA evidence.'}
    output.write('report.json', json_bytes(report))


def run(plan, output):
    analyze(plan, output, plan['paths'])
    from coarse_chain_uncertainty_audit import audit
    audit(plan, output, plan['paths'])


if __name__ == '__main__':
    from offline_timing_runner import main
    main('docs/evidence/coarse-chain-role-scope-2026-10-26/execution-plan.json')

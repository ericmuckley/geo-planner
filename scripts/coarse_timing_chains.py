"""Bounded endpoint-connected cache matching; no driving-time model."""
import base64
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from analyze_timing_cache import canonical
from coarse_path_features import distance_km
from coarse_timing_input import json_bytes, require, usable_limit
from coarse_timing_parquet import decode_lines, interpolate


def row_metadata(row, scope):
    reasons, endpoints = [], []
    limit = usable_limit(row)
    require(limit == scope['frozenLimit'], 'Frozen parser outcome changed')
    require(usable_limit({**row, 'access_restrictions': None}) == scope['frozenSpeedOnlyLimit'], 'Frozen speed-only inventory changed')
    if limit['status'] == 'unsupported_road_role': reasons.append('unsupported_road_role')
    if row.get('level_rules') not in (None, []): reasons.append('unsupported_level_rules')
    try:
        lines = decode_lines(base64.b64decode(row['geometryWkbBase64'], validate=True))
        if len(lines) != 1:
            reasons.append('multipart_geometry')
        else:
            endpoints = [lines[0][0], lines[0][-1]]
    except (ValueError, RuntimeError):
        reasons.append('malformed_geometry')
    ids = [set(), set()]
    connectors = row.get('connectors')
    if not isinstance(connectors, list):
        reasons.append('missing_or_malformed_connectors')
    else:
        for connector in connectors:
            if not isinstance(connector, dict) or type(connector.get('at')) not in (int, float) or not math.isfinite(connector['at']) or not 0 <= connector['at'] <= 1 or not isinstance(connector.get('connector_id'), str) or not connector['connector_id']:
                reasons.append('malformed_connector')
                continue
            for end in (0, 1):
                if abs(connector['at'] - end) <= 1e-9: ids[end].add(connector['connector_id'])
    for end in (0, 1):
        if not ids[end]: reasons.append('missing_endpoint_identity')
        elif len(ids[end]) > 1: reasons.append('multiple_endpoint_identities')
    endpoint_ids = [next(iter(group)) if len(group) == 1 else None for group in ids]
    if endpoint_ids[0] is not None and endpoint_ids[0] == endpoint_ids[1]: reasons.append('same_endpoint_identity')
    return {'ordinal': scope['ordinal'], 'id': row['id'], 'version': row['version'], 'class': row['class'],
        'rawLineSha256': scope['rawLineSha256'], 'fieldsSha256': scope['fieldsSha256'],
        'frozenLimit': limit, 'frozenSpeedOnlyLimit': scope['frozenSpeedOnlyLimit'],
        'scopeRulesSha256': hashlib.sha256(canonical([row.get('speed_limits'), row.get('access_restrictions')])).hexdigest(),
        'rawConnectors': connectors, 'rawLevelRules': row.get('level_rules'), 'endpoints': endpoints,
        'endpointIds': endpoint_ids, 'baseReasons': sorted(set(reasons)), 'memberships': scope['memberships']}


def sample_points(saved, support):
    points, weights, position = [], [], 0
    for si, (a, b, km) in enumerate(saved['sourceSpans']):
        count = max(1, math.ceil(distance_km(a, b) / .025))
        for i in range(count):
            sample = support['samples'][position]
            require(sample[:3] == [si, i, count] and math.isclose(sample[3], km / count, abs_tol=1e-10), 'Saved sample/weight mismatch')
            points.append(interpolate(a, b, (i + .5) / count))
            weights.append(sample[3])
            position += 1
    require(position == len(support['samples']) and math.isclose(sum(weights), saved['sourceKm'], abs_tol=1e-8), 'Complete original source weights')
    return points, weights


def mask_km(mask, weights):
    return math.fsum(weight for i, weight in enumerate(weights) if mask >> i & 1)


def progress(point, indices, points):
    distances = [(distance_km(point, points[i]), i) for i in indices]
    nearest = min(d for d, _ in distances)
    tied = [i for d, i in distances if abs(d - nearest) <= 1e-9]
    return [min(tied), max(tied)], nearest


def make_nodes(metadata, samples, points, box):
    aligned = defaultdict(list)
    for i, sample in enumerate(samples):
        for ordinal in sample[4]: aligned[ordinal].append(i)
    nodes, excluded = {}, []
    for ordinal, indices in sorted(aligned.items()):
        row = metadata[ordinal]
        reasons = list(row['baseReasons'])
        if row['endpoints'] and any(not (box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]) for p in row['endpoints']):
            reasons.append('outside_window_endpoint')
        if not reasons:
            first, d0 = progress(row['endpoints'][0], indices, points)
            last, d1 = progress(row['endpoints'][1], indices, points)
            if max(d0, d1) > .025:
                reasons.append('endpoint_not_near_own_samples')
            elif first[1] < last[0]:
                direction = 0
            elif last[1] < first[0]:
                direction = 1
            else:
                reasons.append('nonprogressing_or_tied_endpoints')
            if not reasons:
                entry, exit_ = (first, last) if direction == 0 else (last, first)
                nodes[ordinal] = {'ordinal': ordinal, 'direction': direction, 'entryId': row['endpointIds'][direction],
                    'exitId': row['endpointIds'][1 - direction], 'entryPoint': row['endpoints'][direction],
                    'exitPoint': row['endpoints'][1 - direction], 'entryProgress': entry, 'exitProgress': exit_,
                    'sampleMin': min(indices), 'sampleMax': max(indices),
                    'maskHex': hex(sum(1 << i for i in indices))}
        if reasons: excluded.append({'ordinal': ordinal, 'reasons': sorted(set(reasons))})
    return nodes, excluded


def can_join(a, b):
    return (a['exitId'] == b['entryId'] and distance_km(a['exitPoint'], b['entryPoint']) <= .025
        and b['sampleMin'] >= a['sampleMin'] and b['sampleMax'] > a['sampleMax']
        and b['entryProgress'][0] >= a['entryProgress'][0] and b['exitProgress'][0] > a['exitProgress'][0])


def adjacency(nodes):
    entering = defaultdict(list)
    for ordinal, node in sorted(nodes.items()): entering[node['entryId']].append(ordinal)
    return {ordinal: [other for other in entering[node['exitId']] if other != ordinal and can_join(node, nodes[other])]
            for ordinal, node in sorted(nodes.items())}


def search_chains(nodes, weights, maximum_rows=64, maximum_states=4096, check=lambda: None):
    links, candidates, caps = adjacency(nodes), {}, set()
    states, total = 0, sum(weights)
    require(total > 0 and all(math.isfinite(w) and w > 0 for w in weights) and maximum_rows > 0 and maximum_states > 0, 'Invalid chain weight/resource bounds')
    masks = {i: int(n['maskHex'], 16) for i, n in nodes.items()}
    def qualifies(mask):
        return mask_km(mask, weights) / total >= .8 - 1e-12
    def union(path):
        mask = 0
        for i in path: mask |= masks[i]
        return mask
    def visit(path, mask):
        nonlocal states
        check()
        if states >= maximum_states:
            caps.add('expanded_states')
            return
        states += 1
        if qualifies(mask):
            if len(path) == 1 or not qualifies(union(path[1:])) and not qualifies(union(path[:-1])):
                key = min(path, tuple(reversed(path)))
                candidates.setdefault(key, {'rowOrdinals': list(path), 'canonicalUndirectedRows': list(key),
                    'coveredSampleMaskHex': hex(mask), 'supportedKm': mask_km(mask, weights),
                    'fraction': min(1., mask_km(mask, weights) / total)})
            return
        following = [i for i in links[path[-1]] if i not in path]
        if len(path) >= maximum_rows and following:
            caps.add('chain_length')
            return
        for i in following:
            visit(path + (i,), mask | masks[i])
            if 'expanded_states' in caps: return
    for seed in sorted(nodes):
        visit((seed,), masks[seed])
        if 'expanded_states' in caps: break
    return {'candidates': [candidates[k] for k in sorted(candidates)], 'expandedStates': states,
            'capReasons': sorted(caps), 'searchCapped': bool(caps)}


def outcome(search, excluded, cached_rows):
    if not cached_rows: return 'unmeasured_empty_cache'
    if search['searchCapped']: return 'search_capped'
    if excluded: return 'unresolved_with_candidates' if search['candidates'] else 'unresolved_without_candidates'
    if not search['candidates']: return 'no_cached_chain'
    return 'single_cached_chain' if len(search['candidates']) == 1 else 'multiple_cached_chains'


def summary(records):
    return {'arcCount': len(records), 'sourceKm': math.fsum(r['sourceKm'] for r in records),
        'statusCounts': dict(Counter(r['status'] for r in records)),
        'statusSourceKm': {s: math.fsum(r['sourceKm'] for r in records if r['status'] == s) for s in sorted({r['status'] for r in records})},
        'recordsWithCandidates': sum(bool(r['candidates']) for r in records),
        'candidateChains': sum(len(r['candidates']) for r in records),
        'cappedRecords': sum(r['searchCapped'] for r in records),
        'formerlyAbsentUncappedWithChain': sum(r['supportsHypothesis'] for r in records),
        'formerlyAbsentUncappedSourceKm': math.fsum(r['sourceKm'] for r in records if r['supportsHypothesis']),
        'baselineProvisionalEligibleKm': math.fsum(r['baselineProvisionalEligibleKm'] for r in records)}


def analyze(plan, output, paths):
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    prior = json.loads(Path(paths['compatibilityReport']).read_text())
    metadata, identities, limits, counts = [], set(), Counter(), Counter()
    with Path(paths['segments']).open('rb') as raw_stream, Path(paths['scopes']).open('rb') as scope_stream:
        for ordinal, (raw, encoded) in enumerate(itertools.zip_longest(raw_stream, scope_stream)):
            output.check()
            require(raw is not None and encoded is not None and max(len(raw), len(encoded)) <= plan['maxLineBytes'], 'All retained rows/scopes required')
            row, scope = json.loads(raw), json.loads(encoded)
            key = row['id'], row['version']
            require(key not in identities and ordinal == scope['ordinal'] and ordinal < plan['expectedRows'], 'Retained identity/ordinal')
            require(key == (scope['id'], scope['version']) and hashlib.sha256(raw).hexdigest() == scope['rawLineSha256'], 'Raw row binding')
            require(row.get('speed_limits') == scope['rawSpeedLimits'] and row.get('access_restrictions') == scope['rawAccessRestrictions'], 'Raw scopes changed')
            identities.add(key)
            record = row_metadata(row, scope)
            output.record('rows.jsonl', record)
            metadata.append(record)
            limits.update([record['frozenLimit']['status']])
            counts['speedRows'] += row.get('speed_limits') not in (None, [], {})
            counts['accessRows'] += row.get('access_restrictions') not in (None, [], {})
    require(len(metadata) == plan['expectedRows'] and dict(limits) == prior['frozenLimitStatusCounts'], 'Full row/classification denominators')
    require(counts['speedRows'] == prior['scopeCounts']['speed']['presentRows'] and counts['accessRows'] == prior['scopeCounts']['access']['presentRows'], 'Frozen scope denominators')
    matches = {}
    with Path(paths['matches']).open('rb') as stream:
        for raw in stream:
            r = json.loads(raw); key = r['windowId'], r['arc']
            require(key not in matches, 'Duplicate saved match')
            matches[key] = (r, hashlib.sha256(raw).hexdigest())
    support_by_window = defaultdict(list)
    with Path(paths['support']).open('rb') as stream:
        for raw in stream:
            r = json.loads(raw); r['_hash'] = hashlib.sha256(raw).hexdigest(); support_by_window[r['windowId']].append(r)
    all_records, summaries, sample_count = [], [], 0
    cached = {w['id']: w['cachedRows'] for w in prior['windows']}
    for window in windows:
        wid, records = window['id'], []
        for support in support_by_window[wid]:
            output.check()
            key = wid, support['arc']; saved, line_sha = matches.pop(key)
            require(support['savedMatchLineSha256'] == line_sha, 'Saved match/support binding')
            points, weights = sample_points(saved, support)
            sample_count += len(points)
            nodes, excluded = make_nodes(metadata, support['samples'], points, window['bbox'])
            searched = search_chains(nodes, weights, plan['maximumRowsPerChain'], plan['maximumExpandedStatesPerArc'], output.check)
            for candidate in searched['candidates']:
                candidate['memberParserStatuses'] = [metadata[i]['frozenLimit']['status'] for i in candidate['rowOrdinals']]
                candidate['allMembersParserUsable'] = all(s == 'usable' for s in candidate['memberParserStatuses'])
            record = {'windowId': wid, 'arc': saved['arc'], 'sourceClassKph': saved['sourceClassKph'],
                'sourceKm': saved['sourceKm'], 'savedSupportLineSha256': support['_hash'], 'oldStatus': saved['status'],
                'baselineProvisionalEligibleKm': saved['provisionalStaticLimitMatchedKm'],
                'sourceStatus': 'incomplete_after_capture_stop', 'nodes': list(nodes.values()), 'excludedRows': excluded, **searched}
            record['status'] = outcome(searched, excluded, cached[wid])
            record['searchExhaustiveForDeclaredRows'] = bool(cached[wid] and not searched['searchCapped'] and not excluded)
            record['supportsHypothesis'] = bool(saved['status'] == 'absent_in_cache' and not searched['searchCapped'] and searched['candidates'])
            if record['supportsHypothesis']:
                require(all(len(c['rowOrdinals']) > 1 for c in searched['candidates']), 'Formerly absent arc cannot gain a single-row candidate')
            output.record('chains.jsonl', record)
            records.append(record); all_records.append(record)
        result = {'id': wid, 'cachedRows': cached[wid], 'sourceStatus': 'incomplete_after_capture_stop',
            'totals': summary(records), 'sourceClassesKph': {str(s): summary([r for r in records if r['sourceClassKph'] == s]) for s in (85, 105)}}
        output.write('windows/' + wid + '.json', json_bytes(result)); summaries.append(result)
        print(json.dumps({'window': wid, 'status': 'source_incomplete', 'chains': result['totals']['candidateChains']}), flush=True)
    require(not matches and len(all_records) == plan['expectedMatches'] and len(windows) == plan['expectedWindows'] and sample_count == plan['expectedSamples'], 'Full source/sample/window denominators')
    report = {'retainedRows': len(metadata), 'samples': sample_count, 'windows': summaries, 'allWindows': summary(all_records),
        'windowsWithCache': summary([r for r in all_records if cached[r['windowId']]]),
        'scopeRowCounts': counts, 'frozenLimitStatusCounts': limits, 'completedSourceWindows': 0,
        'hypothesisSupported': any(r['supportsHypothesis'] for r in all_records), 'originalFeasibilityQualified': False,
        'networkRequests': 0, 'routingQueries': 0, 'publisherGeometryKm': prior['publisherGeometryKm'],
        'scope': 'Endpoint-connected cached matching constraints only, not drivable connectivity, physical/global uniqueness, usable speed coverage or an ETA model. Unknown competitors and every original scope remain; all21 source windows incomplete. No Natural Earth/base alignment.'}
    output.write('report.json', json_bytes(report))


def run(plan, output):
    analyze(plan, output, plan['paths'])
    from coarse_timing_chains_audit import audit
    audit(plan, output, plan['paths'])


if __name__ == '__main__':
    from offline_timing_runner import main
    main('docs/evidence/coarse-timing-chains-2026-10-26/execution-plan.json')

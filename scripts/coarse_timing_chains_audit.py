"""Independent bounded chain enumeration and raw/source accounting."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from coarse_path_features import distance_km
from coarse_timing_input import json_bytes, require, usable_limit
from coarse_timing_compatibility_audit import close


def reference_nodes(metadata, samples, points, box):
    membership = defaultdict(list)
    for i, sample in enumerate(samples):
        for row in sample[4]: membership[row].append(i)
    nodes, excluded = {}, []
    for ordinal in sorted(membership):
        raw = metadata[ordinal]; indices = membership[ordinal]
        reasons = list(raw['baseReasons'])
        if raw['endpoints'] and not all(box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3] for p in raw['endpoints']):
            reasons.append('outside_window_endpoint')
        if not reasons:
            bounds, distances = [], []
            for p in raw['endpoints']:
                by_index = {i: distance_km(p, points[i]) for i in indices}
                best = min(by_index.values()); tied = [i for i, d in by_index.items() if abs(d - best) <= 1e-9]
                bounds.append([min(tied), max(tied)]); distances.append(best)
            if max(distances) > .025: reasons.append('endpoint_not_near_own_samples')
            elif bounds[0][1] < bounds[1][0]: direction = 0
            elif bounds[1][1] < bounds[0][0]: direction = 1
            else: reasons.append('nonprogressing_or_tied_endpoints')
            if not reasons:
                nodes[ordinal] = {'ordinal': ordinal, 'direction': direction,
                    'entryId': raw['endpointIds'][direction], 'exitId': raw['endpointIds'][1 - direction],
                    'entryPoint': raw['endpoints'][direction], 'exitPoint': raw['endpoints'][1 - direction],
                    'entryProgress': bounds[direction], 'exitProgress': bounds[1 - direction],
                    'sampleMin': min(indices), 'sampleMax': max(indices), 'maskHex': hex(sum(2 ** i for i in indices))}
        if reasons: excluded.append({'ordinal': ordinal, 'reasons': sorted(set(reasons))})
    return nodes, excluded


def reference_search(nodes, weights, maximum_rows, maximum_states, check=lambda: None):
    links = {}
    for i, a in sorted(nodes.items()):
        links[i] = []
        for j, b in sorted(nodes.items()):
            if i == j or a['exitId'] != b['entryId']: continue
            if distance_km(a['exitPoint'], b['entryPoint']) > .025: continue
            if b['sampleMin'] < a['sampleMin'] or b['sampleMax'] <= a['sampleMax']: continue
            if b['entryProgress'][0] < a['entryProgress'][0] or b['exitProgress'][0] <= a['exitProgress'][0]: continue
            links[i].append(j)
    def coverage(path):
        mask = 0
        for i in path: mask |= int(nodes[i]['maskHex'], 16)
        km = math.fsum(w for bit, w in enumerate(weights) if mask & 2 ** bit)
        return mask, km
    def following(path):
        return (path + (i,) for i in links[path[-1]] if i not in path)
    pending = [iter((i,) for i in sorted(nodes))]
    candidates, caps, states = {}, set(), 0
    total = sum(weights)
    while pending:
        check()
        try: path = next(pending[-1])
        except StopIteration:
            pending.pop()
            continue
        if states == maximum_states:
            caps.add('expanded_states')
            break
        states += 1
        mask, km = coverage(path)
        if km / total >= .8 - 1e-12:
            minimal = not any(coverage(path[a:b])[1] / total >= .8 - 1e-12
                for a in range(len(path)) for b in range(a + 1, len(path) + 1) if b - a < len(path))
            if minimal:
                key = min(path, tuple(reversed(path)))
                candidates.setdefault(key, {'rowOrdinals': list(path), 'canonicalUndirectedRows': list(key),
                    'coveredSampleMaskHex': hex(mask), 'supportedKm': km, 'fraction': min(1., km / total)})
        elif len(path) >= maximum_rows:
            if any(i not in path for i in links[path[-1]]): caps.add('chain_length')
        else:
            pending.append(following(path))
    return {'candidates': [candidates[k] for k in sorted(candidates)], 'expandedStates': states,
            'capReasons': sorted(caps), 'searchCapped': bool(caps)}


def reference_summary(records):
    statuses = Counter(r['status'] for r in records)
    positive = [r for r in records if r['supportsHypothesis']]
    return {'arcCount': len(records), 'sourceKm': math.fsum(r['sourceKm'] for r in records),
        'statusCounts': dict(statuses), 'statusSourceKm': {s: math.fsum(r['sourceKm'] for r in records if r['status'] == s) for s in sorted(statuses)},
        'recordsWithCandidates': len([r for r in records if r['candidates']]),
        'candidateChains': sum(len(r['candidates']) for r in records), 'cappedRecords': sum(bool(r['capReasons']) for r in records),
        'formerlyAbsentUncappedWithChain': len(positive), 'formerlyAbsentUncappedSourceKm': math.fsum(r['sourceKm'] for r in positive),
        'baselineProvisionalEligibleKm': math.fsum(r['baselineProvisionalEligibleKm'] for r in records)}


def audit(plan, output, paths):
    from coarse_timing_chains import row_metadata, sample_points
    report = json.loads((output.root / 'report.json').read_text())
    prior = json.loads(Path(paths['compatibilityReport']).read_text())
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    metadata, identities, limits, counts = [], set(), Counter(), Counter()
    with Path(paths['segments']).open('rb') as raw_stream, Path(paths['scopes']).open('rb') as scopes, (output.root / 'rows.jsonl').open('rb') as ledger:
        for ordinal, triple in enumerate(itertools.zip_longest(raw_stream, scopes, ledger)):
            output.check()
            raw, scope_raw, encoded = triple
            require(all(v is not None for v in triple), 'Independent retained row roster')
            row, scope, record = json.loads(raw), json.loads(scope_raw), json.loads(encoded)
            key = row['id'], row['version']
            require(key not in identities and (record['id'], record['version']) == key and record['ordinal'] == ordinal, 'Independent retained identities')
            require(record['rawLineSha256'] == hashlib.sha256(raw).hexdigest() == scope['rawLineSha256'], 'Raw retained checksum')
            fields = {k: v for k, v in row.items() if k != 'geometryWkbBase64'}
            require(record['fieldsSha256'] == hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest(), 'Raw field checksum')
            require(record == row_metadata(row, scope), 'Tested raw endpoint/metadata filter changed')
            require(record['frozenLimit'] == usable_limit(row) and record['frozenSpeedOnlyLimit'] == usable_limit({**row, 'access_restrictions': None}), 'Frozen parser values')
            identities.add(key); metadata.append(record)
            limits.update([record['frozenLimit']['status']])
            counts['speedRows'] += row.get('speed_limits') not in (None, [], {})
            counts['accessRows'] += row.get('access_restrictions') not in (None, [], {})
    require(len(metadata) == plan['expectedRows'] == report['retainedRows'], 'Full retained denominator')
    close(report['scopeRowCounts'], counts); close(report['frozenLimitStatusCounts'], limits)
    saved = {}
    with Path(paths['matches']).open('rb') as stream:
        for raw in stream:
            m = json.loads(raw); saved[m['windowId'], m['arc']] = (m, hashlib.sha256(raw).hexdigest())
    supports = defaultdict(list)
    with Path(paths['support']).open('rb') as stream:
        for raw in stream:
            s = json.loads(raw); s['_hash'] = hashlib.sha256(raw).hexdigest(); supports[s['windowId']].append(s)
    cached = {w['id']: w['cachedRows'] for w in prior['windows']}
    records, all_records, samples = defaultdict(list), [], 0
    with (output.root / 'chains.jsonl').open() as stream:
        for window in windows:
            wid = window['id']
            for support in supports[wid]:
                output.check()
                r = json.loads(next(stream)); old, line_sha = saved.pop((wid, support['arc']))
                require((r['windowId'], r['arc']) == (wid, old['arc']) and r['savedSupportLineSha256'] == support['_hash'] and support['savedMatchLineSha256'] == line_sha, 'All saved source/support records')
                require(r['oldStatus'] == old['status'] and r['sourceClassKph'] == old['sourceClassKph'], 'Frozen source classifications')
                close(r['sourceKm'], old['sourceKm']); close(r['baselineProvisionalEligibleKm'], old['provisionalStaticLimitMatchedKm'])
                points, weights = sample_points(old, support); samples += len(points)
                nodes, excluded = reference_nodes(metadata, support['samples'], points, window['bbox'])
                close(r['nodes'], list(nodes.values())); close(r['excludedRows'], excluded)
                expected = reference_search(nodes, weights, plan['maximumRowsPerChain'], plan['maximumExpandedStatesPerArc'], output.check)
                for c in expected['candidates']:
                    c['memberParserStatuses'] = [metadata[i]['frozenLimit']['status'] for i in c['rowOrdinals']]
                    c['allMembersParserUsable'] = all(s == 'usable' for s in c['memberParserStatuses'])
                for key in expected: close(r[key], expected[key])
                if not cached[wid]: status = 'unmeasured_empty_cache'
                elif expected['searchCapped']: status = 'search_capped'
                elif excluded: status = 'unresolved_with_candidates' if expected['candidates'] else 'unresolved_without_candidates'
                else: status = 'no_cached_chain' if not expected['candidates'] else 'single_cached_chain' if len(expected['candidates']) == 1 else 'multiple_cached_chains'
                require(r['status'] == status and r['sourceStatus'] == 'incomplete_after_capture_stop', 'Honest ambiguity/cache outcomes')
                require(r['searchExhaustiveForDeclaredRows'] == bool(cached[wid] and not excluded and not expected['searchCapped']), 'Incomplete search cannot claim exhaustive result')
                require(r['supportsHypothesis'] == bool(old['status'] == 'absent_in_cache' and not expected['searchCapped'] and expected['candidates']), 'Fixed hypothesis decision')
                records[wid].append(r); all_records.append(r)
        require(not stream.read().strip() and not saved, 'Extra/missing source records')
    require(len(all_records) == plan['expectedMatches'] and samples == plan['expectedSamples'] == report['samples'], 'Complete arc/sample denominators')
    close(report['allWindows'], reference_summary(all_records))
    close(report['windowsWithCache'], reference_summary([r for r in all_records if cached[r['windowId']]]))
    require(report['hypothesisSupported'] == any(r['supportsHypothesis'] for r in all_records), 'Fixed aggregate hypothesis decision')
    require(len(report['windows']) == len(windows) == plan['expectedWindows'], 'All windows retained')
    for w in report['windows']:
        wid = w['id']
        require(w['sourceStatus'] == 'incomplete_after_capture_stop' and w['cachedRows'] == cached[wid], 'Source cache remains incomplete')
        close(w['totals'], reference_summary(records[wid]))
        for speed, group in w['sourceClassesKph'].items(): close(group, reference_summary([r for r in records[wid] if r['sourceClassKph'] == int(speed)]))
        require(w == json.loads((output.root / 'windows' / (wid + '.json')).read_text()), 'Window/report mismatch')
    require(report['publisherGeometryKm'] == prior['publisherGeometryKm'], 'Separate publisher/Census denominators')
    require(report['completedSourceWindows'] == report['networkRequests'] == report['routingQueries'] == 0 and not report['originalFeasibilityQualified'], 'No coverage or timing admission')
    output.write('audit.json', json_bytes({'independentBoundedEnumerationJoinsProgressWeightsAmbiguityCapsAndScopeAccounting': True,
        'retainedRows': len(metadata), 'sourceArcWindowRecords': len(all_records), 'samples': samples,
        'plannedWindows': len(windows), 'completedSourceWindows': 0, 'hypothesisSupported': report['hypothesisSupported'],
        'method': 'Separate all-pairs adjacency, progress reconstruction and iterative bounded enumeration with every proper contiguous subchain checked for minimality. Shared sealed numeric/geometry/parser primitives, tested raw metadata filter and source-sample restoration. No physical driving access, identity, completeness or ETA proof.'}))

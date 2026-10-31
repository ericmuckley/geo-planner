"""Independent fragment geometry, provenance, enumeration and control audit."""
import base64
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from analyze_timing_cache import canonical
from coarse_timing_chains import row_metadata, sample_points
from coarse_timing_compatibility_audit import great_circle
from coarse_timing_input import PilotError, json_bytes, require
from coarse_timing_parquet import angle_degrees, decode_lines


def equivalent(actual, expected):
    if isinstance(expected, dict):
        require(actual.keys() == expected.keys(), 'Fragment audit dictionary roster')
        for k in expected: equivalent(actual[k], expected[k])
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), 'Fragment audit list roster')
        for a, b in zip(actual, expected): equivalent(a, b)
    elif type(expected) is float:
        require(type(actual) in (int, float) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), 'Fragment audit numeric value')
    else:
        require(type(actual) is type(expected) and actual == expected, 'Fragment audit exact value')


def reference_fragments(metadata, lines, samples, points, tangents, box, old_nodes, check=lambda: None):
    membership = defaultdict(list)
    for i, s in enumerate(samples):
        for ordinal in s[4]: membership[ordinal].append(i)
    old = {n['ordinal']: n for n in old_nodes}
    nodes, issues, projections = {}, [], []
    for ordinal in sorted(membership):
        check()
        meta, indices, line = metadata[ordinal], membership[ordinal], lines[ordinal]
        if ordinal in old:
            full = old[ordinal]; key = f'{ordinal}/full'
            nodes[key] = dict(full, variantKey=key, mode='full', entryFraction=float(full['direction']),
                exitFraction=float(1 - full['direction']), fractionBasis='normalized_haversine_polyline_length')
        if meta['baseReasons']:
            issues.append({'ordinal': ordinal, 'reasons': meta['baseReasons']}); continue
        lengths = [great_circle(a, b) for a, b in zip(line, line[1:])]
        cumulative = list(itertools.accumulate(lengths, initial=0.))
        total = cumulative[-1]
        def locate(fraction):
            position = fraction * total
            for i, length in enumerate(lengths):
                if length and position <= cumulative[i] + length:
                    t = (position - cumulative[i]) / length
                    return [line[i][j] * (1 - t) + line[i + 1][j] * t for j in (0, 1)]
            return list(line[-1])
        try:
            require(total > 0, 'degenerate_geometry')
            require(len(indices) >= 2, 'insufficient_projection_progress')
            projected = []
            for sample_index in indices:
                p = points[sample_index]; scale = math.cos(math.radians(p[1])); options = []
                for i, length in enumerate(lengths):
                    if not length: continue
                    a, b = line[i:i + 2]
                    v = ((b[0] - a[0]) * scale, b[1] - a[1]); w = ((p[0] - a[0]) * scale, p[1] - a[1])
                    t = min(1., max(0., sum(x * y for x, y in zip(v, w)) / sum(x * x for x in v)))
                    q = [a[j] + t * (b[j] - a[j]) for j in (0, 1)]
                    options.append({'distanceKm': great_circle(p, q), 'along': cumulative[i] + length * t, 'point': q, 'piece': i})
                minimum = min(o['distanceKm'] for o in options)
                ties = [o for o in options if o['distanceKm'] <= minimum + 1e-9]
                require(minimum <= .025, 'projection_outside_distance')
                require(max(o['along'] for o in ties) - min(o['along'] for o in ties) <= 1e-9, 'ambiguous_projection')
                require(all(angle_degrees(*tangents[sample_index], line[o['piece']], line[o['piece'] + 1]) <= 15 for o in ties), 'projection_tangent_mismatch')
                chosen = sorted(ties, key=lambda o: (o['along'], o['piece']))[0]
                projected.append({'fraction': chosen['along'] / total, 'point': chosen['point'], 'distanceKm': minimum})
            fractions = [p['fraction'] for p in projected]
            steps = [(b - a) * total for a, b in zip(fractions, fractions[1:])]
            tied_interior = any(abs(d) <= 1e-9 and not (max(a, b) * total <= 1e-9 or (1 - min(a, b)) * total <= 1e-9)
                for a, b, d in zip(fractions, fractions[1:], steps))
            require(abs(fractions[-1] - fractions[0]) * total > 1e-9 and not tied_interior and
                (min(steps) >= -1e-9 or max(steps) <= 1e-9), 'nonmonotone_or_tied_projection')
            direction = int(fractions[-1] < fractions[0])
            projections.append({'ordinal': ordinal, 'sampleIndices': indices, 'projections': projected})
        except PilotError as error:
            issues.append({'ordinal': ordinal, 'reasons': [str(error)]}); continue
        def endpoint_progress(which):
            distances = {i: great_circle(meta['endpoints'][which], points[i]) for i in indices}
            best = min(distances.values()); ties = [i for i, d in distances.items() if abs(d - best) <= 1e-9]
            return [min(ties), max(ties)], best
        variant_issues = []
        for mode, start_cut, end_cut in [('start', True, False), ('end', False, True), ('both', True, True)]:
            if start_cut and min(fractions[0], 1 - fractions[0]) * total <= 1e-9: continue
            if end_cut and min(fractions[-1], 1 - fractions[-1]) * total <= 1e-9: continue
            start = fractions[0] if start_cut else float(direction)
            end = fractions[-1] if end_cut else float(1 - direction)
            entry, d0 = ([indices[0]] * 2, 0.) if start_cut else endpoint_progress(direction)
            exit_, d1 = ([indices[-1]] * 2, 0.) if end_cut else endpoint_progress(1 - direction)
            q = [locate(start), locate(end)]
            q += [line[i] for i, at in enumerate(cumulative) if min(start, end) * total < at < max(start, end) * total]
            reasons = []
            if any(not (box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]) for p in q): reasons.append('outside_window_fragment')
            if d0 > .025: reasons.append('uncut_entry_not_near_samples')
            if d1 > .025: reasons.append('uncut_exit_not_near_samples')
            if entry[1] >= exit_[0]: reasons.append('nonprogressing_fragment_endpoints')
            kept = [i for i, f in zip(indices, fractions) if min(start, end) - 1e-9 / total <= f <= max(start, end) + 1e-9 / total]
            if not kept: reasons.append('empty_fragment_support')
            if reasons:
                variant_issues.append({'mode': mode, 'reasons': reasons}); continue
            key = f'{ordinal}/{mode}'
            nodes[key] = {'ordinal': ordinal, 'variantKey': key, 'mode': mode, 'direction': direction,
                'entryId': None if start_cut else meta['endpointIds'][direction],
                'exitId': None if end_cut else meta['endpointIds'][1 - direction],
                'entryPoint': locate(start), 'exitPoint': locate(end), 'entryFraction': start, 'exitFraction': end,
                'fractionBasis': 'normalized_haversine_polyline_length', 'entryProgress': entry, 'exitProgress': exit_,
                'sampleMin': min(kept), 'sampleMax': max(kept), 'maskHex': hex(sum(2 ** i for i in kept))}
        if variant_issues: issues.append({'ordinal': ordinal, 'variantExclusions': variant_issues})
    return nodes, issues, projections


def reference_search(nodes, weights, maximum_rows, maximum_states, check=lambda: None):
    links = {}
    for k, a in nodes.items():
        links[k] = []
        for j, b in nodes.items():
            if a['ordinal'] == b['ordinal'] or a['exitId'] is None or b['entryId'] is None or a['exitId'] != b['entryId']: continue
            if great_circle(a['exitPoint'], b['entryPoint']) > .025: continue
            if b['sampleMin'] < a['sampleMin'] or b['sampleMax'] <= a['sampleMax']: continue
            if b['entryProgress'][0] < a['entryProgress'][0] or b['exitProgress'][0] <= a['exitProgress'][0]: continue
            links[k].append(j)
        links[k].sort(key=lambda j: (nodes[j]['ordinal'], nodes[j]['mode']))
    total = math.fsum(weights)
    def coverage(path):
        indices = {i for k in path for i in range(len(weights)) if int(nodes[k]['maskHex'], 16) & 2 ** i}
        return sum(2 ** i for i in indices), math.fsum(weights[i] for i in sorted(indices))
    stack = [iter((k,) for k in sorted(nodes, key=lambda k: (nodes[k]['ordinal'], nodes[k]['mode'])))]
    candidates, caps, states = {}, set(), 0
    while stack:
        check()
        try: path = next(stack[-1])
        except StopIteration:
            stack.pop(); continue
        if states == maximum_states:
            caps.add('expanded_states'); break
        states += 1
        mask, km = coverage(path)
        if km / total >= .8 - 1e-12:
            minimal = all(coverage(path[a:b])[1] / total < .8 - 1e-12 for a in range(len(path))
                for b in range(a + 1, len(path) + 1) if b - a < len(path))
            if minimal:
                candidates[min(path, path[::-1])] = {'variantKeys': list(path), 'rowOrdinals': [nodes[k]['ordinal'] for k in path],
                    'coveredSampleMaskHex': hex(mask), 'supportedKm': km, 'fraction': min(1., km / total),
                    'hasTerminalCut': any(nodes[k]['mode'] != 'full' for k in path)}
            continue
        used = {nodes[k]['ordinal'] for k in path}
        following = [path + (k,) for k in links[path[-1]] if nodes[k]['ordinal'] not in used]
        if len(path) == maximum_rows:
            if following: caps.add('chain_length')
        else: stack.append(iter(following))
    return {'candidates': [candidates[k] for k in sorted(candidates)], 'expandedStates': states, 'capReasons': sorted(caps), 'searchCapped': bool(caps)}


def reference_summary(records):
    original = [r['original'] for r in records]
    positive = [r for r in records if r['supportsHypothesis']]
    return {'arcCount': len(records), 'samples': sum(r['sampleCount'] for r in records),
        'sourceKm': math.fsum(r['sourceKm'] for r in original), 'statusCounts': dict(Counter(r['status'] for r in records)),
        'recordsWithCandidates': len([r for r in records if r['candidates']]), 'fragmentCandidates': sum(len(r['candidates']) for r in records),
        'cappedRecords': len([r for r in records if r['searchCapped']]), 'originalCandidates': sum(len(r['candidates']) for r in original),
        'originalCandidateBearingRecords': len([r for r in original if r['candidates']]), 'newUncappedClippedRecords': len(positive),
        'newUncappedClippedSourceKm': math.fsum(r['original']['sourceKm'] for r in positive),
        'baselineProvisionalEligibleKm': math.fsum(r['baselineProvisionalEligibleKm'] for r in original)}


def audit(plan, output, paths):
    metadata, lines, limits = [], [], Counter()
    with Path(paths['segments']).open('rb') as source, Path(paths['scopes']).open('rb') as scopes, (output.root / 'rows.jsonl').open('rb') as ledger:
        for ordinal, triple in enumerate(itertools.zip_longest(source, scopes, ledger)):
            output.check(); require(all(p is not None for p in triple), 'Audit retained row roster')
            raw, encoded, produced = triple; row, scope, meta = map(json.loads, triple)
            require(scope['ordinal'] == ordinal and meta == row_metadata(row, scope), 'Audit sealed metadata/ordinal')
            require(hashlib.sha256(raw).hexdigest() == meta['rawLineSha256'], 'Audit raw row hash')
            require(hashlib.sha256(canonical({k: v for k, v in row.items() if k != 'geometryWkbBase64'})).hexdigest() == meta['fieldsSha256'], 'Audit raw field hashes')
            require(row.get('speed_limits') == scope['rawSpeedLimits'] and row.get('access_restrictions') == scope['rawAccessRestrictions'], 'Audit raw scopes')
            try: decoded = decode_lines(base64.b64decode(row['geometryWkbBase64'], validate=True))
            except (ValueError, RuntimeError): decoded = []
            metadata.append(meta); lines.append(decoded[0] if len(decoded) == 1 else []); limits.update([meta['frozenLimit']['status']])
    def records(path):
        with Path(path).open('rb') as stream:
            result = {}
            for raw in stream:
                r = json.loads(raw); key = r['windowId'], r['arc']; require(key not in result, 'Audit duplicate arc')
                result[key] = (r, hashlib.sha256(raw).hexdigest())
            return result
    source, support, controls = (records(paths[k]) for k in ('matches', 'support', 'chains'))
    current = records(output.root / 'fragments.jsonl')
    require(set(current) == set(source) == set(support) == set(controls), 'Audit full source/control roster')
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    cached = {w['id']: w['cachedRows'] for w in json.loads(Path(paths['previousReport']).read_text())['windows']}
    boxes = {w['id']: w['bbox'] for w in windows}
    for key, (record, _) in current.items():
        output.check(); saved, match_sha = source[key]; raw_support, support_sha = support[key]; old, old_sha = controls[key]
        require(record['original'] == old and record['originalLineSha256'] == old_sha, 'Audit every original field/candidate unchanged')
        require(raw_support['savedMatchLineSha256'] == match_sha and old['savedSupportLineSha256'] == support_sha, 'Audit original support bindings')
        points, weights = sample_points(saved, raw_support)
        tangents = [saved['sourceSpans'][s[0]][:2] for s in raw_support['samples']]
        nodes, issues, projections = reference_fragments(metadata, lines, raw_support['samples'], points, tangents, boxes[key[0]], old['nodes'], output.check)
        equivalent(record['nodes'], list(nodes.values())); equivalent(record['fragmentIssues'], issues); equivalent(record['projections'], projections)
        expected = reference_search(nodes, weights, plan['maximumRowsPerChain'], plan['maximumExpandedStatesPerArc'], output.check)
        for c in expected['candidates']:
            c['memberParserStatuses'] = [metadata[i]['frozenLimit']['status'] for i in c['rowOrdinals']]
            c['allMembersParserUsable'] = all(s == 'usable' for s in c['memberParserStatuses'])
        equivalent({k: record[k] for k in expected}, expected)
        require(record['sampleCount'] == len(weights), 'Audit sample denominator')
        status = 'unmeasured_empty_cache' if not cached[key[0]] else 'search_capped' if expected['searchCapped'] else 'cached_geometry_candidates' if expected['candidates'] else 'no_candidate_under_fragment_rules'
        positive = bool(cached[key[0]] and not old['candidates'] and not old['searchCapped'] and not expected['searchCapped'] and any(c['hasTerminalCut'] for c in expected['candidates']))
        require(record['status'] == status and record['supportsHypothesis'] == positive, 'Audit outcome/hypothesis')
        require(all(record[k] is False for k in ['sourceComplete', 'physicalIdentityVerified', 'carAccessVerified', 'usableSpeedCoverageAdmitted']), 'Audit no source/identity/access/speed admission')
    all_records = [r for r, _ in current.values()]; totals = reference_summary(all_records)
    report = json.loads((output.root / 'report.json').read_text())
    require(len(metadata) == plan['expectedRows'] == report['retainedRows'] and totals['arcCount'] == plan['expectedMatches'] and totals['samples'] == plan['expectedSamples'], 'Audit complete denominators')
    equivalent(report['allWindows'], totals); equivalent(report['frozenLimitStatusCounts'], dict(limits))
    require(len(windows) == plan['expectedWindows'] == len(report['windows']), 'Audit window count')
    for window, result in zip(windows, report['windows']):
        group = [r for r in all_records if r['windowId'] == window['id']]
        expected = {'id': window['id'], 'cachedRows': cached[window['id']], 'sourceStatus': 'incomplete_after_capture_stop',
            'totals': reference_summary(group), 'sourceClassesKph': {str(s): reference_summary([r for r in group if r['original']['sourceClassKph'] == s]) for s in (85, 105)}}
        equivalent(result, expected); equivalent(json.loads((output.root / 'windows' / (window['id'] + '.json')).read_text()), expected)
    require(report['hypothesisSupported'] == (totals['newUncappedClippedRecords'] > 0), 'Audit fixed decision')
    require(report['completedSourceWindows'] == report['networkRequests'] == report['routingQueries'] == 0 and report['originalFeasibilityQualified'] is False, 'Audit no source/model admission')
    output.write('audit.json', json_bytes({'independentProjectionIntervalConnectorUnionEnumerationAndOriginalControlAudit': True,
        'retainedRows': len(metadata), 'arcWindowRecords': len(current), 'samples': totals['samples'],
        'newUncappedClippedRecords': totals['newUncappedClippedRecords'], 'hypothesisSupported': report['hypothesisSupported'],
        'completedSourceWindows': 0, 'method': 'Separate projections/interval construction and iterative all-pairs minimal-chain enumeration; original fields, fractions, raw metadata and weighted unions checked. Shared sealed WKB/parser/sample/tangent/hash primitives. No physical/access/global identity proof.'}))

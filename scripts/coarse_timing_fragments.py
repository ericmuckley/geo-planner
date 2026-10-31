"""Offline terminal-fragment geometry prototype; never a driving-time model."""
import base64
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from analyze_timing_cache import canonical
from coarse_path_features import distance_km
from coarse_timing_chains import can_join, mask_km, progress, row_metadata, sample_points
from coarse_timing_input import PilotError, json_bytes, require
from coarse_timing_parquet import angle_degrees, decode_lines, interpolate


EVIDENCE = 'docs/evidence/coarse-timing-fragments-2026-10-26'
TIE_KM = 1e-9
MODES = ('full', 'start', 'end', 'both')


def cumulative_lengths(line):
    lengths = [0.]
    for a, b in zip(line, line[1:]): lengths.append(lengths[-1] + distance_km(a, b))
    require(lengths[-1] > 0, 'degenerate_geometry')
    return lengths


def nearest_projection(point, tangent, line, lengths):
    candidates = []
    scale = math.cos(math.radians(point[1]))
    for i, (a, b) in enumerate(zip(line, line[1:])):
        if lengths[i + 1] == lengths[i]: continue
        dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
        t = max(0., min(1., ((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        projected = interpolate(a, b, t)
        candidates.append((distance_km(point, projected), lengths[i] + t * (lengths[i + 1] - lengths[i]), projected, i))
    nearest = min(c[0] for c in candidates)
    tied = [c for c in candidates if c[0] - nearest <= TIE_KM]
    require(nearest <= .025, 'projection_outside_distance')
    require(max(c[1] for c in tied) - min(c[1] for c in tied) <= TIE_KM, 'ambiguous_projection')
    require(all(angle_degrees(*tangent, line[c[3]], line[c[3] + 1]) <= 15 for c in tied), 'projection_tangent_mismatch')
    # Adjacent collinear pieces may tie at the same vertex. The smaller along
    # position is deterministic; distinct along positions remain unresolved.
    chosen = min(tied, key=lambda c: (c[1], c[3]))
    return {'fraction': chosen[1] / lengths[-1], 'point': chosen[2], 'distanceKm': nearest}


def point_at(line, lengths, fraction):
    at = fraction * lengths[-1]
    for i in range(len(line) - 1):
        if lengths[i + 1] > lengths[i] and at <= lengths[i + 1]:
            return interpolate(line[i], line[i + 1], (at - lengths[i]) / (lengths[i + 1] - lengths[i]))
    return list(line[-1])


def interval_in_window(line, lengths, first, last, box):
    lo, hi = sorted((first * lengths[-1], last * lengths[-1]))
    points = [point_at(line, lengths, first), point_at(line, lengths, last)]
    points.extend(p for p, at in zip(line, lengths) if lo < at < hi)
    return all(box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3] for p in points)


def projection_direction(fractions, length):
    delta = [(b - a) * length for a, b in zip(fractions, fractions[1:])]
    require(abs(fractions[-1] - fractions[0]) * length > TIE_KM, 'nonmonotone_or_tied_projection')
    for a, b, d in zip(fractions, fractions[1:], delta):
        if abs(d) <= TIE_KM:
            require(any(max(abs(f - end) for f in (a, b)) * length <= TIE_KM for end in (0, 1)), 'nonmonotone_or_tied_projection')
    require(all(d >= -TIE_KM for d in delta) or all(d <= TIE_KM for d in delta), 'nonmonotone_or_tied_projection')
    return int(fractions[-1] < fractions[0])


def make_fragments(metadata, lines, samples, points, tangents, box, old_nodes, check=lambda: None):
    aligned = defaultdict(list)
    for i, sample in enumerate(samples):
        for ordinal in sample[4]: aligned[ordinal].append(i)
    old = {n['ordinal']: n for n in old_nodes}
    require(len(old) == len(old_nodes) and set(old) <= set(aligned), 'Saved full-node roster')
    nodes, issues, projections = {}, [], []
    for ordinal, indices in sorted(aligned.items()):
        check()
        meta = metadata[ordinal]
        if ordinal in old:
            full = old[ordinal]
            nodes[f'{ordinal}/full'] = {**full, 'variantKey': f'{ordinal}/full', 'mode': 'full',
                'entryFraction': float(full['direction']), 'exitFraction': float(1 - full['direction']),
                'fractionBasis': 'normalized_haversine_polyline_length'}
        if meta['baseReasons']:
            issues.append({'ordinal': ordinal, 'reasons': meta['baseReasons']})
            continue
        line = lines[ordinal]
        try:
            lengths = cumulative_lengths(line)
            require(len(indices) >= 2, 'insufficient_projection_progress')
            projected = [nearest_projection(points[i], tangents[i], line, lengths) for i in indices]
            fractions = [p['fraction'] for p in projected]
            direction = projection_direction(fractions, lengths[-1])
            projections.append({'ordinal': ordinal, 'sampleIndices': indices, 'projections': projected})
        except PilotError as error:
            issues.append({'ordinal': ordinal, 'reasons': [str(error)]})
            continue
        endpoint_progress = [progress(p, indices, points) for p in meta['endpoints']]
        variant_issues = []
        for mode in MODES[1:]:
            cut_start, cut_end = mode in ('start', 'both'), mode in ('end', 'both')
            # A cut must lie strictly inside the original line. Endpoint cases
            # retain the saved full-node eligibility rather than inventing IDs.
            if cut_start and min(fractions[0], 1 - fractions[0]) * lengths[-1] <= TIE_KM: continue
            if cut_end and min(fractions[-1], 1 - fractions[-1]) * lengths[-1] <= TIE_KM: continue
            first = fractions[0] if cut_start else float(direction)
            last = fractions[-1] if cut_end else float(1 - direction)
            entry, d0 = ([indices[0], indices[0]], 0.) if cut_start else endpoint_progress[direction]
            exit_, d1 = ([indices[-1], indices[-1]], 0.) if cut_end else endpoint_progress[1 - direction]
            reasons = []
            if not interval_in_window(line, lengths, first, last, box): reasons.append('outside_window_fragment')
            if d0 > .025: reasons.append('uncut_entry_not_near_samples')
            if d1 > .025: reasons.append('uncut_exit_not_near_samples')
            if entry[1] >= exit_[0]: reasons.append('nonprogressing_fragment_endpoints')
            kept = [i for i, p in zip(indices, projected) if min(first, last) - TIE_KM / lengths[-1] <= p['fraction'] <= max(first, last) + TIE_KM / lengths[-1]]
            if not kept: reasons.append('empty_fragment_support')
            if reasons:
                variant_issues.append({'mode': mode, 'reasons': reasons})
                continue
            key = f'{ordinal}/{mode}'
            nodes[key] = {'ordinal': ordinal, 'variantKey': key, 'mode': mode, 'direction': direction,
                'entryId': None if cut_start else meta['endpointIds'][direction],
                'exitId': None if cut_end else meta['endpointIds'][1 - direction],
                'entryPoint': point_at(line, lengths, first), 'exitPoint': point_at(line, lengths, last),
                'entryFraction': first, 'exitFraction': last, 'fractionBasis': 'normalized_haversine_polyline_length',
                'entryProgress': entry, 'exitProgress': exit_, 'sampleMin': min(kept), 'sampleMax': max(kept),
                'maskHex': hex(sum(1 << i for i in kept))}
        if variant_issues: issues.append({'ordinal': ordinal, 'variantExclusions': variant_issues})
    return nodes, issues, projections


def fragment_links(nodes):
    entering = defaultdict(list)
    for key, node in nodes.items():
        if node['entryId'] is not None: entering[node['entryId']].append(key)
    return {key: sorted((other for other in entering.get(node['exitId'], [])
        if node['exitId'] is not None and nodes[other]['ordinal'] != node['ordinal'] and can_join(node, nodes[other])),
        key=lambda k: (nodes[k]['ordinal'], nodes[k]['mode'])) for key, node in nodes.items()}


def search_fragments(nodes, weights, maximum_rows=64, maximum_states=4096, check=lambda: None):
    require(weights and all(math.isfinite(w) and w > 0 for w in weights), 'Invalid fragment weights')
    require(type(maximum_rows) is int and maximum_rows > 0 and type(maximum_states) is int and maximum_states > 0, 'Invalid fragment caps')
    links, total = fragment_links(nodes), math.fsum(weights)
    candidates, caps, states = {}, set(), 0
    def union(path):
        mask = 0
        for k in path: mask |= int(nodes[k]['maskHex'], 16)
        return mask
    def qualifies(path): return mask_km(union(path), weights) / total >= .8 - 1e-12
    def visit(path):
        nonlocal states
        check()
        if states == maximum_states:
            caps.add('expanded_states'); return
        states += 1
        if qualifies(path):
            if len(path) == 1 or not qualifies(path[1:]) and not qualifies(path[:-1]):
                key = min(path, path[::-1])
                mask = union(path)
                candidates[key] = {'variantKeys': list(path), 'rowOrdinals': [nodes[k]['ordinal'] for k in path],
                    'coveredSampleMaskHex': hex(mask), 'supportedKm': mask_km(mask, weights),
                    'fraction': min(1., mask_km(mask, weights) / total),
                    'hasTerminalCut': any(nodes[k]['mode'] != 'full' for k in path)}
            return
        used = {nodes[k]['ordinal'] for k in path}
        following = [k for k in links[path[-1]] if nodes[k]['ordinal'] not in used]
        if len(path) >= maximum_rows and following:
            caps.add('chain_length'); return
        for k in following:
            visit(path + (k,))
            if 'expanded_states' in caps: return
    for k in sorted(nodes, key=lambda k: (nodes[k]['ordinal'], nodes[k]['mode'])):
        visit((k,))
        if 'expanded_states' in caps: break
    return {'candidates': [candidates[k] for k in sorted(candidates)], 'expandedStates': states,
        'capReasons': sorted(caps), 'searchCapped': bool(caps)}


def fragment_status(search, cached_rows):
    if not cached_rows: return 'unmeasured_empty_cache'
    if search['searchCapped']: return 'search_capped'
    return 'cached_geometry_candidates' if search['candidates'] else 'no_candidate_under_fragment_rules'


def summary(records):
    return {'arcCount': len(records), 'samples': sum(r['sampleCount'] for r in records),
        'sourceKm': math.fsum(r['original']['sourceKm'] for r in records),
        'statusCounts': dict(Counter(r['status'] for r in records)),
        'recordsWithCandidates': sum(bool(r['candidates']) for r in records),
        'fragmentCandidates': sum(len(r['candidates']) for r in records), 'cappedRecords': sum(r['searchCapped'] for r in records),
        'originalCandidates': sum(len(r['original']['candidates']) for r in records),
        'originalCandidateBearingRecords': sum(bool(r['original']['candidates']) for r in records),
        'newUncappedClippedRecords': sum(r['supportsHypothesis'] for r in records),
        'newUncappedClippedSourceKm': math.fsum(r['original']['sourceKm'] for r in records if r['supportsHypothesis']),
        'baselineProvisionalEligibleKm': math.fsum(r['original']['baselineProvisionalEligibleKm'] for r in records)}


def analyze(plan, output, paths):
    windows = json.loads(Path(paths['proposal']).read_text())['selection']['windows']
    previous = json.loads(Path(paths['previousReport']).read_text())
    metadata, lines, identities, limits = [], [], set(), Counter()
    with Path(paths['segments']).open('rb') as raw_stream, Path(paths['scopes']).open('rb') as scopes:
        for ordinal, pair in enumerate(itertools.zip_longest(raw_stream, scopes)):
            output.check()
            raw, encoded = pair
            require(all(v is not None and len(v) <= plan['maxLineBytes'] for v in pair), 'Complete bounded row/scope roster')
            row, scope = json.loads(raw), json.loads(encoded)
            key = row['id'], row['version']
            require(key not in identities and ordinal == scope['ordinal'] and key == (scope['id'], scope['version']), 'Frozen identity/ordinal')
            require(hashlib.sha256(raw).hexdigest() == scope['rawLineSha256'], 'Raw source line binding')
            require(hashlib.sha256(canonical({k: v for k, v in row.items() if k != 'geometryWkbBase64'})).hexdigest() == scope['fieldsSha256'], 'Raw fields binding')
            require(row.get('speed_limits') == scope['rawSpeedLimits'] and row.get('access_restrictions') == scope['rawAccessRestrictions'], 'Raw scopes changed')
            meta = row_metadata(row, scope)
            try: decoded = decode_lines(base64.b64decode(row['geometryWkbBase64'], validate=True))
            except (ValueError, RuntimeError): decoded = []
            line = decoded[0] if len(decoded) == 1 else []
            metadata.append(meta); lines.append(line); identities.add(key); limits.update([meta['frozenLimit']['status']])
            output.record('rows.jsonl', meta)
    require(len(metadata) == plan['expectedRows'] and limits == previous['frozenLimitStatusCounts'], 'Retained row/parser denominators')
    def keyed(path):
        result = {}
        with Path(path).open('rb') as stream:
            for raw in stream:
                output.check(); require(len(raw) <= plan['maxLineBytes'], 'Bounded saved record')
                r = json.loads(raw); key = r['windowId'], r['arc']
                require(key not in result, 'Duplicate saved arc')
                result[key] = (r, hashlib.sha256(raw).hexdigest())
        return result
    matches, supports, controls = (keyed(paths[k]) for k in ('matches', 'support', 'chains'))
    require(set(matches) == set(supports) == set(controls), 'Complete source/control roster')
    cached = {w['id']: w['cachedRows'] for w in previous['windows']}
    records, window_summaries = [], []
    for window in windows:
        group = []
        for key in sorted(k for k in supports if k[0] == window['id']):
            output.check()
            saved, match_sha = matches[key]; support, support_sha = supports[key]; old, old_sha = controls[key]
            require(support['savedMatchLineSha256'] == match_sha and old['savedSupportLineSha256'] == support_sha, 'Saved control/support/match binding')
            points, weights = sample_points(saved, support)
            tangents = [saved['sourceSpans'][s[0]][:2] for s in support['samples']]
            nodes, issues, projections = make_fragments(metadata, lines, support['samples'], points, tangents, window['bbox'], old['nodes'], output.check)
            searched = search_fragments(nodes, weights, plan['maximumRowsPerChain'], plan['maximumExpandedStatesPerArc'], output.check)
            for c in searched['candidates']:
                c['memberParserStatuses'] = [metadata[i]['frozenLimit']['status'] for i in c['rowOrdinals']]
                c['allMembersParserUsable'] = all(s == 'usable' for s in c['memberParserStatuses'])
            record = {'windowId': key[0], 'arc': key[1], 'original': old, 'originalLineSha256': old_sha,
                'sampleCount': len(weights), 'nodes': list(nodes.values()), 'fragmentIssues': issues, 'projections': projections,
                **searched, 'sourceComplete': False, 'physicalIdentityVerified': False, 'carAccessVerified': False,
                'usableSpeedCoverageAdmitted': False}
            record['status'] = fragment_status(searched, cached[key[0]])
            record['supportsHypothesis'] = bool(cached[key[0]] and not old['candidates'] and not old['searchCapped'] and not searched['searchCapped'] and any(c['hasTerminalCut'] for c in searched['candidates']))
            output.record('fragments.jsonl', record); records.append(record); group.append(record)
        result = {'id': window['id'], 'cachedRows': cached[window['id']], 'sourceStatus': 'incomplete_after_capture_stop',
            'totals': summary(group), 'sourceClassesKph': {str(s): summary([r for r in group if r['original']['sourceClassKph'] == s]) for s in (85, 105)}}
        output.write('windows/' + window['id'] + '.json', json_bytes(result)); window_summaries.append(result)
    totals = summary(records)
    require(totals['arcCount'] == plan['expectedMatches'] and totals['samples'] == plan['expectedSamples'] and len(windows) == plan['expectedWindows'], 'Full source/sample/window denominators')
    require(totals['originalCandidates'] == previous['cohorts']['all']['originalCandidateChains'], 'Original candidate control')
    report = {'retainedRows': len(metadata), 'frozenLimitStatusCounts': limits, 'windows': window_summaries,
        'allWindows': totals, 'hypothesisSupported': totals['newUncappedClippedRecords'] > 0,
        'completedSourceWindows': 0, 'originalFeasibilityQualified': False, 'networkRequests': 0, 'routingQueries': 0,
        'scope': 'Cached geometric terminal-fragment hypothesis only. Every original chain record preserved; all21 source windows incomplete. No physical/global uniqueness, car access, usable-speed, ETA or model admission.'}
    output.write('report.json', json_bytes(report))


def run(plan, output):
    analyze(plan, output, plan['paths'])
    from coarse_timing_fragments_audit import audit
    audit(plan, output, plan['paths'])


if __name__ == '__main__':
    from offline_timing_runner import main
    main(EVIDENCE + '/execution-plan.json')

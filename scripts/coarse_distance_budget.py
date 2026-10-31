"""Saved unbuffered-path distance accounting; no graph load, search or fit."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

from coarse_timing_exposure import cohorts, distribution, equal, indexed, require

QUANTUM = 1 / 600
TOLERANCE = 1e-8


def distance_km(a, b):
    require(len(a) == len(b) == 2 and all(math.isfinite(v) for v in [*a, *b]), 'Invalid point')
    lat = math.radians(b[1] - a[1])
    lon = math.radians(b[0] - a[0])
    h = math.sin(lat / 2) ** 2 + math.cos(math.radians(a[1])) * math.cos(math.radians(b[1])) * math.sin(lon / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))


def endpoint_interval(minutes, speed_upper):
    require(math.isfinite(minutes) and minutes >= 0, 'Invalid endpoint price')
    require(math.isfinite(speed_upper) and speed_upper > 0, 'Invalid speed bound')
    return {'minimumKm': 0., 'maximumKm': minutes * speed_upper / 60,
            'status': 'bounded_mixed_attachment', 'paidMinutes': minutes}


def straight_step(edge):
    km = distance_km(edge['fromPoint'], edge['toPoint'])
    raw = km / 25 * 60
    minutes = edge['minutes']
    if edge['kind'] == 'local':
        equal(minutes, raw, 'Local price is not exact distance/local25')
    else:
        require(edge['kind'] == 'transfer', 'Unsupported straight step')
        equal(minutes * 600, round(minutes * 600), 'Nonquantized transfer')
        require(minutes >= QUANTUM - TOLERANCE and
                -TOLERANCE <= minutes - raw <= QUANTUM + TOLERANCE,
                'Transfer price is not rounded local25 with minimum charge')
    return km, minutes - raw


def distance_row(path, exposure, provider, source_edges, base_edges, speed_upper):
    require(path['id'] == exposure['id'] == provider['id'], 'Case IDs differ')
    require(not path['direct'] and path['edges'], 'Explicit captured path required')
    require(path['origin'] == provider['origin'] and path['destination'] == provider['destination'], 'Endpoint IDs differ')
    equal(path['pointMinutes'], provider['candidateMinutes'], 'Captured/provider old model price')
    equal(exposure['referenceMinutes'], provider['orsMinutes'], 'Saved ORS time')
    equal(path['pointMinutes'], sum(path['components'].values()), 'Captured component sum')
    equal(path['pointMinutes'] - exposure['referenceMinutes'], exposure['oldSignedErrorMinutes'], 'Old signed error')
    require(path['components'] == exposure['oldComponents'] or all(
        abs(v - exposure['oldComponents'][k]) < TOLERANCE for k, v in path['components'].items()), 'Exposure components')
    source_index = base_index = 0
    lengths = {'detailedSourceKm': 0., 'baseSourceKm': 0., 'baseConnectorKm': 0., 'localKm': 0., 'transferKm': 0.}
    prices = {'road': 0., 'local': 0., 'transfer': 0.}
    rounding = {'sourceMinutes': 0., 'baseMinutes': 0., 'transferMinutes': 0.}
    pure_by_class = {k: 0. for k in exposure['sourceMinutesByClass']}
    audit = []
    previous = None
    for index, edge in enumerate(path['edges']):
        require(math.isfinite(edge['minutes']) and edge['minutes'] > 0, 'Invalid transition price')
        if previous is not None:
            require(previous['target'] == edge['from'] and previous['toPoint'] == edge['fromPoint'], 'Disconnected captured chain')
        previous = edge
        prices[edge['kind']] += edge['minutes']
        item = {'index': index, 'from': edge['from'], 'target': edge['target'], 'kind': edge['kind'], 'minutes': edge['minutes']}
        if 'arc' in edge:
            require(edge['kind'] == 'road' and source_index < len(source_edges), 'Missing source occurrence')
            proof = source_edges[source_index]
            source_index += 1
            require(proof['arc'] == edge['arc'], 'Source arc occurrence/order')
            equal(proof['minutes'], edge['minutes'], 'Source occurrence price')
            km, speed = proof['sourceKm'], proof['speedKph']
            require(km >= 0 and 0 < speed <= speed_upper, 'Source distance/speed')
            raw = km / speed * 60
            require(-TOLERANCE <= edge['minutes'] - raw <= QUANTUM + TOLERANCE, 'Original source rounding')
            pure_by_class[str(speed)] += raw
            lengths['detailedSourceKm'] += km
            rounding['sourceMinutes'] += edge['minutes'] - raw
            item.update(arc=edge['arc'], sourceKm=km, speedKph=speed, distanceKm=km,
                        roundingMinutes=edge['minutes'] - raw, provenance='saved_cumulative_source_length')
        elif edge['kind'] == 'road':
            require(base_index < len(base_edges), 'Missing selected base occurrence')
            proof = base_edges[base_index]
            base_index += 1
            equal(proof['minutes'], edge['minutes'], 'Base occurrence price')
            road, connector, speed = proof['roadKm'], proof['connectorKm'], proof['speedKph']
            require(road >= 0 and connector >= 0 and 0 < speed <= speed_upper, 'Base length/speed')
            require(proof['sourceKind'] in ('natural-earth', 'census'), 'Unknown base source kind')
            require(proof['connectorSpeedKph'] == (55 if proof['sourceKind'] == 'natural-earth' else 25), 'Connector speed')
            raw = road / speed * 60
            local = connector / proof['connectorSpeedKph'] * 60
            equal(raw, proof['sourceRoadMinutes'], 'Base source time')
            equal(local, proof['connectorMinutes'], 'Base connector time')
            equal(edge['minutes'] - raw - local, proof['roundingMinutes'], 'Base rounding')
            require(-TOLERANCE <= proof['roundingMinutes'] <= QUANTUM + TOLERANCE, 'Base quantization')
            pure_by_class[str(speed)] += raw
            lengths['baseSourceKm'] += road
            lengths['baseConnectorKm'] += connector
            rounding['baseMinutes'] += proof['roundingMinutes']
            item.update(key=proof['key'], sourceKind=proof['sourceKind'], sourceKm=road, connectorKm=connector,
                        speedKph=speed, distanceKm=road + connector, roundingMinutes=proof['roundingMinutes'],
                        provenance='saved_selected_source_and_connector_proof')
        else:
            km, extra = straight_step(edge)
            lengths[edge['kind'] + 'Km'] += km
            if edge['kind'] == 'transfer':
                rounding['transferMinutes'] += extra
            item.update(distanceKm=km, roundingMinutes=extra, provenance='captured_state_straight_local25',
                        fromPoint=edge['fromPoint'], toPoint=edge['toPoint'])
        audit.append(item)
    require(source_index == len(source_edges) and base_index == len(base_edges), 'Unused source/base proof occurrence')
    for kind, value in prices.items():
        equal(value, path['components'][kind], kind + ' sum')
    for speed, value in pure_by_class.items():
        equal(value, exposure['sourceMinutesByClass'][speed], 'Source class minutes')
    equal(lengths['detailedSourceKm'], provider['detailedCensusSourceKm'], 'Detailed source length')
    origin = endpoint_interval(path['components']['origin'], speed_upper)
    destination = endpoint_interval(path['components']['destination'], speed_upper)
    known = sum(lengths.values())
    lower = known + origin['minimumKm'] + destination['minimumKm']
    upper = known + origin['maximumKm'] + destination['maximumKm']
    reference = provider['orsPolylineKm']
    require(math.isfinite(reference) and reference > 0, 'Missing ORS decoded-polyline length')
    status = ('recorded_model_shorter' if upper < reference - TOLERANCE else
              'recorded_model_longer' if lower > reference + TOLERANCE else 'recorded_length_intervals_overlap')
    row = {**exposure, **lengths, 'knownDistanceKm': known, 'originInterval': origin, 'destinationInterval': destination,
           'distanceMinimumKm': lower, 'distanceMaximumKm': upper, 'endpointUncertaintyKm': upper - lower,
           'orsPolylineKm': reference, 'differenceMinimumKm': lower - reference, 'differenceMaximumKm': upper - reference,
           'ratioMinimum': lower / reference, 'ratioMaximum': upper / reference,
           'lengthStatus': status, 'rounding': rounding, 'sourceOccurrences': source_index, 'baseOccurrences': base_index,
           'scope': 'Captured unbuffered walk-weight lengths; mixed endpoints bounded. Current residual cohorts do not imply current-path lengths.'}
    return row, {'id': path['id'], 'edges': audit}


def summarize(rows):
    fields = ('distanceMinimumKm', 'distanceMaximumKm', 'endpointUncertaintyKm', 'orsPolylineKm',
              'differenceMinimumKm', 'differenceMaximumKm', 'ratioMinimum', 'ratioMaximum',
              'oldSignedErrorMinutes', 'currentSignedErrorMinutes')
    return {'cases': len(rows), 'caseIds': [r['id'] for r in rows],
            'sensitivities': sum(r['valhallaMinutes'] is not None for r in rows),
            'statusCounts': {status: sum(r['lengthStatus'] == status for r in rows) for status in
                             ('recorded_model_shorter', 'recorded_model_longer', 'recorded_length_intervals_overlap')},
            'unboundedOrMissing': 0, 'metrics': {field: distribution([r[field] for r in rows]) for field in fields}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('plan_sha256')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    plan_raw = (root / 'docs/evidence/coarse-distance-budget-2026-10-25/plan.json').read_bytes()
    require(hashlib.sha256(plan_raw).hexdigest() == args.plan_sha256, 'Plan binding')
    plan = json.loads(plan_raw)
    for path, expected in plan['inputs'].items():
        require(hashlib.sha256((root / path).read_bytes()).hexdigest() == expected, path)
    for path, expected in plan['toolFiles'].items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path)
    geometry = json.loads((root / plan['sourcePolicy']).read_text())
    require(max(geometry['sources']['speeds'].values()) == plan['endpointSpeedUpperKph'] == 105, 'Source speed ceiling')
    output = (root / args.output).resolve()
    require(output == (root / plan['output']).resolve() and output.is_relative_to(root / 'data/coarse-quality'), 'Output path')
    output.mkdir()
    (output / 'plan.json').write_bytes(plan_raw)
    def load(name):
        path = root / plan['files'][name]
        return json.loads(gzip.decompress(path.read_bytes())) if path.suffix == '.gz' else json.loads(path.read_text())
    captured = load('paths')
    started = time.perf_counter()
    try:
        sources = [indexed(items, name) for items, name in [(captured, 'paths'),
            (load('exposure')['rows'], 'exposure'), (load('provider')['rows'], 'provider'),
            (load('sourceEdges'), 'source edges'), (load('baseEdges'), 'base edges')]]
        require(all(set(s) == set(sources[0]) for s in sources), 'Case ID sets differ')
        rows, audits = [], []
        for key in sources[0]:
            path, exposure, provider, source, base = (s[key] for s in sources)
            row, audit = distance_row(path, exposure, provider, source['edges'], base['edges'], plan['endpointSpeedUpperKph'])
            rows.append(row)
            audits.append(audit)
        require(len(rows) == 83 and sum(r['valhallaMinutes'] is not None for r in rows) == 35, '83/35 denominator')
        report = {'planSha256': args.plan_sha256, 'cases': 83, 'sensitivities': 35,
                  'rows': rows, 'cohorts': {name: summarize(group) for name, group in cohorts(rows).items()},
                  'ledger': [{'id': r['id'], 'status': 'bounded', 'lengthStatus': r['lengthStatus']} for r in rows],
                  'allRecordedCostsSourcesAndOccurrencesReconciled': True,
                  'routingQueries': 0, 'providerRequests': 0, 'runtimeChanged': False,
                  'elapsedSeconds': time.perf_counter() - started, 'scope': plan['scope']}
        with (output / 'report.json').open('x') as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
        with (output / 'edge-audit.json.gz').open('xb') as stream:
            stream.write(gzip.compress((json.dumps(audits, separators=(',', ':'), allow_nan=False) + '\n').encode(), mtime=0))
    except Exception as error:
        with (output / 'failure.json').open('x') as stream:
            stream.write(json.dumps({'error': str(error), 'plannedCases': 83, 'sensitivities': 35,
                'ledger': [{'id': p['id'], 'status': 'not_emitted_due_to_failure'} for p in captured]}, indent=2) + '\n')
        raise
    print(json.dumps({'cases': 83, 'sensitivities': 35, 'cohorts': len(report['cohorts']),
                      'allReconciled': True, 'summary': report['cohorts']['all'], 'routingQueries': 0}, indent=2))


if __name__ == '__main__':
    main()

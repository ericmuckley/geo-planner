"""Join saved timing/coverage evidence. Standard library only; no routing or fitting."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

TOLERANCE = 1e-8
SPEEDS = (55, 85, 90, 105)
COVERAGE = ('censusWithin1KmOfOrs', 'censusWithin3KmOfOrs',
            'orsWithin1KmOfCensusSubset', 'orsWithin3KmOfCensusSubset')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def equal(a, b, label):
    require(math.isfinite(a) and math.isfinite(b) and abs(a - b) < TOLERANCE, label)


def indexed(rows, label, compound=False):
    result = {}
    for row in rows:
        key = row['set'] + '/' + row['id'] if compound else row['id']
        require(key not in result, f'Duplicate {label}: {key}')
        result[key] = row
    return result


def sign(value):
    return 'faster' if value < -TOLERANCE else 'slower' if value > TOLERANCE else 'equal'


def join_rows(control, paths, base, base_edges, comparison):
    sources = [indexed(items, label, label == 'comparison') for items, label in
               [(control, 'control'), (paths, 'paths'), (base, 'base'),
                (base_edges, 'base edges'), (comparison, 'comparison')]]
    expected = set(sources[0])
    require(all(set(source) == expected for source in sources), 'Case ID sets differ')
    rows = []
    for key in sources[0]:
        c, p, b, e, a = (source[key] for source in sources)
        require(c['set'] == p['set'] == b['set'] == a['set'], f'{key}: set')
        equal(c['referenceMinutes'], p['orsMinutes'], key + ': reference')
        equal(c['referenceMinutes'], a['referenceMinutes'], key + ': reference comparison')
        require(c['valhallaMinutes'] == a['valhallaMinutes'], key + ': Valhalla')
        require(c['budgetMinutes'] == a['budgetMinutes'], key + ': budget')
        equal(c['oldSourceMinutes'], p['candidateMinutes'], key + ': path price')
        equal(c['oldSourceMinutes'], b['candidateMinutes'], key + ': base price')
        equal(c['actualAllowanceMinutes'], a['candidate']['pointMinutes'], key + ': current price')
        equal(c['v9Minutes'], a['baseline']['pointMinutes'], key + ': v9 price')
        for label, total_key in [('old', 'oldSourceMinutes'), ('held', 'heldStateMinutes'),
                                 ('actual', 'actualAllowanceMinutes')]:
            equal(sum(c[label + 'Components'].values()), c[total_key], key + ': components')
        costs = p['costs']
        equal(costs['accountedMinutes'], c['oldSourceMinutes'], key + ': accounting')
        equal(costs['detailedCensusMinutes'] + costs['coarseBaseRoadMinutes'],
              c['oldComponents']['road'], key + ': road')
        for field, component in [('transferMinutes', 'transfer'), ('localMinutes', 'local'),
                                 ('unresolvedOriginMinutes', 'origin'),
                                 ('unresolvedDestinationMinutes', 'destination')]:
            equal(costs[field], c['oldComponents'][component], key + ': ' + component)
        equal(costs['unresolvedDirectRoadMinutes'], 0, key + ': unsupported direct path')
        require(not (set(p['classes']) | set(c['sourceByClass'])) - {str(s) for s in SPEEDS},
                key + ': unknown source class')
        pure = {str(s): 0. for s in SPEEDS}
        for speed, detail in p['classes'].items():
            pure[speed] += detail['sourceKm'] / int(speed) * 60
        equal(sum(d['minutes'] for d in p['classes'].values()),
              costs['detailedCensusMinutes'], key + ': detailed class cost')
        equal(sum(d['sourceKm'] for d in p['classes'].values()),
              p['detailedCensusSourceKm'], key + ': detailed source length')
        equal(sum(d['edges'] for d in p['classes'].values()), p['detailedEdges'], key + ': edges')
        grouped = defaultdict(lambda: defaultdict(float))
        for edge in e['edges']:
            speed = str(edge['speedKph'])
            require(speed in pure, key + ': unknown base source class')
            source = edge['roadKm'] / edge['speedKph'] * 60
            connector = edge['connectorKm'] / edge['connectorSpeedKph'] * 60
            equal(source, edge['sourceRoadMinutes'], key + ': base source')
            equal(connector, edge['connectorMinutes'], key + ': base connector')
            equal(source + connector + edge['roundingMinutes'], edge['minutes'], key + ': base sum')
            pure[speed] += source
            group = grouped[edge['sourceKind']]
            for name, value in [('minutes', edge['minutes']), ('sourceRoadMinutes', source),
                                ('connectorMinutes', connector), ('roundingMinutes', edge['roundingMinutes']),
                                ('roadKm', edge['roadKm']), ('connectorKm', edge['connectorKm']), ('edges', 1)]:
                group[name] += value
        require(set(grouped) == set(b['groups']), key + ': source groups')
        for kind, group in grouped.items():
            for field, value in group.items():
                equal(value, b['groups'][kind][field], key + ': base ' + field)
        equal(sum(g['minutes'] for g in grouped.values()), costs['coarseBaseRoadMinutes'], key + ': base cost')
        for speed, value in pure.items():
            equal(value, c['sourceByClass'].get(speed, 0), key + ': pure source class ' + speed)
        source_minutes = sum(pure.values())
        equal(source_minutes, c['fullRoadSourceMinutes'], key + ': pure source total')
        base_connector = sum(g['connectorMinutes'] for g in grouped.values())
        base_rounding = sum(g['roundingMinutes'] for g in grouped.values())
        detailed_rounding = costs['detailedCensusMinutes'] - sum(
            d['sourceKm'] / int(s) * 60 for s, d in p['classes'].items())
        require(detailed_rounding >= -TOLERANCE, key + ': detailed rounding')
        equal(source_minutes + base_connector + base_rounding + detailed_rounding,
              c['oldComponents']['road'], key + ': road decomposition')
        equal(c['oldSourceSignedErrorMinutes'], c['oldSourceMinutes'] - c['referenceMinutes'], key + ': old residual')
        equal(c['actualSignedErrorMinutes'], c['actualAllowanceMinutes'] - c['referenceMinutes'], key + ': new residual')
        for field in COVERAGE:
            value = p[field]
            require(value is None or math.isfinite(value) and 0 <= value <= 1, key + ': coverage range')
        empty = p['detailedEdges'] == 0
        require(not empty or p['detailedCensusSourceKm'] == 0 and not p['classes'], key + ': empty detail')
        for field in COVERAGE[:2]:
            require((p[field] is None) == empty, key + ': coverage eligibility')
        shares = {s: value / source_minutes if source_minutes else None for s, value in pure.items()}
        if source_minutes:
            equal(sum(shares.values()), 1, key + ': class shares')
        equal(c['oldSourceMinutes'] * p['detailedCensusTimeShare'], costs['detailedCensusMinutes'], key + ': detail share')
        rows.append({
            'id': key, 'set': c['set'], 'budgetMinutes': c['budgetMinutes'],
            'referenceMinutes': c['referenceMinutes'], 'valhallaMinutes': c['valhallaMinutes'],
            'oldSignedErrorMinutes': c['oldSourceSignedErrorMinutes'],
            'currentSignedErrorMinutes': c['actualSignedErrorMinutes'],
            'oldResidualSign': sign(c['oldSourceSignedErrorMinutes']),
            'currentResidualSign': sign(c['actualSignedErrorMinutes']),
            'oldComponents': c['oldComponents'], 'sourceMinutesByClass': pure,
            'sourceSharesByClass': shares, 'sourceMinutes': source_minutes,
            'baseConnectorMinutes': base_connector, 'baseRoundingMinutes': base_rounding,
            'detailedRoundingMinutes': detailed_rounding,
            'endpointMinutes': c['oldComponents']['origin'] + c['oldComponents']['destination'],
            'localMinutes': c['oldComponents']['local'], 'transferMinutes': c['oldComponents']['transfer'],
            'detailedCensusTimeShare': p['detailedCensusTimeShare'],
            'detailedCensusSourceKm': p['detailedCensusSourceKm'], 'detailedEdges': p['detailedEdges'],
            'coverageStatus': 'no_full_census' if empty else 'detailed_subset_available',
            **{field: p[field] for field in COVERAGE},
            'newMissVsV9': c['newMissVsV9'], 'newMissVsSource': c['newMissVsSource'],
            'persistentSourceMiss': c['persistentSourceMiss'],
            'originalRegressionGateExceeded': c['originalRegressionGateExceeded'],
        })
    return rows


def distribution(values):
    valid = [v for v in values if v is not None]
    require(all(math.isfinite(v) for v in valid), 'Nonfinite summary value')
    return {'available': len(valid), 'missing': len(values) - len(valid),
            'minimum': min(valid) if valid else None,
            'median': statistics.median(valid) if valid else None,
            'maximum': max(valid) if valid else None}


def cohorts(rows):
    groups = {'all': rows}
    for name in ('frontier', 'original', 'regional'):
        groups[name] = [r for r in rows if r['set'] == name]
    for budget in (360, 600, 720):
        groups[f'budget/{budget}'] = [r for r in rows if r['budgetMinutes'] == budget]
        groups[f'frontierBudget/{budget}'] = [r for r in rows if r['set'] == 'frontier' and r['budgetMinutes'] == budget]
    for model in ('old', 'current'):
        for value in ('faster', 'equal', 'slower'):
            groups[f'{model}Residual/{value}'] = [r for r in rows if r[model + 'ResidualSign'] == value]
    for name in ('newMissVsV9', 'newMissVsSource', 'persistentSourceMiss', 'originalRegressionGateExceeded'):
        groups[name] = [r for r in rows if r[name]]
    return groups


def summarize(rows):
    fields = ('oldSignedErrorMinutes', 'currentSignedErrorMinutes', 'sourceMinutes',
              'baseConnectorMinutes', 'baseRoundingMinutes', 'detailedRoundingMinutes',
              'endpointMinutes', 'localMinutes', 'transferMinutes', 'detailedCensusTimeShare',
              'detailedCensusSourceKm', *COVERAGE)
    return {'cases': len(rows), 'caseIds': [r['id'] for r in rows],
            'sensitivities': sum(r['valhallaMinutes'] is not None for r in rows),
            'noFullCensus': sum(r['coverageStatus'] == 'no_full_census' for r in rows),
            'metrics': {field: distribution([r[field] for r in rows]) for field in fields},
            'sourceMinutesByClass': {str(s): distribution([r['sourceMinutesByClass'][str(s)] for r in rows]) for s in SPEEDS},
            'sourceSharesByClass': {str(s): distribution([r['sourceSharesByClass'][str(s)] for r in rows]) for s in SPEEDS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('plan_sha256')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    plan_path = root / 'docs/evidence/coarse-timing-exposure-2026-10-25/plan.json'
    raw = plan_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == args.plan_sha256, 'Plan binding differs')
    plan = json.loads(raw)
    for name, expected in plan['inputs'].items():
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name)
    for name, expected in plan['toolFiles'].items():
        require(hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name)
    output = (root / args.output).resolve()
    require(output == (root / plan['output']).resolve(), 'Output differs')
    require(output.is_relative_to(root / 'data/coarse-quality'), 'Output is not ignored diagnostic data')
    output.mkdir()
    (output / 'plan.json').write_bytes(raw)
    started = time.perf_counter()
    def load(name):
        path = root / plan['files'][name]
        return json.loads(gzip.decompress(path.read_bytes())) if path.suffix == '.gz' else json.loads(path.read_text())
    control = load('control')['rows']
    try:
        rows = join_rows(control, load('paths')['rows'], load('base')['rows'],
                         load('baseEdges'), load('comparison')['normalizedRows'])
        require(len(rows) == 83, '83-case denominator')
        require(sum(r['valhallaMinutes'] is not None for r in rows) == 35, '35 sensitivities')
        require(sum(r['coverageStatus'] == 'no_full_census' for r in rows) == 3, '3 uncovered cases')
        groups = {name: summarize(group) for name, group in cohorts(rows).items()}
        report = {'planSha256': args.plan_sha256, 'cases': 83, 'sensitivities': 35,
                  'allIdentifiersComponentsClassesAndCoverageReconciled': True,
                  'rows': rows, 'cohorts': groups,
                  'coverageLedger': [{'id': r['id'], 'status': r['coverageStatus']} for r in rows],
                  'routingQueries': 0, 'providerRequests': 0, 'runtimeChanged': False,
                  'elapsedSeconds': time.perf_counter() - started,
                  'scope': plan['scope']}
        with (output / 'report.json').open('x') as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    except Exception as error:
        with (output / 'failure.json').open('x') as stream:
            stream.write(json.dumps({'error': str(error), 'plannedCases': 83, 'sensitivities': 35,
                                     'status': 'failed; no cases replaced', 'routingQueries': 0,
                                     'ledger': [{'id': row['id'], 'status': 'not_emitted_due_to_join_failure'}
                                                for row in control]}, indent=2) + '\n')
        raise
    print(json.dumps({'cases': 83, 'sensitivities': 35, 'cohorts': len(groups),
                      'noFullCensus': 3, 'allReconciled': True, 'routingQueries': 0,
                      'providerRequests': 0, 'runtimeChanged': False}, indent=2))


if __name__ == '__main__':
    main()

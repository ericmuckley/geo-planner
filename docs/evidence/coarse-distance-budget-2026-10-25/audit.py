"""Independent stored distance/source/cost/bound/cohort audit; no producer import."""
import gzip
import hashlib
import json
import math
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())
unpack = lambda p: json.loads(gzip.decompress(p.read_bytes()))
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
close = lambda a, b: abs(a - b) < 1e-8
recipe = load(folder / 'plan.json')
plan = load(folder / 'analysis-plan.json')
for path, expected in plan['inputs'].items():
    assert digest(repo / path) == expected, path
report = load(folder / 'report.json')
assert report['planSha256'] == digest(folder / 'plan.json')
paths = {r['id']: r for r in unpack(repo / recipe['files']['paths'])}
exposures = {r['id']: r for r in load(repo / recipe['files']['exposure'])['rows']}
providers = {r['id']: r for r in load(repo / recipe['files']['provider'])['rows']}
source = {r['id']: r['edges'] for r in unpack(repo / recipe['files']['sourceEdges'])}
base = {r['id']: r['edges'] for r in unpack(repo / recipe['files']['baseEdges'])}
audits = {r['id']: r['edges'] for r in unpack(folder / 'edge-audit.json.gz')}
rows = report['rows']
assert len(rows) == len(paths) == len(exposures) == len(providers) == len(audits) == 83
assert {r['id'] for r in rows} == set(paths) == set(exposures) == set(providers) == set(source) == set(base) == set(audits)
assert sum(r['valhallaMinutes'] is not None for r in rows) == 35

def haversine(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))

edge_count = source_count = base_count = 0
for row in rows:
    key = row['id']
    path, exposure, provider = paths[key], exposures[key], providers[key]
    for field, value in exposure.items():
        assert row[field] == value, (key, field)
    assert len(audits[key]) == len(path['edges'])
    old = path['components']
    totals = {kind: 0. for kind in ['road', 'local', 'transfer']}
    lengths = {kind: 0. for kind in ['detailedSourceKm', 'baseSourceKm', 'baseConnectorKm', 'localKm', 'transferKm']}
    roundings = {kind: 0. for kind in ['sourceMinutes', 'baseMinutes', 'transferMinutes']}
    pure_by_class = {s: 0. for s in exposure['sourceMinutesByClass']}
    si = bi = 0
    previous = None
    for index, (edge, result) in enumerate(zip(path['edges'], audits[key])):
        assert result['index'] == index
        assert all(result[k] == edge[k] for k in ['from', 'target', 'kind', 'minutes'])
        if previous is not None:
            assert previous['target'] == edge['from'] and previous['toPoint'] == edge['fromPoint']
        previous = edge
        totals[edge['kind']] += edge['minutes']
        if 'arc' in edge:
            proof = source[key][si]
            si += 1
            assert result['arc'] == proof['arc'] == edge['arc']
            assert close(proof['minutes'], edge['minutes'])
            km = proof['sourceKm']
            raw = km / proof['speedKph'] * 60
            assert close(result['distanceKm'], km) and close(result['sourceKm'], km)
            assert result['speedKph'] == proof['speedKph']
            assert -1e-8 <= edge['minutes'] - raw <= 1 / 600 + 1e-8
            roundings['sourceMinutes'] += edge['minutes'] - raw
            lengths['detailedSourceKm'] += km
            pure_by_class[str(proof['speedKph'])] += raw
        elif edge['kind'] == 'road':
            proof = base[key][bi]
            bi += 1
            assert close(proof['minutes'], edge['minutes'])
            assert result['key'] == proof['key'] and result['sourceKind'] == proof['sourceKind']
            assert result['sourceKm'] == proof['roadKm'] and result['connectorKm'] == proof['connectorKm']
            assert close(result['distanceKm'], proof['roadKm'] + proof['connectorKm'])
            lengths['baseSourceKm'] += proof['roadKm']
            lengths['baseConnectorKm'] += proof['connectorKm']
            raw = proof['roadKm'] / proof['speedKph'] * 60
            connector = proof['connectorKm'] / proof['connectorSpeedKph'] * 60
            assert close(raw, proof['sourceRoadMinutes']) and close(connector, proof['connectorMinutes'])
            assert close(raw + connector + proof['roundingMinutes'], edge['minutes'])
            assert -1e-8 <= proof['roundingMinutes'] <= 1 / 600 + 1e-8
            roundings['baseMinutes'] += proof['roundingMinutes']
            pure_by_class[str(proof['speedKph'])] += raw
        else:
            km = haversine(edge['fromPoint'], edge['toPoint'])
            raw = km / 25 * 60
            assert close(result['distanceKm'], km)
            assert result['fromPoint'] == edge['fromPoint'] and result['toPoint'] == edge['toPoint']
            lengths[edge['kind'] + 'Km'] += km
            if edge['kind'] == 'transfer':
                assert close(edge['minutes'] * 600, round(edge['minutes'] * 600))
                assert edge['minutes'] >= 1 / 600 - 1e-8
                assert -1e-8 <= edge['minutes'] - raw <= 1 / 600 + 1e-8
                roundings['transferMinutes'] += edge['minutes'] - raw
            else:
                assert close(edge['minutes'], raw)
        assert close(result['roundingMinutes'], edge['minutes'] - raw - (connector if 'arc' not in edge and edge['kind'] == 'road' else 0))
    assert si == row['sourceOccurrences'] == len(source[key])
    assert bi == row['baseOccurrences'] == len(base[key])
    for kind, value in totals.items():
        assert close(value, old[kind])
    for field, value in lengths.items():
        assert close(value, row[field]), (key, field)
    for field, value in roundings.items():
        assert close(value, row['rounding'][field])
    for speed, value in pure_by_class.items():
        assert close(value, exposure['sourceMinutesByClass'][speed])
    known = sum(lengths.values())
    assert close(known, row['knownDistanceKm'])
    for label in ['origin', 'destination']:
        interval = row[label + 'Interval']
        assert interval['minimumKm'] == 0 and interval['status'] == 'bounded_mixed_attachment'
        assert interval['paidMinutes'] == old[label]
        assert close(interval['maximumKm'], old[label] * 105 / 60)
    low, high = known, known + (old['origin'] + old['destination']) * 105 / 60
    reference = provider['orsPolylineKm']
    assert row['orsPolylineKm'] == reference
    for field, value in [('distanceMinimumKm', low), ('distanceMaximumKm', high),
                         ('endpointUncertaintyKm', high - low), ('ratioMinimum', low / reference),
                         ('ratioMaximum', high / reference), ('differenceMinimumKm', low - reference),
                         ('differenceMaximumKm', high - reference)]:
        assert close(row[field], value), (key, field)
    status = 'recorded_model_shorter' if high < reference - 1e-8 else 'recorded_model_longer' if low > reference + 1e-8 else 'recorded_length_intervals_overlap'
    assert row['lengthStatus'] == status
    edge_count += len(path['edges'])
    source_count += si
    base_count += bi

def select(name):
    if name == 'all':
        return rows
    if name in ['frontier', 'original', 'regional']:
        return [r for r in rows if r['set'] == name]
    if name.startswith('budget/') or name.startswith('frontierBudget/'):
        budget = int(name.split('/')[1])
        return [r for r in rows if r['budgetMinutes'] == budget and (not name.startswith('frontierBudget/') or r['set'] == 'frontier')]
    if 'Residual/' in name:
        model, sign = name.split('Residual/')
        return [r for r in rows if r[model + 'ResidualSign'] == sign]
    return [r for r in rows if r[name]]

for name, summary in report['cohorts'].items():
    group = select(name)
    assert summary['cases'] == len(group) and summary['caseIds'] == [r['id'] for r in group]
    assert summary['sensitivities'] == sum(r['valhallaMinutes'] is not None for r in group)
    assert sum(summary['statusCounts'].values()) == len(group) and summary['unboundedOrMissing'] == 0
    for status, count in summary['statusCounts'].items():
        assert count == sum(r['lengthStatus'] == status for r in group)
    for field, expected in summary['metrics'].items():
        values = sorted(r[field] for r in group)
        size = len(values)
        median = (values[(size - 1) // 2] + values[size // 2]) / 2 if size else None
        assert expected == {'available': size, 'missing': 0, 'minimum': values[0] if size else None,
                            'median': median, 'maximum': values[-1] if size else None}
assert report['ledger'] == [{'id': r['id'], 'status': 'bounded', 'lengthStatus': r['lengthStatus']} for r in rows]
assert report['routingQueries'] == report['providerRequests'] == 0 and not report['runtimeChanged']
analysis = {'analysisPlanSha256': digest(folder / 'analysis-plan.json'),
            'independentCostsOccurrencesDistanceBoundsAndCohortsAudit': True,
            'cases': 83, 'sensitivities': 35, 'cohorts': len(report['cohorts']),
            'transitionsChecked': edge_count, 'sourceOccurrences': source_count, 'baseOccurrences': base_count,
            'bounded': 83, 'unboundedOrMissing': 0,
            'statusCounts': report['cohorts']['all']['statusCounts'],
            'newMissStatusCounts': report['cohorts']['newMissVsSource']['statusCounts'],
            'persistentMissStatusCounts': report['cohorts']['persistentSourceMiss']['statusCounts'],
            'scope': 'Stored unbuffered model-weight distances and saved decoded ORS lengths, not true route geometry or causal speeds.'}
with (folder / 'analysis.json').open('x') as stream:
    stream.write(json.dumps(analysis, indent=2) + '\n')
print(json.dumps(analysis, indent=2))

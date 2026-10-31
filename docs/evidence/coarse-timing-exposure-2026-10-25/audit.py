"""Independent stored join/cohort audit; does not import the producer or load a graph."""
import gzip
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())
hash_file = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
close = lambda a, b: abs(a - b) < 1e-8
plan = load(folder / 'analysis-plan.json')
for path, expected in plan['inputs'].items():
    assert hash_file(repo / path) == expected, path
recipe = load(folder / 'plan.json')
report = load(folder / 'report.json')
assert report['planSha256'] == hash_file(folder / 'plan.json')
source = lambda name: load(repo / recipe['files'][name])
control = {r['id']: r for r in source('control')['rows']}
paths = {r['id']: r for r in source('paths')['rows']}
base = {r['id']: r for r in source('base')['rows']}
edges = {r['id']: r for r in json.loads(gzip.decompress((repo / recipe['files']['baseEdges']).read_bytes()))}
comparison = {r['set'] + '/' + r['id']: r for r in source('comparison')['normalizedRows']}
rows = report['rows']
assert len(rows) == len(control) == len(paths) == len(base) == len(edges) == len(comparison) == 83
assert {r['id'] for r in rows} == set(control) == set(paths) == set(base) == set(edges) == set(comparison)
assert sum(r['valhallaMinutes'] is not None for r in rows) == 35
speeds = ('55', '85', '90', '105')
coverage = ('censusWithin1KmOfOrs', 'censusWithin3KmOfOrs',
            'orsWithin1KmOfCensusSubset', 'orsWithin3KmOfCensusSubset')
def residual_sign(value):
    if abs(value) <= 1e-8:
        return 'equal'
    return 'slower' if value > 0 else 'faster'

for r in rows:
    key = r['id']
    c, p, b, a = control[key], paths[key], base[key], comparison[key]
    assert r['set'] == c['set'] == p['set'] == b['set'] == a['set']
    assert r['budgetMinutes'] == c['budgetMinutes'] == a['budgetMinutes']
    assert r['valhallaMinutes'] == c['valhallaMinutes'] == a['valhallaMinutes']
    assert r['referenceMinutes'] == c['referenceMinutes'] == a['referenceMinutes']
    for original, joined in [('oldSourceSignedErrorMinutes', 'oldSignedErrorMinutes'),
                              ('actualSignedErrorMinutes', 'currentSignedErrorMinutes')]:
        assert r[joined] == c[original]
    assert r['oldResidualSign'] == residual_sign(r['oldSignedErrorMinutes'])
    assert r['currentResidualSign'] == residual_sign(r['currentSignedErrorMinutes'])
    source_minutes = {s: p['classes'].get(s, {}).get('sourceKm', 0) / int(s) * 60 for s in speeds}
    for edge in edges[key]['edges']:
        source_minutes[str(edge['speedKph'])] += edge['sourceRoadMinutes']
    for speed in speeds:
        assert close(source_minutes[speed], r['sourceMinutesByClass'][speed])
        assert close(source_minutes[speed], c['sourceByClass'].get(speed, 0))
        if r['sourceMinutes']:
            assert close(r['sourceSharesByClass'][speed], source_minutes[speed] / sum(source_minutes.values()))
        else:
            assert r['sourceSharesByClass'][speed] is None
    assert close(sum(source_minutes.values()), r['sourceMinutes'])
    connector = sum(g['connectorMinutes'] for g in b['groups'].values())
    base_rounding = sum(g['roundingMinutes'] for g in b['groups'].values())
    detailed_rounding = p['costs']['detailedCensusMinutes'] - sum(
        v['sourceKm'] / int(k) * 60 for k, v in p['classes'].items())
    assert close(connector, r['baseConnectorMinutes'])
    assert close(base_rounding, r['baseRoundingMinutes'])
    assert close(detailed_rounding, r['detailedRoundingMinutes'])
    assert close(r['sourceMinutes'] + connector + base_rounding + detailed_rounding,
                 r['oldComponents']['road'])
    assert r['oldComponents'] == c['oldComponents']
    for field in ['localMinutes', 'transferMinutes']:
        assert close(r[field], c['oldComponents'][field.removesuffix('Minutes')])
    assert close(r['endpointMinutes'], c['oldComponents']['origin'] + c['oldComponents']['destination'])
    for field in [*coverage, 'detailedCensusTimeShare', 'detailedCensusSourceKm', 'detailedEdges']:
        assert r[field] == p[field]
    assert (r['coverageStatus'] == 'no_full_census') == (p['detailedEdges'] == 0)
    for field in ['newMissVsV9', 'newMissVsSource', 'persistentSourceMiss', 'originalRegressionGateExceeded']:
        assert r[field] == c[field]

def choose(name):
    if name == 'all':
        return rows
    if name in ['frontier', 'original', 'regional']:
        return [r for r in rows if r['set'] == name]
    if name.startswith('budget/') or name.startswith('frontierBudget/'):
        budget = int(name.split('/')[1])
        return [r for r in rows if r['budgetMinutes'] == budget and
                (not name.startswith('frontierBudget/') or r['set'] == 'frontier')]
    if 'Residual/' in name:
        model, sign = name.split('Residual/')
        return [r for r in rows if r[model + 'ResidualSign'] == sign]
    return [r for r in rows if r[name]]

def check_distribution(expected, values):
    valid = sorted(v for v in values if v is not None)
    size = len(valid)
    middle = (valid[(size - 1) // 2] + valid[size // 2]) / 2 if size else None
    assert expected == {'available': size, 'missing': len(values) - size,
                        'minimum': valid[0] if size else None, 'median': middle,
                        'maximum': valid[-1] if size else None}

for name, summary in report['cohorts'].items():
    group = choose(name)
    assert summary['cases'] == len(group)
    assert summary['caseIds'] == [r['id'] for r in group]
    assert summary['sensitivities'] == sum(r['valhallaMinutes'] is not None for r in group)
    assert summary['noFullCensus'] == sum(r['coverageStatus'] == 'no_full_census' for r in group)
    for field, expected in summary['metrics'].items():
        check_distribution(expected, [r[field] for r in group])
    for field in ['sourceMinutesByClass', 'sourceSharesByClass']:
        for speed, expected in summary[field].items():
            check_distribution(expected, [r[field][speed] for r in group])
assert report['coverageLedger'] == [{'id': r['id'], 'status': r['coverageStatus']} for r in rows]
assert sum(r['coverageStatus'] == 'no_full_census' for r in rows) == 3
assert report['routingQueries'] == report['providerRequests'] == 0 and not report['runtimeChanged']
analysis = {'analysisPlanSha256': hash_file(folder / 'analysis-plan.json'),
            'independentIdentifiersSourceComponentsAndCohortsAudit': True,
            'cases': 83, 'sensitivities': 35, 'cohorts': len(report['cohorts']),
            'coverageAvailable': 80, 'noFullCensus': 3,
            'oldResidualCounts': {s: len(choose('oldResidual/' + s)) for s in ['faster', 'equal', 'slower']},
            'currentResidualCounts': {s: len(choose('currentResidual/' + s)) for s in ['faster', 'equal', 'slower']},
            'allOriginalGatesAndPriorDecisionsUnchanged': True,
            'scope': 'Descriptive saved-output audit only; no graph/model load, fit, query or accuracy qualification.'}
with (folder / 'analysis.json').open('x') as stream:
    stream.write(json.dumps(analysis, indent=2) + '\n')
print(json.dumps(analysis, indent=2))

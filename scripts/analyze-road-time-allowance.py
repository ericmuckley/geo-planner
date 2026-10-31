"""Post-result audit/description of saved outputs; never executes a route search."""
import gzip
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

source, output = map(Path, sys.argv[1:])
root = Path('docs/evidence/coarse-road-time-allowance-2026-10-25')
load = lambda path: json.loads(path.read_text())
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
plan = load(root / 'analysis-plan.json')
for name, expected in plan['inputs'].items():
    assert digest(Path(name)) == expected, name
raw = load(source / 'comparison.json')
execution = load(source / 'execution-plan.json')
assert digest(source / 'execution-plan.json') == raw['planSha256']
saved = load(Path(execution['baseline']))
identity = lambda row: f"{row['set']}/{row['id']}"
baseline = {identity(row): row for row in saved['rows']}
assert len(baseline) == len(raw['rows']) == 83
paths_raw = (source / 'paths.json.gz').read_bytes()
assert hashlib.sha256(paths_raw).hexdigest() == raw['pathSha256']
paths = {row['id']: row for row in json.loads(gzip.decompress(paths_raw))}
assert len(paths) == 83
rows = []
for row in raw['rows']:
    key = identity(row)
    before = baseline[key]
    for name in ['origin', 'destination', 'budgetMinutes', 'referenceMinutes', 'valhallaMinutes']:
        assert row[name] == before[name], (key, name)
    assert row['baseline'] == before['candidate'], key
    path = paths[key]
    assert path['components'] == row['candidate']['pathComponents']
    assert path['pointMinutes'] == row['candidate']['pointMinutes']
    for model in ['baseline', 'candidate']:
        measured = row[model]
        assert measured['pointMinutes'] is not None and math.isfinite(measured['pointMinutes'])
        assert abs(math.fsum(measured['pathComponents'].values()) - measured['pointMinutes']) < 1e-8
        expected = ('ambiguous' if abs(row['referenceMinutes'] - row['budgetMinutes']) <= 5 else
                    'correct' if measured['predictedReachable'] == (row['referenceMinutes'] < row['budgetMinutes']) else
                    'falseReachable' if measured['predictedReachable'] else 'missedReachable')
        assert measured['classification'] == expected, (key, model)
    assert all(edge['minutes'] > 0 for edge in path['edges'])
    if not path['direct']:
        assert abs(math.fsum(edge['minutes'] for edge in path['edges']) -
                   math.fsum(row['candidate']['pathComponents'][name] for name in ['road', 'local', 'transfer'])) < 1e-8
    else:
        assert not path['edges']
    # Normalize the explicit v9/candidate objects; inherited scalar fields are absent.
    assert not any(name in row for name in ["baselinePointMinutes", "baselineErrorMinutes", "candidateErrorMinutes"])
    normalized = {name: row[name] for name in ['id', 'set', 'origin', 'destination', 'budgetMinutes',
                                              'referenceMinutes', 'valhallaMinutes', 'baseline', 'candidate']}
    normalized['baselineErrorMinutes'] = row['baseline']['pointMinutes'] - row['referenceMinutes']
    normalized['candidateErrorMinutes'] = row['candidate']['pointMinutes'] - row['referenceMinutes']
    normalized['pointTimeChangeMinutes'] = row['candidate']['pointMinutes'] - row['baseline']['pointMinutes']
    normalized['absoluteErrorChangeMinutes'] = abs(normalized['candidateErrorMinutes']) - abs(normalized['baselineErrorMinutes'])
    assert abs(normalized['absoluteErrorChangeMinutes'] - row['absoluteErrorChangeMinutes']) < 1e-8
    normalized['fullCensusEdgeMinutes'] = math.fsum(e['minutes'] for e in path['edges'] if 'arc' in e)
    normalized['baseRoadEdgeMinutes'] = math.fsum(e['minutes'] for e in path['edges'] if e['kind'] == 'road' and 'arc' not in e)
    normalized['componentChangesMinutes'] = {name: row['candidate']['pathComponents'][name] - row['baseline']['pathComponents'][name]
                                             for name in row['baseline']['pathComponents']}
    rows.append(normalized)
assert {identity(row) for row in rows} == set(baseline)

def summary(items, model, reference='referenceMinutes'):
    errors = sorted(abs(row[model]['pointMinutes'] - row[reference]) for row in items)
    return {'count': len(items), 'meanAbsoluteMinutes': statistics.fmean(errors),
            'meanSignedMinutes': statistics.fmean(row[model]['pointMinutes'] - row[reference] for row in items),
            'medianAbsoluteMinutes': statistics.median(errors),
            'p90AbsoluteMinutes': errors[math.ceil(len(errors) * 0.9) - 1],
            'classifications': {label: sum(row[model]['classification'] == label for row in items)
                                for label in ['correct', 'falseReachable', 'missedReachable', 'ambiguous']}}
paired = lambda items: {model: summary(items, model) for model in ['baseline', 'candidate']}
overall = paired(rows)
groups = {name: [row for row in rows if row['set'] == name] for name in ['frontier', 'original', 'regional']}
sets = {name: paired(items) for name, items in groups.items()}
horizons = {str(h): paired([row for row in groups['frontier'] if row['budgetMinutes'] == h]) for h in [360, 600, 720]}
sensitivity = {name: {model: summary(items, model, 'valhallaMinutes') for model in ['baseline', 'candidate']}
               for name, items in groups.items() if name != 'frontier'}
limits = execution['gates']
within = lambda value, maximum: value <= maximum + 1e-10
f = sets['frontier']['candidate']
older = groups['original'] + groups['regional']
max_frontier = max(row['absoluteErrorChangeMinutes'] for row in groups['frontier'])
max_older = max(row['absoluteErrorChangeMinutes'] for row in older)
gates = {
    'overallMean': within(overall['candidate']['meanAbsoluteMinutes'], limits['overallMaeMaximum']),
    'frontierMean': within(f['meanAbsoluteMinutes'], limits['frontierMaeMaximum']),
    'originalMean': within(sets['original']['candidate']['meanAbsoluteMinutes'], limits['originalMaeMaximum']),
    'regionalMean': within(sets['regional']['candidate']['meanAbsoluteMinutes'], limits['regionalMaeMaximum']),
    'frontierP90': within(f['p90AbsoluteMinutes'], limits['frontierP90Maximum']),
    'horizonMeans': all(within(v['candidate']['meanAbsoluteMinutes'], v['baseline']['meanAbsoluteMinutes']) for v in horizons.values()),
    'horizonP90': all(within(v['candidate']['p90AbsoluteMinutes'], v['baseline']['p90AbsoluteMinutes']) for v in horizons.values()),
    'frontierWorstRegression': within(max_frontier, limits['maximumIndividualAbsoluteErrorIncreaseMinutes']['frontier']),
    'olderWorstRegression': within(max_older, limits['maximumIndividualAbsoluteErrorIncreaseMinutes']['older']),
    'frontierDefiniteClassificationErrors': f['classifications']['falseReachable'] + f['classifications']['missedReachable'] <= limits['maximumFrontierDefiniteErrors'],
    'frontierMissed': f['classifications']['missedReachable'] <= limits['maximumFrontierMissed'],
    'twelveHourMissed': horizons['720']['candidate']['classifications']['missedReachable'] <= limits['maximum12hMissed'],
    'all83Paired': len(rows) == 83,
    'all166PathSums': True,
    'all35StillShaded': len(older) == 35 and all(row['candidate']['predictedReachable'] for row in older),
    'frontierMedian': within(f['medianAbsoluteMinutes'], limits['frontierMedianMaximum']),
    'overallP90NoWorse': within(overall['candidate']['p90AbsoluteMinutes'], overall['baseline']['p90AbsoluteMinutes']),
    'originalP90NoWorse': within(sets['original']['candidate']['p90AbsoluteMinutes'], sets['original']['baseline']['p90AbsoluteMinutes']),
    'regionalP90NoWorse': within(sets['regional']['candidate']['p90AbsoluteMinutes'], sets['regional']['baseline']['p90AbsoluteMinutes']),
    'valhallaOriginalNoWorse': within(sensitivity['original']['candidate']['meanAbsoluteMinutes'], sensitivity['original']['baseline']['meanAbsoluteMinutes']),
    'valhallaRegionalNoWorse': within(sensitivity['regional']['candidate']['meanAbsoluteMinutes'], sensitivity['regional']['baseline']['meanAbsoluteMinutes']),
}
assert gates == raw['gates']
assert all(gates.values()) == raw['accuracyGatesPassed']
for key in ['meanAbsoluteMinutes', 'medianAbsoluteMinutes', 'p90AbsoluteMinutes']:
    for model in ['baseline', 'candidate']:
        assert abs(overall[model][key] - raw['overall'][model][key]) < 1e-8
diagnosis = {
    'fasterPointPredictions': sum(row['pointTimeChangeMinutes'] < -1e-8 for row in rows),
    'slowerPointPredictions': sum(row['pointTimeChangeMinutes'] > 1e-8 for row in rows),
    'improvedAbsoluteErrors': sum(row['absoluteErrorChangeMinutes'] < -1e-8 for row in rows),
    'regressedAbsoluteErrors': sum(row['absoluteErrorChangeMinutes'] > 1e-8 for row in rows),
    'meanPointTimeChangeMinutes': statistics.fmean(row['pointTimeChangeMinutes'] for row in rows),
    'meanComponentChangesMinutes': {name: statistics.fmean(row['componentChangesMinutes'][name] for row in rows)
                                    for name in rows[0]['componentChangesMinutes']},
    'fullCensusEdgeMinutesShareOfAllCandidateTime': math.fsum(row['fullCensusEdgeMinutes'] for row in rows) /
                                                  math.fsum(row['candidate']['pointMinutes'] for row in rows),
    'scope': 'Post-result descriptive path accounting, not causal isolation. Origin/destination attachments combine partial-source/base/local costs; full-Census share excludes those attachments. No new routing, physical/source qualification or accuracy tuning.'}
timings = raw['originResults']
result = {'independentGateAnd166ComponentSumAudit': True, 'all83And35Retained': True,
          'accuracyGatesPassed': all(gates.values()), 'gates': gates,
          'overall': overall, 'sets': sets, 'byHorizon': horizons, 'valhallaSensitivity': sensitivity,
          'worstRegressions': {'frontier': max_frontier, 'older': max_older}, 'diagnosis': diagnosis,
          'diagnosticSearchMsRange': [min(r['searchMs'] for r in timings), max(r['searchMs'] for r in timings)],
          'worstRegressionsRows': sorted(rows, key=lambda row: row['absoluteErrorChangeMinutes'], reverse=True)[:10],
          'normalizedRows': rows, 'rawScalarFieldNote': 'The versioned runner exports only current case/model fields. No inherited scalar error fields remain. Independent errors derive from explicit v9/cost-candidate objects.',
          'outboundCalls': raw['outboundCalls'], 'runtimeChanged': False}
with output.open('x') as stream:
    stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
print(json.dumps({key: result[key] for key in ['independentGateAnd166ComponentSumAudit', 'accuracyGatesPassed', 'overall', 'worstRegressions', 'diagnosis', 'diagnosticSearchMsRange']}, indent=2))

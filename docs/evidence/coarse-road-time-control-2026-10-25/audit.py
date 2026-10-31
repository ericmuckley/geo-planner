"""Independent saved-output arithmetic audit; no model load or route search."""
import gzip
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())
unpack = lambda path: json.loads(gzip.decompress(path.read_bytes()))
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
close = lambda a, b: abs(a - b) < 1e-8

plan = load(folder / 'analysis-plan.json')
for name, expected in plan['inputs'].items():
    assert digest(repo / name) == expected, name
control_plan = load(folder / 'plan.json')
report = load(folder / 'report.json')
rows = report['rows']
old = {r['id']: r for r in unpack(repo / control_plan['oldPaths'])}
current = {r['id']: r for r in unpack(repo / control_plan['currentPaths'])}
edges = {r['id']: r for r in unpack(folder / 'edge-audit.json.gz')}
comparison = {r['set'] + '/' + r['id']: r
              for r in load(repo / control_plan['comparison'])['rows']}
assert len(rows) == len(old) == len(current) == len(edges) == len(comparison) == 83
assert {r['id'] for r in rows} == set(old) == set(current) == set(edges) == set(comparison)
assert sum(r['valhallaMinutes'] is not None for r in rows) == 35
assert report['planSha256'] == digest(folder / 'plan.json')
assert report['routeSearches'] == report['outboundCalls'] == 0
assert not report['runtimeChanged'] and report['sourceRoadTimeFactor'] == 1.1

components_checked = 0
edges_checked = 0
for r in rows:
    key = r['id']
    e = edges[key]
    sample = comparison[key]
    for label, path in [('old', old[key]), ('actual', current[key])]:
        assert all(close(v, r[label + 'Components'][k]) for k, v in path['components'].items())
        captured = path['edges']
        replayed = e[label + 'Edges']
        assert len(captured) == len(replayed)
        for a, b in zip(captured, replayed):
            for field in ['from', 'target', 'kind', 'arc']:
                assert a.get(field) == b.get(field), (key, field)
            assert close(a['minutes'], b['minutes'])
    assert len(e['oldEdges']) == len(e['heldEdges'])
    for a, b in zip(e['oldEdges'], e['heldEdges']):
        assert all(a.get(k) == b.get(k) for k in ['from', 'target', 'arc'])
        assert b['minutes'] >= a['minutes'] - 1e-8
    for label, total_key in [('old', 'oldSourceMinutes'),
                             ('held', 'heldStateMinutes'),
                             ('actual', 'actualAllowanceMinutes')]:
        component = r[label + 'Components']
        sums = {'road': 0., 'local': 0., 'transfer': 0.}
        cost = component['origin']
        maximum = cost
        previous = None
        for edge in e[label + 'Edges']:
            assert edge['minutes'] > 0
            if previous is not None:
                assert previous == edge['from']
            previous = edge['target']
            sums[edge['kind']] += edge['minutes']
            cost += edge['minutes']
            maximum = max(maximum, cost)
            edges_checked += 1
        assert all(close(sums[k], component[k]) for k in sums)
        assert close(sum(component.values()), r[total_key])
        assert close(cost + component['destination'], r[total_key])
        components_checked += 1
        if label == 'held':
            assert close(maximum, r['heldStatePrefixMaximum'])
            assert r['boundApplied'] == (maximum <= control_plan['diagnosticCapMinutes'] + 1e-8)
            assert r['capLimited'] != r['boundApplied']
        else:
            assert maximum <= control_plan['diagnosticCapMinutes'] + 1e-8
    assert close(r['oldSourceMinutes'], old[key]['pointMinutes'])
    assert close(r['actualAllowanceMinutes'], current[key]['pointMinutes'])
    assert close(r['actualAllowanceMinutes'], sample['candidate']['pointMinutes'])
    assert close(r['directCostShift'], r['heldStateMinutes'] - r['oldSourceMinutes'])
    assert close(r['pathChoiceBenefit'], r['heldStateMinutes'] - r['actualAllowanceMinutes'])
    assert close(r['actualCostShift'], r['actualAllowanceMinutes'] - r['oldSourceMinutes'])
    assert close(r['actualCostShift'], r['directCostShift'] - r['pathChoiceBenefit'])
    if r['boundApplied']:
        assert r['pathChoiceBenefit'] >= -1e-8
    assert close(r['fullRoadSourceMinutes'], sum(r['sourceByClass'].values()))
    assert close(r['roadAllowanceShift'], .1 * r['fullRoadSourceMinutes'])
    assert close(r['directCostShift'], sum(r[k] for k in [
        'roadAllowanceShift', 'baseRoundingShift', 'samePairAlternativeShift', 'endpointShift']))
    assert close(r['endpointShift'], r['componentShifts']['origin'] + r['componentShifts']['destination'])
    for k in r['oldComponents']:
        assert close(r['componentShifts'][k], r['heldComponents'][k] - r['oldComponents'][k])
    assert close(r['oldSourceSignedErrorMinutes'], r['oldSourceMinutes'] - r['referenceMinutes'])
    assert close(r['actualSignedErrorMinutes'], r['actualAllowanceMinutes'] - r['referenceMinutes'])
    missed = sample['candidate']['classification'] == 'missedReachable'
    old_missed = control_plan['oldClassifications'][key] == 'missedReachable'
    assert r['newMissVsV9'] == (missed and sample['baseline']['classification'] != 'missedReachable')
    assert r['newMissVsSource'] == (missed and not old_missed)
    assert r['persistentSourceMiss'] == (missed and old_missed)
    limit = 20 if r['set'] == 'frontier' else 5
    assert r['originalRegressionGateExceeded'] == (sample['absoluteErrorChangeMinutes'] > limit + 1e-10)
    same = (len(e['oldEdges']) == len(e['actualEdges']) and all(
        all(a.get(k) == b.get(k) for k in ['from', 'target', 'arc'])
        for a, b in zip(e['oldEdges'], e['actualEdges'])))
    assert r['sameStateSequence'] == same
    assert r['withinStateKindChanges'] == sum(a['kind'] != b['kind']
        for a, b in zip(e['oldEdges'], e['heldEdges']))

cohorts = {'all': rows, **{s: [r for r in rows if r['set'] == s]
                         for s in ['frontier', 'original', 'regional']},
           **{k: [r for r in rows if r[k]] for k in ['newMissVsV9', 'newMissVsSource',
                 'persistentSourceMiss', 'originalRegressionGateExceeded']}}
mean_fields = {'meanDirectCostShift': 'directCostShift',
               'meanPathChoiceBenefit': 'pathChoiceBenefit',
               'meanActualCostShift': 'actualCostShift',
               'meanOldSourceSignedError': 'oldSourceSignedErrorMinutes',
               'meanActualSignedError': 'actualSignedErrorMinutes',
               'meanRoadAllowanceShift': 'roadAllowanceShift',
               'meanBaseRoundingShift': 'baseRoundingShift',
               'meanSamePairAlternativeShift': 'samePairAlternativeShift',
               'meanEndpointShift': 'endpointShift'}
for name, group in cohorts.items():
    summary = report['summary'][name]
    assert summary['cases'] == len(group)
    for output, field in mean_fields.items():
        assert close(summary[output], sum(r[field] for r in group) / len(group))
    assert summary['stateSequencesChanged'] == sum(not r['sameStateSequence'] for r in group)
    assert summary['capLimited'] == sum(r['capLimited'] for r in group)
    assert summary['nontrivialPathChoiceBenefit'] == sum(r['pathChoiceBenefit'] > 1e-8 for r in group)
assert report['boundVerified'] == sum(r['boundApplied'] for r in rows)
assert report['capLimited'] == sum(r['capLimited'] for r in rows)
assert {r['id']: r['status'] for r in report['ledger']} == {
    r['id']: 'cap_limited' if r['capLimited'] else 'bound_verified' for r in rows}

misses = cohorts['newMissVsSource']
all_summary = report['summary']['all']
analysis = {
    'analysisPlanSha256': digest(folder / 'analysis-plan.json'),
    'independentArithmeticAndCapturedIdentityAudit': True,
    'cases': 83, 'valhallaSensitivities': 35,
    'componentTotalsChecked': components_checked,
    'transitionPricesSummed': edges_checked,
    'boundVerified': report['boundVerified'], 'capLimited': report['capLimited'],
    'summary': report['summary'],
    'maximumPathChoiceBenefitMinutes': max(r['pathChoiceBenefit'] for r in rows),
    'maximumHeldStatePrefixMinutes': max(r['heldStatePrefixMaximum'] for r in rows),
    'fractionDirectCostNotOffsetByPathChoice':
        1 - all_summary['meanPathChoiceBenefit'] / all_summary['meanDirectCostShift'],
    'newMissesAlreadySlowerThanOrs': sum(r['oldSourceSignedErrorMinutes'] > 0 for r in misses),
    'newMissesPreviouslyFasterThanOrs': sum(r['oldSourceSignedErrorMinutes'] < 0 for r in misses),
    'oldSourceFasterThanOrs': sum(r['oldSourceSignedErrorMinutes'] < 0 for r in rows),
    'allowanceFasterThanOrs': sum(r['actualSignedErrorMinutes'] < 0 for r in rows),
    'newMissRows': misses,
    'scope': 'Saved-output descriptive audit, not a new routing/accuracy/traffic/national qualification.'
}
with (folder / 'analysis.json').open('x') as stream:
    stream.write(json.dumps(analysis, indent=2) + '\n')
print(json.dumps({k: v for k, v in analysis.items() if k not in ['newMissRows', 'summary']}, indent=2))

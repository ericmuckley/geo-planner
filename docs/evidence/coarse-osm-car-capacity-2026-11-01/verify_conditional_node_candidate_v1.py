"""Independently recompute the frozen candidate's numerical gates from saved rows."""
import json
import math

from verify_incomplete_node_inventory_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def summary(rows, model, reference='referenceMinutes'):
    errors = sorted(abs(r[model]['pointMinutes'] - r[reference]) for r in rows
                    if r[model]['pointMinutes'] is not None)
    if not errors:
        return dict(meanAbsoluteMinutes=None, medianAbsoluteMinutes=None, p90AbsoluteMinutes=None)
    n = len(errors)
    return dict(meanAbsoluteMinutes=math.fsum(errors) / n,
                medianAbsoluteMinutes=(errors[(n - 1) // 2] + errors[n // 2]) / 2,
                p90AbsoluteMinutes=errors[math.ceil(n * 0.9) - 1])


def recompute_gates(rows):
    groups = {name: [r for r in rows if r['set'] == name]
              for name in ('original', 'regional', 'frontier')}
    frontier = groups['frontier']
    older = groups['original'] + groups['regional']

    def within(value, maximum):
        return value is not None and maximum is not None and math.isfinite(value) and value <= maximum + 1e-10

    def compare(items, metric, ratio=1, reference='referenceMinutes'):
        after = summary(items, 'candidate', reference)[metric]
        before = summary(items, 'baseline', reference)[metric]
        return within(after, None if before is None else before * ratio)

    def misses(items):
        return sum(r['candidate']['classification'] == 'missedReachable' for r in items)

    def losses(items):
        return max((r['absoluteErrorChangeMinutes'] if r['absoluteErrorChangeMinutes'] is not None else math.inf)
                   for r in items)

    horizon = {h: [r for r in frontier if r['budgetMinutes'] == h] for h in (360, 600, 720)}
    return dict(
        overallMean=compare(rows, 'meanAbsoluteMinutes', .9),
        frontierMean=compare(frontier, 'meanAbsoluteMinutes', .9),
        originalMean=compare(groups['original'], 'meanAbsoluteMinutes'),
        regionalMean=compare(groups['regional'], 'meanAbsoluteMinutes'),
        originalP90=compare(groups['original'], 'p90AbsoluteMinutes'),
        regionalP90=compare(groups['regional'], 'p90AbsoluteMinutes'),
        frontierMedian=compare(frontier, 'medianAbsoluteMinutes'),
        frontierP90=compare(frontier, 'p90AbsoluteMinutes'),
        horizonMeans=all(compare(items, 'meanAbsoluteMinutes') for items in horizon.values()),
        horizonP90=all(compare(items, 'p90AbsoluteMinutes') for items in horizon.values()),
        valhallaOriginalMean=compare(groups['original'], 'meanAbsoluteMinutes', reference='valhallaMinutes'),
        valhallaRegionalMean=compare(groups['regional'], 'meanAbsoluteMinutes', reference='valhallaMinutes'),
        frontierWorstRegression=losses(frontier) <= 20 + 1e-10,
        olderWorstRegression=losses(older) <= 5 + 1e-10,
        frontierDefiniteErrors=sum(r['candidate']['classification'] in ('falseReachable', 'missedReachable')
                                  for r in frontier) <= 12,
        frontierMissed=misses(frontier) <= 2,
        twelveHourMissed=misses(horizon[720]) <= 1,
        all83Finite=len(rows) == 83 and all(r['candidate']['pointMinutes'] is not None for r in rows),
        all35OlderShaded=len(older) == 35 and all(r['candidate']['predictedReachable'] for r in older),
    )


def verify():
    result = previous()
    report = stage('conditional-node-evaluation')
    assert report['recipeSha256'] == sha(HERE / 'conditional-node-candidate-plan-v1.json')
    rows = report['rows']
    assert len(rows) == report['originalCases'] == 83 and report['valhallaCases'] == 35
    old = load(HERE / 'passable-node-evaluation-raw-v1/report.json')
    prior = {r['id']: r for r in old['rows']}
    assert len({r['id'] for r in rows}) == 83 and set(prior) == {r['id'] for r in rows}
    for row in rows:
        for name in ('set', 'origin', 'destination', 'budgetMinutes', 'referenceMinutes', 'valhallaMinutes', 'baseline'):
            assert row[name] == prior[row['id']][name], (row['id'], name)
        predicted = row['candidate']['pointMinutes']
        baseline = row['baseline']['pointMinutes']
        expected = None if predicted is None or baseline is None else (
            abs(predicted - row['referenceMinutes']) - abs(baseline - row['referenceMinutes']))
        if expected is None:
            assert row['absoluteErrorChangeMinutes'] is None
        else:
            assert math.isclose(row['absoluteErrorChangeMinutes'], expected, rel_tol=0, abs_tol=1e-10)
        shaded = row['candidate']['predictedReachable']
        classification = ('ambiguous' if abs(row['referenceMinutes'] - row['budgetMinutes']) <= 5
                          else 'correct' if shaded == (row['referenceMinutes'] < row['budgetMinutes'])
                          else 'falseReachable' if shaded else 'missedReachable')
        assert row['candidate']['classification'] == classification
    for name, selected in [('overall', rows), *[(k, [r for r in rows if r['set'] == k])
                                               for k in ('original', 'regional', 'frontier')]]:
        recorded = report['overall'] if name == 'overall' else report['sets'][name]
        for model in ('baseline', 'candidate'):
            for metric, value in summary(selected, model).items():
                assert value is None and recorded[model][metric] is None or (
                    value is not None and math.isclose(value, recorded[model][metric], rel_tol=0, abs_tol=1e-10))
    gates = recompute_gates(rows)
    assert gates == report['gates'] and all(gates.values()) == report['numericalGatesPassed']
    assert not report['candidateAdmitted'] and not report['frozenLocalGridOrMapsReused']
    assert report['everyEndpointRecomputed'] and report['validatedInitialChoices'] == 10403
    assert report['productionDisplays'] == 37 and report['diagnosticDisplays'] == report['origins'] == 21
    assert report['contextStates'] == 34253 and report['contextDataBackingBytes'] == 1788678
    assert report['providerRequests'] == 0 and report['waterPacketObservationsCompared'] == 1002
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers']
    assert report['retainedBackingGatePassed'] == (report['retainedBackingBytes'] <= 162238546)
    record = load(HERE / 'conditional-node-evaluation-closed-v1.json')
    maps = []
    for phase in report['phases']:
        assert phase['diagnostic']['restorationChecked']
        for output in [phase['diagnostic']['output'], *[p['output'] for p in phase['productions']]]:
            assert all(record['roster'][output['filename']][k] == output[k] for k in ('bytes', 'sha256'))
            maps.append(output['filename'])
    assert len(maps) == len(set(maps)) == 58
    total = result['newUniqueClosedAllocationBytes'] + record['usage']['conservativeAllocatedBytes']
    return {**result, 'status': 'conditional_node_full_candidate_original_gates_independently_recomputed',
            'registeredClosedRoots': 365, 'newUniqueClosedAllocationBytes': total,
            'newFullCandidateScorePending': False,
            'meanAbsoluteMinutes': report['overall']['candidate']['meanAbsoluteMinutes'],
            'previousPassableCandidateMeanAbsoluteMinutes': old['overall']['candidate']['meanAbsoluteMinutes'],
            'failedOriginalGates': sorted(k for k, value in gates.items() if not value),
            'all83Finite': gates['all83Finite'], 'all58MapsFresh': True,
            'retainedBackingBytes': report['retainedBackingBytes'],
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

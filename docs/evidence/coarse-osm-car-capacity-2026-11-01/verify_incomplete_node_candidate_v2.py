"""Independently recompute the frozen candidate's numerical gates from saved rows."""
import json
import math

from verify_incomplete_node_candidate_stop_v1 import verify as previous
from verify_conditional_node_candidate_v1 import summary, recompute_gates
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    report = stage('incomplete-node-evaluation-v2')
    assert report['recipeSha256'] == sha(HERE / 'incomplete-node-candidate-plan-v2.json')
    rows = report['rows']
    assert len(rows) == report['originalCases'] == 83 and report['valhallaCases'] == 35
    old = load(HERE / 'conditional-node-evaluation-raw-v1/report.json')
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
    assert report['endpointArtifactsIdenticalToPrevious'] == 79 and not report['roadArrivalTimeIncreases']
    assert report['productionDisplays'] == 37 and report['diagnosticDisplays'] == report['origins'] == 21
    assert report['contextStates'] == 34253 and report['contextDataBackingBytes'] == 1788678
    assert report['providerRequests'] == 0 and report['waterPacketObservationsCompared'] == 1002
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers']
    assert report['retainedBackingGatePassed'] == (report['retainedBackingBytes'] <= 162238546)
    record = load(HERE / 'incomplete-node-evaluation-v2-closed-v1.json')
    maps = []
    for phase in report['phases']:
        assert phase['diagnostic']['restorationChecked']
        for output in [phase['diagnostic']['output'], *[p['output'] for p in phase['productions']]]:
            assert all(record['roster'][output['filename']][k] == output[k] for k in ('bytes', 'sha256'))
            maps.append(output['filename'])
    assert len(maps) == len(set(maps)) == 58
    total = result['newUniqueClosedAllocationBytes'] + record['usage']['conservativeAllocatedBytes']
    return {**result, 'status': 'incomplete_node_v2_full_candidate_original_gates_independently_recomputed',
            'registeredClosedRoots': 374, 'newUniqueClosedAllocationBytes': total,
            'newFullCandidateScorePending': False, 'nextFullCandidateScorePending': False, 'scoreScope': 'New fully recomputed V2 incomplete-node result; the prior deadline stop remains separately preserved.',
            'meanAbsoluteMinutes': report['overall']['candidate']['meanAbsoluteMinutes'],
            'previousConditionalCandidateMeanAbsoluteMinutes': old['overall']['candidate']['meanAbsoluteMinutes'],
            'failedOriginalGates': sorted(k for k, value in gates.items() if not value),
            'all83Finite': gates['all83Finite'], 'all58MapsFresh': True,
            'retainedBackingBytes': report['retainedBackingBytes'],
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

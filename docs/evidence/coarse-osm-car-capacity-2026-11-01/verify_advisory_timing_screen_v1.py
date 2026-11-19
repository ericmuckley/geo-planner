"""Recompute the one fixed-witness advisory sensitivity; never qualify a model."""
import json
import math

from verify_current_way_source_features_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    plan = load(HERE/'advisory-timing-sensitivity-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin, name
    report = load(HERE/'advisory-timing-sensitivity-v1.json')
    assert report['recipeSha256'] == sha(HERE/'advisory-timing-sensitivity-plan-v1.json')
    candidate = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    by_id = {r['id']: r for r in candidate['rows']}
    rows = report['rows']
    assert len(rows) == len({r['id'] for r in rows}) == 83 and set(by_id) == {r['id'] for r in rows}
    for row in rows:
        original = by_id[row['id']]
        for name in ('set', 'referenceMinutes', 'valhallaMinutes'):
            assert row[name] == original[name]
        assert row['currentMinutes'] == original['candidate']['pointMinutes']
        assert row['baselineMinutes'] == original['baseline']['pointMinutes']
        assert row['fixedWitnessSensitivityMinutes'] >= row['currentMinutes']-1e-9
        assert math.isclose(row['minutesAdded'], row['fixedWitnessSensitivityMinutes']-row['currentMinutes'], rel_tol=0, abs_tol=1e-9)
        assert row['overDiagnosticHorizon'] == (row['fixedWitnessSensitivityMinutes'] > 900)
    groups = [('overall', rows, report['overall'], 'referenceMinutes')]
    groups += [(name, [r for r in rows if r['set'] == name], report['sets'][name], 'referenceMinutes') for name in ('original','regional','frontier')]
    groups += [(name, [r for r in rows if r['set'] == name], report['valhalla'][name], 'valhallaMinutes') for name in ('original','regional')]
    for _, selected, saved, reference in groups:
        assert saved['cases'] == len(selected)
        for value, key in [('baselineMinutes','baselineMeanAbsoluteMinutes'), ('currentMinutes','currentMeanAbsoluteMinutes'), ('fixedWitnessSensitivityMinutes','fixedWitnessSensitivityMeanAbsoluteMinutes')]:
            expected = math.fsum(abs(r[value]-r[reference]) for r in selected)/len(selected)
            assert math.isclose(expected, saved[key], rel_tol=0, abs_tol=1e-10)
        assert math.isclose(math.fsum(r['minutesAdded'] for r in selected)/len(selected), saved['meanMinutesAdded'], rel_tol=0, abs_tol=1e-10)
    assert not report['isCandidateEvaluation'] and not report['policyActivated'] and not report['originalGatesChanged']
    assert report['modelQueries'] == report['providerRequests'] == report['newMaps'] == 0
    return {**result, 'status': 'advisory_all83_fixed_witness_sensitivity_independently_recomputed',
            'advisorySensitivityMeanAbsoluteMinutes': report['overall']['fixedWitnessSensitivityMeanAbsoluteMinutes'],
            'advisoryOriginalSensitivityMeanAbsoluteMinutes': report['sets']['original']['fixedWitnessSensitivityMeanAbsoluteMinutes'],
            'advisoryScreenIsCandidateEvaluation': False, 'advisoryModelOrPriceActivated': False}


if __name__ == '__main__':
    print(json.dumps(verify()))

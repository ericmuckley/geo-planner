"""Compare the two fixed national results; no model evaluation or cost fitting."""
import hashlib
import json
from pathlib import Path
from statistics import mean


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    repo = Path(__file__).resolve().parents[1]
    here = repo/'docs/evidence/coarse-osm-car-capacity-2026-11-01'
    old_path, new_path = (here/name for name in ('access-candidate-evaluation-raw-v1/report.json', 'entry-evaluation-raw-v1/report.json'))
    for path, name in [(old_path, 'access-candidate-evaluation-closed-v1.json'), (new_path, 'entry-evaluation-closed-v1.json')]:
        closed = json.loads((here/name).read_bytes())
        assert sha(path) == closed['roster']['report.json']['sha256']
    old, new = (json.loads(p.read_bytes()) for p in (old_path, new_path))
    original = {r['id']: r for r in old['rows']}
    assert len(original) == len(new['rows']) == 83
    rows = []
    for row in new['rows']:
        previous = original[row['id']]
        assert row['set'] == previous['set'] and row['referenceMinutes'] == previous['referenceMinutes']
        a, b = previous['candidate']['pointMinutes'], row['candidate']['pointMinutes']
        assert (a is None) == (b is None)
        common = {'id': row['id'], 'set': row['set'], 'referenceMinutes': row['referenceMinutes'], 'previousMinutes': a, 'newMinutes': b}
        if a is None:
            rows.append({**common, 'unavailable': True})
            continue
        reference = row['referenceMinutes']
        rows.append({**common, 'unavailable': False, 'changeMinutes': b-a,
                     'signedErrorMinutes': b-reference, 'absoluteErrorChangeMinutes': abs(b-reference)-abs(a-reference)})
    finite = [r for r in rows if not r['unavailable']]
    phases = [q for p in new['phases'] if 'diagnostic' in p for q in [p['diagnostic'], *p['productions']]]
    additions = {q['stats']['maximumBackingBufferBytes']-q['fieldStats']['maximumBackingBufferBytes'] for q in phases}
    assert additions == {8548069}
    field_max = max(q['fieldStats']['maximumBackingBufferBytes'] for q in phases)
    display_max = max(q['stats']['maximumBackingBufferBytes'] for q in phases)
    assert display_max < 67108864 and new['afterLoad']['arrayBuffers'] == new['afterQueries']['arrayBuffers']
    report = {'status': 'complete_fixed_entry_candidate_comparison_no_cost_fit', 'sourceBindings': {str(p.relative_to(repo)): sha(p) for p in (old_path, new_path, Path(__file__))},
              'rows': rows, 'allCasesRetained': 83, 'finite': len(finite), 'unavailable': 83-len(finite),
              'previousMaeMinutes': mean(abs(r['previousMinutes']-r['referenceMinutes']) for r in finite),
              'newMaeMinutes': mean(abs(r['newMinutes']-r['referenceMinutes']) for r in finite),
              'changed': sum(abs(r['changeMinutes']) > 1e-8 for r in finite),
              'faster': sum(r['changeMinutes'] < -1e-8 for r in finite), 'slower': sum(r['changeMinutes'] > 1e-8 for r in finite),
              'newUnderestimates': sum(r['signedErrorMinutes'] < 0 for r in finite), 'newOverestimates': sum(r['signedErrorMinutes'] > 0 for r in finite),
              'absoluteErrorImproves': sum(r['absoluteErrorChangeMinutes'] < -1e-8 for r in finite),
              'absoluteErrorWorsens': sum(r['absoluteErrorChangeMinutes'] > 1e-8 for r in finite),
              'largestTravelTimeChanges': sorted(finite, key=lambda r: abs(r['changeMinutes']), reverse=True)[:12],
              'fieldBackingMaxBytes': field_max, 'fieldPlusDisplayBackingMaxBytes': display_max,
              'fullDisplayAllowanceBytes': 8548069, 'allOldPositiveRoadTotalsRetained': new['roadMonotonicComparisons'],
              'settledArrayBuffersAfterLoadAndQueries': new['afterLoad']['arrayBuffers'],
              'numericalGatesPassed': new['numericalGatesPassed'], 'providerRequests': 0, 'modelActivated': False,
              'scope': 'All fixed observed development cases, no fresh holdout or causality claim. Faster estimates and mostly negative residuals motivate path diagnosis; they do not establish a new speed coefficient. No provider/source/model operation or gate change.'}
    output = here/'entry-comparison-v1.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'largestTravelTimeChanges', 'sourceBindings')}))


if __name__ == '__main__':
    run()

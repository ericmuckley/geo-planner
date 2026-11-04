"""One externally specified fixed-path sensitivity, never a routing candidate."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(recipe, pin):
    repo = Path(__file__).resolve().parents[1]
    assert sha(recipe) == pin
    plan = json.loads(recipe.read_bytes())
    assert plan['taggedSpeedRatio'] == [9, 10] and plan['defaultSpeedRatio'] == [1, 1]
    for name, expected in plan['bindings'].items():
        assert sha(repo/name) == expected
    candidate = json.loads((repo/plan['candidate']).read_bytes())
    source = json.loads((repo/plan['attributes']).read_bytes())
    attributes = {r['id']: r for r in source['rows']}
    assert len(attributes) == 80 and len(candidate['rows']) == 83
    rows = []
    for original in candidate['rows']:
        before = original['candidate']['pointMinutes']
        if before is None:
            assert original['id'] not in attributes
            rows.append({'id': original['id'], 'set': original['set'], 'unavailable': True})
            continue
        record = attributes[original['id']]
        assert record['candidateMinutes'] == before and record['referenceMinutes'] == original['referenceMinutes']
        assert record['defaultTicks']+record['taggedTicks'] == record['roadTicks']
        # Continuous elapsed-time sensitivity on the frozen path. This does
        # not claim primitive re-quantization, a new optimum or a new map.
        after = before + record['taggedTicks']/(480*9)
        rows.append({'id': original['id'], 'set': original['set'], 'unavailable': False,
                     'referenceMinutes': record['referenceMinutes'], 'currentMinutes': before,
                     'fixedPathSensitivityMinutes': after, 'taggedRoadMinutes': record['taggedTicks']/480})
    def summarize(items):
        return {'cases': len(items), 'currentMaeMinutes': mean(abs(r['currentMinutes']-r['referenceMinutes']) for r in items),
                'fixedPathSensitivityMaeMinutes': mean(abs(r['fixedPathSensitivityMinutes']-r['referenceMinutes']) for r in items),
                'meanTimeAddedMinutes': mean(r['fixedPathSensitivityMinutes']-r['currentMinutes'] for r in items)}
    finite = [r for r in rows if not r['unavailable']]
    assert len(finite) == 80 and len(rows) == 83
    report = {'status': 'one_external_tagged90_fixed_path_sensitivity_complete', 'recipeSha256': pin,
              'rows': rows, 'same80': summarize(finite), 'sets': {s: summarize([r for r in finite if r['set'] == s]) for s in ('original', 'regional', 'frontier')},
              'newRoutingQueries': 0, 'newMaps': 0, 'providerRequests': 0, 'policyActivated': False,
              'isCandidateEvaluation': False, 'originalGatesChanged': False,
              'scope': 'One predeclared source-informed 90%-of-tagged-speed sensitivity on all frozen winner paths. Defaults/local/signals remain fixed, nulls remain. No sweep, fit, source repricing, new shortest paths, shading/physical/accuracy/app admission; it cannot substitute for a full independently audited candidate.'}
    with (repo/plan['output']).open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('status', 'same80', 'sets', 'isCandidateEvaluation')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('pin')
    args = parser.parse_args()
    run(args.recipe, args.pin)

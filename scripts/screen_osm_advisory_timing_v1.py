"""One all-route advisory-cap sensitivity on fixed witnesses, without routing."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean
import resource
import sys
import time

from coarse_osm_advisory_timing_v1 import POLICY, estimated_speed
from inventory_osm_complete_path_features_v1 import sha, unpack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    repo = Path(__file__).resolve().parents[1]
    recipe = repo/args.plan
    assert sha(recipe) == args.pin
    plan = json.loads(recipe.read_bytes())
    assert plan['policy'] == POLICY and not (repo/plan['output']).exists()
    assert sys.platform == plan['hostPlatform'] == 'darwin'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes'] < 72*1024**3
    for name, pin in plan['bindings'].items():
        assert sha(repo/name) == pin, name
    source = json.loads((repo/plan['sourceReport']).read_bytes())
    tags = unpack(repo/plan['sourceRoot']/'way-tags.json.gz', source['tagArtifact'])
    attr = json.loads((repo/plan['attributeReport']).read_bytes())
    attributes = unpack(repo/plan['attributeRoot']/'arc-attributes.json.gz', attr['artifact'])
    paths = json.loads((repo/plan['pathReport']).read_bytes())
    candidate = json.loads((repo/plan['candidate']).read_bytes())
    by_id = {row['id']: row for row in candidate['rows']}
    assert len(tags) == 33427 and len(attributes) == 43910 and paths['paths'] == 83 and paths['unavailable'] == 0
    rows = []
    changed_arcs = set()
    statuses = Counter()
    for row in paths['rows']:
        assert time.monotonic()-began < 60 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < 4*1024**3
        record = unpack(repo/plan['pathRoot']/row['asset']['filename'], row['asset'])
        sample = by_id[row['id']]
        assert record['sample']['id'] == row['id']
        current = sum(row['components'].values())/480
        assert current == sample['candidate']['pointMinutes']
        repriced = []
        old_road = changed = 0
        for step in (record['road'] or {}).get('steps', []):
            attribute = attributes[str(step['arc'])]
            original = tags[str(attribute['sourceWay'])]
            speed, status = estimated_speed(original, attribute['sourceSpeedKph'])
            statuses[status] += 1
            old_road += step['ticks']
            repriced.append(step['ticks']*attribute['sourceSpeedKph']/speed)
            if speed < attribute['sourceSpeedKph']:
                changed += 1
                changed_arcs.add(step['arc'])
        assert old_road == row['components']['roadTravelTicks']
        after = (sum(row['components'].values())-old_road+math.fsum(repriced))/480
        assert after >= current-1e-9
        rows.append({'id': row['id'], 'set': sample['set'], 'referenceMinutes': sample['referenceMinutes'],
                     'valhallaMinutes': sample['valhallaMinutes'], 'baselineMinutes': sample['baseline']['pointMinutes'],
                     'currentMinutes': current, 'fixedWitnessSensitivityMinutes': after,
                     'minutesAdded': after-current, 'changedSteps': changed, 'overDiagnosticHorizon': after > 900})
    assert len(rows) == len({r['id'] for r in rows}) == len(by_id) == 83
    def summarize(items, reference='referenceMinutes'):
        assert items and all(r[reference] is not None for r in items)
        return {'cases': len(items), 'baselineMeanAbsoluteMinutes': mean(abs(r['baselineMinutes']-r[reference]) for r in items),
                'currentMeanAbsoluteMinutes': mean(abs(r['currentMinutes']-r[reference]) for r in items),
                'fixedWitnessSensitivityMeanAbsoluteMinutes': mean(abs(r['fixedWitnessSensitivityMinutes']-r[reference]) for r in items),
                'meanMinutesAdded': mean(r['minutesAdded'] for r in items)}
    result = {'status': 'unscoped_advisory_cap_all83_fixed_witness_sensitivity_complete', 'recipeSha256': args.pin,
              'rows': rows, 'overall': summarize(rows),
              'sets': {s: summarize([r for r in rows if r['set'] == s]) for s in ('original','regional','frontier')},
              'valhalla': {s: summarize([r for r in rows if r['set'] == s], 'valhallaMinutes') for s in ('original','regional')},
              'uniqueChangedArcs': len(changed_arcs), 'stepStatuses': dict(statuses),
              'modelQueries': 0, 'providerRequests': 0, 'newMaps': 0, 'policyActivated': False,
              'originalGatesChanged': False, 'isCandidateEvaluation': False,
              'hostSecondsIncludingBindingsSourceAndAllPaths': time.monotonic()-began, 'scope': plan['scope']}
    with (repo/plan['output']).open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status','overall','sets','valhalla','uniqueChangedArcs','isCandidateEvaluation')}))


if __name__ == '__main__':
    main()

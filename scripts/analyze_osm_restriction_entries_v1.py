"""Read the saved relation inventory; qualify shapes without rebuilding a graph."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_restriction_entry_v1 import entry_restriction

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    assert sha(REPO / args.plan) == args.pin
    plan = json.loads((REPO / args.plan).read_bytes())
    for name, pin in plan['bindings'].items():
        assert sha(REPO / name) == pin, name
    statuses, fallback, candidates = Counter(), Counter(), []
    seen = set()
    with (REPO / plan['source']).open() as stream:
        for line in stream:
            assert len(line) <= 8388608
            raw = json.loads(line)
            element = raw['element']
            assert element['id'] not in seen and len(seen) < 10000
            seen.add(element['id'])
            old = restriction_policy(element)
            statuses[old['status']] += 1
            entry = entry_restriction(element)
            if entry is not None:
                candidates.append({**asdict(entry), 'elementSha256': raw['elementSha256']})
            elif old['status'] == 'closed-unsupported':
                fallback[old['reason']] += 1
    assert statuses == {'via-node': 4078, 'closed-unsupported': 819, 'non-car': 3}
    report = {'status': 'saved_relation_entry_shape_inventory_complete', 'recipeSha256': args.pin,
              'sourceRelations': len(seen), 'originalStatuses': dict(statuses),
              'entryCandidateShapes': candidates, 'candidateShapes': len(candidates),
              'unchangedFallbackRelations': sum(fallback.values()), 'fallbackReasons': dict(fallback),
              'sourcePbfReads': 0, 'modelQueries': 0, 'policyActivated': False,
              'scope': 'Captured validation metadata only. Shape feasibility and synthetic conservative-subset proof do not establish actual arc resolution, recovery, ETA, national coverage or physical/app acceptance. Preserve fallback closure union from every other relation; never subtract converted IDs globally.'}
    with (REPO / plan['output']).open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'entryCandidateShapes'}))


if __name__ == '__main__':
    main()

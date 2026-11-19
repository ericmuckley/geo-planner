"""Compare every frozen conditional candidate case with the prior water result."""
import argparse
import hashlib
import json
from pathlib import Path

from review_osm_water_candidate_v1 import review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    parser.add_argument('current', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    old, new = args.previous.read_bytes(), args.current.read_bytes()
    current = json.loads(new)
    result = review(json.loads(old), current)
    result.update(
        status='complete_frozen_conditional_candidate_all_case_comparison',
        frozenNumericalGatesPassed=current['numericalGatesPassed'],
        frozenNumericalGates=current['gates'],
        inputs={str(args.previous): hashlib.sha256(old).hexdigest(), str(args.current): hashlib.sha256(new).hexdigest()},
        producerSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        comparisonHelperSha256=hashlib.sha256(Path(__file__).with_name('review_osm_water_candidate_v1.py').read_bytes()).hexdigest(),
        providerRequests=0, modelQueries=0, policyChangedByReview=False,
        scope='Every83 original IDs/references/baseline semantics retained, with missing cases explicit. New source-policy graph compared to prior waterV6; v9 remains numerical baseline. Observed development data, not holdout/national/traffic truth. Review performs no query, fit, policy or app change.')
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'inputs', 'scope')}))


if __name__ == '__main__':
    main()

"""Inventory original tags for all current path roads without repricing or routing."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

from inventory_osm_current_path_features_v1 import FEATURES, bins
from coarse_osm_car_explicit_lanes_v1 import way_policy

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unpack(path, asset):
    packed = path.read_bytes()
    assert len(packed) == asset.get('bytes', asset.get('compressedBytes'))
    assert hashlib.sha256(packed).hexdigest() == asset['sha256']
    raw = gzip.decompress(packed)
    assert len(raw) == asset['rawBytes'] and hashlib.sha256(raw).hexdigest() == asset['rawSha256']
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    plan_path = REPO/args.plan
    assert sha(plan_path) == args.pin
    plan = json.loads(plan_path.read_bytes())
    assert sys.platform == plan['hostPlatform'] == 'darwin' and plan['features'] == list(FEATURES)
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes'] < 72*1024**3
    assert not (REPO/plan['output']).exists()
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin, name
    report = json.loads((REPO/plan['sourceReport']).read_bytes())
    assert report['allCurrentSelectedWays'] == 33427 and report['allCachedOriginalTagsExact']
    tags = unpack(REPO/plan['sourceRoot']/'way-tags.json.gz', report['tagArtifact'])
    attr_report = json.loads((REPO/plan['attributeReport']).read_bytes())
    attributes = unpack(REPO/plan['attributeRoot']/'arc-attributes.json.gz', attr_report['artifact'])
    assert len(tags) == 33427 and len(attributes) == 43910
    assert {str(a['sourceWay']) for a in attributes.values()} == set(tags)
    policies = {identity: way_policy(original) for identity, original in tags.items()}
    rate_mismatches = []
    for arc, attribute in attributes.items():
        identity = str(attribute['sourceWay'])
        assert tags[identity]['highway'] == attribute['role']
        policy = policies[identity]
        forward = attribute['direction'] == 1
        legal = policy.forward if forward else policy.backward
        default = policy.forward_default if forward else policy.backward_default
        estimated = None if legal is None else legal if default else legal*0.9
        if (policy.reason is not None or estimated is None or default != attribute['defaultSpeed']
                or not math.isclose(estimated, attribute['sourceSpeedKph'], rel_tol=0, abs_tol=1e-9)):
            rate_mismatches.append({'arc': int(arc), 'sourceWay': attribute['sourceWay'],
                                    'policyReason': policy.reason, 'direction': attribute['direction'],
                                    'expectedEstimatedSpeedKph': estimated,
                                    'recordedEstimatedSpeedKph': attribute['sourceSpeedKph'],
                                    'expectedDefault': default, 'recordedDefault': attribute['defaultSpeed']})
    way_features = {feature: Counter(row.get(feature) for row in tags.values()) for feature in FEATURES}
    paths = json.loads((REPO/plan['pathReport']).read_bytes())
    assert paths['paths'] == len(paths['rows']) == 83 and paths['unavailable'] == 0
    rows = []
    selected = set()
    totals = {feature: Counter() for feature in FEATURES}
    for row in paths['rows']:
        assert time.monotonic()-began < 120 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < 4*1024**3
        record = unpack(REPO/plan['pathRoot']/row['asset']['filename'], row['asset'])
        assert record['sample']['id'] == row['id']
        features = {feature: Counter() for feature in FEATURES}
        explicit = default = 0
        for step in (record['road'] or {}).get('steps', []):
            key = str(step['arc'])
            selected.add(key)
            attribute = attributes[key]
            original = tags[str(attribute['sourceWay'])]
            if attribute['defaultSpeed']:
                default += step['ticks']
            else:
                explicit += step['ticks']
            for feature in FEATURES:
                value = original.get(feature)
                features[feature][value] += step['ticks']
                totals[feature][value] += step['ticks']
        road = record['components']['roadTravelTicks']
        assert explicit+default == road == row['components']['roadTravelTicks']
        assert all(sum(c.values()) == road for c in features.values())
        rows.append({'id': row['id'], 'set': record['sample']['set'], 'roadTicks': road,
                     'explicitTicks': explicit, 'defaultTicks': default, 'missingRawSourceTicks': 0,
                     'features': {key: bins(counter) for key, counter in features.items()}})
    assert selected == set(attributes) and len({r['id'] for r in rows}) == 83
    result = {'status': 'all83_current_paths_complete_original_source_features_inventoried', 'recipeSha256': args.pin,
              'selectedSourceWays': len(tags), 'selectedArcs': len(attributes), 'unknownRawSourceWays': 0,
              'rawTagRateComparisons': len(attributes), 'rawTagRateMismatches': rate_mismatches,
              'rawTagRatesAgreeWithCurrentPolicy': not rate_mismatches,
              'sourceWayFeatures': {key: bins(counter) for key, counter in way_features.items()},
              'pathFeatureTickTotals': {key: bins(counter) for key, counter in totals.items()},
              'rows': rows, 'roadTicks': sum(r['roadTicks'] for r in rows),
              'explicitTicks': sum(r['explicitTicks'] for r in rows), 'defaultTicks': sum(r['defaultTicks'] for r in rows),
              'sourcePbfReads': 0, 'newDataAcquired': 0, 'modelQueries': 0, 'providerRequests': 0, 'policyChanged': False,
              'hostSecondsIncludingBindingsAndAllSourcePathJoins': time.monotonic()-began,
              'scope': 'ALL83current winners/43910source arcs/33427source roads, with complete newly audited original raw tags. Null is a known absent tag; zero raw source omissions. Fixed12featurekeys and exact old path tick exposures; independently replay the existing generic car/lane/conditional raw policy and fixed9/10explicit/defaults-unchanged rates against every selected direction. Preserve all mismatches; this does not change a source permission or price. No cap/default/advisory reinterpretation, speed factor, reprice, new optimum/map, fit/sweep/selected-case exception or permission/app change. These are observed development paths, not countrywide tag frequencies or nationwide accuracy. Metadata-host duration includes allbindings/joins/output, not queries/cloud.'}
    raw = (json.dumps(result, indent=2, allow_nan=False)+'\n').encode()
    assert len(raw) <= 16*1024**2
    with (REPO/plan['output']).open('xb') as stream:
        stream.write(raw)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows','sourceWayFeatures','pathFeatureTickTotals','scope')}))


if __name__ == '__main__':
    main()

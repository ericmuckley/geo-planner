"""All cached reference corridors versus complete excluded-major-way geometry."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_backbone_paths import MultiCorridorIndex
from coarse_path_features import polyline_samples
from coarse_osm_source_gap_corridors_v1 import exposure

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    plan_path = REPO/args.plan
    assert sha(plan_path) == args.pin
    plan = json.loads(plan_path.read_bytes())
    assert plan['radiiKm'] == [0.1, 0.25, 1] and plan['winnerGapRadiusKm'] == 1
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes'] < 72*1024**3
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin, name

    def check():
        assert time.monotonic()-began < 600, 'Source-gap metadata analysis deadline'
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert peak*(1 if sys.platform == 'darwin' else 1024) < 4*1024**3, 'Source-gap host peak RSS'

    inventory = json.loads((REPO/plan['inventoryReport']).read_bytes())
    assert inventory['selectedWays'] == 52743 and inventory['selectedSourceReferences'] == 449987
    artifact = inventory['artifact']
    source = REPO/plan['inventoryRoot']/artifact['file']
    assert source.stat().st_size == artifact['bytes'] <= 50331648 and sha(source) == artifact['sha256']
    parts = {'baseIneligible': [], 'baseEligibleFallbackClosed': []}
    records = points = raw_bytes = 0
    digest = hashlib.sha256()
    with gzip.open(source, 'rb') as stream:
        while True:
            raw = stream.readline(4194305)
            if not raw:
                break
            assert len(raw) <= 4194304 and raw.endswith(b'\n')
            digest.update(raw)
            raw_bytes += len(raw)
            row = json.loads(raw)
            assert not row['baseEligible'] or row['finalFallbackClosed']
            category = 'baseEligibleFallbackClosed' if row['baseEligible'] else 'baseIneligible'
            parts[category].append([[x/1e7, y/1e7] for x, y in row['xyE7']])
            records += 1
            points += len(row['xyE7'])
            if records % 1024 == 0:
                check()
    assert records == 52743 and points == 449987
    assert raw_bytes == artifact['rawBytes'] and digest.hexdigest() == artifact['rawSha256']
    assert len(parts['baseIneligible']) == 33683 and len(parts['baseEligibleFallbackClosed']) == 19060
    indexes = {name: MultiCorridorIndex(lines) for name, lines in parts.items()}
    del parts
    check()
    provider = {}
    for bundle in plan['bundles']:
        root = REPO/bundle
        for i, query in enumerate(json.loads((root/'plan.json').read_bytes())['queries']):
            key = query['id'].split('/', 1)[-1]
            assert key not in provider
            provider[key] = root/f'{i:02d}-response.txt'
    assert len(provider) == 83
    witness = json.loads((REPO/plan['witnessReport']).read_bytes())
    closed = json.loads((REPO/plan['witnessClosed']).read_bytes())
    findings = json.loads((REPO/plan['findings']).read_bytes())
    by_id = {row['id']: row for row in findings['rows']}
    assert witness['paths'] == len(witness['rows']) == len(by_id) == 83 and witness['unavailable'] == 0
    rows = []
    for item in witness['rows']:
        check()
        asset = item['asset']
        name = asset['filename']
        assert Path(name).name == name
        path = REPO/plan['witnessRoot']/name
        assert path.stat().st_size == closed['roster'][name]['bytes'] == asset['compressedBytes'] <= 2097152
        assert sha(path) == closed['roster'][name]['sha256'] == asset['sha256']
        with gzip.open(path, 'rb') as stream:
            raw = stream.read(33554433)
        assert len(raw) == asset['rawBytes'] <= 33554432 and hashlib.sha256(raw).hexdigest() == asset['rawSha256']
        saved = json.loads(raw)
        assert saved['sample']['id'] == item['id']
        assert sum(saved['components'].values()) == saved['sumTicks'] == item['sumTicks']
        feature = json.loads(provider[item['id']].read_bytes())['features'][0]
        assert feature['geometry']['type'] == 'LineString'
        assert abs(feature['properties']['summary']['duration']/60-saved['sample']['referenceMinutes']) < 1e-8
        reference = [point[:2] for point in feature['geometry']['coordinates']]
        current_parts = [saved['localCoordinates']]
        if saved['initialConnection'] is not None:
            connection = saved['initialConnection']
            current_parts.append([connection['origin'], connection['snap']['coordinate']])
        if saved['roadGeometry'] is not None:
            current_parts.append(saved['roadGeometry']['coordinates'])
        observation = exposure(list(polyline_samples(reference, 1)), MultiCorridorIndex(current_parts), indexes)
        previous = by_id[item['id']]
        rows.append({'id': item['id'], 'set': saved['sample']['set'],
                     'signedMinutes': previous['signedMinutes'],
                     'fullGeometryDistanceRatio': previous['fullGeometryDistanceRatio'],
                     'defaultRoadMinutes': previous['sourceSpeedExposure']['defaultTicks']/480,
                     **observation})
        print(json.dumps({'case':len(rows),'cases':83,'id':item['id']}), flush=True)
    assert len({row['id'] for row in rows}) == 83
    keys = ('0.1','0.25','1')
    total = sum(row['referenceSampleKm'] for row in rows)
    outside = sum(row['referenceOutsideWinner1Km'] for row in rows)
    near = {key:sum(row['outsideWinner1KmNearAnyExcludedKm'][key] for row in rows) for key in keys}
    report = {'status':'all83_cached_reference_excluded_major_way_corridor_observations_complete',
              'recipeSha256':args.pin,'rows':rows,'sourceInventoryWays':records,'sourceInventoryReferences':points,
              'allCasesRetained':83,'radiiKm':plan['radiiKm'],'winnerGapRadiusKm':1,
              'referenceSampleKm':total,'referenceOutsideWinner1Km':outside,
              'outsideWinner1KmNearAnyExcludedKm':near,
              'fractionOfOutsideWinner1KmNearAnyExcluded':{key:(value/outside if outside else None) for key,value in near.items()},
              'providerRequests':0,'modelQueries':0,'sourcePbfReads':0,'permissionOrPriceChanges':False,'appActivated':False,
              'hostSecondsIncludingBindingsIndexAndAll83Observations':time.monotonic()-began,
              'scope':'All83 observed development reference/winner paths and the COMPLETE52743excludedmajorway inventory; fixed1km segment-midpoint quadrature and100/250/1000m geometric proximity. Exclusive categories are source-base-ineligible versus base-eligible finalfallbackclosed; stored original flags are not assumed current rawtag rejection causes. Overlapping/parallel candidates explicitly remain ambiguous: proximity is NOT way identity, topological connectivity, permission or proof of a causal detour. Absence may involve non-major roads,node-only barriers,source-date/preferences/cost differences or unmatched geometry. Every current timing/gate/permission stays. No fit/reprice/route/newreference/PBF/sourceconstructor/DB/app action; hostRSS/deadline metadata analysis, not cgroup/cloud/query/app qualification.'}
    check()
    with (REPO/plan['output']).open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({key:report[key] for key in ['status','referenceOutsideWinner1Km','fractionOfOutsideWinner1KmNearAnyExcluded','hostSecondsIncludingBindingsIndexAndAll83Observations']}))


if __name__ == '__main__':
    main()

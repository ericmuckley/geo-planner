"""Inventory cached raw timing-related tags without fitting or changing road costs."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import sys
import time

REPO = Path(__file__).resolve().parents[1]
FEATURES = ('surface', 'tracktype', 'smoothness', 'junction', 'lanes', 'motorroad',
            'maxspeed', 'maxspeed:forward', 'maxspeed:backward', 'maxspeed:advisory',
            'maxspeed:type', 'zone:maxspeed')
ROLES = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
         'secondary', 'secondary_link', 'tertiary', 'tertiary_link'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stable(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def bins(counter):
    return [{'value': value, 'count': count} for value, count in
            sorted(counter.items(), key=lambda item: (item[0] is not None, item[0] or ''))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    recipe = REPO/args.plan
    assert sha(recipe) == args.pin
    plan = json.loads(recipe.read_bytes())
    assert plan['features'] == list(FEATURES)
    assert sys.platform == plan['hostPlatform'] == 'darwin'
    output = REPO/plan['output']
    assert not output.exists()
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes'] < 72*1024**3
    before = {name: stable(REPO/name) for name in plan['bindings']}
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin, name

    def check():
        assert time.monotonic()-began < 120
        # macOS getrusage reports bytes; this is a host bound, not a cgroup measurement.
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < 4*1024**3

    attribute_report = json.loads((REPO/plan['attributeReport']).read_bytes())
    asset = attribute_report['artifact']
    packed = (REPO/plan['attributeRoot']/asset['file']).read_bytes()
    assert len(packed) == asset['bytes'] and hashlib.sha256(packed).hexdigest() == asset['sha256']
    raw = gzip.decompress(packed)
    assert len(raw) == asset['rawBytes'] and hashlib.sha256(raw).hexdigest() == asset['rawSha256']
    attributes = json.loads(raw)
    assert len(attributes) == attribute_report['selectedArcs'] == 43910
    wanted = {a['sourceWay'] for a in attributes.values()}
    known = {}
    counts = {key: Counter() for key in FEATURES}
    cache = REPO/plan['sourceCache']
    db = sqlite3.connect(cache.resolve().as_uri()+'?mode=ro&immutable=1', uri=True)
    cached = major = 0
    try:
        for identity, raw in db.execute("SELECT id,raw FROM objects WHERE kind='way'"):
            cached += 1
            if cached % 4096 == 0:
                check()
            assert len(raw) <= 8*1024**2
            record = json.loads(raw)
            assert record['id'] == int(identity)
            tags = record['tags']
            assert isinstance(tags, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items())
            if tags.get('highway') in ROLES:
                major += 1
                for key in FEATURES:
                    counts[key][tags.get(key)] += 1
            if int(identity) in wanted:
                assert int(identity) not in known and tags.get('highway') in ROLES
                known[int(identity)] = {'highway': tags['highway'], **{key: tags.get(key) for key in FEATURES}}
    finally:
        db.close()
    assert cached == 239253 and major == 28995
    paths = json.loads((REPO/plan['pathReport']).read_bytes())
    assert paths['paths'] == len(paths['rows']) == 83 and paths['unavailable'] == 0
    rows = []
    selected = set()
    for row in paths['rows']:
        check()
        a = row['asset']
        packed = (REPO/plan['pathRoot']/a['filename']).read_bytes()
        assert len(packed) == a['compressedBytes'] and hashlib.sha256(packed).hexdigest() == a['sha256']
        raw = gzip.decompress(packed)
        assert len(raw) == a['rawBytes'] and hashlib.sha256(raw).hexdigest() == a['rawSha256']
        record = json.loads(raw)
        assert record['sample']['id'] == row['id']
        feature_ticks = {key: Counter() for key in FEATURES}
        covered = unknown = 0
        for step in (record['road'] or {}).get('steps', []):
            key = str(step['arc'])
            selected.add(key)
            attr = attributes[key]
            tags = known.get(attr['sourceWay'])
            if tags is None:
                unknown += step['ticks']
                continue
            assert tags['highway'] == attr['role']
            covered += step['ticks']
            for feature in FEATURES:
                feature_ticks[feature][tags[feature]] += step['ticks']
        assert covered+unknown == record['components']['roadTravelTicks'] == row['components']['roadTravelTicks']
        assert all(sum(c.values()) == covered for c in feature_ticks.values())
        rows.append({'id': row['id'], 'set': record['sample']['set'], 'roadTicks': covered+unknown,
                     'cachedRawTagTicks': covered, 'missingRawSourceTicks': unknown,
                     'features': {key: bins(c) for key, c in feature_ticks.items()}})
    assert selected == set(attributes) and len({r['id'] for r in rows}) == 83
    for name, status in before.items():
        assert stable(REPO/name) == status, name
    check()
    result = {'status': 'all83_current_path_cached_raw_source_features_inventoried', 'recipeSha256': args.pin,
              'cachedWayRecordsChecked': cached, 'cachedMajorWayRecordsChecked': major,
              'selectedArcs': len(attributes), 'selectedSourceWays': len(wanted),
              'selectedSourceWaysWithCachedRawTags': len(known),
              'selectedSourceWaysWithoutCachedRawTags': len(wanted)-len(known),
              'cachedMajorWayFeatures': {key: bins(c) for key, c in counts.items()},
              'roadTicks': sum(r['roadTicks'] for r in rows),
              'cachedRawTagTicks': sum(r['cachedRawTagTicks'] for r in rows),
              'missingRawSourceTicks': sum(r['missingRawSourceTicks'] for r in rows), 'rows': rows,
              'sourcePbfReads': 0, 'newDataAcquired': 0, 'modelQueries': 0, 'providerRequests': 0,
              'policyChanged': False, 'hostSecondsIncludingBindingsCacheAndAllPaths': time.monotonic()-began,
              'scope': 'All current83 winners/all43910 source arcs. Raw cache covers21 historical source windows, not the country. Known source without a tag (null) is distinct from unavailable raw source. Tick bins describe repeated actual path exposure, not traffic, fitted costs or an exact repricing. Surface/advisory/other tags are observations only; no access/closure/default/price/matching/display/gate change or national accuracy/app admission.'}
    encoded = (json.dumps(result, indent=2, allow_nan=False)+'\n').encode()
    assert len(encoded) <= 16*1024**2
    with output.open('xb') as stream:
        stream.write(encoded)
    print(json.dumps({key: value for key, value in result.items() if key not in ('rows','cachedMajorWayFeatures','scope')}))


if __name__ == '__main__':
    main()

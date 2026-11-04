"""One bounded host transformation of sealed relation metadata into typed inputs."""
from array import array
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_entry_records_v1 import prepare

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    assert sha(REPO/args.plan) == args.pin and sys.byteorder == 'little'
    plan = json.loads((REPO/args.plan).read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-car-entry-records-v1' and plan['maxOwnedBytes'] == 16777216
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes'] < 64*1024**3
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin, name
    closed = json.loads((REPO/plan['metadataClosed']).read_bytes())
    source = REPO/closed['root']/'unsupported-relations.jsonl'
    expected = closed['roster']['unsupported-relations.jsonl']
    assert source.is_file() and not source.is_symlink() and source.stat().st_size == expected['bytes'] == 21119251
    facts = json.loads((REPO/plan['factsClosed']).read_bytes())
    closures = array('Q')
    for name, pin in sorted(facts['roster'].items()):
        if name.startswith('cost-facts/closures-'):
            path = REPO/facts['root']/name
            assert path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256']
            closures.frombytes(path.read_bytes())
    assert len(closures) == 149699
    root = REPO/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes((REPO/args.plan).read_bytes())
    def save(name, value):
        with (root/name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
    def check():
        assert time.monotonic()-began < 300
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss*(1 if sys.platform == 'darwin' else 1024) < 4*1024**3
    try:
        with source.open('rb') as stream, (root/'rules.bin').open('xb') as rules, (root/'fallback-closures.u64').open('xb') as fallback:
            result = prepare(stream, rules, fallback, expected_rows=70376, expected_bytes=expected['bytes'], expected_sha256=expected['sha256'], expected_closures=closures, check=check)
        assets = {n: {'bytes': (root/n).stat().st_size, 'sha256': sha(root/n)} for n in ['rules.bin', 'fallback-closures.u64']}
        assert sum(v['bytes'] for v in assets.values()) < 8*1048576
        save('artifacts.json', assets)
        save('report.json', {'status': 'typed_national_entry_metadata_prepared', 'recipeSha256': args.pin, **result, 'assets': assets,
                             'hostSeconds': time.monotonic()-began, 'sourcePbfReads': 0, 'graphQueries': 0, 'countryGraphChanged': False,
                             'scope': 'Small host functional metadata transformation with explicit caps, not a cgroup/graph/ETA/app measurement. Native resolution still must add full fallbacks for every unresolved candidate; no old fallback closure may be subtracted globally.'})
        print(json.dumps(result))
    except BaseException as error:
        save('failure.json', {'status': 'entry_metadata_preparation_stopped', 'error': repr(error), 'hostSeconds': time.monotonic()-began})
        raise


if __name__ == '__main__':
    main()

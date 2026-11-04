"""Independently decode every new candidate storage byte against closed arrays."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_packed_codec_audit_v1 import FILES, decode
from audit_osm_paid_geometry_codec_v1 import NAMES as GEOMETRY_NAMES


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(recipe, pin):
    began = time.monotonic()
    repo = Path(__file__).resolve().parents[1]
    assert sha(recipe) == pin
    plan = json.loads(recipe.read_bytes())
    kind = plan['kind']
    assert kind in ('core', 'geometry')
    source_name = 'spatial' if kind == 'core' else 'geometry'
    assert plan['source'] == f'data/coarse-quality/us-osm-car-entry-derived-{source_name}-v1'
    assert plan['codec'] == f'data/coarse-quality/us-osm-car-entry-codec-{kind}-v1'
    assert plan['output'] == f'data/coarse-quality/us-osm-car-entry-codec-audit-{kind}-v1'
    assert plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes'] + plan.get('additionalActiveReservationBytes', 0) + 8388608 < 68719476736
    for name, expected in plan['bindings'].items():
        assert name.startswith(('scripts/', 'routing/', 'docs/evidence/')) and sha(repo/name) == expected, name
    source, codec, output = (repo/plan[k] for k in ('source', 'codec', 'output'))
    closed = json.loads((repo/plan['closedRecord']).read_bytes())
    codec_closed = json.loads((repo/plan['codecClosedRecord']).read_bytes())
    assert closed['root'] == plan['source'] and codec_closed['root'] == plan['codec']
    assert sha(codec/'manifest.json') == codec_closed['roster']['manifest.json']['sha256'] == plan['manifestSha256']
    output.mkdir()
    (output/'execution-plan.json').write_bytes(recipe.read_bytes())
    try:
        manifest = json.loads((codec/'manifest.json').read_bytes())
        assert manifest['format'] == 'packed-integer-delta-byteplanes-gzip-v1'
        prefix = 'routing/' if kind == 'core' else 'geometry/'
        names = FILES if kind == 'core' else GEOMETRY_NAMES
        fields = manifest['fields']
        assert set(fields) == {prefix+name for name in names}
        total = compressed_total = 0
        for name in sorted(names):
            key = prefix+name
            row, original = fields[key], closed['roster'][key]
            width = 4 if name.endswith(('.i32', '.u32')) else 3 if name.endswith('.u24') else 2 if name.endswith('.u16') else 1
            lanes = 2 if name == 'xy.i32' else 1
            assert (row['wordBytes'], row['lanes']) == (width, lanes)
            assert row['file'] == 'fields/'+name+'.gz'
            assert row['rawBytes'] == original['bytes'] <= 67108864 and row['rawSha256'] == original['sha256']
            path, raw_path = codec/row['file'], source/key
            assert path.is_file() and not path.is_symlink() and path.stat().st_size == row['compressedBytes'] <= 67108864
            assert raw_path.is_file() and not raw_path.is_symlink() and raw_path.stat().st_size == row['rawBytes']
            assert sha(path) == row['compressedSha256'] == codec_closed['roster'][row['file']]['sha256']
            with gzip.open(path, 'rb') as stream:
                encoded = stream.read(row['rawBytes']+1)
            assert len(encoded) == row['rawBytes']
            restored = decode(encoded, width, lanes)
            assert restored == raw_path.read_bytes() and hashlib.sha256(restored).hexdigest() == original['sha256']
            total += len(restored)
            compressed_total += row['compressedBytes']
            assert total <= (201326592 if kind == 'core' else 50331648) and compressed_total <= 125829120
            assert time.monotonic()-began < 120
        report = {'status': 'independent_complete_entry_candidate_storage_bytes_passed', 'kind': kind,
                  'fields': len(fields), 'bytesIndependentlyDecodedAndCompared': total, 'compressedBytes': compressed_total,
                  'secondsHostIncludingBindingsDecodeAndComparison': time.monotonic()-began,
                  'sourcePbfReads': 0, 'nativeProducerExecutions': 0, 'routingQueries': 0, 'appActivated': False,
                  'scope': 'Host functional storage audit using the sealed independent decoder. No protected Linux/cgroup, geometry reconstruction, route/ETA or app timing admission.'}
        with (output/'report.json').open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps(report))
    except BaseException as error:
        with (output/'failure.json').open('x') as stream:
            json.dump({'error': repr(error), 'seconds': time.monotonic()-began}, stream)
            stream.write('\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('pin')
    args = parser.parse_args()
    run(args.recipe, args.pin)

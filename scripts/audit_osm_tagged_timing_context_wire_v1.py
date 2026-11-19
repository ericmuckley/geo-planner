"""Independently check copied core bytes and decode every changed/context byte."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_context_records_v1 import CONTEXT_FIELDS
from coarse_osm_packed_codec_audit_v1 import decode


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(recipe, pin):
    began = time.monotonic()
    repo = Path(__file__).resolve().parents[1]
    assert sha(recipe) == pin
    plan = json.loads(recipe.read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-tagged-timing-context-wire-audit-v1'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+8388608 < 72*1024**3
    for name, expected in plan['bindings'].items():
        assert sha(repo/name) == expected
    wire, parent, records = (repo/plan[k] for k in ('wire', 'sourceCore', 'sourceRecords'))
    closed = json.loads((repo/plan['wireClosed']).read_bytes())
    original = json.loads((repo/plan['sourceCoreClosed']).read_bytes())
    sources = json.loads((repo/plan['sourceRecordsClosed']).read_bytes())
    assert closed['root'] == plan['wire'] and original['root'] == plan['sourceCore'] and sources['root'] == plan['sourceRecords']
    source_manifest = json.loads((parent/'manifest.json').read_bytes())
    core = json.loads((wire/'core/manifest.json').read_bytes())
    context = json.loads((wire/'context/manifest.json').read_bytes())
    for name in ('core/manifest.json', 'context/manifest.json'):
        assert sha(wire/name) == closed['roster'][name]['sha256']
    assert core['format'] == source_manifest['format'] == 'packed-integer-delta-byteplanes-gzip-v1'
    assert core['requiresTurnContextSearch'] is True
    assert context['format'] == 'static-via-way-context-gzip-v1'
    assert context['graphCoreManifestSha256'] == sha(wire/'core/manifest.json')
    assert context['contextRecordsReportSha256'] == core['contextRecordsReportSha256'] == sha(records/'report.json')
    source_report = json.loads((records/'report.json').read_bytes())
    assert context['graphArcCount'] == source_report['retainedArcsMapped']
    assert set(core['fields']) == set(source_manifest['fields']) and len(core['fields']) == 13
    assert set(context['fields']) == {'context/'+name for name in CONTEXT_FIELDS}
    output = repo/plan['output']
    output.mkdir()
    (output/'execution-plan.json').write_bytes(recipe.read_bytes())
    try:
        copied = decoded = compressed = 0
        for name, field in core['fields'].items():
            assert field['file'] == 'fields/'+Path(name).name+'.gz'
            path = wire/'core'/field['file']
            assert path.stat().st_size == field['compressedBytes'] and sha(path) == field['compressedSha256'] == closed['roster']['core/'+field['file']]['sha256']
            if name != 'routing/forbidden-turns.u24':
                assert field == source_manifest['fields'][name]
                assert sha(parent/field['file']) == original['roster'][field['file']]['sha256']
                assert path.read_bytes() == (parent/field['file']).read_bytes()
                copied += 1
            else:
                assert (field['wordBytes'], field['lanes']) == (3, 1)
                with gzip.open(path, 'rb') as stream:
                    encoded = stream.read(field['rawBytes']+1)
                assert len(encoded) == field['rawBytes']
                restored = decode(encoded, 3, 1)
                assert restored == (records/'records'/name).read_bytes()
                assert hashlib.sha256(restored).hexdigest() == field['rawSha256'] == sources['roster']['records/'+name]['sha256']
                decoded += len(restored)
            compressed += field['compressedBytes']
            assert time.monotonic()-began < 120
        assert copied == 12
        context_bytes = 0
        for name, field in context['fields'].items():
            assert field['file'] == 'fields/'+Path(name).name+'.gz'
            path = wire/'context'/field['file']
            assert path.stat().st_size == field['compressedBytes'] and sha(path) == field['compressedSha256'] == closed['roster']['context/'+field['file']]['sha256']
            assert field['rawBytes'] == sources['roster']['records/'+name]['bytes'] <= 16777216
            with gzip.open(path, 'rb') as stream:
                raw = stream.read(field['rawBytes']+1)
            assert len(raw) == field['rawBytes'] and raw == (records/'records'/name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == field['rawSha256'] == sources['roster']['records/'+name]['sha256']
            context_bytes += len(raw)
            compressed += field['compressedBytes']
            assert time.monotonic()-began < 120
        assert context_bytes == source_report['contextRuntimeBackingBytes']
        report = {'status': 'independent_complete_tagged_timing_context_wire_bytes_passed',
                  'copiedCoreFieldsByteIdentical': copied, 'replacementCoreBytesIndependentlyDecoded': decoded,
                  'contextFieldsIndependentlyDecoded': 6, 'contextBytesIndependentlyCompared': context_bytes,
                  'combinedCoreAndContextCompressedBytes': compressed,
                  'hostSecondsIncludingBindingsCopiesAndIndependentDecode': time.monotonic()-began,
                  'sourcePbfReads': 0, 'nativeProducerExecutions': 0, 'routingQueries': 0, 'appActivated': False,
                  'scope': 'Every copied compressed core field equals its sealed parent;all changed retained-static-source-plus-multi-entry-turn/context bytes independently decode to source-audited records. The core requires the matching context search. No actual loader/query/paid-progress/lifetime/retained/app/package/ETA admission.'}
        with (output/'report.json').open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps(report))
    except BaseException as error:
        with (output/'failure.json').open('x') as stream:
            json.dump({'error': repr(error), 'hostSeconds': time.monotonic()-began}, stream)
            stream.write('\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('pin')
    args = parser.parse_args()
    run(args.recipe, args.pin)

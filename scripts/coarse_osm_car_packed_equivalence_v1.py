"""Compare every native captured output byte against the closed Python formatter."""
import hashlib
import json
from pathlib import Path
import time


def run(native, repo, check):
    began = time.monotonic()
    source = repo/'data/coarse-quality/us-osm-car-cost-graph-captured-v5'
    reference = repo/'data/coarse-quality/us-osm-car-packed-capture-v1'
    counts = json.loads((source/'audit.json').read_bytes())['facts']
    expected = [counts[key] for key in ('selectedNodes','anchors','majorWays','preClosureArcs','postClosureArcs','supportedViaNodeRules')]
    output = Path('/work/routing');output.mkdir()
    result = native.encode(source/'cost-facts', output, expected);check()
    artifacts = json.loads((reference/'artifacts.json').read_bytes())
    assert {p.name for p in output.iterdir()} == {Path(name).name for name in artifacts}
    total = 0
    for name, pin in artifacts.items():
        actual = (output/Path(name).name).read_bytes();original = (reference/name).read_bytes()
        assert actual == original and len(actual) == pin['bytes'] and hashlib.sha256(actual).hexdigest() == pin['sha256'], name
        total += len(actual);check()
    assert total == result['payloadBytes']
    return {'status': 'native_captured_wire_byte_identical_to_independent_python_formatter', **result,
            'filesByteIdentical': len(artifacts), 'bytesIndependentlyCompared': total,
            'secondsIncludingNativeEncodingAndByteComparison': time.monotonic()-began,
            'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'modelChanged': False,
            'countryOrAppQualified': False}

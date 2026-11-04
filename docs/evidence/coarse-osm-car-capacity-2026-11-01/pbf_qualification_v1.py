"""Exercise the new composed PBF entry point on a tiny generated source only."""
from array import array
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_car_capacity_v2 import Capacity
from coarse_osm_car_capacity_v2_test import CAPS
from coarse_osm_country_wire_v4 import reference_seal
from coarse_osm_native_smoke import STATE, fixture_records, write_xml
from coarse_timing_input import PilotError


def audit():
    import osmium
    began = time.monotonic()
    root = Path('/work')
    rows = fixture_records()
    source = root/'fixture.osm.pbf'
    xml = root/'fixture.osm'
    write_xml(xml, rows)
    header = osmium.io.Header()
    header.set('osmosis_replication_timestamp', STATE)
    with osmium.SimpleWriter(str(source), bufsz=65536, header=header) as writer:
        for row in osmium.FileProcessor(str(xml)):
            writer.add(row)
    artifact = Path('/artifacts/car-capacity.so')
    with artifact.open('rb') as stream:
        pin = hashlib.file_digest(stream, 'sha256').hexdigest()
    valid = Capacity(artifact, pin)
    target = root/'valid'
    target.mkdir()
    valid.begin(array('Q'), 4, target)
    try:
        receipt = valid.scan(source, STATE, CAPS)
        result = valid.finish()
    finally:
        valid.release()
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0 and receipt['semanticSha256'] == reference_seal(rows)
    assert (result['majorWays'], result['preClosureArcs'], result['postLocatableClosureArcs']) == (2, 2, 0)
    assert result['policyFullyLocatable']
    rejected = []
    for name, path, snapshot in [('header-epoch', source, '2026-10-24T21:21:21Z'), ('truncated', root/'truncated.osm.pbf', STATE)]:
        if name == 'truncated':
            path.write_bytes(source.read_bytes()[:-1])
        destination = root/name
        destination.mkdir()
        engine = Capacity(artifact, pin)
        engine.begin(array('Q'), 4, destination)
        try:
            try:
                engine.scan(path, snapshot, CAPS)
                raise AssertionError('Invalid tiny PBF accepted')
            except PilotError:
                rejected.append(name)
            try:
                engine.finish()
                raise AssertionError('Invalid source finished')
            except PilotError:
                pass
            assert not list(destination.glob('ways-*.bin'))
        finally:
            engine.release()
    return {'status': 'passed_composed_actual_tiny_pbf_entry_point', 'checks': 3, 'syntheticSourceBytes': source.stat().st_size,
            'semanticSha256': receipt['semanticSha256'], 'nativeArtifactSha256': pin, 'validCounters': result,
            'rejectedInputs': rejected, 'pythonProjectionFrames': 0, 'nativeLibraryUsed': True,
            'secondsIncludingTinySourceWriteReadAndRejectionChecks': time.monotonic()-began,
            'sourcePbfReads': 0, 'networkRequests': 0, 'applicationDbReads': 0, 'nationalGraphBuilt': False, 'modelChanged': False}

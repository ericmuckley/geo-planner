"""Independent saved synthetic qualification proof; no native/PBF/producer execution."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--local-assets', action='store_true')
parser.add_argument('--draft', action='store_true')
options = parser.parse_args()
f = Path(__file__).resolve().parent
r = f.parents[2]
load = lambda p: json.loads(p.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


seal = f/'sha256.json'
if seal.exists():
    assert not options.draft
    manifest = load(seal)
    assert set(manifest) == {str(p.relative_to(f)) for p in f.rglob('*') if p.is_file() and p != seal}
    for name, pin in manifest.items():
        assert sha(f/name) == pin, name
else:
    assert options.draft
    manifest = {}
parent = load(f/'parent-proof.json')
assert sha(r/parent['path']/'sha256.json') == parent['manifestSha256']
arguments = sys.argv
try:
    sys.argv = [str(r/parent['path']/'verify.py')]
    with contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(sys.argv[0], run_name='__main__')
finally:
    sys.argv = arguments
sys.path.insert(0, str(r/'scripts'))
from run_osm_country_screen_v1 import validate, isolation, ASSET_PROOF, ASSET_ROOT
from coarse_osm_projector_v1 import reference_seal
from coarse_osm_country_screen_v1 import priority, RECEIPT_NAMES, LIMIT_NAMES, XY
from coarse_osm_delta_v1 import ReferenceCodec
from coarse_osm_delta_v2 import Reader
from coarse_osm_records import canonical, normalize
from coarse_osm_compact_v1 import coordinate

plan = load(f/'qualification-plan.json')
validate(plan)
freeze = load(f/'qualification-freeze.json')
assert sha(f/'qualification-plan.json') == freeze['recipeSha256'] == 'b61b64f5405a0528333f543b0f99efecd7e8412aab05a2ae9eb91ebf42d2c4b8'
raw = f/'raw'
assert sha(raw/'execution-plan.json') == freeze['recipeSha256']
for name, pin in plan['inputs'].items():
    if not name.startswith('data/'):
        assert sha(r/name) == pin, name
assert len(freeze['producerFiles']) == 4
for name, pin in freeze['producerFiles'].items():
    assert pin == plan['inputs'][name] == sha(r/name), name
assert len(plan['testIds']) == len(set(plan['testIds'])) == freeze['testCount'] == 103
summary = load(raw/'run-summary.json')
assert summary['status'] == 'country_screen_synthetic_qualified'
assert summary['phaseClientExitCodes'] == {'build': 0, 'controls': 0}
assert summary['networkRequests'] == summary['sourceOrSavedSampleReads'] == 0
assert not summary['fullImportAdmitted'] and not summary['modelChanged']
assert summary['hostSecondsIncludingInputAssetHashesBuildControlsCleanup'] == 16.939384625060484 < 600
cleanup = load(f/'cleanup-audit.json')
assert cleanup['exitCode'] == 1 and cleanup['bothIndependentInspectAbsent']
for phase in ('build', 'controls'):
    initial = load(raw/phase/'container-initial.json')
    isolation(initial, phase)
    assert not any(m['Destination'].startswith(('/samples/', '/source')) for m in initial['Mounts'])
    actual = load(raw/phase/'container-result.json')
    assert actual['clientExitCode'] == actual['State']['ExitCode'] == 0
    assert not actual['State']['Running'] and not actual['State']['OOMKilled']
    removed = load(raw/phase/'cleanup.json')
    assert removed['removed'] and removed['independentInspectAbsent']
    assert removed['ownedContainer'] in cleanup['ownedContainers']
    metrics = load(raw/phase/'metrics-end.json')
    assert int(metrics['memory.max']) == 4294967296 and int(metrics['memory.swap.max']) == 0
    assert 0 < int(metrics['memory.peak']) < 4294967296
    events = dict(line.split() for line in metrics['memory.events'].splitlines())
    assert events['oom'] == events['oom_kill'] == '0'

built = load(raw/'build/result.json')
assert built['artifactBytes'] == 2002760
assert built['artifactSha256'] == '0b3d2d9e609350252fb9850a2342215c6fae3172b03b76fc65350b55c66b9a53'
assert built['sourceSha256'] == sha(r/'scripts/coarse_osm_country_screen_v1.cpp') == sha(raw/'build/country-screen.cpp')
assert built['deltaSourceSha256'] == sha(r/'scripts/coarse_osm_delta_v1.cpp') == sha(raw/'build/delta.cpp')
assert built['elfSha256'] == sha(raw/'build/elf.log')
controls = load(raw/'controls/controls.json')
assert controls['tests'] == 103 and controls['successful']
assert controls['failures'] == controls['errors'] == controls['skipped'] == 0
log = (raw/'controls/worker.log').read_text()
assert 'Ran 103 tests' in log and '\nOK\n' in log
actual_ids = [line.split(' (')[0] for line in log.splitlines() if line.startswith('test_')]
assert len(actual_ids) == 103
result = load(raw/'controls/result.json')
assert result['status'] == 'passed_country_screen_synthetic_qualification'
assert result['controls'] == controls and not result['nationalExecutionAdmitted'] and not result['modelChanged']
assert result['aggregateCppSourceReceipts'] == 86867
scope = load(f/'scope-notes.json')['conservativeSyntheticViewBudget']
components = ('returnedCppReceipts', 'positiveEncoderAndReferenceViews', 'terminatedChildUpperBound',
              'otherPythonReferenceAndEncodingReserve', 'checkpointFramePreparationViews')
assert sum(scope[k] for k in components) == scope['upperBoundIncludingReserves'] == 1080422 < scope['limit'] == 2000000
abi = load(f/'abi.json')
assert list(abi['receiptSlots'].values()) == list(RECEIPT_NAMES)
assert list(abi['limitSlots'].values()) == list(LIMIT_NAMES)

fields = load(raw/'controls/reference-fields.json')
assert fields == load(raw/'controls/projected-fields.json') and len(fields) == 500
for row in fields:
    assert normalize(row, '2026-10-25T21:21:21Z', 1048576) == row
semantic = reference_seal(fields)
assert semantic == result['proof']['semanticSha256'] == 'b98149892668d7880e9c4d7443f56d81dbd1a16a33f0a0c62699c78d269200f8'
proof = result['proof']
assert proof == load(raw/'controls/proof-receipt.json')
assert proof['nativeEof'] and proof['counts'] == {'node': 300, 'way': 200}
assert proof['sourceIdentity']['sourceSha256'] == sha(raw/'controls/fixture.pbf')
assert proof['sourceIdentity']['framingBytesRead'] == proof['postSourceHashBytes'] == 1202
assert proof['knownGuardReadBytes'] == 2404
pipeline = load(raw/'controls/two-pass/result.json')
assert pipeline['status'] == result['positivePipelineStatus'] == 'passed_bounded_country_screen_pipeline'
assert pipeline['objectReceipts'] == result['positivePipelineReceipts'] == 1000
pair = raw/'controls/two-pass'
a, b = (load(pair/name/'summary.json') for name in ('pass-a', 'pass-b'))
assert [a, b] == pipeline['passes']
assert a['globalManifest'] == b['globalManifest'] and a['mapping'] == b['mapping']
assert a['receipt']['semanticSha256'] == b['receipt']['semanticSha256'] == semantic
assert a['receipt']['pythonProjectionFrames'] == b['receipt']['pythonProjectionFrames'] == 0
assert (pair/'pass-a/global-directory.bin').read_bytes() == (pair/'pass-b/global-directory.bin').read_bytes()
assert (pair/'pass-a/global-catalog.json').read_bytes() == (pair/'pass-b/global-catalog.json').read_bytes()
assert (pair/'pass-a/probe/index.json').read_bytes() == (pair/'pass-b/probe/index.json').read_bytes()
assert not (pair/'pass-a/probe/00000000.bin').exists()
node_rows = [(row['id'], coordinate(row['lon'], 180), coordinate(row['lat'], 90)) for row in fields if row['type'] == 'node']
reader = Reader(pair/'pass-b/probe', ReferenceCodec())
actual_rows = []
try:
    for number in range(reader.manifest['blocks']):
        ids, xy = reader.block(number)
        actual_rows.extend((identity, xy[2*k], xy[2*k+1]) for k, identity in enumerate(ids))
    assert actual_rows == node_rows
    assert reader.manifest == a['globalManifest']
    assert reader.bytes == a['logicalWholeIndexBytes'] == b['logicalWholeIndexBytes']
finally:
    reader.close()
expected_witness = b''.join(XY.pack(*row) for row in node_rows)
assert (pair/'pass-b/source-witness.bin').read_bytes() == expected_witness
assert hashlib.sha256(expected_witness).hexdigest() == pipeline['referenceAudit']['idXYRowsSha256']
ways = [row for row in fields if row['type'] == 'way']
chosen = sorted(enumerate(ways), key=lambda item: (priority(item[1]['id']), item[1]['id'], item[0]))[:128]
expected_trace = [{'wayID': row['id'], 'version': row['version'], 'sourceWayOrdinal': ordinal,
                   'priority': priority(row['id']), 'references': row['nodes']} for ordinal, row in chosen]
assert expected_trace == load(pair/'pass-a/way-trace.json') == load(pair/'pass-b/way-trace.json')
keys = [row[0] for row in node_rows]
cohorts = {'local': list(reversed(keys))+keys[:128], 'spread': [keys[0], keys[0]],
           'way-refs': [ref for row in expected_trace for ref in row['references']]}
xy_by_id = {identity: (x, y) for identity, x, y in node_rows}
lookup = load(pair/'lookup.json')
assert lookup == pipeline['lookup'] and lookup['authenticatedShardBytes'] == 34692
for query in lookup['runs']:
    ids = cohorts[query['cohort']]
    expected_bits = b''.join(struct.pack('<dd', xy_by_id[i][0]/10000000, xy_by_id[i][1]/10000000) for i in ids)
    assert query['occurrences'] == len(ids) and query['uniqueIds'] == len(set(ids))
    assert query['coordinateBitsSha256'] == hashlib.sha256(expected_bits).hexdigest()
    assert query['authenticatedShardBytes'] == (5782 if query['kind'] == 'cold-application' else 2891)
assert len(lookup['runs']) == 9
closed = load(f/'closed-output.json')
assert closed['files'] == len(closed['roster']) == 54
assert closed['totalBytes'] == sum(row['bytes'] for row in closed['roster'].values()) == 3519966
assert closed['mirroredFiles'] == len(closed['mirroredRoster']) == 53
assert closed['mirroredBytes'] == sum(row['bytes'] for row in closed['mirroredRoster'].values()) == 1517206
assert set(closed['mirroredRoster']) == {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
for name, row in closed['mirroredRoster'].items():
    assert (raw/name).stat().st_size == row['bytes'] and sha(raw/name) == row['sha256'], name
assert closed['roster']['build/country-screen.so'] == {'bytes': built['artifactBytes'], 'sha256': built['artifactSha256']}
if options.local_assets:
    for name, pin in plan['inputs'].items():
        assert sha(r/name) == pin, name
    root = r/closed['root']
    assert set(closed['roster']) == {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    for name, row in closed['roster'].items():
        assert (root/name).stat().st_size == row['bytes'] and sha(root/name) == row['sha256'], name
    module = runpy.run_path(str(r/ASSET_PROOF))
    assert module['snapshot'](r/ASSET_ROOT) == plan['rootfs']['portable']
    for name, header in plan['headers'].items():
        assert module['snapshot'](r/header['path']) == header['portable']
print(json.dumps({'qualificationProofPassed': True, 'draft': options.draft, 'recordFiles': len(manifest),
                  'producerFiles': 263, 'priorSealedRuns': 53, 'actualLinuxTests': 103, 'linuxSkips': 0,
                  'all500FullFieldsAnd300CoordinateRowsVerified': True, 'lookupOrderDuplicatesAndBitsVerified': True,
                  'bothOwnedWorkersIndependentlyAbsent': True, 'localAssetsChecked': options.local_assets,
                  'nationalExecutionAdmitted': False, 'modelChanged': False}, indent=2))

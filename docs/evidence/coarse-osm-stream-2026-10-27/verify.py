"""Saved prototype proof; no network, Docker, native scan or producer replay."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sqlite3
import statistics
import struct
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bindings(mapping, root):
    for name, pin in mapping.items():
        assert sha(root / name) == pin, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
bindings(manifest, folder)
parent = load(folder / 'parent-proof.json')
assert sha(repo / parent['path'] / 'sha256.json') == parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):
    runpy.run_path(str(repo / parent['path'] / 'verify.py'), run_name='__main__')
assert sha(folder / 'execution-plan.json') == '2b91e6547522e701ca0043e73fc4490932ae9c2687980a73ee0aa6db01475bd1'
plan = load(folder / 'execution-plan.json')
assert plan['phase'] == 'offline_stream_profile_v1' and plan['network'] == 'none' and plan['imagePull'] == 'never'
assert len(plan['inputs']) == 234 and len(plan['workerFiles']) == 233
bindings({n: s for n, s in plan['inputs'].items() if not n.startswith('data/')}, repo)
assert '/inputs/source.pbf' not in plan['mounts'].values()
assert all('us-osm-input-v3/download' not in name for name in plan['mounts'])
assert len(plan['extractConfig']['windows']) == 21
caps = plan['caps']
assert caps['minimumMedianSpeedup'] == 1.25 and caps['maximumSampleIndexFraction'] == .75
assert caps['totalNativeObjects'] == 2000000 and caps['memoryBytes'] == 4294967296
raw = folder / 'raw'
assert load(raw / 'controls.json') == {'tests': 27, 'successful': True, 'failures': 0, 'errors': 0, 'skipped': 0}
initial = load(raw / 'container-initial.json')
assert initial['Limits'] == {'NetworkMode': 'none', 'Memory': 4294967296, 'MemorySwap': 4294967296,
    'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'}}
assert all(not r['writable'] for r in initial['Mounts'] if r['destination'] != '/work')
assert {u['Name']: (u['Soft'], u['Hard']) for u in initial['Ulimits']} == {'core': (0, 0), 'fsize': (67108864, 67108864)}
guards = load(raw / 'resource-guards.json')
assert guards['memory'] == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0}
assert guards['tmpBytes'] == 268435456 and guards['fileBytes'] == 67108864
final = load(raw / 'container-result.json')['State']
assert final['ExitCode'] == 0 and not final['Running'] and not final['OOMKilled']
summary = load(raw / 'run-summary.json')
assert summary['workerClientExitCode'] == 0 and summary['hostSecondsBeforeSummary'] < 600
cleanup = load(raw / 'cleanup.json')
assert cleanup['removed'] and cleanup['independentInspectAbsent']
independent = load(folder / 'cleanup-audit.json')
assert independent['ownedContainer'] == cleanup['ownedContainer'] and independent['independentInspectAbsent'] and independent['exitCode'] == 1
result = load(raw / 'result.json')
assert result['status'] == 'passed_sample_screen' and result['sampleGatesPassed'] and result['equivalentSamplesAndCoordinates']
assert result['workerSecondsBeforeSummary'] < 300 and result['observedProcessMaxRssKiB'] * 1024 < caps['memoryBytes']
assert not any(result[k] for k in ('wholeSourceEof', 'wholeExtractionQualified', 'modelChanged', 'networkRequests'))
assert result['nativeObjectVisits'] == plan['sourceReadBounds']['plannedNativeVisitsIncludingEncoding'] == 521000
cases = result['cases']
assert len(cases) == 8 and [(r['name'], r['mode']) for r in cases] == [tuple(c) for c in plan['cases']]
for row in cases:
    assert row == dict(name=row['name'], **load(raw / row['name'] / 'result.json'))
    assert row['counts'] == {'node': 64000} and row['nativePrefixEof']
    assert row['projectedSha256'] == 'e845926261ab0fc4d7c1d8a904e08bbde01fd9e063b582d6537fc4cdd0a957b7'
    assert row['indexLoopSeconds'] < 60
indexed = [r for r in cases if r['mode'] in ('v4', 'compact')]
assert len({r['lookupCoordinateSha256'] for r in indexed}) == 1
medians = {mode: statistics.median(r['indexLoopSeconds'] for r in indexed if r['mode'] == mode) for mode in ('v4', 'compact')}
assert medians == result['medianIndexSeconds']
assert medians['v4'] / medians['compact'] == result['medianSpeedup'] >= 1.25
for row in indexed:
    assert row['indexBytes'] == (1748992 if row['mode'] == 'v4' else 1024256)
    assert row['lookupQueries'] == 1152 and row['lookupSeconds'] > 0
assert result['indexByteFraction'] == 1024256 / 1748992 <= .75
for mode, row in zip(('v4', 'validation'), result['mixed']):
    assert row == load(raw / ('mixed-' + mode) / 'result.json')
    assert row['counts'] == {'node': 1000, 'way': 1000, 'relation': 1000}
    assert row['projectedSha256'] == plan['mixed']['sha256'] and row['nativePrefixEof']
audit = load(folder / 'index-byte-audit.json')
assert audit['sqliteFilesIdentical'] and not audit['nativeReplay']
assert len(audit['cases']) == 3 and all(r['rowsCompared'] == 64000 and r['exactCoordinateFloatBits'] for r in audit['cases'])
decision = load(folder / 'design-decision.json')
forecast = decision['forecast']
assert forecast['optimisticTwoNodePassSeconds'] == 2 * 1606229364 * medians['compact'] / 64000
assert forecast['marginedTwoNodePassSeconds'] == 2 * forecast['optimisticTwoNodePassSeconds'] > 14340
assert forecast['payloadOnlyAtStorageMargin'] == 1.5 * 16 * 1606229364 > forecast['oldPerIndexBytes'] == 25769803776
assert not forecast['payloadOnlyStorageScreenPasses']
assert not decision['fullExtractionAdmitted'] and not decision['nationalSourceMountedOrReadByProfile'] and not decision['modelChanged']
checks = load(folder / 'verification.json')
assert checks['hostTests'] == checks['linuxTests'] == 27 and checks['hostPassed'] == 26 and checks['hostNativeSkipped'] == 1
assert checks['checkPassed197Files'] and checks['typecheckPassed'] and checks['buildPassed']
roster = load(folder / 'closed-output.json')
assert roster['files'] == len(roster['roster']) == 45 and roster['totalBytes'] == sum(r['bytes'] for r in roster['roster'].values()) == 13120016
for name, row in roster['roster'].items():
    mirror = raw / name
    if mirror.exists():
        assert sha(mirror) == row['sha256'] and mirror.stat().st_size == row['bytes']

local = '--local-assets' in sys.argv
if local:
    bindings(plan['inputs'], repo)
    root = repo / roster['root']
    assert set(roster['roster']) == {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    for name, row in roster['roster'].items():
        path = root / name
        assert not path.is_symlink() and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], name
    reference = root / 'pair-0-v4/nodes.sqlite'
    with sqlite3.connect(reference.resolve().as_uri() + '?mode=ro', uri=True) as db:
        expected = db.execute('SELECT id,lon,lat FROM nodes ORDER BY id').fetchall()
    for row in indexed:
        if row['mode'] == 'v4':
            assert sha(root / row['name'] / 'nodes.sqlite') == audit['sqliteSha256']
            continue
        index = root / row['name'] / 'nodes'
        catalog = load(index / 'index.json')
        actual = []
        for number, entry in enumerate(catalog['entries']):
            raw_bytes = (index / f'{number:08d}.bin').read_bytes()
            magic, count, first, last, digest = struct.unpack_from('<8sQQQ32s', raw_bytes)
            assert magic == b'GPCOOR1\0' and len(raw_bytes) == 64 + 16 * count
            assert hashlib.sha256(raw_bytes[64:]).digest() == digest
            assert hashlib.sha256(raw_bytes).hexdigest() == entry['sha256']
            actual.extend((i, x / 10000000, y / 10000000) for i, x, y in struct.iter_unpack('<qii', raw_bytes[64:]))
        assert len(actual) == len(expected) == 64000
        assert all(a[0] == b[0] and struct.pack('<dd', *a[1:]) == struct.pack('<dd', *b[1:]) for a, b in zip(actual, expected))

print(json.dumps({'recordFiles': len(manifest), 'producerFiles': 229, 'priorSealedRuns': 42,
    'bindingsValid': True, 'localAssetsChecked': local, 'medianSpeedup': result['medianSpeedup'],
    'indexByteFraction': result['indexByteFraction'], 'nativeViewsIncludingReencoding': 521000,
    'independentCleanupConfirmed': True, 'wholeExtractionQualified': False, 'v9Unchanged': True}, indent=2))

"""Read-only saved inventory proof; no Docker, network or native/producer replay."""
import collections
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bindings(mapping, root):
    for name, digest in mapping.items():
        assert sha(root / name) == digest, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
bindings(manifest, folder)
parent = load(folder / 'parent-proof.json')
assert sha(repo / parent['path'] / 'sha256.json') == parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):
    runpy.run_path(str(repo / parent['path'] / 'verify.py'), run_name='__main__')

names = ['execution-plan.json', 'inventory-plan-v2.json', 'inventory-plan-v3.json']
pins = ['32459e6f534412de7dad837f5b6241712ab043ad108dcd0f97fb1efcd3e7641d',
        '0292d5f66edbf6a38df2c31a8e002a4204221d93bfab283d5e9ecc1346514466',
        'cf1d2b7fcb228b4a64324d3333e83cf4a40857ce6ac5b6717564fef49b64b30f']
plans = [load(folder / name) for name in names]
for name, pin in zip(names, pins):
    assert sha(folder / name) == pin
assert [len(p['inputs']) for p in plans] == [250, 279, 308]
assert [len(p['workerFiles']) for p in plans] == [219, 222, 225]
assert [p['caps']['visitLimit'] for p in plans] == [1110000000, 1610000000, 1930000000]
for plan in plans:
    bindings({name: digest for name, digest in plan['inputs'].items() if not name.startswith('data/')}, repo)
    assert plan['network'] == 'none' and plan['imagePull'] == 'never'
    assert len(plan['extractConfig']['windows']) == 21
    assert plan['forecastInputs'] == plans[0]['forecastInputs']
    for key in ('extractConfig', 'source', 'imageId', 'site', 'runtime'):
        assert plan[key] == plans[0][key], key
    for key in ('samplePerKind', 'sampleBytes', 'elementBytes', 'headerBytes', 'workingBytesIncludingTmp',
                'tmpBytes', 'fileBytes', 'reportBytes', 'memoryBytes', 'cpus', 'pids',
                'forecastTimeMargin', 'forecastStorageMargin'):
        assert plan['caps'][key] == plans[0]['caps'][key], key
revision = plans[2]['inventoryOnlyRevision']
assert revision['noFurtherNativeInventoryAllocationInThisStage']
assert revision['originalFullImportPerTypeCeilingsStillHeld']
assert revision['observedSourceCallbacksAlreadySpent'] + plans[2]['caps']['visitLimit'] + 1 == 4430000003 < 4440000000
assert [plans[2]['caps'][kind + 'Limit'] for kind in ('node', 'way', 'relation')] == [1930000000] * 3
assert plans[2]['caps']['countSeconds'] == 1500 and plans[2]['caps']['hostSeconds'] == 2100

results = []
summaries = []
rosters = []
for index, plan in enumerate(plans):
    version = 'v' + str(index + 1)
    root = folder / version
    result = load(root / 'result.json')
    inventory = result['inventory']
    results.append(result)
    assert inventory == load(root / 'scan/inventory-result.json')
    assert sum(inventory['counts'].values()) == inventory['nativeCallbackVisits']
    assert inventory['sampleCounts'] == {k: min(n, 1000) for k, n in inventory['counts'].items()}
    assert not inventory['sourceMetadataValidatedGlobally']
    assert inventory['sampleBytes'] <= plan['caps']['sampleBytes']
    assert inventory['elapsedCountSeconds'] < plan['caps']['countSeconds']
    assert result['workerSecondsBeforeSummary'] < plan['caps']['workerSeconds']
    assert result['observedProcessMaxRssKiB'] * 1024 < plan['caps']['memoryBytes']
    expected_exit = 0 if index == 2 else 2
    final = load(root / 'container-result.json')['State']
    assert final['ExitCode'] == expected_exit and not final['OOMKilled'] and not final['Running']
    summary = load(root / 'run-summary.json')
    summaries.append(summary)
    assert summary['workerClientExitCode'] == expected_exit
    assert summary['wholeSourceNativeEof'] == (index == 2)
    assert summary['hostSecondsIncludingHashAndCleanupBeforeSummary'] < plan['caps']['hostSeconds']
    assert not summary['networkRequests'] and not summary['wholeExtractionQualified'] and not summary['modelChanged']
    controls = load(root / 'controls.json')
    assert controls == {'tests': 24 if index == 0 else 25, 'successful': True, 'failures': 0, 'errors': 0, 'skipped': 0}
    initial = load(root / 'container-initial.json')
    assert initial['Limits'] == {'NetworkMode': 'none', 'Memory': 4294967296, 'MemorySwap': 4294967296,
        'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'}}
    assert all(not row['writable'] for row in initial['Mounts'] if row['destination'] != '/work')
    assert {u['Name']: (u['Soft'], u['Hard']) for u in initial['Ulimits']} == {'core': (0, 0), 'fsize': (67108864, 67108864)}
    guards = load(root / 'resource-guards.json')
    assert guards['memory'] == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0}
    assert guards['tmpBytes'] == 268435456
    cleanup = load(root / 'cleanup.json')
    independent = load(folder / (version + '-cleanup-audit.json'))
    assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent']
    assert cleanup['ownedContainer'] == independent['ownedContainer']
    binding = load(root / 'source-binding.json')
    assert binding['bytesHashedBeforeNativeWork'] == plan['source']['bytes'] == 12229320016
    assert binding['sha256'] == plan['source']['sha256'] and binding['md5'] == plan['source']['md5']
    header = load(root / 'header.json')
    assert header['prefix']['frames'] == 1 and header['prefix']['sampleBytes'] == 191
    assert header['identity']['publisherStateUtc'] == plan['source']['publisherStateUtc']
    assert set(header['identity']['requiredFeatures']) == {'DenseNodes', 'OsmSchema-V0.6'}
    assert sha(root / 'header.osm.pbf') == header['prefix']['sampleSha256']
    comparison = load(root / 'sample-comparison.json')
    assert comparison == result['sampleComparison'] and comparison['equivalent'] and comparison['allSampleRecordsAccepted']
    assert comparison['sampleCounts'] == inventory['sampleCounts'] and not comparison['wholeSourceMetadataValidation']
    for kind, row in comparison['cases'].items():
        assert row == load(root / ('validation-' + kind) / 'result.json')
        assert row['accepted'] and row['error'] is None
        assert row['returnedRecords'] == row['visits'] == sum(inventory['sampleCounts'].values())
        assert row['returnedSha256'] == inventory['sampleSha256'] and row['loadedCounts'] == inventory['sampleCounts']
        nonempty_counts = {k: n for k, n in inventory['sampleCounts'].items() if n}
        assert row['passes'] == [{'label': 'mixed-sample', 'status': 'eof', 'counts': nonempty_counts}]
    assert all(not result[k] for k in ('networkRequests', 'wholeExtractionQualified', 'sourceFeasibilityQualified',
        'publisherBoundaryQualified', 'usableAttributesQualified', 'modelChanged'))
    assert len(result['windows']) == 21 and {w['status'] for w in result['windows']} == {'unqualified_inventory_only'}
    roster = load(folder / (version + '-output.json'))
    rosters.append(roster)
    assert roster['files'] == len(roster['roster']) == 23
    assert roster['totalBytes'] == sum(row['bytes'] for row in roster['roster'].values())
    assert roster['totalBytes'] < plan['caps']['workingBytesIncludingTmp'] - plan['caps']['tmpBytes']
    for name, row in roster['roster'].items():
        mirror = root / name
        if mirror.is_file():
            assert mirror.stat().st_size == row['bytes'] and sha(mirror) == row['sha256'], name
        else:
            assert index == 2 and name == 'scan/samples.jsonl'
    assert not any(name.endswith('.sqlite') for name in roster['roster'])

for result, count in zip(results[:2], (1000000001, 1500000001)):
    inv = result['inventory']
    assert inv['counts'] == {'node': count, 'way': 0, 'relation': 0}
    assert not inv['wholeSourceNativeEof'] and inv['status'] == 'stopped'
    assert inv['error'] == {'type': 'PilotError', 'message': 'Inventory native object cap'}
    assert result['importerDecision']['decision'] == 'hold_incomplete_inventory'
    assert not result['importerDecision']['countsComplete']

final = results[2]
inventory = final['inventory']
counts = {'node': 1606229364, 'way': 162688797, 'relation': 1624265}
assert inventory['counts'] == counts and inventory['nativeCallbackVisits'] == 1770542426
assert inventory['wholeSourceNativeEof'] and inventory['status'] == 'native_eof' and inventory['error'] is None
assert inventory['sampleCounts'] == dict.fromkeys(counts, 1000) and inventory['sampleBytes'] == 3304488
assert inventory['sampleSha256'] == 'fd45e8844f790da058c708689548ee477382826d202ff06968d91db5ee1aee95'
decision = final['importerDecision']
assert decision['decision'] == 'reject_current_all_node_four_pass_strategy'
assert decision['reasons'] == ['node_index_time_screen', 'coordinate_index_storage_screen']
assert decision['originalFullImportRowCeilings'] == {'node': 1000000000, 'way': 100000000, 'relation': 10000000}
assert decision['originalFullImportRowCeilingsExceeded'] and not decision['wholeExtractionAdmitted']
forecast = decision['forecast']
inputs = plans[2]['forecastInputs']
assert forecast['optimisticTwoNodeIndexSeconds'] == 2 * counts['node'] * inputs['candidateNodeIndexMedianSeconds'] / 64000
assert forecast['marginedTwoNodeIndexSeconds'] == 2 * forecast['optimisticTwoNodeIndexSeconds'] > 14340
assert forecast['indexBytesEachBeforeMargin'] == counts['node'] * 1748992 / 64000
assert forecast['marginedIndexBytesEach'] == 1.5 * forecast['indexBytesEachBeforeMargin'] > 25769803776
assert forecast['marginedWorkingBytes'] == inputs['otherOriginalWorkingBytes'] + 2 * forecast['marginedIndexBytesEach'] > 68719476736
design = load(folder / 'design-decision.json')
arithmetic = design['hardArithmetic']
assert arithmetic['fourFullPassVisits'] == 4 * inventory['nativeCallbackVisits'] == 7082169704 > arithmetic['originalTotalVisitCeiling'] == 4440000000
assert arithmetic['twoFullPassVisits'] == 2 * inventory['nativeCallbackVisits'] == 3541084852 < 4440000000
assert arithmetic['fourPassExcessVisits'] == 2642169704 and arithmetic['twoPassRemainingVisitAllowance'] == 898915148
assert design['fixedPrefixForecast'] == forecast and design['inventoryCounts'] == counts
assert design['compactIndexHypothesis']['payloadBytesPerIndex'] == 16 * counts['node'] == 25699669824
assert not design['fullExtractionAdmitted'] and not design['newNativeInventoryAllocation'] and not design['modelChanged']
execution = load(folder / 'execution-result.json')
assert execution['sourceCallbackVisitsAcrossInventoryAttempts'] == sum(r['inventory']['nativeCallbackVisits'] for r in results) == 4270542428 < 4430000003
assert execution['hostSecondsAcrossInventoryAttempts'] == sum(s['hostSecondsIncludingHashAndCleanupBeforeSummary'] for s in summaries) < 14400
assert execution['completeCounts'] == counts and execution['wholeSourceNativeEof']
audit = load(folder / 'sample-byte-audit.json')
assert audit['sampleSha256'] == inventory['sampleSha256'] and audit['sampleBytes'] == inventory['sampleBytes']
assert audit['sampleCounts'] == inventory['sampleCounts'] and audit['canonicalLines'] and audit['v1V2V3NodeSampleBytesIdentical']
assert not audit['nativeReplay'] and not audit['sourceSelectionIndependentlyReplayed']
checks = load(folder / 'verification.json')
assert checks['hostV3Tests'] == checks['linuxV3Tests'] == 25
assert checks['hostV3Passed'] == 23 and checks['hostNativeSkips'] == 2 and checks['linuxNativeSkips'] == 0
assert checks['checkPassed197Files'] and checks['typecheckPassed'] and checks['buildPassed']

local = '--local-assets' in sys.argv
if local:
    for plan in plans:
        bindings(plan['inputs'], repo)
    for version, roster in zip(('v1', 'v2', 'v3'), rosters):
        root = repo / roster['root']
        assert set(roster['roster']) == {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        for name, row in roster['roster'].items():
            path = root / name
            assert not path.is_symlink() and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], name
    root = repo / rosters[2]['root']
    lines = (root / 'scan/samples.jsonl').read_bytes().splitlines(keepends=True)
    by_kind = collections.defaultdict(list)
    for line in lines:
        raw = json.loads(line)
        assert json.dumps(raw, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n' == line
        by_kind[raw['type']].append(line)
    assert {k: len(v) for k, v in by_kind.items()} == inventory['sampleCounts']
    for kind, records in by_kind.items():
        raw = b''.join(records)
        assert hashlib.sha256(raw).hexdigest() == audit['sampleTypeSha256'][kind]
        assert len(raw) == audit['sampleTypeBytes'][kind]
    assert b''.join(by_kind['node']) == (folder / 'v1/scan/samples.jsonl').read_bytes() == (folder / 'v2/scan/samples.jsonl').read_bytes()
    with (repo / plans[2]['source']['path']).open('rb') as stream:
        assert stream.read(191) == (folder / 'v3/header.osm.pbf').read_bytes()

print(json.dumps({'recordFiles': len(manifest), 'producerFiles': 223, 'priorSealedRuns': 41,
    'bindingsValid': True, 'localAssetsChecked': local, 'counts': counts, 'wholeSourceNativeEof': True,
    'mixedSampleRecords': 3000, 'sourceCallbackVisitsAcrossAttempts': 4270542428,
    'sourceRequests': 0, 'ownedRemovalsIndependentlyConfirmed': True,
    'currentFourPassImporterRejected': True, 'wholeExtractionQualified': False, 'v9Unchanged': True}, indent=2))

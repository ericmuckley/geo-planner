"""Read-only native tool milestone proof; no HTTP/Docker/setup/native-reader replay."""
import hashlib
import json
from pathlib import Path
import sys


folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(mapping, root):
    for name, digest in mapping.items(): assert sha(root / name) == digest, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
files(manifest, folder)
checks = load(folder / 'checks.json'); files(checks['producerFiles'], repo); files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    prior = repo / 'docs/evidence' / name; assert sha(prior / 'sha256.json') == record['manifestSha256']
    previous = load(prior / 'sha256.json'); assert len(previous) == record['files']; files(previous, prior)
for name, expected in [('execution-plan.json', 'c3a7ee162f29a67fc9a284e327edcc0f0dcd84be8fa03540f7c38a963a68f301'),
    ('offline-execution-plan.json', '7a8e2b4a2cbf78d8b062c7917328c7cbd63c6be4b6f92f0a663dbe811be82591')]:
    assert sha(folder / name) == expected
    plan = load(folder / name)
    # The v3 recipe additionally binds a retained ignored package body; local-assets checks it below.
    files({p: s for p, s in plan['inputs'].items() if not p.startswith('data/')}, repo)
v2 = folder / 'v2'; v3 = folder / 'v3'; ledger = load(v2 / 'acquire/http/http-ledger.json'); audit = load(folder / 'tool-audit.json')
assert len(ledger['events']) == 1 and not ledger['stopped'] and ledger['receivedBodyBytes'] == 83528
event = ledger['events'][0]; pin = load(folder / 'execution-plan.json')['package']
assert event['bodySha256'] == pin['sha256'] == 'b61d2bdf82134f6db0ba5c73d9cfe88805a64cbadbd0d0dffff8410958aab005'
assert event['status'] == 200 and event['outcome'] == 'complete' and event['url'] == pin['url'] and event['bodyBytes'] == int(event['headers']['content-length']) == 83528
assert load(v2 / 'acquire/failure.json')['error'] == 'Unexpected runtime symlink'
assert load(v2 / 'run-summary.json')['status'] == 'stopped'
summary = load(v3 / 'run-summary.json'); assert summary['status'] == 'passed' and summary['runtimePackageRequests'] == 0
assert summary['phases'] == [{'phase': 'prepare', 'exitCode': 0}, {'phase': 'offline', 'exitCode': 0}]
runtime = load(v3 / 'prepare/runtime-receipt.json')
assert runtime['library']['bytes'] == 174168 and runtime['library']['sha256'] == '96c872449f41ac16cf6c974ea93e053713b41ea103165cb2c99bb0ebdc2e94be'
assert runtime['copyright']['bytes'] == 1756 and not runtime['packageScriptsExecuted']
assert load(v3 / 'offline/runtime-preflight.json')['runtimeClosurePassed']
assert load(v3 / 'offline/installation.json')['installedBytes'] == 8241646 and load(v3 / 'offline/installation.json')['installedFiles'] == 182
native = v3 / 'offline/native'; smoke = load(native / 'smoke-result.json'); state = load(native / 'extract/state.json')
assert smoke['status'] == 'passed' and smoke['tinyNativeDecoderQualified'] and smoke['pbfBytes'] == 564 and smoke['inputRecords'] == 9
assert smoke['retainedRecords'] == 4 and smoke['fourPassVisits'] == state['scanObjectVisits'] == 36
assert smoke['nativeTruncatedCheck']['rejected'] and len(smoke['negativeFramingChecks']) == 7 and all(p['rejected'] for p in smoke['negativeFramingChecks'])
assert sha(native / 'fixture.osm.pbf') == smoke['sourceIdentity']['sourceSha256']
assert sha(native / 'extract/elements.jsonl') == smoke['outputSha256'] == state['outputSha256']
assert load(native / 'extract/audit.json')['independentSelectionNativeIdentityAndOutputAudit']
assert not smoke['nationalSourceFeasibilityQualified'] and not state['sourceFeasibilityQualified'] and not state['publisherBoundaryQualified']
for root, phase, network, code in [(v2, 'acquire', 'bridge', 2), (v3, 'prepare', 'none', 0), (v3, 'offline', 'none', 0)]:
    container = load(root / phase / 'container-result.json'); cleanup = load(root / phase / 'cleanup.json')
    assert container['State']['ExitCode'] == code and not container['State']['OOMKilled']
    assert container['Limits'] == {'NetworkMode': network, 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True,
        'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=64m'}}
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    assert load(root / phase / 'resource-guards.json')['memory'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert len(load(folder / 'cleanup-audit.json')['workers']) == 3 and all(p['independentInspectAbsent'] for p in load(folder / 'cleanup-audit.json')['workers'])
assert audit['status'] == 'passed' and audit['independentArchiveReconstructionExecuted'] and audit['tinyNativeDecoderQualified']
assert audit['packageGetsAcrossV2V3'] == 1 and audit['additionalV3NetworkRequests'] == 0 and not audit['nationalSourceFeasibilityQualified']
assert audit['outputFiles'] == {'v2': 10, 'v3': 382} and audit['outputFileBytes'] == {'v2': 101981, 'v3': 16741766}
next_plan = load(folder / 'next-data-freeze-plan.json')
files({p: s for p, s in next_plan['runtimeInputs'].items() if not p.startswith('data/')}, repo)
local = '--local-assets' in sys.argv
if local:
    files(checks['assetFiles'], repo); files(checks['toolFiles'], repo); files(next_plan['runtimeInputs'], repo)
    for path, roster in checks['completedOutputs'].items(): assert set(roster) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    for output, mirrors in checks['mirroredOutputReports'].items():
        for name, mirror in mirrors.items(): assert sha(repo / output / name) == sha(folder / mirror)
    for name in ('execution-plan.json', 'offline-execution-plan.json'): files(load(folder / name)['inputs'], repo)
    sys.path.insert(0, str(repo / 'scripts')); from audit_osm_tools_v3 import audit as reconcile
    expected = dict(audit); expected['independentArchiveReconstructionExecuted'] = False
    assert reconcile(repo) == expected  # Native Zstandard reconstruction is the separately captured Linux receipt.
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']), 'priorSealedRuns': len(checks['priorSealedEvidence']),
    'allBindingsValid': True, 'localAssetsChecked': local, 'assetFiles': len(checks['assetFiles']), 'tools': len(checks['toolFiles']), 'completedOutputs': len(checks['completedOutputs']),
    'runtimePackageGets': 1, 'runtimePackageBodyBytes': 83528, 'additionalV3NetworkRequests': 0, 'tinyNativeDecoderQualified': True,
    'nativePbfBytes': 564, 'fourPassVisits': 36, 'nationalSourceQualified': False, 'v9Unchanged': True}, indent=2))

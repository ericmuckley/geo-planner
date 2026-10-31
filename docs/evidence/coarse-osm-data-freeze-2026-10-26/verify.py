"""Read-only executable data-freeze proof. Never start workers or acquire source data."""
import hashlib
import json
from pathlib import Path
import sys


folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


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
plan = load(folder / 'execution-plan.json')
expected = 'bc57f4e3e82a03201b4964efd0d33c5813a04410e5e048544bd2e7df4a459f14'
assert sha(folder / 'execution-plan.json') == expected and plan['phase'] == 'national_input_v2'
files({p: s for p, s in plan['inputs'].items() if not p.startswith('data/')}, repo)
proposal = load(repo / plan['proposal']); config = plan['extractConfig']; caps = config['proposedCaps']
assert config['source'] == proposal['source'] and config['windows'] == proposal['windows'] and len(config['windows']) == 21
expected_caps = dict(proposal['proposedCaps']); expected_caps.update(httpAttempts=1, wheelGets=0, metadataGets=0, toolArchiveBodyBytesWithinTotal=0, metadataBodyBytesWithinTotal=0)
assert caps == expected_caps and plan['sourceSpec'] == {'url': proposal['source']['url'], 'kind': 'pbf', 'maxBytes': 12229320016,
    'exactBytes': 12229320016, 'md5': 'c5abaec55e724255277f22fb97941e5a', 'seconds': 5400}
assert plan['activation'] == {'largerDataLimits': True, 'publisherState': '2026-10-25T21:21:21Z', 'onlyWhenExactHostCommandExecutes': True}
assert plan['networks'] == ['bridge', 'none'] and plan['imagePull'] == 'never'
assert len(plan['inputs']) == 206 and len(plan['workerFiles']) == 200 and len(plan['mounts']) == 16
assert len([p for p in plan['workerFiles'] if p.startswith('/tools/site/')]) == 182
arithmetic = load(folder / 'arithmetic.json'); components = config['resourceArithmetic']['storageComponents']
assert components == proposal['resourceArithmetic']['storageComponents']
assert sum(components.values()) == arithmetic['assignedWorkingBytes'] == 65270488400
assert arithmetic['workingSlackBytes'] == caps['workingBytesIncludingTmp'] - sum(components.values()) == 3448988336
assert arithmetic['maximumSourceBodyReadBytes'] == 12229320017 and arithmetic['bodySlackBytes'] == 655581871
assert plan['reservedReadOnlyInputsBytes'] == arithmetic['actualReadOnlyInputReservationBytes'] == 10722475
probe = load(folder / 'resource-probe-v2.json')
assert probe['producerSha256'] == sha(repo / 'scripts/coarse_osm_data.py')
assert probe['memory'] == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0} and probe['tmpBytes'] == 268435456
assert probe['cpuQuota'] == 2 * probe['cpuPeriod'] and probe['pidsLimit'] == 64 and probe['rootReadOnly']
assert probe['coreLimit'] == [0, 0] and probe['fileSizeLimit'] == [25769803776, 25769803776]
assert probe['watchdogKilledStalledChild'] and probe['absoluteTimerInterrupted'] and probe['tinySqlitePageCapStoppedWrites']
capacity = load(folder / 'capacity.json'); checked = load(folder / 'readonly-check.json')
assert checked['status'] == 'checked_not_executed' and checked['httpRequestsMade'] == 0 and not checked['outputCreated']
for observed in (capacity, checked['capacity']):
    assert observed['hostDiskAvailableBytes'] >= caps['requiredInitialFreeBytes'] == 85899345920
    assert observed['hostMemoryBytes'] >= 8589934592 and observed['dockerMemoryBytes'] >= 6442450944
    assert observed['hostCpuCount'] >= 2 and observed['dockerCpuCount'] >= 2
commands = load(folder / 'commands.json'); base = ['python3', '-B', 'scripts/prepare_osm_input_v2.py', str((folder / 'execution-plan.json').relative_to(repo)), expected, plan['output']]
assert commands['executeLaterOnce'] == base and commands['readOnlyCheck'] == base + ['--check'] and not commands['executedNow']
readiness = load(folder / 'pre-freeze-checks.json')
assert readiness['linux4GiBTests'] == {'run': 17, 'passed': 17} and readiness['hostTests'] == {'run': 17, 'passed': 16, 'skippedQualifiedLinuxNative': 1}
assert readiness['sourceRequests'] == readiness['providerRequests'] == 0 and readiness['outputAbsent']
local = '--local-assets' in sys.argv
if local:
    files(checks['assetFiles'], repo); files(checks['toolFiles'], repo); files(plan['inputs'], repo)
    for path, roster in checks['completedOutputs'].items(): assert set(roster) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    site = repo / plan['site']; assert {str(p.relative_to(repo)) for p in site.rglob('*') if p.is_file()} == {p for p in plan['inputs'] if p.startswith(plan['site'] + '/')}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']), 'priorSealedRuns': len(checks['priorSealedEvidence']),
    'allBindingsValid': True, 'localAssetsChecked': local, 'assetFiles': len(checks['assetFiles']), 'tools': len(checks['toolFiles']), 'completedOutputs': len(checks['completedOutputs']),
    'hostInputBindings': 206, 'workerFileBindings': 200, 'linuxDataControls': 17, 'resourceConfigurationChecked': True, 'readOnlyPreflightPassed': True,
    'futureSourceGetAttempts': 1, 'sourceRequestsAtPreparation': 0, 'nationalDataExecutedAtPreparation': False, 'sourceModelQualified': False, 'v9Unchanged': True}, indent=2))

"""Read-only design/probe proof. Never executes the probe, Docker or source readers."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
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
plan = load(folder / 'capability-plan.json')
assert sha(folder / 'capability-plan.json') == '21579cbf16848d835eea81c83a3b60d116c08202bafafbbe6dd20a927c806f98'
assert sha(folder / 'probe.py') == plan['probeSha256'] == 'b7dd9d68b461ac43a12d0dc5ff78ebfcd981c44d8478e99e73ebaef8d3c60950'
assert plan['network'] == 'none' and plan['pull'] == 'never' and plan['hostTimeoutSeconds'] == 45
assert not plan['sourceAndSamplesMounted'] and not plan['compilationAllowed']
initial = load(folder / 'container-initial.json')
assert initial['Limits'] == {'NetworkMode': 'none', 'Memory': 4294967296, 'MemorySwap': 4294967296,
    'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'}}
assert {m['destination'] for m in initial['Mounts']} == {'/probe.py', '/tools/site', '/tools/runtime'}
assert all(not m['writable'] for m in initial['Mounts'])
assert {u['Name']: (u['Soft'], u['Hard']) for u in initial['Ulimits']} == {'core': (0, 0), 'fsize': (16777216, 16777216)}
final = load(folder / 'container-result.json')
assert final['clientExitCode'] == final['State']['ExitCode'] == 0
assert not final['State']['Running'] and not final['State']['OOMKilled']
cleanup = load(folder / 'cleanup.json')
independent = load(folder / 'cleanup-audit.json')
assert cleanup['removed'] and cleanup['inspectAbsent'] and independent['independentInspectAbsent']
assert independent['ownedContainer'] == cleanup['ownedContainer'] and independent['exitCode'] == 1
observed = load(folder / 'probe-stdout.json')
assert len(observed['commands']) == 14 and all(row['path'] is None for row in observed['commands'].values())
assert not any(name.endswith(('.h', '.hpp')) for name in observed['nativeFiles'])
assert all(not row['exists'] for name, row in observed['headers'].items() if not name.endswith('/Python.h'))
assert not any(observed['optionalBuildModules'].values())
assert len(observed['mapTypes']) == 8 and 'sparse_file_array' in observed['mapTypes']
assert observed['machine'] == 'aarch64' and observed['zlibRuntimeVersion'] == '1.2.11'
assert observed['memory'] == {'memory.max': '4294967296', 'memory.swap.max': '0', 'pids.max': '64', 'cpu.max': '200000 100000'}
assert all(observed[k] == 0 for k in ('sourceObjectsRead', 'sampleFilesRead', 'compilations', 'networkRequests'))
execution = load(folder / 'execution-result.json')
scope = load(folder / 'timing-scope.json')
assert scope['recordedSeconds'] == execution[scope['rawField']] < 45
assert scope['toolReportedWholeCommandWallSeconds'] < 45
assert not execution['modelChanged']
decision = load(folder / 'capability-decision.json')
assert not decision['fullImportAdmitted'] and not decision['modelChanged']
guards = load(folder / 'guard-map.json')
assert len(guards) == 10 and all(not g['implemented'] for g in guards)
fmt = load(folder / 'format-design.json')
assert (fmt['rowsPerBlock'], fmt['blocksPerShard'], fmt['blockHeaderBytes'], fmt['directoryEntryBytes']) == (4096, 512, 64, 32)
assert not fmt['nationalIdRangeKnown']
calculator = runpy.run_path(str(folder / 'resource_screen.py'), run_name='design_arithmetic')
resource = calculator['result']()
assert resource == load(folder / 'resource-screen.json')
bound = calculator['bound']
for count, gap in [(1, 1), (2, 1), (2, 127), (2, 128), (2, 2**62), (100, 1), (100, 127), (100, 128), (100, 16384), (4097, 1), (4097, 128), (8193, 2**35)]:
    actual = sum((gap.bit_length() + 6) // 7 for i in range(count) if i % 4096)
    assert actual <= bound(count, 1 + (count - 1) * gap)['idVarintBytesUpperBound']
threshold = resource['largestMaximumIdPassingThisBound']
assert bound(1606229364, threshold)['perIndexScreenPassesConditionally']
assert not bound(1606229364, threshold + 1)['perIndexScreenPassesConditionally']
assert resource['actualNationalMaximumId'] is None
assert resource['illustrativeBound']['perIndexScreenPassesConditionally']
assert not resource['fullSigned63IdDomain']['perIndexScreenPassesConditionally']
assert resource['conditionalMarginedWorkingBytes'] < 68719476736
assert resource['additionalPrimaryDirectoryAndReceiptBytes'] == 29342272
assert resource['futureMarginedTwoNodePassForecastSecondsAtGate'] < 14340 / 2
assert not resource['fullImportAdmitted'] and not resource['anyNewNationalScan']
proposal = load(folder / 'dependency-proposal.json')
assert proposal['builder']['manifestDigest'] is None
assert all(s['fullCommit'] is None and s['archiveSha256'] is None for s in proposal['headerSources'])
next_stage = proposal['nextMetadataOnlyStage']
assert (next_stage['maximumRequests'], next_stage['maximumBodyBytesEach'], next_stage['maximumBodyBytesTotal'], next_stage['retries']) == (16, 2097152, 16777216, 0)
assert sum(proposal['componentCeilings'].values()) == proposal['closureReservationBytes'] == 14 * 1024**3
assert not proposal['fullImportAdmitted']
pins = load(folder / 'bindings.json')
bindings({n: s for n, s in pins.items() if not n.startswith('data/')}, repo)
local = '--local-assets' in sys.argv
if local:
    bindings(pins, repo)
print(json.dumps({'recordFiles': len(manifest), 'unchangedProducerFiles': 229, 'priorSealedRuns': 43,
    'bindingsValid': True, 'localAssetsChecked': local, 'probeReplayed': False, 'sourceOrSampleScans': 0,
    'compilerAbsentOnCheckedPath': True, 'nativeDesignImplemented': False, 'buildClosureLocked': False,
    'conditionalStorageBoundVerified': True, 'fullImportAdmitted': False, 'v9Unchanged': True}, indent=2))

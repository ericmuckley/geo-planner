"""Offline version3 correction using the saved exact package and six saved wheels."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from coarse_osm_bulk_transport import unpack_wheel
from coarse_osm_runtime import inspect_library
from coarse_osm_runtime_package import ZSTD_PATH, ZSTD_SHA
from coarse_osm_runtime_package_v3 import extract_runtime
from coarse_osm_records import strict_json
from coarse_timing_input import cgroup_limit, digest, json_bytes, require, start_watchdog
from setup_osm_tools import bounded_process, inventory, native_proof, wheel_metadata


def validate_plan(plan, scope):
    require(plan['phase'] == 'cached_runtime_correction_v3' and plan['output'] == scope['freshOutput'], 'Runtime phase/output')
    require(plan['package'] == scope['package'] and plan['caps'] == scope['caps'] and plan['imageId'] == scope['imageId'], 'Runtime pin/cap/image drift')
    require(plan['networks'] == ['none', 'none'] and plan['imagePull'] == 'never', 'Runtime network/pull drift')
    require(plan['zstd'] == {'path': ZSTD_PATH, 'sha256': ZSTD_SHA, 'versionNumber': 10505}, 'Runtime decoder pin')
    require(len(plan['wheels']) == 6 and sum(p['bytes'] for p in plan['wheels']) == 2387936, 'Saved wheel closure')
    require(type(plan['reservedReadOnlyInputsBytes']) is int and 2387936 <= plan['reservedReadOnlyInputsBytes'] <= 16777216, 'Read-only input storage reservation')


def prepare(root, plan):
    root = Path(root); archive = Path('/inputs/runtime-package.deb')
    require(archive.stat().st_size == plan['package']['exactBytes'] and digest(archive) == plan['package']['sha256'], 'Saved runtime package binding')
    receipt = extract_runtime(archive, plan['package'], root / 'runtime')
    (root / 'runtime-receipt.json').write_bytes(json_bytes(receipt))


def offline(root, plan, lock, recipe, expected):
    root = Path(root); began = time.monotonic(); caps = plan['caps']
    receipt = strict_json(Path('/inputs/runtime-receipt.json').read_bytes())
    require(receipt['archiveSha256'] == plan['package']['sha256'], 'Runtime receipt archive binding')
    preflight = inspect_library('/inputs/runtime/libexpat.so.1', receipt['library']['sha256'])
    require(digest('/inputs/runtime/copyright') == receipt['copyright']['sha256'], 'Runtime copyright binding')
    (root / 'runtime-preflight.json').write_bytes(json_bytes(preflight))
    validation = root / 'validation'; validation.mkdir(); expanded = 0; wheel_receipts = []
    archives = [Path('/inputs/wheels') / pin['filename'] for pin in lock['packages']]
    for archive, pin in zip(archives, lock['packages']):
        target = validation / pin['name']
        result = unpack_wheel(archive, pin, target, caps['validationBytes'] - expanded); expanded += result['installedBytes']
        wheel_receipts.append({'name': pin['name'], **result, 'metadata': wheel_metadata(target, pin, lock)})
    (root / 'wheel-validation.json').write_bytes(json_bytes({'bytes': expanded, 'packages': wheel_receipts}))
    site = root / 'site'; require(not site.exists(), 'New installed target required')
    maximum = expanded + caps['installedTreeBytes'] + caps['reportReserveBytes']
    bounded_process([sys.executable, '-B', '-m', 'pip', 'install', '--isolated', '--disable-pip-version-check', '--no-index', '--no-deps',
        '--no-compile', '--no-cache-dir', '--no-warn-script-location', '--target', str(site), *map(str, archives)], root, 120, maximum, log_name='pip.log')
    installed = inventory(site, caps['installedTreeBytes']); (root / 'installed-inventory.json').write_bytes(json_bytes(installed))
    bounded_process(['env', 'LD_LIBRARY_PATH=/inputs/runtime', sys.executable, '-B', '/code/setup_osm_tools_v3.py', str(recipe), expected, str(root), '--worker', 'proof'],
        root, 60, maximum, log_name='proof.log')
    require(inventory(site, caps['installedTreeBytes']) == installed, 'Native proof changed installed tree')
    proof = strict_json((root / 'native-proof.json').read_bytes())
    (root / 'installation.json').write_bytes(json_bytes({'status': 'passed', 'versions': proof['versions'], 'installedBytes': installed['bytes'],
        'installedFiles': len(installed['files']), 'tinyNativeDecoderQualified': proof['tinyNativeDecoderQualified'], 'nationalSourceFeasibilityQualified': False,
        'network': 'none', 'offlineSecondsBeforeReceipt': time.monotonic() - began, 'storageGuard': '20ms child polling/64MiB per-file limit/final inventory; not aggregate filesystem quota'}))


def worker(recipe, expected, root, phase):
    require(digest(recipe) == expected, 'Runtime recipe binding'); plan = strict_json(Path(recipe).read_bytes())
    for path, sha in plan['workerFiles'].items(): require(digest(path) == sha, 'Runtime worker binding: ' + path)
    validate_plan(plan, strict_json(Path('/inputs/scope.json').read_bytes()))
    require(cgroup_limit() == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}, 'Runtime actual memory/swap')
    require(digest(ZSTD_PATH) == ZSTD_SHA, 'Runtime cached decoder SHA')
    root = Path(root); seconds = 60 if phase == 'proof' else 600; watchdog = start_watchdog(seconds)
    guard = root / ('proof-resource-guards.json' if phase == 'proof' else 'resource-guards.json')
    with guard.open('xb') as stream: stream.write(json_bytes({'phase': phase, 'memory': cgroup_limit(), 'watchdogSeconds': seconds}))
    try:
        lock = strict_json(Path('/inputs/lock.json').read_bytes())
        require([(p['filename'], p['bytes'], p['sha256']) for p in plan['wheels']] == [(p['filename'], p['size'], p['sha256']) for p in lock['packages']], 'Saved wheels differ from exact lock')
        if phase == 'prepare': prepare(root, plan)
        elif phase == 'offline': offline(root, plan, lock, recipe, expected)
        else:
            require(os.environ.get('LD_LIBRARY_PATH') == '/inputs/runtime' and not (root / 'native-proof.json').exists(), 'Scoped runtime path/new proof')
            api = ctypes.CDLL('/inputs/runtime/libexpat.so.1'); api.XML_ExpatVersion.restype = ctypes.c_char_p
            with (root / 'expat-version.json').open('xb') as stream: stream.write(json_bytes({'version': api.XML_ExpatVersion().decode(), 'librarySha256': digest('/inputs/runtime/libexpat.so.1')}))
            native_proof(root, lock)
        return 0
    except Exception as error:
        with (root / ('proof-failure.json' if phase == 'proof' else 'failure.json')).open('xb') as stream:
            stream.write(json_bytes({'status': 'stopped', 'phase': phase, 'errorType': type(error).__name__, 'error': str(error)[:5000], 'nativeOrNationalGateRelaxed': False}))
        return 2
    finally:
        if watchdog.poll() is None: watchdog.terminate(); watchdog.wait(timeout=5)


def driver(recipe, expected, output):
    repo = Path(__file__).resolve().parents[1]; path = Path(recipe).resolve()
    require(path.is_relative_to(repo / 'docs/evidence') and digest(path) == expected, 'Runtime host recipe binding/path')
    plan = strict_json(path.read_bytes()); validate_plan(plan, strict_json((repo / plan['scope']).read_bytes()))
    for name, sha in plan['inputs'].items(): require(digest(repo / name) == sha, 'Runtime host input: ' + name)
    root = (repo / output).resolve(); require(root == repo / plan['output'], 'Runtime frozen output')
    mounts = []
    for source, target in plan['mounts'].items():
        host = (repo / source).resolve()
        require(host.is_relative_to(repo) and host.is_file() and target.startswith(('/code/', '/inputs/')), 'Runtime isolated mount')
        require(plan['inputs'][source] == plan['workerFiles'][target], 'Runtime mount/hash binding')
        mounts += ['--mount', f'type=bind,src={host},dst={target},readonly']
    root.mkdir(); (root / 'execution-plan.json').write_bytes(path.read_bytes())
    started = time.monotonic(); deadline = started + 570; results = []
    working_max = plan['caps']['workingBytesIncludingTmp'] - plan['caps']['tmpBytes'] - plan['reservedReadOnlyInputsBytes']
    for phase, network in zip(('prepare', 'offline'), plan['networks']):
        stage = root / phase; stage.mkdir(); identity = None; result = 2
        owner = uuid.uuid4().hex
        name = 'geo-planner-runtime-v3-' + owner[:12]; (stage / 'container-name.txt').write_text(name + '\n')
        def run(args, **options):
            left = deadline - time.monotonic(); require(left > 0, 'Shared runtime deadline')
            return subprocess.run(args, timeout=min(options.pop('timeout', 30), left), **options)
        extra = []
        if phase == 'offline':
            receipt = strict_json((root / 'prepare/runtime-receipt.json').read_bytes())
            for filename, record in [('libexpat.so.1', receipt['library']), ('copyright', receipt['copyright'])]:
                host = root / 'prepare/runtime' / filename; require(digest(host) == record['sha256'], 'Extracted runtime binding')
                extra += ['--mount', f'type=bind,src={host},dst=/inputs/runtime/{filename},readonly']
            extra += ['--mount', f'type=bind,src={root / "prepare/runtime-receipt.json"},dst=/inputs/runtime-receipt.json,readonly']
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.runtime-owner=' + owner, '--network=' + network, '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g', '--cpus=2', '--pids-limit=64', '--tmpfs=/tmp:rw,size=64m',
            '--mount', f'type=bind,src={stage},dst=/work', '--mount', f'type=bind,src={path},dst=/inputs/recipe.json,readonly', *mounts, *extra,
            '--entrypoint=python3', plan['imageId'], '-B', '/code/setup_osm_tools_v3.py', '/inputs/recipe.json', expected, '/work', '--worker', phase]
        try:
            created = run(command, check=True, capture_output=True, text=True).stdout.strip()
            require(len(created) == 64 and all(c in '0123456789abcdef' for c in created), 'Runtime owned worker ID'); identity = created
            def inspect(): return json.loads(run(['docker', 'inspect', identity], check=True, capture_output=True, text=True).stdout)[0]
            before = inspect(); hc = before['HostConfig']
            expected_limits = {'NetworkMode': network, 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True,
                'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=64m'}}
            require(before['Image'] == plan['imageId'] and all(hc[k] == v for k, v in expected_limits.items()), 'Runtime container isolation drift')
            with (stage / 'worker.log').open('xb') as log:
                child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
                try:
                    while child.poll() is None:
                        require(time.monotonic() < deadline, 'Shared runtime deadline'); inventory(root, working_max)
                        require(log.tell() <= 65536, 'Runtime worker log cap'); time.sleep(.1)
                    result = child.returncode
                finally:
                    if child.poll() is None: child.kill()
                    child.wait(timeout=5)
            after = inspect(); results.append({'phase': phase, 'exitCode': result})
            (stage / 'container-result.json').write_bytes(json_bytes({'Image': after['Image'], 'State': after['State'], 'Limits': expected_limits,
                'Mounts': [{'destination': m['Destination'], 'writable': m['RW']} for m in before['Mounts']]}))
        except Exception as error:
            (stage / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'ownedContainer': identity, 'hardStopCountersMayBePartial': True})); raise
        finally:
            if identity is None:
                found = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=max(1, min(5, started + 600 - time.monotonic())))
                if found.returncode == 0:
                    owned = json.loads(found.stdout)[0]
                    require(owned['Config']['Labels'].get('geo-planner.runtime-owner') == owner and owned['Image'] == plan['imageId'], 'Refuse cleanup of unowned container')
                    identity = owned['Id']
                else: require('No such' in found.stderr, 'Owned-name discovery failed')
            if identity:
                subprocess.run(['docker', 'rm', '-f', identity], check=True, capture_output=True, timeout=max(1, min(15, started + 600 - time.monotonic())))
                absent = subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, timeout=max(1, min(10, started + 600 - time.monotonic())))
                require(absent.returncode != 0 and 'No such' in absent.stderr, 'Runtime independent owned cleanup')
                (stage / 'cleanup.json').write_bytes(json_bytes({'ownedContainer': identity, 'removed': True, 'independentInspectAbsent': True}))
        if result: break
    saved = inventory(root, working_max); elapsed = time.monotonic() - started; require(elapsed < 600, 'Runtime final shared deadline')
    summary = {'status': 'passed' if len(results) == 2 and all(p['exitCode'] == 0 for p in results) else 'stopped', 'phases': results,
        'driverSecondsIncludingCleanupBeforeSummary': elapsed, 'outputBytesBeforeSummary': saved['bytes'], 'reservedReadOnlyInputsBytes': plan['reservedReadOnlyInputsBytes'],
        'runtimePackageRequests': 0, 'metadataRequests': 0, 'wheelRequests': 0, 'nationalPbfRequests': 0, 'providerRequests': 0, 'nationalSourceFeasibilityQualified': False}
    (root / 'run-summary.json').write_bytes(json_bytes(summary)); return 0 if summary['status'] == 'passed' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('recipe'); parser.add_argument('sha256'); parser.add_argument('output')
    parser.add_argument('--worker', choices=('prepare', 'offline', 'proof')); args = parser.parse_args()
    raise SystemExit(worker(args.recipe, args.sha256, args.output, args.worker) if args.worker else driver(args.recipe, args.sha256, args.output))

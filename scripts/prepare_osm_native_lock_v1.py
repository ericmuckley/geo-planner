"""Run one frozen native-build metadata lock; no image/source acquisition."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import resource
import subprocess
import time
import unittest
import uuid

from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_data_v3 import tree_bytes
from coarse_osm_native_lock_v1 import CAPS, SOURCES, ROOT_URL, resolve, save, verify_saved
from coarse_osm_records import strict_json
from coarse_timing_input import digest, require, start_watchdog
from prepare_osm_input_v3 import capacity
from run_osm_stream_v1 import cleanup as cleanup_owned

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'


def limits(network):
    return {'NetworkMode': network, 'Memory': 4294967296, 'MemorySwap': 4294967296,
        'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'}}


def validate(plan):
    require(plan['phase'] == 'native_build_metadata_lock_v1' and plan['caps'] == CAPS, 'Native lock phase/caps drift')
    require(plan['imageId'] == IMAGE and plan['imagePull'] == 'never', 'Native lock cached image')
    require(plan['output'] == 'data/coarse-quality/us-osm-native-lock-v1', 'Native lock output')
    require(plan['rootUrl'] == ROOT_URL and plan['sources'] == [list(s) for s in SOURCES], 'Native lock selectors drift')
    require(plan['phases'] == {'controls': 'none', 'acquire': 'bridge'}, 'Native lock network phases')
    for name, destination in plan['mounts'].items():
        require(not name.startswith('/') and all(p not in ('.', '..') for p in PurePosixPath(name).parts), 'Unsafe native-lock mount path')
        require(name.startswith('scripts/') and name.endswith('.py') or name == 'docs/evidence/coarse-osm-native-design-2026-10-27/dependency-proposal.json', 'No road/source/sample mounts')
        require(plan['inputs'][name] == plan['workerFiles'][destination] and destination.startswith(('/code/', '/inputs/')), 'Native lock mount binding')


def settle_error(call, identity, name, owner, root, client_code):
    """Capture interrupted worker exit/OOM before the shared removal helper runs."""
    found = call(['docker', 'inspect', identity or name])
    if found.returncode != 0:
        require('No such' in found.stderr, 'Native lock error discovery')
        return
    obj = json.loads(found.stdout)[0]
    require(obj['Config']['Labels'].get('geo-planner.stream-owner') == owner and obj['Image'] == IMAGE, 'Refuse unrelated native-lock stop')
    if obj['State']['Running']:
        stopped = call(['docker', 'kill', obj['Id']])
        require(stopped.returncode == 0, 'Native lock owned stop')
        obj = json.loads(call(['docker', 'inspect', obj['Id']]).stdout)[0]
        require(not obj['State']['Running'], 'Native lock worker still running after stop')
    save(root / 'container-error-final.json', {'State': obj['State'], 'clientExitCode': client_code,
        'normalWorkerResult': False, 'scope': 'Error-path observation; created/not-started is not a successful executed worker.'})


def check_isolation(observed, network):
    require(observed['Image'] == IMAGE and all(observed['HostConfig'][k] == v for k, v in limits(network).items()), 'Native lock isolation drift')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] != '/work'), 'Native lock writable input')
    require({u['Name']: (u['Soft'], u['Hard']) for u in observed['HostConfig']['Ulimits']} == {'core': (0, 0), 'fsize': (67108864, 67108864)}, 'Native lock file/core limits')


def worker(plan, root, phase):
    root = Path(root)
    watchdog = start_watchdog(60 if phase == 'controls' else CAPS['workerSeconds'])
    try:
        verify_worker_inputs(plan)
        disk = os.statvfs('/tmp')
        require(disk.f_blocks * disk.f_frsize == CAPS['tmpBytes'], 'Native lock tmp guard')
        require(resource.getrlimit(resource.RLIMIT_FSIZE) == (CAPS['fileBytes'], CAPS['fileBytes']), 'Native lock file guard')
        save(root / 'resource-guards.json', {'memory': memory_guard(), 'tmpBytes': CAPS['tmpBytes'], 'fileBytes': CAPS['fileBytes'],
            'phase': phase, 'watchdogSeconds': 60 if phase == 'controls' else CAPS['workerSeconds']})
        if phase == 'controls':
            suite = unittest.defaultTestLoader.loadTestsFromName('coarse_osm_native_lock_v1_test')
            result = unittest.TextTestRunner().run(suite)
            save(root / 'controls.json', {'tests': result.testsRun, 'successful': result.wasSuccessful(),
                'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)})
            return 0 if result.wasSuccessful() and not result.skipped else 2
        return resolve(root)
    except Exception as error:
        save(root / 'worker-failure.json', {'errorType': type(error).__name__, 'error': str(error)[:1000], 'metadataLockComplete': False})
        return 2
    finally:
        if watchdog.poll() is None:
            watchdog.terminate()
        watchdog.wait(timeout=5)


def driver(recipe, expected, output):
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo / 'docs/evidence') and digest(recipe) == expected, 'Native lock recipe path/hash')
    plan = strict_json(recipe.read_bytes())
    validate(plan)
    root = (repo / output).resolve()
    require(root == repo / plan['output'] and not root.exists(), 'Native lock requires fresh exact output')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(recipe.read_bytes())
    began = time.monotonic()
    deadline, hard = began + CAPS['hostWorkSeconds'], began + CAPS['hostSeconds']
    owner = uuid.uuid4().hex
    save(root / 'owner.json', {'label': owner, 'image': IMAGE, 'labelKey': 'geo-planner.stream-owner', 'scope': 'Reuses frozen label/image-checked cleanup helper; not a profile producer replay.'})
    phase_results = {}
    success = False
    def check():
        require(time.monotonic() < deadline, 'Native lock host work deadline')
        require(tree_bytes(root) <= CAPS['workingBytes'] - CAPS['tmpBytes'], 'Native lock storage cap')
        disk = os.statvfs(root)
        require(disk.f_bavail * disk.f_frsize >= 2147483648, 'Native lock disk headroom')
    def call(args, **kwargs):
        check()
        return subprocess.run(args, capture_output=True, text=True, timeout=min(15, max(.01, deadline - time.monotonic())), **kwargs)
    def phase_run(phase):
        phase_root = root / phase
        phase_root.mkdir()
        name = f'geo-planner-native-lock-v1-{phase}-' + owner[:12]
        identity = child = None
        save(phase_root / 'owner.json', {'name': name, 'label': owner})
        network = plan['phases'][phase]
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.stream-owner=' + owner,
            '--network=' + network, '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=64',
            '--ulimit', 'core=0:0', '--ulimit', 'fsize=67108864:67108864', '--tmpfs=/tmp:rw,size=256m', '--env', 'LD_LIBRARY_PATH=/tools/runtime']
        for source, destination in plan['mounts'].items():
            command += ['--mount', f'type=bind,src={repo / source},dst={destination},readonly']
        command += ['--mount', f'type=bind,src={repo / plan["site"]},dst=/tools/site,readonly']
        for filename, path in plan['runtime'].items():
            command += ['--mount', f'type=bind,src={repo / path},dst=/tools/runtime/{filename},readonly']
        command += ['--mount', f'type=bind,src={phase_root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
            '--entrypoint=python3', IMAGE, '-B', '/code/prepare_osm_native_lock_v1.py', '/inputs/recipe.json', expected, '/work', '--worker', '--phase', phase]
        try:
            identity = call(command, check=True).stdout.strip()
            require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Native lock owned ID')
            initial = json.loads(call(['docker', 'inspect', identity], check=True).stdout)[0]
            check_isolation(initial, network)
            save(phase_root / 'container-initial.json', {'Image': initial['Image'], 'Limits': limits(network), 'Ulimits': initial['HostConfig']['Ulimits'],
                'Mounts': [{'destination': m['Destination'], 'writable': m['RW']} for m in initial['Mounts']]})
            with (phase_root / 'worker.log').open('xb') as log:
                child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
                while child.poll() is None:
                    check()
                    require(log.tell() <= CAPS['reportBytes'], 'Native lock log cap')
                    time.sleep(.25)
                code = child.returncode
            final = json.loads(call(['docker', 'inspect', identity], check=True).stdout)[0]
            save(phase_root / 'container-result.json', {'Image': final['Image'], 'State': final['State'], 'clientExitCode': code})
            require(final['State']['ExitCode'] == code and not final['State']['OOMKilled'], 'Native lock exit/OOM')
            return code
        finally:
            if child is not None and child.poll() is None:
                child.kill(); child.wait(timeout=5)
            def cleanup_call(args):
                return subprocess.run(args, capture_output=True, text=True, timeout=max(1, min(15, hard - time.monotonic())))
            try:
                if not (phase_root / 'container-result.json').exists():
                    settle_error(cleanup_call, identity, name, owner, phase_root, child.returncode if child is not None else None)
            finally:
                cleanup_owned(cleanup_call, identity, name, owner, IMAGE, phase_root)
    try:
        for name, pin in plan['inputs'].items():
            check()
            require(digest(repo / name) == pin, 'Native lock input drift: ' + name)
        observed = capacity(repo)
        require(observed['hostDiskAvailableBytes'] >= 3221225472 and observed['hostMemoryBytes'] >= 8589934592
            and observed['dockerMemoryBytes'] >= 6442450944 and min(observed['hostCpuCount'], observed['dockerCpuCount']) >= 2, 'Native lock capacity')
        save(root / 'capacity-at-start.json', observed)
        phase_results['controls'] = phase_run('controls')
        require(phase_results['controls'] == 0, 'Native lock offline controls failed')
        phase_results['acquire'] = phase_run('acquire')
        if (root / 'acquire/result.json').exists() and (root / 'acquire/http/ledger.json').exists():
            save(root / 'offline-audit.json', verify_saved(root / 'acquire'))
            success = phase_results['acquire'] == 0
    except (Exception, KeyboardInterrupt) as error:
        save(root / 'driver-failure.json', {'errorType': type(error).__name__, 'error': str(error)[:1000], 'metadataLockComplete': False, 'partialCountersMayBeUnfinalized': True})
    elapsed = time.monotonic() - began
    require(elapsed < CAPS['hostSeconds'] and tree_bytes(root) <= CAPS['workingBytes'] - CAPS['tmpBytes'], 'Native lock final resource cap')
    save(root / 'run-summary.json', {'status': 'metadata_locked_not_acquired' if success else 'stopped', 'phaseClientExitCodes': phase_results,
        'hostSecondsIncludingHashStartupControlsAcquireOfflineAuditCleanup': elapsed, 'binaryDownloads': 0, 'sourceOrSampleReads': 0,
        'compilerQualified': False, 'fullImportAdmitted': False, 'modelChanged': False})
    return 0 if success else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe'); parser.add_argument('sha256'); parser.add_argument('output')
    parser.add_argument('--worker', action='store_true'); parser.add_argument('--phase', choices=['controls', 'acquire'])
    args = parser.parse_args()
    if args.worker:
        require(args.phase is not None and digest(args.recipe) == args.sha256, 'Native lock worker binding')
        plan = strict_json(Path(args.recipe).read_bytes()); validate(plan)
        __import__('sys').path.insert(0, '/tools/site')
        raise SystemExit(worker(plan, args.output, args.phase))
    raise SystemExit(driver(args.recipe, args.sha256, args.output))

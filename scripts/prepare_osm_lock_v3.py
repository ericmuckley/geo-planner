"""Version3 metadata correction: reuse saved Requests; four bounded catalogues only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_osm_bulk_transport import Meter, wheel_lock
from coarse_osm_records import strict_json
from coarse_timing_input import cgroup_limit, digest, json_bytes, require, start_watchdog


DEPENDENCIES = ['charset-normalizer', 'idna', 'urllib3', 'certifi']


def validate_plan(plan):
    require(plan['phase'] == 'metadata_only_dependency_lock_v3' and plan['network'] == 'bridge', 'Only metadata setup is executable')
    require(plan['caps'] == {'attempts': 4, 'totalBytes': 16777216, 'kindBytes': {'metadata': 16777216, 'wheel': 0, 'pbf': 0},
        'wallSeconds': 300, 'idleSeconds': 20, 'workingBytes': 536870912, 'errorBytes': 65536}, 'Metadata setup cap drift')
    require(plan['specs'] == [{'url': f'https://pypi.org/pypi/{n}/json', 'kind': 'metadata', 'maxBytes': 3145728, 'seconds': 20} for n in DEPENDENCIES], 'Fixed metadata endpoints/order')
    require(plan['memoryBytes'] == 1073741824 and plan['tmpBytes'] == 67108864 and plan['imagePull'] == 'never', 'Setup resource drift')
    require(plan['output'] == 'data/coarse-quality/us-osm-tool-lock-v3', 'Setup output drift')


def resolve(root, plan, proposal, captured, captured_requests, *, transport=None, clock=time.monotonic, alarm=None, lock_options=None):
    root = Path(root); require(not (root / 'lock.json').exists(), 'Lock refuses overwrite')
    http_root = root / 'http'; http_root.mkdir()
    options = {'transport': transport, 'clock': clock}
    if alarm is not None: options['alarm'] = alarm
    meter = Meter(http_root, plan['specs'], plan['caps'], **options)
    try:
        metadata = {'osmium': captured, 'requests': captured_requests}
        for i, name in enumerate(DEPENDENCIES): metadata[name] = strict_json(meter.fetch(i).read_bytes())
        lock = wheel_lock(metadata, proposal['tools'], **(lock_options or {}))
        (root / 'lock.json').write_bytes(json_bytes(lock))
        (root / 'setup-state.json').write_bytes(json_bytes({'status': 'metadata_lock_ready_tools_not_fetched', 'packageCount': len(lock['packages']),
            'toolBinaryDownloads': 0, 'pbfRequests': 0, 'sourceFeasibilityQualified': False, 'actualDecoderQualified': False}))
        return 0
    except Exception as error:
        (root / 'setup-state.json').write_bytes(json_bytes({'status': 'stopped', 'errorType': type(error).__name__, 'error': str(error)[:2000],
            'toolBinaryDownloads': 0, 'pbfRequests': 0, 'sourceFeasibilityQualified': False, 'actualDecoderQualified': False,
            'plannedRequests': [{'url': s['url'], 'status': meter.events[i]['outcome'] if i < len(meter.events) else 'unmeasured_after_stop'} for i, s in enumerate(plan['specs'])]}))
        return 2


def worker(plan_path, root, expected):
    require(digest(plan_path) == expected, 'Setup recipe binding')
    plan = strict_json(Path(plan_path).read_bytes()); validate_plan(plan)
    for path, sha in plan['workerFiles'].items(): require(digest(path) == sha, 'Worker source binding: ' + path)
    require(cgroup_limit() == {'memoryMaxBytes': plan['memoryBytes'], 'swapMaxBytes': 0}, 'Setup actual memory/swap drift')
    watchdog = start_watchdog(plan['caps']['wallSeconds'])
    try:
        Path(root, 'resource-guards.json').write_bytes(json_bytes({'memory': cgroup_limit(), 'independentWatchdogSeconds': plan['caps']['wallSeconds'],
            'networkMode': 'bridge', 'scope': 'Metadata lock only; no wheel/PBF/credentials.'}))
        return resolve(root, plan, strict_json(Path(plan['proposal']).read_bytes()), strict_json(Path(plan['captured']).read_bytes()), strict_json(Path(plan['capturedRequests']).read_bytes()))
    finally:
        if watchdog.poll() is None: watchdog.terminate(); watchdog.wait(timeout=5)


def driver(recipe, expected, output):
    repo = Path(__file__).resolve().parents[1]; path = Path(recipe).resolve()
    require(path.is_relative_to(repo / 'docs/evidence') and digest(path) == expected, 'Host recipe binding/path')
    plan = strict_json(path.read_bytes()); validate_plan(plan)
    for name, sha in plan['inputs'].items(): require(digest(repo / name) == sha, 'Host input binding: ' + name)
    root = (repo / output).resolve(); require(root == (repo / plan['output']).resolve(), 'Output differs from frozen recipe')
    mounts = []
    for source, target in plan['mounts'].items():
        host = (repo / source).resolve()
        require(host.is_relative_to(repo) and host.is_file() and target.startswith(('/code/', '/inputs/')), 'Invalid isolated file mount')
        require(plan['inputs'][source] == plan['workerFiles'][target], 'Worker mount/hash binding')
        mounts += ['--mount', f'type=bind,src={host},dst={target},readonly']
    root.mkdir(); (root / 'execution-plan.json').write_bytes(path.read_bytes())
    name = 'geo-planner-osm-tools-' + uuid.uuid4().hex[:12]; identity = None; started = time.monotonic()
    (root / 'container-name.txt').write_text(name + '\n')
    command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--network=bridge', '--read-only', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g', '--cpus=2', '--pids-limit=64', '--tmpfs=/tmp:rw,size=64m',
        '--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={path},dst=/inputs/recipe.json,readonly', *mounts,
        '--entrypoint=python3', plan['imageId'], '-B', '/code/prepare_osm_lock_v3.py', '/inputs/recipe.json', expected, '/work', '--worker']
    try:
        identity = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30).stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Owned container identity')
        def inspect(): return json.loads(subprocess.run(['docker', 'inspect', identity], check=True, capture_output=True, text=True, timeout=30).stdout)[0]
        before = inspect(); hc = before['HostConfig']
        require(before['Image'] == plan['imageId'] and hc['NetworkMode'] == 'bridge' and hc['Memory'] == hc['MemorySwap'] == plan['memoryBytes'] and hc['ReadonlyRootfs'], 'Setup container isolation drift')
        with (root / 'worker.log').open('xb') as log:
            result = subprocess.run(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT,
                timeout=max(1, plan['caps']['wallSeconds'] - (time.monotonic() - started)))
        after = inspect(); (root / 'container-result.json').write_bytes(json_bytes({'State': after['State'], 'Image': after['Image'],
            'Limits': {k: after['HostConfig'][k] for k in ['NetworkMode', 'Memory', 'MemorySwap', 'ReadonlyRootfs']}}))
        if result.returncode:
            setup = strict_json((root / 'setup-state.json').read_bytes()) if (root / 'setup-state.json').exists() else None
            (root / 'driver-stop.json').write_bytes(json_bytes({'workerExitCode': result.returncode, 'admitted': False,
                'lastSetupStateRetained': setup is not None, 'hardStopCountersMayBePartial': bool(after['State'].get('OOMKilled')) or setup is None or result.returncode not in (0, 2)}))
        return result.returncode
    except Exception as error:
        (root / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'ownedContainer': identity, 'admitted': False,
            'hardStopCountersMayBePartial': True, 'policy': 'Retain attempted setup; no resume/retry/overwrite.'}))
        raise
    finally:
        if identity:
            subprocess.run(['docker', 'rm', '-f', identity], check=True, capture_output=True, timeout=30)
            (root / 'cleanup.json').write_bytes(json_bytes({'ownedContainer': identity, 'removed': True}))
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) + plan['tmpBytes'] <= plan['caps']['workingBytes'], 'Final setup storage cap')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe'); parser.add_argument('sha256'); parser.add_argument('output'); parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    raise SystemExit(worker(args.recipe, args.output, args.sha256) if args.worker else driver(args.recipe, args.sha256, args.output))


if __name__ == '__main__': main()

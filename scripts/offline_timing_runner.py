"""Shared bounded, network-disabled launcher for new frozen diagnostics."""
import argparse
import importlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from analyze_timing_cache import Output
from coarse_timing_input import cgroup_limit, digest, json_bytes, require, start_watchdog
from run_timing_cache import network_guard


def worker(plan_path, root, expected_sha):
    require(digest(plan_path) == expected_sha, 'Offline plan binding')
    plan = json.loads(Path(plan_path).read_text())
    for path, sha in plan['workerFiles'].items():
        require(digest(path) == sha, 'Worker input binding: ' + path)
    require(plan['entryModule'].isidentifier() and '/code/' + plan['entryModule'] + '.py' in plan['workerFiles'], 'Unbound entry module')
    root = Path(root)
    require(not (root / 'state.json').exists(), 'Diagnostic refuses overwrite')
    state = {'status': 'running', 'memoryGuard': cgroup_limit(), 'networkGuard': network_guard(),
             'networkRequests': 0, 'routingQueries': 0, 'originalFeasibilityQualified': False}
    output = Output(root, plan['outputBytes'] - plan['reservedBytes'], plan['wallSeconds'])
    (root / 'state.json').write_bytes(json_bytes(state))
    watchdog = start_watchdog(plan['wallSeconds'])
    try:
        importlib.import_module(plan['entryModule']).run(plan, output)
        state.update(status='diagnostic_complete_source_incomplete', elapsedSeconds=output.clock() - output.started,
                     outputBytesMetered=output.bytes)
        return 0
    except Exception as error:
        state.update(status='stopped', errorType=type(error).__name__, error=str(error)[:2000])
        return 2
    finally:
        (root / 'state.json').write_bytes(json_bytes(state))
        if watchdog.poll() is None:
            watchdog.terminate()
            watchdog.wait(timeout=5)


def driver(plan_path, destination, expected_sha):
    repo = Path(__file__).resolve().parents[1]
    plan_path = (repo / plan_path).resolve()
    require(plan_path.is_relative_to(repo / 'docs/evidence') and digest(plan_path) == expected_sha, 'Execution-plan binding')
    plan = json.loads(plan_path.read_text())
    for path, sha in plan['inputs'].items():
        require(digest(repo / path) == sha, 'Input binding: ' + path)
    root = (repo / destination).resolve()
    require(root == (repo / plan['output']).resolve() and root.is_relative_to(repo / 'data/coarse-quality'), 'Output path differs')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(plan_path.read_bytes())
    name = 'geo-planner-offline-' + uuid.uuid4().hex[:12]
    (root / 'container-name.txt').write_text(name + '\n')
    command = ['docker', 'create', '--pull=never', '--init', '--name', name,
        '--label', 'geo-planner.offline-plan=' + expected_sha, '--network=none', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g',
        '--cpus=2', '--pids-limit=64', '--tmpfs=/tmp:rw,size=64m',
        '--mount', f'type=bind,src={root},dst=/work',
        '--mount', f'type=bind,src={plan_path},dst=/inputs/plan.json,readonly']
    for source, target in plan['mounts'].items():
        path = (repo / source).resolve()
        require(path.is_relative_to(repo) and (target == '/code' or target.startswith('/inputs/')), 'Unsafe read-only mount')
        command.extend(['--mount', f'type=bind,src={path},dst={target},readonly'])
    command.extend(['--entrypoint=python3', plan['containerImageId'], '-B', '/code/' + plan['entryModule'] + '.py',
                    '/inputs/plan.json', expected_sha, '--worker', '/work'])
    identity = None
    try:
        started = time.monotonic()
        identity = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30).stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Invalid owned container')
        def inspect():
            return json.loads(subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, check=True, timeout=30).stdout)[0]
        before = inspect()
        require(before['HostConfig']['NetworkMode'] == 'none' and before['HostConfig']['Memory'] == plan['memoryBytes'] and before['HostConfig']['MemorySwap'] == plan['memoryBytes'], 'Container isolation differs')
        with (root / 'worker.log').open('xb') as log:
            result = subprocess.run(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT,
                timeout=max(1, plan['wallSeconds'] - (time.monotonic() - started)))
        record = inspect()
        (root / 'container-result.json').write_bytes(json_bytes({'State': record['State'], 'Image': record['Image'],
            'Limits': {k: record['HostConfig'][k] for k in ['Memory', 'MemorySwap', 'ReadonlyRootfs', 'NetworkMode']}}))
        print(json.dumps({'workerExitCode': result.returncode, 'state': str(root / 'state.json')}, indent=2))
        return result.returncode
    except Exception as error:
        (root / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'ownedContainer': identity}))
        raise
    finally:
        if identity:
            subprocess.run(['docker', 'rm', '-f', identity], capture_output=True, check=True, timeout=30)
            (root / 'cleanup.json').write_bytes(json_bytes({'ownedContainer': identity, 'removed': True}))
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) <= plan['outputBytes'], 'Final output cap')


def main(default_plan):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('sha')
    parser.add_argument('--worker')
    args = parser.parse_args()
    raise SystemExit(worker(args.output, args.worker, args.sha) if args.worker else driver(default_plan, args.output, args.sha))

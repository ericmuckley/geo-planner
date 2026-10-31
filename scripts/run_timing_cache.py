"""Corrected offline runner; preserves the sealed first-launch failure."""
import argparse
import json
from pathlib import Path
import socket
import struct
import subprocess
import time
import uuid

from analyze_timing_cache import Output, analyze
from coarse_timing_cache_audit import audit
from coarse_timing_input import cgroup_limit, digest, json_bytes, require, start_watchdog
from coarse_timing_parquet import load_source


def validate_namespace(flags, ipv4_routes, ipv6_routes):
    require('lo' in flags and flags['lo'] & 8, 'Missing loopback interface')
    require(all(name == 'lo' or not bits & 1 for name, bits in flags.items()), 'Active non-loopback interface')
    require(all(line.split()[0] == 'lo' for line in ipv4_routes.splitlines()[1:] if line.strip()), 'Non-loopback IPv4 route')
    require(all(line.split()[-1] == 'lo' for line in ipv6_routes.splitlines() if line.strip()), 'Non-loopback IPv6 route')


def network_guard():
    import fcntl
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as handle:
        flags = {name: struct.unpack_from('H', fcntl.ioctl(handle.fileno(), 0x8913,
            struct.pack('256s', name.encode())), 16)[0] for _, name in socket.if_nameindex()}
    v4, v6 = (Path('/proc/net/' + name).read_text() for name in ['route', 'ipv6_route'])
    validate_namespace(flags, v4, v6)
    return {'interfaceFlags': flags, 'ipv4Routes': v4, 'ipv6Routes': v6,
            'scope': 'No active non-loopback link or non-loopback route. Dormant kernel tunnel devices are permitted; Docker network mode must also be none.'}


def worker(plan_path, root, expected_sha):
    require(digest(plan_path) == expected_sha, 'Offline plan binding')
    plan = json.loads(Path(plan_path).read_text())
    for name, sha in plan['workerFiles'].items():
        require(digest(name) == sha, 'Worker input binding: ' + name)
    root = Path(root)
    require(not (root / 'state.json').exists(), 'Offline analysis refuses overwrite')
    state = {'status': 'running', 'memoryGuard': cgroup_limit(), 'networkGuard': network_guard(),
             'networkRequests': 0, 'routingQueries': 0, 'originalFeasibilityQualified': False}
    output = Output(root, plan['outputBytes'] - plan['reservedBytes'], plan['wallSeconds'])
    (root / 'state.json').write_bytes(json_bytes(state))
    watchdog = start_watchdog(plan['wallSeconds'])
    try:
        proposal = json.loads(Path('/inputs/proposal.json').read_text())
        data = load_source(plan)
        analyze(plan, output, '/cache/segments.jsonl', proposal, data)
        audit(plan, output, proposal, data)
        state.update(status='offline_analysis_complete_source_incomplete', elapsedSeconds=output.clock() - output.started,
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


def driver(plan_path, expected_sha):
    repo = Path(__file__).resolve().parents[1]
    plan_path = Path(plan_path).resolve()
    require(plan_path.is_relative_to(repo / 'docs/evidence'), 'Plan outside evidence')
    require(digest(plan_path) == expected_sha, 'Offline execution-plan binding')
    plan = json.loads(plan_path.read_text())
    for name, sha in plan['inputs'].items():
        require(digest(repo / name) == sha, 'Input binding: ' + name)
    root = (repo / plan['output']).resolve()
    require(root.is_relative_to(repo / 'data/coarse-quality'), 'Unexpected output path')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(plan_path.read_bytes())
    name = 'geo-planner-timing-cache-' + uuid.uuid4().hex[:12]
    (root / 'container-name.txt').write_text(name + '\n')
    command = ['docker', 'create', '--pull=never', '--init', '--name', name,
        '--label', 'geo-planner.timing-cache-plan=' + expected_sha, '--network=none', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g',
        '--cpus=2', '--pids-limit=64', '--tmpfs=/tmp:rw,size=64m',
        '--mount', f'type=bind,src={repo / "scripts"},dst=/code,readonly',
        '--mount', f'type=bind,src={root},dst=/work',
        '--mount', f'type=bind,src={plan_path},dst=/inputs/plan.json,readonly',
        '--mount', f'type=bind,src={repo / plan["proposal"]},dst=/inputs/proposal.json,readonly',
        '--mount', f'type=bind,src={repo / plan["geometryReport"]},dst=/inputs/geometry-report.json,readonly',
        '--mount', f'type=bind,src={repo / plan["geometryDirectory"]},dst=/geometry,readonly',
        '--mount', f'type=bind,src={repo / plan["cacheDirectory"]},dst=/cache,readonly',
        '--entrypoint=python3', plan['containerImageId'], '-B', '/code/run_timing_cache.py',
        '/inputs/plan.json', expected_sha, '--worker', '/work']
    identity = None
    try:
        started = time.monotonic()
        identity = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30).stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Invalid owned container')
        before = json.loads(subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, check=True, timeout=30).stdout)[0]
        require(before['HostConfig']['NetworkMode'] == 'none' and before['HostConfig']['Memory'] == plan['memoryBytes'] and before['HostConfig']['MemorySwap'] == plan['memoryBytes'], 'Container isolation differs from plan')
        with (root / 'worker.log').open('xb') as log:
            result = subprocess.run(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT,
                timeout=max(1, plan['wallSeconds'] - (time.monotonic() - started)))
        record = json.loads(subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, check=True, timeout=30).stdout)[0]
        inspection = {'State': record['State'], 'Image': record['Image'],
            'Limits': {k: record['HostConfig'][k] for k in ['Memory', 'MemorySwap', 'ReadonlyRootfs', 'NetworkMode']}}
        (root / 'container-result.json').write_bytes(json_bytes(inspection))
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('sha')
    parser.add_argument('--worker')
    args = parser.parse_args()
    raise SystemExit(worker(args.plan, args.worker, args.sha) if args.worker else driver(args.plan, args.sha))

"""Hash-bound isolated launcher for the separately frozen native-OSM pilot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode
import uuid

from coarse_timing_input import cgroup_limit, digest, json_bytes, require, start_watchdog


PLAN = 'docs/evidence/coarse-osm-pilot-2026-10-26/execution-plan.json'


def load_queries(proposal, manifest, paths, original):
    require(manifest['snapshotUtc'] == proposal['source']['snapshotUtc'] and len(manifest['queries']) == proposal['windows']['count'] == 21, 'Frozen snapshot/window count')
    require([q['id'] for q in manifest['queries']] == proposal['windows']['ids'] == [w['id'] for w in original['selection']['windows']], 'Original window order')
    result = []
    for q, w in zip(manifest['queries'], original['selection']['windows'], strict=True):
        require(q['bbox'] == w['bbox'] and q['id'] in paths, 'Original window bounds/query path')
        text = Path(paths[q['id']]).read_text()
        require(digest(paths[q['id']]) == q['querySha256'], 'Frozen QL checksum')
        body = urlencode({'data': text}).encode()
        require(hashlib.sha256(body).hexdigest() == q['formBodySha256'] and len(body) == q['formBodyBytes'], 'Frozen POST checksum/length')
        result.append({**q, 'text': text})
    return result


def worker(plan_path, root, expected_sha):
    require(digest(plan_path) == expected_sha, 'Worker execution-plan binding')
    plan = json.loads(Path(plan_path).read_text())
    for path, sha in plan['workerFiles'].items(): require(digest(path) == sha, 'Worker file binding: ' + path)
    proposal = json.loads(Path(plan['paths']['proposal']).read_text())
    manifest = json.loads(Path(plan['paths']['manifest']).read_text())
    original = json.loads(Path(plan['paths']['originalWindows']).read_text())
    queries = load_queries(proposal, manifest, plan['queryPaths'], original)
    root = Path(root); require(not (root / 'state.json').exists(), 'Worker refuses overwrite')
    guards = cgroup_limit()
    require(guards == {'memoryMaxBytes': proposal['hardCaps']['clientMemoryBytes'], 'swapMaxBytes': 0}, 'Frozen Linux memory guard')
    require(plan['network'] == 'bridge' and plan['imagePull'] == 'never', 'Frozen network/image policy')
    watchdog = start_watchdog(proposal['hardCaps']['wallSeconds'])
    try:
        (root / 'resource-guards.json').write_bytes(json_bytes({'memoryGuard': guards,
            'networkPolicy': 'Bridge namespace; all HTTP via frozen direct-HTTPS meter and exact host/path/form allowlist, no proxy/cookie/credential handler.',
            'independentWatchdogSeconds': proposal['hardCaps']['wallSeconds']}))
        from coarse_osm_input import capture
        from coarse_osm_audit import audit
        state = capture(proposal, queries, root)
        audited = audit(proposal, queries, root)
        return 0 if state['status'] == 'captured_all_windows_analysis_pending' and audited['captureComplete'] else 2
    except Exception as error:
        (root / 'worker-failure.json').write_bytes(json_bytes({'errorType': type(error).__name__, 'error': str(error)[:2000],
            'captureAdmitted': False, 'originalStateRetained': (root / 'state.json').exists(),
            'windows': [{'id': q['id'], 'status': 'unmeasured_or_unqualified_after_worker_failure'} for q in queries]}))
        return 2
    finally:
        if watchdog.poll() is None:
            watchdog.terminate(); watchdog.wait(timeout=5)


def driver(destination, expected_sha):
    repo = Path(__file__).resolve().parents[1]; plan_path = repo / PLAN
    require(digest(plan_path) == expected_sha, 'Execution-plan binding')
    plan = json.loads(plan_path.read_text())
    for path, sha in plan['inputs'].items(): require(digest(repo / path) == sha, 'Host file binding: ' + path)
    root = (repo / destination).resolve()
    require(root == (repo / plan['output']).resolve() and root.is_relative_to(repo / 'data/coarse-quality'), 'Output path differs')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(plan_path.read_bytes())
    name = 'geo-planner-osm-' + uuid.uuid4().hex[:12]; (root / 'container-name.txt').write_text(name + '\n')
    command = ['docker', 'create', '--pull=never', '--init', '--name', name,
        '--label', 'geo-planner.osm-plan=' + expected_sha, '--network=bridge', '--read-only', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g', '--cpus=2', '--pids-limit=64',
        '--tmpfs=/tmp:rw,size=64m', '--mount', f'type=bind,src={root},dst=/work',
        '--mount', f'type=bind,src={plan_path},dst=/inputs/plan.json,readonly']
    for source, target in plan['mounts'].items():
        path = (repo / source).resolve()
        require(path.is_relative_to(repo) and path.is_file() and (target.startswith('/inputs/') or target.startswith('/code/')), 'Invalid read-only input mount')
        command.extend(['--mount', f'type=bind,src={path},dst={target},readonly'])
    command.extend(['--entrypoint=python3', plan['containerImageId'], '-B', '/code/coarse_osm_input.py', '/inputs/plan.json', expected_sha, '--worker', '/work'])
    identity = None; started = time.monotonic()
    try:
        identity = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30).stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Invalid owned container identity')
        def inspect(): return json.loads(subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, check=True, timeout=30).stdout)[0]
        before = inspect(); config = before['HostConfig']
        require(before['Image'] == plan['containerImageId'] and config['NetworkMode'] == 'bridge' and config['Memory'] == config['MemorySwap'] == 1073741824 and config['ReadonlyRootfs'], 'Container isolation differs')
        with (root / 'worker.log').open('xb') as stream:
            result = subprocess.run(['docker', 'start', '-a', identity], stdout=stream, stderr=subprocess.STDOUT,
                timeout=max(1, plan['wallSeconds'] - (time.monotonic() - started)))
        record = inspect()
        (root / 'container-result.json').write_bytes(json_bytes({'State': record['State'], 'Image': record['Image'],
            'Limits': {k: record['HostConfig'][k] for k in ('NetworkMode', 'Memory', 'MemorySwap', 'ReadonlyRootfs')}}))
        if result.returncode:
            state = json.loads((root / 'state.json').read_text()) if (root / 'state.json').exists() else None
            (root / 'driver-stop.json').write_bytes(json_bytes({'workerExitCode': result.returncode, 'captureAdmitted': False,
                'lastStateRetained': state is not None, 'hardStopCountersMayBePartial': not (root / 'audit.json').exists() or state is None or state['status'] not in ('stopped', 'captured_all_windows_analysis_pending')}))
        print(json.dumps({'workerExitCode': result.returncode, 'state': str(root / 'state.json')}, indent=2))
        return result.returncode
    except Exception as error:
        (root / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'ownedContainer': identity,
            'captureAdmitted': False, 'reason': 'Preserve attempted run; do not resume, overwrite or retry.'}))
        raise
    finally:
        if identity:
            subprocess.run(['docker', 'rm', '-f', identity], capture_output=True, check=True, timeout=30)
            (root / 'cleanup.json').write_bytes(json_bytes({'ownedContainer': identity, 'removed': True}))
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) + plan['tmpBytes'] <= plan['workingBytes'], 'Final working-file/tmp cap')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output'); parser.add_argument('sha'); parser.add_argument('--worker')
    args = parser.parse_args()
    raise SystemExit(worker(args.output, args.worker, args.sha) if args.worker else driver(args.output, args.sha))

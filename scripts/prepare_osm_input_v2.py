"""Frozen one-GET national input orchestration. --check is read-only; no work on import."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from coarse_osm_data import download_source, extract_source, memory_guard, tree_bytes, validate_plan, verify_completed_data, verify_worker_inputs
from coarse_osm_records import strict_json
from coarse_osm_input import absolute_timeout
from coarse_timing_input import digest, json_bytes, require, start_watchdog


def capacity(repo):
    disk = os.statvfs(repo)
    host_memory = int(subprocess.run(['sysctl', '-n', 'hw.memsize'], check=True, capture_output=True, text=True, timeout=5).stdout)
    docker = json.loads(subprocess.run(['docker', 'info', '--format', '{{json .}}'], check=True, capture_output=True, text=True, timeout=15).stdout)
    return {'hostDiskAvailableBytes': disk.f_bavail * disk.f_frsize, 'hostMemoryBytes': host_memory, 'hostCpuCount': os.cpu_count(),
        'dockerMemoryBytes': docker['MemTotal'], 'dockerCpuCount': docker['NCPU']}


def validate_capacity(observed, config):
    caps = config['proposedCaps']
    require(observed['hostDiskAvailableBytes'] >= caps['requiredInitialFreeBytes'], 'Insufficient current disk capacity')
    require(observed['hostMemoryBytes'] >= 8589934592 and observed['dockerMemoryBytes'] >= 6442450944, 'Insufficient current host/Docker memory')
    require(observed['hostCpuCount'] >= 2 and observed['dockerCpuCount'] >= 2, 'Insufficient current CPU capacity')


def preflight(recipe, expected, output, repo):
    repo = Path(repo).resolve(); path = Path(recipe).resolve()
    require(path.is_relative_to(repo / 'docs/evidence') and digest(path) == expected, 'Data recipe binding/path')
    plan = strict_json(path.read_bytes()); validate_plan(plan, strict_json((repo / plan['proposal']).read_bytes()))
    for name, sha in plan['inputs'].items(): require(digest(repo / name) == sha, 'Data host input: ' + name)
    root = (repo / output).resolve(); require(root == repo / plan['output'] and not root.exists(), 'New frozen data output required')
    site = repo / plan['site']; actual = {str(p.relative_to(repo)) for p in site.rglob('*') if p.is_file()}
    require(actual == {p for p in plan['inputs'] if p.startswith(plan['site'] + '/')}, 'Host qualified site roster drift')
    require(not any(p.is_symlink() for p in site.rglob('*')), 'Host qualified site symlink')
    current = capacity(repo); validate_capacity(current, plan['extractConfig'])
    image = json.loads(subprocess.run(['docker', 'image', 'inspect', plan['imageId']], check=True, capture_output=True, text=True, timeout=10).stdout)[0]
    require(image['Id'] == plan['imageId'] and image['Architecture'] == 'arm64', 'Cached data image drift')
    return path, plan, root, current


def worker(recipe, expected, root, phase, seconds):
    began = time.monotonic(); require(0 < seconds <= 14400, 'Data remaining deadline')
    require(digest(recipe) == expected, 'Data worker recipe binding'); plan = strict_json(Path(recipe).read_bytes())
    validate_plan(plan, strict_json(Path('/inputs/proposal.json').read_bytes()))
    memory = memory_guard(); watchdog = start_watchdog(seconds)
    root = Path(root)
    def remaining():
        value = seconds - (time.monotonic() - began); require(value > 0, 'Data shared phase deadline'); return value
    try:
        verify_worker_inputs(plan)
        tmp = os.statvfs('/tmp'); require(tmp.f_blocks * tmp.f_frsize == 268435456, 'Data tmpfs drift')
        with (root / 'resource-guards.json').open('xb') as stream:
            stream.write(json_bytes({'memory': memory, 'tmpBytes': tmp.f_blocks * tmp.f_frsize, 'watchdogSeconds': seconds,
                'phase': phase, 'remainingSecondsAfterBindings': remaining(), 'qualification': 'Configured resources, not workload performance/peak proof'}))
        if phase == 'download': download_source(root, plan, remaining())
        else:
            require(os.environ.get('LD_LIBRARY_PATH') == '/tools/runtime', 'Scoped data runtime path')
            sys.path.insert(0, '/tools/site')
            receipt = strict_json(Path('/inputs/source-receipt.json').read_bytes())
            require(receipt['status'] == 'download_complete_analysis_pending' and receipt['bodyBytes'] == plan['sourceSpec']['exactBytes']
                and receipt['publisherMd5'] == plan['sourceSpec']['md5'], 'Complete source receipt required')
            state = extract_source('/inputs/source.pbf', root, plan, remaining(), receipt)
            if state['status'] != 'extracted_publisher_file_analysis_pending': return 2
        return 0
    except Exception as error:
        with (root / 'failure.json').open('xb') as stream:
            stream.write(json_bytes({'status': 'stopped', 'phase': phase, 'errorType': type(error).__name__, 'error': str(error)[:3000],
                'sourceFeasibilityQualified': False, 'derivedIndexesTrusted': False, 'rawDecodedObjectCountsMayBePartial': phase == 'extract',
                'windows': [{'id': w['id'], 'status': 'unqualified_after_data_stop'} for w in plan['extractConfig']['windows']]}))
        return 2
    finally:
        if watchdog.poll() is None: watchdog.terminate(); watchdog.wait(timeout=5)


def run_data(recipe, expected, output, *, repo=None, check_only=False):
    repo = Path(repo or Path(__file__).resolve().parents[1]).resolve()
    path, plan, root, observed = preflight(recipe, expected, output, repo)
    if check_only:
        return {'status': 'checked_not_executed', 'capacity': observed, 'httpRequestsMade': 0, 'outputCreated': False,
            'activationRequiresExactExecutionCommand': True}
    mounts = []
    for source, target in plan['mounts'].items():
        host = (repo / source).resolve(); require(host.is_relative_to(repo) and host.is_file() and target.startswith(('/code/', '/inputs/')), 'Data isolated file mount')
        require(plan['inputs'][source] == plan['workerFiles'][target], 'Data mount binding')
        mounts += ['--mount', f'type=bind,src={host},dst={target},readonly']
    mounts += ['--mount', f'type=bind,src={repo / plan["site"]},dst=/tools/site,readonly']
    for filename, source in plan['runtime'].items():
        require(filename in ('libexpat.so.1', 'copyright') and source in plan['inputs'], 'Data runtime mount binding')
        mounts += ['--mount', f'type=bind,src={repo / source},dst=/tools/runtime/{filename},readonly']
    root.mkdir(); (root / 'execution-plan.json').write_bytes(path.read_bytes()); (root / 'capacity-at-start.json').write_bytes(json_bytes(observed))
    started = time.monotonic(); hard_deadline = started + 14400; work_deadline = hard_deadline - 60
    caps = plan['extractConfig']['proposedCaps']; results = []
    max_output = caps['workingBytesIncludingTmp'] - caps['tmpBytes'] - plan['reservedReadOnlyInputsBytes']
    for phase, network in zip(('download', 'extract'), plan['networks']):
        stage = root / phase; stage.mkdir(); owner = uuid.uuid4().hex; name = 'geo-planner-data-v2-' + owner[:12]; identity = None
        (stage / 'container-name.txt').write_text(name + '\n')
        def call(args, **options):
            left = work_deadline - time.monotonic(); require(left > 0, 'Data shared host deadline')
            return subprocess.run(args, timeout=min(options.pop('timeout', 30), left), **options)
        extra = []
        if phase == 'extract':
            extra = ['--env', 'LD_LIBRARY_PATH=/tools/runtime', '--mount', f'type=bind,src={root / "download/http/001.bin"},dst=/inputs/source.pbf,readonly',
                '--mount', f'type=bind,src={root / "download/source-receipt.json"},dst=/inputs/source-receipt.json,readonly']
        left = work_deadline - time.monotonic(); require(left > 0, 'No data phase allowance')
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.data-owner=' + owner,
            '--network=' + network, '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g', '--cpus=2',
            '--pids-limit=64', '--ulimit', 'core=0:0', '--ulimit', 'fsize=25769803776:25769803776', '--tmpfs=/tmp:rw,size=256m',
            '--mount', f'type=bind,src={stage},dst=/work', '--mount', f'type=bind,src={path},dst=/inputs/recipe.json,readonly', *mounts, *extra,
            '--entrypoint=python3', plan['imageId'], '-B', '/code/prepare_osm_input_v2.py', '/inputs/recipe.json', expected, '/work', '--worker', phase, '--seconds', str(left)]
        result = 2
        try:
            created = call(command, check=True, capture_output=True, text=True).stdout.strip()
            require(len(created) == 64 and all(c in '0123456789abcdef' for c in created), 'Data owned worker ID'); identity = created
            def inspect(): return json.loads(call(['docker', 'inspect', identity], check=True, capture_output=True, text=True).stdout)[0]
            before = inspect(); hc = before['HostConfig']
            expected_limits = {'NetworkMode': network, 'Memory': 4294967296, 'MemorySwap': 4294967296, 'ReadonlyRootfs': True,
                'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'}}
            require(before['Image'] == plan['imageId'] and all(hc[k] == v for k, v in expected_limits.items()), 'Data container isolation drift')
            require(all(not m['RW'] for m in before['Mounts'] if m['Destination'] != '/work'), 'Unexpected writable data input')
            require({u['Name']: (u['Soft'], u['Hard']) for u in hc['Ulimits']} == {'core': (0, 0), 'fsize': (25769803776, 25769803776)}, 'Data file/core limits drift')
            with (stage / 'worker.log').open('xb') as log:
                child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
                try:
                    while child.poll() is None:
                        require(time.monotonic() < work_deadline, 'Data shared host deadline')
                        require(tree_bytes(root) <= max_output and log.tell() <= 1048576, 'Data output/log storage cap')
                        disk = os.statvfs(root); require(disk.f_bavail * disk.f_frsize >= caps['hostFreeHeadroomBytes'], 'Data live disk headroom')
                        time.sleep(.25)
                    result = child.returncode
                finally:
                    if child.poll() is None: child.kill()
                    child.wait(timeout=5)
            after = inspect()
            require(after['State']['ExitCode'] == result and not (result == 0 and after['State']['OOMKilled']), 'Data client/worker exit drift')
            results.append({'phase': phase, 'exitCode': result})
            (stage / 'container-result.json').write_bytes(json_bytes({'Image': after['Image'], 'State': after['State'], 'Limits': expected_limits,
                'Ulimits': hc['Ulimits'], 'Mounts': [{'destination': m['Destination'], 'writable': m['RW']} for m in before['Mounts']]}))
            if result:
                (stage / 'driver-stop.json').write_bytes(json_bytes({'workerExitCode': result, 'sourceFeasibilityQualified': False, 'derivedIndexesTrusted': False,
                    'hardStopCountersMayBePartial': after['State']['OOMKilled'] or result not in (0, 2),
                    'windows': [{'id': w['id'], 'status': 'unqualified_after_data_stop'} for w in plan['extractConfig']['windows']]}))
        except Exception as error:
            (stage / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'ownedContainer': identity, 'hardStopCountersMayBePartial': True,
                'sourceFeasibilityQualified': False, 'derivedIndexesTrusted': False, 'windows': [{'id': w['id'], 'status': 'unqualified_after_driver_stop'} for w in plan['extractConfig']['windows']]})); raise
        finally:
            def cleanup_call(args): return subprocess.run(args, capture_output=True, text=True, timeout=max(1, min(15, hard_deadline - time.monotonic())))
            if identity is None:
                found = cleanup_call(['docker', 'inspect', name])
                if found.returncode == 0:
                    owned = json.loads(found.stdout)[0]; require(owned['Config']['Labels'].get('geo-planner.data-owner') == owner and owned['Image'] == plan['imageId'], 'Refuse unowned data cleanup'); identity = owned['Id']
                else: require('No such' in found.stderr, 'Data owned-name discovery failed')
            if identity:
                removed = cleanup_call(['docker', 'rm', '-f', identity]); require(removed.returncode == 0, 'Data owned removal failed')
                absent = cleanup_call(['docker', 'inspect', identity]); require(absent.returncode != 0 and 'No such' in absent.stderr, 'Data independent owned cleanup')
                (stage / 'cleanup.json').write_bytes(json_bytes({'ownedContainer': identity, 'removed': True, 'independentInspectAbsent': True}))
        if result: break
    success = len(results) == 2 and all(p['exitCode'] == 0 for p in results)
    if success:
        try:
            # One final raw SHA scan is separate from polling/framing and shares the same host deadline.
            with absolute_timeout(max(.001, hard_deadline - time.monotonic() - 2)): verify_completed_data(root, plan)
        except Exception as error:
            success = False
            (root / 'completion-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'sourceFeasibilityQualified': False, 'derivedIndexesTrusted': False,
                'windows': [{'id': w['id'], 'status': 'unqualified_after_completion_check'} for w in plan['extractConfig']['windows']]}))
    elapsed = time.monotonic() - started; require(elapsed < 14400 and tree_bytes(root) <= max_output, 'Final data time/storage cap')
    summary = {'status': 'acquired_file_extract_complete_source_unqualified' if success else 'stopped', 'phases': results,
        'driverSecondsIncludingCleanupBeforeSummary': elapsed, 'sourceFeasibilityQualified': False, 'publisherBoundaryQualified': False,
        'usableAttributesQualified': False, 'modelChanged': False, 'providerRequests': 0, 'metadataRequests': 0, 'wheelRequests': 0}
    (root / 'run-summary.json').write_bytes(json_bytes(summary)); return 0 if success else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('recipe'); parser.add_argument('sha256'); parser.add_argument('output')
    parser.add_argument('--check', action='store_true'); parser.add_argument('--worker', choices=('download', 'extract')); parser.add_argument('--seconds', type=float)
    args = parser.parse_args()
    if args.worker: raise SystemExit(worker(args.recipe, args.sha256, args.output, args.worker, args.seconds))
    result = run_data(args.recipe, args.sha256, args.output, check_only=args.check)
    if args.check: print(json.dumps(result, indent=2))
    else: raise SystemExit(result)

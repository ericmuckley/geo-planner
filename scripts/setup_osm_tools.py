"""One frozen tool-only acquisition, isolated installation and native fixture proof."""
import argparse
from email.parser import BytesParser
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import selectors
import subprocess
import sys
import time
import uuid

from coarse_osm_bulk_transport import Meter, packaging_api, unpack_wheel
from coarse_osm_native_smoke import smoke
from coarse_osm_records import canonical, strict_json
from coarse_timing_input import cgroup_limit, digest, json_bytes, require, start_watchdog


SCOPE = 'docs/evidence/coarse-osm-tool-lock-v3-run-2026-10-26/next-tool-setup-plan.json'
SCOPE_SHA = '5f878e0b6271b4a705b6f4171b5ebcc551349446e533736e2bab5c7d824e1bb7'


def inventory(root, max_bytes, max_files=10000):
    files = {}; total = 0
    for path in sorted(Path(root).rglob('*')):
        require(not path.is_symlink(), 'Tool tree symlink')
        if path.is_dir(): continue
        require(path.is_file(), 'Tool tree special entry')
        total += path.stat().st_size; require(total <= max_bytes and len(files) < max_files, 'Tool tree byte/file cap')
        files[str(path.relative_to(root))] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    return {'bytes': total, 'files': files}


def validate_plan(plan, scope, lock):
    require(plan['phase'] == 'locked_tools_only_v1' and plan['output'] == scope['newOutput'] and plan['imageId'] == scope['imageId'], 'Tool scope/output/image drift')
    require(plan['scopeSha256'] == SCOPE_SHA and plan['caps'] == scope['proposedCaps'], 'Tool scope/cap drift')
    specs = [{'url': p['url'], 'kind': 'wheel', 'maxBytes': p['size'], 'exactBytes': p['size'], 'sha256': p['sha256'], 'seconds': 120,
        'filename': p['filename'], 'name': p['name'], 'version': p['version']} for p in lock['packages']]
    require(plan['wheelSpecs'] == scope['wheelSpecs'] == specs and len(specs) == 6 and lock['toolArchiveBytes'] == 2387936, 'Exact locked wheel scope drift')
    require(plan['networks'] == ['bridge', 'none'] and plan['imagePull'] == 'never', 'Tool network/pull drift')
    require(plan['inputs'][SCOPE] == SCOPE_SHA and all(plan['inputs'][p] == sha for p, sha in scope['inputs'].items()), 'Tool prerequisite bindings')


def wheel_metadata(root, pin, lock):
    paths = list(Path(root).glob('*.dist-info/METADATA')); require(len(paths) == 1, 'Wheel metadata count')
    metadata = BytesParser().parsebytes(paths[0].read_bytes())
    Req, Spec, _, name, parse, tags, env = packaging_api()
    require(name(metadata['Name']) == pin['name'] and metadata['Version'] == pin['version'], 'Wheel name/version')
    target = env(); target['extra'] = ''
    require(not metadata['Requires-Python'] or Spec(metadata['Requires-Python']).contains(target['python_full_version']), 'Wheel Python compatibility')
    require(bool(parse(pin['filename'])[3].intersection(tags())), 'Wheel target ABI tags')
    dependencies = []
    for text in metadata.get_all('Requires-Dist', []):
        req = Req(text)
        if req.marker and not req.marker.evaluate(target): continue
        require(not req.url and not req.extras, 'Unsupported wheel dependency')
        dependencies.append([name(req.name), str(req.specifier)])
    require(sorted(dependencies) == pin['dependencies'], 'Actual wheel dependency metadata differs from saved lock')
    for dependency, constraint in dependencies:
        require(Spec(constraint).contains(next(p['version'] for p in lock['packages'] if p['name'] == dependency)), 'Actual wheel dependency closure')
    return {'name': pin['name'], 'version': pin['version'], 'dependencies': sorted(dependencies), 'metadataSha256': digest(paths[0])}


def acquire(root, plan, lock, *, transport=None):
    root = Path(root).resolve(); http = root / 'http'; http.mkdir()
    caps = plan['caps']
    meter = Meter(http, plan['wheelSpecs'], {'attempts': 6, 'totalBytes': caps['totalHttpBodyBytes'],
        'kindBytes': {'metadata': 0, 'wheel': caps['totalHttpBodyBytes'], 'pbf': 0}, 'wallSeconds': caps['wallSeconds'],
        'idleSeconds': 20, 'workingBytes': caps['workingBytesIncludingTmp'] - caps['tmpBytes'], 'errorBytes': 65536}, transport=transport)
    paths = [meter.fetch(i) for i in range(len(plan['wheelSpecs']))]
    validation = root / 'validation'; validation.mkdir(); receipts = []; total = 0
    for archive, pin in zip(paths, lock['packages']):
        folder = validation / pin['name']
        unpacked = unpack_wheel(archive, pin, folder, caps['unpackedValidationBytes'] - total)
        total += unpacked['installedBytes']
        receipts.append({'archive': str(archive.relative_to(root)), 'filename': pin['filename'], 'sha256': digest(archive),
            **unpacked, 'metadata': wheel_metadata(folder, pin, lock)})
    receipt = {'status': 'six_locked_archives_validated', 'archiveBytes': sum(p.stat().st_size for p in paths), 'validationBytes': total, 'packages': receipts}
    (root / 'acquisition.json').write_bytes(json_bytes(receipt)); return receipt


def bounded_process(command, root, seconds, max_bytes, *, log_limit=65536, log_name='child.log'):
    """Bound child time/logs/files; polling limits are recorded, not disk-quota claims."""
    require(seconds > 0, 'Subprocess deadline')
    def limits(): resource.setrlimit(resource.RLIMIT_FSIZE, (67108864, 67108864))
    started = time.monotonic(); log = bytearray()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=limits,
        env={'PATH': os.environ['PATH'], 'PYTHONDONTWRITEBYTECODE': '1', 'PIP_CONFIG_FILE': '/dev/null', 'HOME': '/tmp', 'TMPDIR': '/tmp'})
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while True:
                require(time.monotonic() - started < seconds, 'Subprocess deadline')
                require(sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file()) <= max_bytes, 'Subprocess tree byte cap')
                ready = selector.select(.02)
                for key, _ in ready:
                    raw = os.read(key.fileobj.fileno(), 65536)
                    if not raw: selector.unregister(key.fileobj)
                    else:
                        log.extend(raw); require(len(log) <= log_limit, 'Subprocess log cap')
                if child.poll() is not None and not selector.get_map(): break
        require(child.returncode == 0, 'Offline child failed: ' + log.decode(errors='replace')[:2000])
        return bytes(log)
    finally:
        if child.poll() is None: child.kill()
        child.wait(timeout=5); child.stdout.close()
        (Path(root) / log_name).write_bytes(log[:log_limit])


def install_and_smoke(root, plan, lock, recipe, expected):
    root = Path(root); site = root / 'site'; require(not site.exists(), 'Installed target refuses reuse')
    caps = plan['caps']; began = time.monotonic()
    archives = [Path('/inputs/wheels') / p['filename'] for p in lock['packages']]
    for path, pin in zip(archives, lock['packages']): require(path.stat().st_size == pin['size'] and digest(path) == pin['sha256'], 'Offline archive binding')
    log = bounded_process([sys.executable, '-B', '-m', 'pip', 'install', '--isolated', '--disable-pip-version-check', '--no-index', '--no-deps',
        '--no-compile', '--no-cache-dir', '--no-warn-script-location', '--target', str(site), *map(str, archives)], root,
        min(120, caps['wallSeconds']), caps['installedTreeBytes'], log_name='pip.log')
    installed = inventory(site, caps['installedTreeBytes'])
    (root / 'installed-inventory.json').write_bytes(json_bytes(installed))
    bounded_process([sys.executable, '-B', '/code/setup_osm_tools.py', str(recipe), expected, str(root), '--worker', 'proof'],
        root, 60, caps['installedTreeBytes'] + caps['reportsStateReserveBytes'], log_name='proof.log')
    proof = strict_json((root / 'native-proof.json').read_bytes())
    require(inventory(site, caps['installedTreeBytes']) == installed, 'Import/smoke changed installed tool tree')
    result = {'status': 'passed', 'versions': proof['versions'], 'installedBytes': installed['bytes'], 'installedFiles': len(installed['files']),
        'tinyNativeDecoderQualified': proof['tinyNativeDecoderQualified'], 'nationalSourceFeasibilityQualified': False,
        'network': 'none', 'installAndSmokeSeconds': time.monotonic() - began,
        'storageGuard': '20ms child tree polling + 64MiB per-file RLIMIT_FSIZE + prevalidated wheels; no aggregate filesystem quota claim', 'pipLogBytes': len(log)}
    (root / 'installation.json').write_bytes(json_bytes(result)); return result


def native_proof(root, lock):
    root = Path(root); site = root / 'site'; sys.path.insert(0, str(site)); versions = {}
    for pin in lock['packages']:
        distribution = importlib.metadata.distribution(pin['name'])
        require(Path(distribution.locate_file('')).resolve() == site.resolve() and distribution.version == pin['version'], 'Installed version/location drift')
        versions[pin['name']] = distribution.version
    for module in ('certifi', 'charset_normalizer', 'idna', 'osmium', 'requests', 'urllib3'):
        imported = importlib.import_module(module); require(Path(imported.__file__).resolve().is_relative_to(site.resolve()), 'Import escaped isolated target')
    native = smoke(root / 'native', strict_json(Path('/inputs/proposal.json').read_bytes()))
    result = {'versions': versions, 'tinyNativeDecoderQualified': native['tinyNativeDecoderQualified']}
    (root / 'native-proof.json').write_bytes(json_bytes(result)); return result


def worker(recipe, expected, root, phase):
    require(digest(recipe) == expected, 'Worker recipe binding')
    plan = strict_json(Path(recipe).read_bytes())
    for path, sha in plan['workerFiles'].items(): require(digest(path) == sha, 'Worker source binding: ' + path)
    scope = strict_json(Path('/inputs/scope.json').read_bytes()); lock = strict_json(Path('/inputs/lock.json').read_bytes()); validate_plan(plan, scope, lock)
    require(cgroup_limit() == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}, 'Actual memory/swap drift')
    seconds = 60 if phase == 'proof' else plan['caps']['wallSeconds']
    watchdog = start_watchdog(seconds)
    root = Path(root)
    guard = 'proof-resource-guards.json' if phase == 'proof' else 'resource-guards.json'
    (root / guard).write_bytes(json_bytes({'memory': cgroup_limit(), 'watchdogSeconds': seconds, 'phase': phase}))
    try:
        if phase == 'acquire': acquire(root, plan, lock)
        elif phase == 'offline': install_and_smoke(root, plan, lock, recipe, expected)
        else: native_proof(root, lock)
        return 0
    except Exception as error:
        failure = 'proof-failure.json' if phase == 'proof' else 'failure.json'
        (root / failure).write_bytes(json_bytes({'status': 'stopped', 'phase': phase, 'errorType': type(error).__name__, 'error': str(error)[:4000],
            'nationalSourceFeasibilityQualified': False, 'policy': 'Preserve failed attempt; no retry/resume/overwrite.'})); return 2
    finally:
        if watchdog.poll() is None: watchdog.terminate(); watchdog.wait(timeout=5)


def driver(recipe, expected, output):
    repo = Path(__file__).resolve().parents[1]; path = Path(recipe).resolve()
    require(path.is_relative_to(repo / 'docs/evidence') and digest(path) == expected, 'Host recipe binding/path')
    plan = strict_json(path.read_bytes()); scope = strict_json((repo / SCOPE).read_bytes())
    lock = strict_json((repo / plan['lock']).read_bytes()); validate_plan(plan, scope, lock)
    for name, sha in plan['inputs'].items(): require(digest(repo / name) == sha, 'Host input binding: ' + name)
    root = (repo / output).resolve(); require(root == (repo / plan['output']).resolve(), 'Frozen output path')
    mounts = []
    for source, target in plan['mounts'].items():
        host = (repo / source).resolve()
        require(host.is_relative_to(repo) and host.is_file() and target.startswith(('/code/', '/inputs/')), 'Invalid isolated file mount')
        require(plan['inputs'][source] == plan['workerFiles'][target], 'Worker mount binding')
        mounts += ['--mount', f'type=bind,src={host},dst={target},readonly']
    root.mkdir(); (root / 'execution-plan.json').write_bytes(path.read_bytes())
    started = time.monotonic(); deadline = started + 570  # Last 30 seconds reserved for cleanup inside the shared 600s cap.
    results = []
    for phase, network in zip(('acquire', 'offline'), plan['networks']):
        stage = root / phase; stage.mkdir(); identity = None
        name = 'geo-planner-osm-tools-' + uuid.uuid4().hex[:12]; (stage / 'container-name.txt').write_text(name + '\n')
        def run(args, **options):
            remaining = deadline - time.monotonic(); require(remaining > 0, 'Shared tool deadline')
            return subprocess.run(args, timeout=min(options.pop('timeout', 30), remaining), **options)
        extra = []
        if phase == 'offline':
            for i, pin in enumerate(lock['packages'], 1):
                archive = root / 'acquire/http' / f'{i:03d}.bin'
                require(digest(archive) == pin['sha256'], 'Host archive binding')
                extra += ['--mount', f'type=bind,src={archive},dst=/inputs/wheels/{pin["filename"]},readonly']
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--network=' + network, '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g', '--cpus=2', '--pids-limit=64', '--tmpfs=/tmp:rw,size=64m',
            '--mount', f'type=bind,src={stage},dst=/work', '--mount', f'type=bind,src={path},dst=/inputs/recipe.json,readonly', *mounts, *extra,
            '--entrypoint=python3', plan['imageId'], '-B', '/code/setup_osm_tools.py', '/inputs/recipe.json', expected, '/work', '--worker', phase]
        try:
            identity = run(command, check=True, capture_output=True, text=True).stdout.strip()
            require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Owned worker ID')
            def inspect(): return json.loads(run(['docker', 'inspect', identity], check=True, capture_output=True, text=True).stdout)[0]
            before = inspect(); hc = before['HostConfig']
            require(before['Image'] == plan['imageId'] and hc['NetworkMode'] == network and hc['Memory'] == hc['MemorySwap'] == 1073741824
                and hc['ReadonlyRootfs'] and hc['NanoCpus'] == 2000000000 and hc['PidsLimit'] == 64 and hc['Tmpfs'] == {'/tmp': 'rw,size=64m'}, 'Actual worker isolation drift')
            # Poll an attached client so storage/time are bounded even if the worker stalls.
            with (stage / 'worker.log').open('xb') as log:
                client = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
                try:
                    while client.poll() is None:
                        require(time.monotonic() < deadline, 'Shared tool deadline')
                        inventory(root, plan['caps']['workingBytesIncludingTmp'] - plan['caps']['tmpBytes'])
                        require(log.tell() <= 65536, 'Worker log bound'); time.sleep(.1)
                    result = client.returncode
                finally:
                    if client.poll() is None: client.kill()
                    client.wait(timeout=5)
            after = inspect()
            record = {'State': after['State'], 'Image': after['Image'], 'Limits': {k: hc[k] for k in ('NetworkMode', 'Memory', 'MemorySwap', 'ReadonlyRootfs', 'NanoCpus', 'PidsLimit', 'Tmpfs')},
                'Mounts': [{'destination': m['Destination'], 'writable': m['RW']} for m in before['Mounts']]}
            (stage / 'container-result.json').write_bytes(json_bytes(record)); results.append({'phase': phase, 'exitCode': result})
        except Exception as error:
            (stage / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'ownedContainer': identity, 'hardStopCountersMayBePartial': True}))
            raise
        finally:
            if identity:
                subprocess.run(['docker', 'rm', '-f', identity], check=True, capture_output=True, timeout=max(1, min(15, started + 600 - time.monotonic())))
                absent = subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, timeout=max(1, min(10, started + 600 - time.monotonic())))
                require(absent.returncode != 0 and 'No such' in absent.stderr, 'Independent owned cleanup check')
                (stage / 'cleanup.json').write_bytes(json_bytes({'ownedContainer': identity, 'removed': True, 'independentInspectAbsent': True}))
        if result != 0: break
    total = inventory(root, plan['caps']['workingBytesIncludingTmp'] - plan['caps']['tmpBytes'])
    summary = {'status': 'passed' if len(results) == 2 and all(r['exitCode'] == 0 for r in results) else 'stopped', 'phases': results,
        'driverSecondsIncludingCleanupBeforeSummary': time.monotonic() - started, 'outputBytesBeforeSummary': total['bytes'],
        'nationalPbfRequests': 0, 'metadataRequests': 0, 'providerRequests': 0, 'nationalSourceFeasibilityQualified': False}
    require(summary['driverSecondsIncludingCleanupBeforeSummary'] < 600, 'Shared final deadline')
    (root / 'run-summary.json').write_bytes(json_bytes(summary)); return 0 if summary['status'] == 'passed' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe'); parser.add_argument('sha256'); parser.add_argument('output'); parser.add_argument('--worker', choices=('acquire', 'offline', 'proof'))
    args = parser.parse_args()
    raise SystemExit(worker(args.recipe, args.sha256, args.output, args.worker) if args.worker else driver(args.recipe, args.sha256, args.output))


if __name__ == '__main__': main()

"""Run one exact frozen, offline, bounded sample profile; no national source mount."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_data_v3 import tree_bytes
from coarse_osm_profile import save
from coarse_osm_records import strict_json
from coarse_timing_input import digest, require
from prepare_osm_input_v3 import capacity
from profile_osm_stream_v1 import CAPS, CASES, worker

LIMITS = {'NetworkMode': 'none', 'Memory': 4294967296, 'MemorySwap': 4294967296,
    'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'}}


def validate(plan):
    require(plan['phase'] == 'offline_stream_profile_v1' and plan['caps'] == CAPS and plan['cases'] == [list(c) for c in CASES], 'Stream phase/caps/cases drift')
    require(plan['network'] == 'none' and plan['imagePull'] == 'never', 'Stream offline only')
    require(plan['output'] == 'data/coarse-quality/us-osm-stream-v1', 'Stream fresh output binding')
    require(plan['prefix'] == {'path': 'data/coarse-quality/us-osm-profile-v2/prefix.osm.pbf', 'bytes': 377536,
        'sha256': '8c27122ee2321a320cf33c1f8c678fdd3041fee16621984380e768d4746d38b8'}, 'Stream prefix binding')
    require(plan['mixed'] == {'path': 'data/coarse-quality/us-osm-inventory-v3/scan/samples.jsonl', 'bytes': 3304488,
        'sha256': 'fd45e8844f790da058c708689548ee477382826d202ff06968d91db5ee1aee95'}, 'Stream mixed binding')
    require(len(plan['extractConfig']['windows']) == 21, 'Stream unchanged windows')
    require(plan['imageId'] == 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402', 'Stream cached image')


def check_isolation(observed, image):
    require(observed['Image'] == image and all(observed['HostConfig'][k] == v for k, v in LIMITS.items()), 'Stream isolation drift')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] != '/work'), 'Stream writable input')
    require({u['Name']: (u['Soft'], u['Hard']) for u in observed['HostConfig']['Ulimits']} == {'core': (0, 0), 'fsize': (67108864, 67108864)}, 'Stream file/core limits')


def cleanup(call, identity, name, owner, image, root):
    found = call(['docker', 'inspect', identity or name])
    if found.returncode != 0:
        require('No such' in found.stderr, 'Stream cleanup discovery failed')
        save(root / 'cleanup.json', {'ownedNameAbsent': True, 'ownedContainer': None})
        return
    obj = json.loads(found.stdout)[0]
    require(obj['Config']['Labels'].get('geo-planner.stream-owner') == owner and obj['Image'] == image, 'Refuse unrelated stream cleanup')
    identity = obj['Id']
    save(root / 'container-before-removal.json', {'State': obj['State']})
    removed = call(['docker', 'rm', '-f', identity])
    require(removed.returncode == 0, 'Stream owned removal failed')
    absent = call(['docker', 'inspect', identity])
    require(absent.returncode != 0 and 'No such' in absent.stderr, 'Stream owned absence failed')
    save(root / 'cleanup.json', {'ownedContainer': identity, 'removed': True, 'independentInspectAbsent': True})


def run(recipe, expected, output):
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo / 'docs/evidence') and digest(recipe) == expected, 'Stream recipe path/hash')
    plan = strict_json(recipe.read_bytes())
    validate(plan)
    root = (repo / output).resolve()
    require(root == repo / plan['output'] and not root.exists(), 'Stream output reuse/path')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(recipe.read_bytes())
    began = time.monotonic()
    deadline, hard = began + CAPS['hostWorkSeconds'], began + CAPS['hostSeconds']
    owner = uuid.uuid4().hex
    name = 'geo-planner-stream-v1-' + owner[:12]
    identity = child = result = None
    success = False
    save(root / 'owner.json', {'name': name, 'label': owner, 'image': plan['imageId']})
    def check():
        require(time.monotonic() < deadline, 'Stream host work deadline')
        require(tree_bytes(root) <= CAPS['workingBytesIncludingTmp'] - CAPS['tmpBytes'], 'Stream owned storage cap')
        disk = __import__('os').statvfs(root)
        require(disk.f_bavail * disk.f_frsize >= 2147483648, 'Stream disk headroom')
    def call(args, **kwargs):
        check()
        return subprocess.run(args, timeout=min(15, max(.01, deadline - time.monotonic())), capture_output=True, text=True, **kwargs)
    try:
        for path, pin in plan['inputs'].items():
            check()
            require(digest(repo / path) == pin, 'Stream input drift: ' + path)
        before = {}
        for key in ('prefix', 'mixed'):
            spec = plan[key]
            path = repo / spec['path']
            require(path.stat().st_size == spec['bytes'] and digest(path) == spec['sha256'], 'Stream sample identity')
            before[key] = stat_key(path)
        observed = capacity(repo)
        require(observed['hostDiskAvailableBytes'] >= 3221225472 and observed['hostMemoryBytes'] >= 8589934592 and observed['dockerMemoryBytes'] >= 6442450944
            and min(observed['hostCpuCount'], observed['dockerCpuCount']) >= 2, 'Stream capacity')
        save(root / 'capacity-at-start.json', observed)
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.stream-owner=' + owner,
            '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=64',
            '--ulimit', 'core=0:0', '--ulimit', 'fsize=67108864:67108864', '--tmpfs=/tmp:rw,size=256m', '--env', 'LD_LIBRARY_PATH=/tools/runtime']
        for source, destination in plan['mounts'].items():
            command += ['--mount', f'type=bind,src={repo / source},dst={destination},readonly']
        command += ['--mount', f'type=bind,src={repo / plan["site"]},dst=/tools/site,readonly']
        for filename, path in plan['runtime'].items():
            command += ['--mount', f'type=bind,src={repo / path},dst=/tools/runtime/{filename},readonly']
        command += ['--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
            '--entrypoint=python3', plan['imageId'], '-B', '/code/run_osm_stream_v1.py', '/inputs/recipe.json', expected, '/work', '--worker']
        identity = call(command, check=True).stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Stream owned ID')
        initial = json.loads(call(['docker', 'inspect', identity], check=True).stdout)[0]
        check_isolation(initial, plan['imageId'])
        save(root / 'container-initial.json', {'Image': initial['Image'], 'Limits': LIMITS, 'Ulimits': initial['HostConfig']['Ulimits'],
            'Mounts': [{'destination': m['Destination'], 'writable': m['RW']} for m in initial['Mounts']]})
        with (root / 'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                check()
                require(log.tell() <= CAPS['reportBytes'], 'Stream log cap')
                time.sleep(.25)
            result = child.returncode
        final = json.loads(call(['docker', 'inspect', identity], check=True).stdout)[0]
        save(root / 'container-result.json', {'State': final['State'], 'Image': final['Image']})
        require(final['State']['ExitCode'] == result and not final['State']['OOMKilled'], 'Stream exit/OOM')
        require(all(before[key] == stat_key(repo / plan[key]['path']) for key in before), 'Stream input mutation')
        success = result == 0
    except (Exception, KeyboardInterrupt) as error:
        save(root / 'driver-failure.json', {'errorType': type(error).__name__, 'error': str(error)[:2000], 'wholeExtractionQualified': False})
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        def cleanup_call(args):
            return subprocess.run(args, capture_output=True, text=True, timeout=max(1, min(15, hard - time.monotonic())))
        cleanup(cleanup_call, identity, name, owner, plan['imageId'], root)
    elapsed = time.monotonic() - began
    require(elapsed < CAPS['hostSeconds'] and tree_bytes(root) <= CAPS['workingBytesIncludingTmp'] - CAPS['tmpBytes'], 'Stream final time/storage')
    save(root / 'run-summary.json', {'status': 'passed_sample_screen' if success else 'stopped_or_gate_failed', 'workerClientExitCode': result, 'hostSecondsBeforeSummary': elapsed,
        'networkRequests': 0, 'wholeExtractionQualified': False, 'modelChanged': False})
    return 0 if success else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('sha256')
    parser.add_argument('output')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        require(digest(args.recipe) == args.sha256, 'Stream worker recipe hash')
        plan = strict_json(Path(args.recipe).read_bytes())
        validate(plan)
        __import__('sys').path.insert(0, '/tools/site')
        raise SystemExit(worker(plan, args.output))
    raise SystemExit(run(args.recipe, args.sha256, args.output))

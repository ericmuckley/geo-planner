"""Cached native entry resolver/CSR controls and captured correction equivalence."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
import unittest
import uuid

from coarse_osm_build_v1 import sha
from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
from coarse_osm_records import strict_json
from coarse_timing_input import require, start_watchdog
from prepare_osm_native_lock_v1 import IMAGE, cleanup_owned, settle_error
from run_osm_build_v1 import COMPILER, tool
from run_osm_country_screen_v15 import ASSET_ROOT
from coarse_osm_car_policy_v2 import POLICY as BASE_POLICY

POLICY = {"id": "native-conservative-entry-v1", "basePolicyId": BASE_POLICY["id"], "unchanged": "source costs, permissions, node flags and supported turns", "change": "qualified static single-via-way prohibitions use conservative entry pairs; all other/unresolved closure unions remain"}

FLAGS = ['-std=c++17', '-O2', '-ffp-contract=off', '-fPIC', '-shared', '-fvisibility=hidden', '-static-libstdc++', '-static-libgcc',
         '/work/coarse_osm_car_entry_native_v1.cpp', '-Wl,-z,defs', '-Wl,--exclude-libs,ALL', '-Wl,-Bsymbolic-functions', '-o', '/work/car-entry.so']
OUTPUTS = {stage: 'data/coarse-quality/us-osm-car-entry-' + stage + '-v1' for stage in ('build', 'controls', 'equivalence')}
CAPS = {'memoryBytes': 4294967296, 'tmpBytes': 268435456, 'fileBytes': 67108864,
        'ownedBytes': {'build': 67108864, 'controls': 67108864, 'equivalence': 67108864}, 'entries': 1024,
        'priorRetainedReserveBytes': 64500000000, 'overallRetainedBytes': 68719476736,
        'workerSeconds': {'build': 150, 'controls': 150, 'equivalence': 600},
        'hostSeconds': {'build': 180, 'controls': 180, 'equivalence': 660}}
TESTS = 12


def validate(plan):
    stage = plan['stage']
    require(stage in OUTPUTS and plan['phase'] == 'car_entry_native_v1', 'Entry native stage/phase')
    require(plan['caps'] == CAPS and plan['policy'] == POLICY and plan['image'] == IMAGE and plan['flags'] == FLAGS, 'Entry native frozen parameters')
    require(plan['output'] == OUTPUTS[stage] and plan['network'] == 'none' and plan['imagePull'] == 'never', 'Entry native output/network')
    require(set(plan['inputs']) == set(plan['mounts']) and plan['tests'] == TESTS, 'Entry native exact roster/tests')
    for name, dest in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and dest.startswith(('/code/', '/reference/', '/tools/', '/repo/', '/inputs/', '/docs/')), 'Entry native readonly input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and 'primary-index' not in name, 'Entry native no country/fine input')
    require(plan['rootfs']['path'] == ASSET_ROOT and plan['headers'] == {}, 'Entry native cached compiler/no third-party headers')
    require(CAPS['priorRetainedReserveBytes'] + sum(plan['newClosedAllocations'].values()) + sum(CAPS['ownedBytes'].values()) + CAPS['tmpBytes'] < CAPS['overallRetainedBytes'], 'Entry native aggregate envelope')
    for name in ('coarse_osm_car_entry_native_v1_test.py', 'coarse_osm_car_entry_equivalence_v1.py', 'coarse_osm_packed_capture_v1.py'):
        require(plan['mounts'].get('scripts/'+name) == '/code/'+name, 'Cost exact dependency mount: '+name)
    if stage != 'build':
        require(plan['artifact']['path'] == OUTPUTS['build'] + '/car-entry.so', 'Entry native artifact identity')
    if stage == 'equivalence':
        require(plan['admission']['tests'] == TESTS and plan['admission']['successful'] and plan['admission']['skips'] == 0, 'Entry native controls before captured data')


def bounded_save(root, name, value):
    path = root / name
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    require(path.parent == root and not path.exists() and len(raw) <= 2097152, 'Entry native fresh bounded record')
    with path.open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_data import verify_worker_inputs, memory_guard
    root = Path('/work')
    stage = plan['stage']
    began = time.monotonic()
    timer = start_watchdog(CAPS['workerSeconds'][stage])
    def check():
        require(time.monotonic() - began < CAPS['workerSeconds'][stage] - 5, 'Entry native worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= CAPS['ownedBytes'][stage], 'Entry native owned allocation cap')
    try:
        verify_worker_inputs({'workerFiles': {dest: plan['inputs'][name] for name, dest in plan['mounts'].items()}})
        memory_guard()
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(CAPS['memoryBytes']) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Entry native hard memory/swap')
        tmp = os.statvfs('/builder/tmp' if stage == 'build' else '/tmp')
        require(tmp.f_blocks * tmp.f_frsize == CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE) == (CAPS['fileBytes'], CAPS['fileBytes']), 'Entry native tmp/file limits')
        if stage == 'build':
            root.chmod(0o777)
            for name in ('coarse_osm_car_entry_native_v1.cpp', 'coarse_osm_car_packed_native_v1.cpp'):
                shutil.copyfile('/code/' + name, root / name)
            tool(root, 'compiler-version', [COMPILER, '--version'], check)
            tool(root, 'compile', [COMPILER, *FLAGS], check)
            elf = tool(root, 'elf', ['/usr/bin/readelf', '-h', '-d', '-V', '-Ws', '/work/car-entry.so'], check)
            import re
            needed = re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', elf)
            require('AArch64' in elf and 'little endian' in elf and 'GLIBCXX_' not in elf and all(n in elf for n in ('gp_car_entry_abi', 'gp_car_entry_resolve', 'gp_car_entry_augment', 'gp_car_packed_abi', 'gp_car_packed_encode')), 'Entry native ELF/static runtime')
            require(set(needed) <= {'libm.so.6', 'libc.so.6', 'libpthread.so.0', 'libdl.so.2', 'librt.so.1', 'ld-linux-aarch64.so.1'}, 'Entry native ABI dependencies')
            bounded_save(root, 'result.json', {'status': 'compiled_controls_pending', 'artifactSha256': sha(root/'car-entry.so'), 'artifactBytes': (root/'car-entry.so').stat().st_size, 'needed': needed})
        else:
            from coarse_osm_car_entry_native_v1 import NativeEntries
            artifact = ('/artifacts/car-entry.so', plan['artifact']['sha256'])
            native = NativeEntries(*artifact)
            if stage == 'controls':
                import coarse_osm_car_entry_native_v1_test as tests
                tests.configure_native(*artifact)
                tested = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
                result = {'tests': tested.testsRun, 'successful': tested.wasSuccessful(), 'failures': len(tested.failures), 'errors': len(tested.errors), 'skips': len(tested.skipped)}
                bounded_save(root, 'controls.json', result)
                require(result['successful'] and result['tests'] == TESTS and result['skips'] == 0, 'Entry native controls')
            else:
                from coarse_osm_car_entry_equivalence_v1 import run
                result = run(native, Path('/repo'), check)
            bounded_save(root, 'result.json', result | {'secondsIncludingBindingsAndTests': time.monotonic()-began})
        return 0
    except BaseException as error:
        bounded_save(root, 'worker-failure.json', {'errorType': type(error).__name__, 'error': str(error)[:2000], 'nationalOrModelAdmitted': False})
        return 2
    finally:
        bounded_save(root, 'metrics.json', resource_metrics())
        if timer.poll() is None:
            timer.terminate()
        timer.wait(timeout=5)

def isolation(observed,stage):
    host=observed['HostConfig'];tmp='/builder/tmp' if stage=='build' else '/tmp'
    expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{tmp:'rw,size=256m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Entry native observed isolation')
    require({c.removeprefix('CAP_') for c in host.get('CapAdd') or []}==({'SYS_CHROOT'} if stage=='build' else set()) and {c.removeprefix('CAP_') for c in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Entry native capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] not in ('/work','/builder/work')),'Entry native readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Entry native hard file/core')


def driver(plan,recipe):
    repo=Path(__file__).resolve().parents[1];stage=plan['stage'];root=repo/OUTPUTS[stage]
    from coarse_osm_python_bindings_v1 import require_bindings
    require_bindings(repo,['scripts/run_osm_car_entry_native_v1.py','scripts/coarse_osm_car_entry_native_v1_test.py','scripts/coarse_osm_car_entry_equivalence_v1.py'],plan['mounts'])
    require(not root.exists(),'Entry native fresh output required');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-car-entry-'+stage+'-'+owner[:12];identity=child=None;code=2
    bounded_save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds'][stage]-15,'Entry native host deadline')
        usage=owned_usage(root);require(usage['conservativeAllocatedBytes']<=CAPS['ownedBytes'][stage] and usage['entries']<=CAPS['entries'],'Entry native host allocation/namespace')
        require(shutil.disk_usage(root).free>=1073741824,'Entry native disk headroom')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin in plan['inputs'].items():check();require(sha(repo/name_input)==pin,'Entry native host input drift: '+name_input)
        if stage=='build':
            spec=importlib.util.spec_from_file_location('qualified_asset_contents',repo/plan['assetProof']);assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
            require(assets.snapshot(repo/ASSET_ROOT)==plan['rootfs']['portable'],'Entry native cached compiler contents')
            
        else:require(sha(repo/plan['artifact']['path'])==plan['artifact']['sha256'],'Entry native host artifact drift')
        # Build/controls use synthetic data only; equivalence adds sealed captured metadata.
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--tmpfs',('/builder/tmp' if stage=='build' else '/tmp')+':rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        if stage=='build':
            args+=['--cap-add=SYS_CHROOT','--mount',f'type=bind,src={repo/ASSET_ROOT},dst=/builder,readonly','--mount',f'type=bind,src={root},dst=/builder/work']
        else:args+=['--mount',f'type=bind,src={repo/OUTPUTS["build"]},dst=/artifacts,readonly']
        # All mounted files are exactly checksum-bound, including cached site files.
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_car_entry_native_v1.py','/inputs/recipe.json',sha(recipe),'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Entry native owned identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,stage)
        bounded_save(root,'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();require((root/'worker.log').stat().st_size<=2097152,'Entry native log cap');time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];bounded_save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Entry native worker failed/OOM');code=0
    except BaseException as error:bounded_save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child is not None else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    bounded_save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingBindingsWorkerCleanup':time.monotonic()-began,'stage':stage,'networkRequests':0,'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Entry native recipe binding');plan=strict_json(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe))

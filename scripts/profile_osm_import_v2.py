"""Run one frozen, network-disabled importer-prefix profile in the qualified image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from coarse_osm_data_v3 import tree_bytes
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_profile_v2 import CAPS, CASES, worker, save
from coarse_osm_records import strict_json
from coarse_timing_input import digest, require
from prepare_osm_input_v3 import capacity


def validate(plan):
    require(plan['phase'] == 'offline_import_profile_v2' and plan['caps'] == CAPS, 'Profile phase/caps drift')
    require(plan['cases'] == [list(case) for case in CASES], 'Profile fixed cases drift')
    require(plan['network'] == 'none' and plan['imagePull'] == 'never', 'Profile must be offline')
    require(plan['output'] == 'data/coarse-quality/us-osm-profile-v2', 'Profile output drift')
    require(plan['source']['bytes'] == 12229320016 and plan['source']['sha256'] == '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
        and plan['source']['md5'] == 'c5abaec55e724255277f22fb97941e5a', 'Profile source identity drift')
    require(len(plan['extractConfig']['windows']) == 21, 'Original window roster required')


def verify_source(source, spec, check):
    before = stat_key(source)
    require(before[2] == spec['bytes'], 'Profile full-source size')
    sha, md5 = hashlib.sha256(), hashlib.md5()
    began = time.monotonic()
    with source.open('rb') as stream:
        while raw := stream.read(8388608):
            check()
            sha.update(raw)
            md5.update(raw)
    require(before == stat_key(source) and sha.hexdigest() == spec['sha256'] and md5.hexdigest() == spec['md5'], 'Profile complete-source hash drift')
    return before, {'bytesHashedBeforeNativeWork': before[2], 'sha256': sha.hexdigest(), 'md5': md5.hexdigest(),
        'hostHashSeconds': time.monotonic()-began, 'sourceStat': before,
        'scope': 'One identity-only full-byte pass; no native objects decoded.'}


def run(recipe, expected, output, *, repo=None):
    repo = Path(repo or Path(__file__).resolve().parents[1]).resolve()
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo / 'docs/evidence') and digest(recipe) == expected, 'Profile recipe path/hash')
    plan = strict_json(recipe.read_bytes()); validate(plan)
    root = (repo / output).resolve()
    require(root == repo / plan['output'] and not root.exists(), 'Profile requires fresh frozen output')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(recipe.read_bytes())
    began = time.monotonic(); deadline = began + CAPS['hostWorkSeconds']; hard_deadline = began + CAPS['hostSeconds']
    owner = uuid.uuid4().hex; name = 'geo-planner-profile-v2-' + owner[:12]
    identity = None; child = None; success = False; result = None
    save(root / 'owner.json', {'name': name, 'label': owner, 'image': plan['imageId']})
    def check():
        require(time.monotonic() < deadline, 'Profile shared host deadline')
        disk = os.statvfs(root)
        require(disk.f_bavail * disk.f_frsize >= 2147483648, 'Profile disk headroom')
    def call(args, **options):
        check()
        return subprocess.run(args, timeout=min(options.pop('timeout', 15), max(.01, deadline-time.monotonic())), **options)
    try:
        for filename, sha in plan['inputs'].items():
            check(); require(digest(repo / filename) == sha, 'Profile input drift: ' + filename)
        base = strict_json((repo / plan['basePlan']).read_bytes())
        require(plan['extractConfig'] == base['extractConfig'] and plan['imageId'] == base['imageId'] and plan['site'] == base['site'] and plan['runtime'] == base['runtime'], 'Profile base semantics/tools drift')
        source = repo / plan['source']['path']
        before, binding = verify_source(source, plan['source'], check)
        save(root / 'source-binding.json', binding)
        observed = capacity(repo)
        require(observed['hostDiskAvailableBytes'] >= 3221225472 and observed['hostMemoryBytes'] >= 8589934592
            and observed['dockerMemoryBytes'] >= 6442450944 and min(observed['hostCpuCount'], observed['dockerCpuCount']) >= 2, 'Profile capacity')
        save(root / 'capacity-at-start.json', observed)
        image = json.loads(call(['docker', 'image', 'inspect', plan['imageId']], capture_output=True, text=True, check=True).stdout)[0]
        require(image['Id'] == plan['imageId'] and image['Architecture'] == 'arm64', 'Qualified cached image drift')
        mounts=[]
        for filename, destination in plan['mounts'].items():
            mounts += ['--mount', f'type=bind,src={repo / filename},dst={destination},readonly']
        mounts += ['--mount', f'type=bind,src={repo / plan["site"]},dst=/tools/site,readonly']
        for filename, path in plan['runtime'].items():
            mounts += ['--mount', f'type=bind,src={repo / path},dst=/tools/runtime/{filename},readonly']
        command = ['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.profile-owner='+owner,
            '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64',
            '--ulimit','core=0:0','--ulimit',f'fsize={CAPS["fileBytes"]}:{CAPS["fileBytes"]}','--tmpfs=/tmp:rw,size=256m',
            '--env','LD_LIBRARY_PATH=/tools/runtime','--mount',f'type=bind,src={root},dst=/work',
            '--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--mount',f'type=bind,src={source},dst=/inputs/source.pbf,readonly',
            *mounts,'--entrypoint=python3',plan['imageId'],'-B','/code/profile_osm_import_v2.py','/inputs/recipe.json',expected,'/work','--worker']
        created = call(command, capture_output=True, text=True, check=True).stdout.strip()
        require(len(created) == 64 and all(c in '0123456789abcdef' for c in created), 'Profile owned ID')
        identity = created
        def inspect(): return json.loads(call(['docker','inspect',identity],capture_output=True,text=True,check=True).stdout)[0]
        initial = inspect(); hc = initial['HostConfig']
        limits = {'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{'/tmp':'rw,size=256m'}}
        require(initial['Image'] == plan['imageId'] and all(hc[k] == v for k,v in limits.items()), 'Profile isolation drift')
        require(all(not m['RW'] for m in initial['Mounts'] if m['Destination'] != '/work'), 'Profile writable input')
        require({u['Name']:(u['Soft'],u['Hard']) for u in hc['Ulimits']} == {'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])}, 'Profile file/core limits')
        save(root / 'container-initial.json', {'Image':initial['Image'],'State':initial['State'],'Limits':limits,'Ulimits':hc['Ulimits'],
            'Mounts':[{'destination':m['Destination'],'writable':m['RW']} for m in initial['Mounts']]})
        with (root / 'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                check(); require(tree_bytes(root) <= CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'] and log.tell() <= CAPS['reportBytes'], 'Profile storage/log cap')
                time.sleep(.25)
            result = child.returncode
        final = inspect()
        save(root / 'container-result.json', {'Image':final['Image'],'State':final['State']})
        require(final['State']['ExitCode'] == result and not final['State']['OOMKilled'], 'Profile worker/client exit or OOM')
        require(before == stat_key(source), 'Profile source changed during worker')
        success = result == 0
    except (Exception, KeyboardInterrupt) as error:
        save(root / 'driver-failure.json', {'errorType':type(error).__name__,'error':str(error)[:2000],
            'wholeExtractionQualified':False,'partialIndexesTrusted':False})
    finally:
        if child is not None and child.poll() is None:
            child.kill(); child.wait(timeout=5)
        def cleanup_call(args):
            return subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(15,hard_deadline-time.monotonic())))
        found = cleanup_call(['docker','inspect',identity or name])
        if found.returncode == 0:
            owned = json.loads(found.stdout)[0]
            require(owned['Config']['Labels'].get('geo-planner.profile-owner') == owner and owned['Image'] == plan['imageId'], 'Refuse unrelated profile cleanup')
            identity = owned['Id']
            save(root / 'container-before-removal.json', {'State':owned['State'],'scope':'Pre-removal observation; final exit/OOM requires container-result.'})
            removed = cleanup_call(['docker','rm','-f',identity]); require(removed.returncode == 0,'Profile owned removal')
            absent = cleanup_call(['docker','inspect',identity]); require(absent.returncode != 0 and 'No such' in absent.stderr,'Profile owned absence')
            save(root / 'cleanup.json',{'ownedContainer':identity,'removed':True,'independentInspectAbsent':True})
        else:
            require('No such' in found.stderr,'Profile cleanup discovery')
            save(root / 'cleanup.json',{'ownedContainer':None,'ownedNameAbsent':True})
    elapsed = time.monotonic()-began
    require(elapsed < CAPS['hostSeconds'] and tree_bytes(root) <= CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'], 'Profile final resource cap')
    save(root / 'run-summary.json',{'status':'passed_bounded_profile' if success else 'stopped','hostSecondsIncludingHashAndCleanupBeforeSummary':elapsed,
        'workerClientExitCode':result,'networkRequests':0,'wholeSourceEof':False,'wholeExtractionQualified':False,'modelChanged':False})
    return 0 if success else 2


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output');parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    if args.worker:
        require(digest(args.recipe) == args.sha256,'Profile worker recipe hash')
        plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
        sys.path.insert(0,'/tools/site')
        raise SystemExit(worker(plan,args.output))
    raise SystemExit(run(args.recipe,args.sha256,args.output))

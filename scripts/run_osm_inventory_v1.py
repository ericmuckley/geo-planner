"""Run one frozen, network-disabled native inventory in the qualified image."""
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
from coarse_osm_inventory import CAPS, worker, save
from profile_osm_import_v2 import verify_source
from coarse_osm_records import strict_json
from coarse_timing_input import digest, require
from prepare_osm_input_v3 import capacity


def validate(plan):
    require(plan['phase'] == 'offline_inventory_v1' and plan['caps'] == CAPS, 'Inventory phase/caps drift')
    require(plan['network'] == 'none' and plan['imagePull'] == 'never', 'Inventory must be offline')
    require(plan['output'] == 'data/coarse-quality/us-osm-inventory-v1', 'Inventory output drift')
    require(plan['source']['bytes'] == 12229320016 and plan['source']['sha256'] == '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
        and plan['source']['md5'] == 'c5abaec55e724255277f22fb97941e5a', 'Inventory source identity drift')
    require(len(plan['extractConfig']['windows']) == 21, 'Original window roster required')


def verify_forecast(plan,base,profile):
    config=base['extractConfig'];caps=config['proposedCaps']
    require([caps[k] for k in ('scanNodesPerPass','scanWaysPerPass','scanRelationsPerPass')] == [CAPS[k] for k in ('nodeLimit','wayLimit','relationLimit')], 'Inventory original row ceilings')
    index=next(row for row in profile['cases'] if row['mode']=='index')
    expected={'candidateNodeIndexMedianSeconds':profile['medianIndexSeconds']['candidate'],
        'nodeSampleCount':index['counts']['node'],'sampleIndexBytes':index['indexBytes'],
        'workSeconds':caps['wallSeconds']-60,'sqliteIndexBytesEach':caps['sqliteIndexBytesEach'],
        'workingBytes':caps['workingBytesIncludingTmp'],
        'otherOriginalWorkingBytes':sum(config['resourceArithmetic']['storageComponents'].values())-2*caps['sqliteIndexBytesEach']}
    require(plan['forecastInputs']==expected and expected['nodeSampleCount']>0, 'Inventory forecast binding drift')


def run(recipe, expected, output, *, repo=None):
    repo = Path(repo or Path(__file__).resolve().parents[1]).resolve()
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo / 'docs/evidence') and digest(recipe) == expected, 'Inventory recipe path/hash')
    plan = strict_json(recipe.read_bytes()); validate(plan)
    root = (repo / output).resolve()
    require(root == repo / plan['output'] and not root.exists(), 'Inventory requires fresh frozen output')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(recipe.read_bytes())
    began = time.monotonic(); deadline = began + CAPS['hostWorkSeconds']; hard_deadline = began + CAPS['hostSeconds']
    owner = uuid.uuid4().hex; name = 'geo-planner-inventory-v1-' + owner[:12]
    identity = None; child = None; success = False; result = None
    save(root / 'owner.json', {'name': name, 'label': owner, 'image': plan['imageId']})
    def check():
        require(time.monotonic() < deadline, 'Inventory shared host deadline')
        disk = os.statvfs(root)
        require(disk.f_bavail * disk.f_frsize >= 2147483648, 'Inventory disk headroom')
    def call(args, **options):
        check()
        return subprocess.run(args, timeout=min(options.pop('timeout', 15), max(.01, deadline-time.monotonic())), **options)
    try:
        for filename, sha in plan['inputs'].items():
            check(); require(digest(repo / filename) == sha, 'Inventory input drift: ' + filename)
        base = strict_json((repo / plan['basePlan']).read_bytes())
        require(plan['extractConfig'] == base['extractConfig'] and plan['imageId'] == base['imageId'] and plan['site'] == base['site'] and plan['runtime'] == base['runtime'], 'Inventory base semantics/tools drift')
        verify_forecast(plan,base,strict_json((repo / plan['profileResult']).read_bytes()))
        source = repo / plan['source']['path']
        before, binding = verify_source(source, plan['source'], check)
        save(root / 'source-binding.json', binding)
        observed = capacity(repo)
        require(observed['hostDiskAvailableBytes'] >= 3221225472 and observed['hostMemoryBytes'] >= 8589934592
            and observed['dockerMemoryBytes'] >= 6442450944 and min(observed['hostCpuCount'], observed['dockerCpuCount']) >= 2, 'Inventory capacity')
        save(root / 'capacity-at-start.json', observed)
        image = json.loads(call(['docker', 'image', 'inspect', plan['imageId']], capture_output=True, text=True, check=True).stdout)[0]
        require(image['Id'] == plan['imageId'] and image['Architecture'] == 'arm64', 'Qualified cached image drift')
        mounts=[]
        for filename, destination in plan['mounts'].items():
            mounts += ['--mount', f'type=bind,src={repo / filename},dst={destination},readonly']
        mounts += ['--mount', f'type=bind,src={repo / plan["site"]},dst=/tools/site,readonly']
        for filename, path in plan['runtime'].items():
            mounts += ['--mount', f'type=bind,src={repo / path},dst=/tools/runtime/{filename},readonly']
        command = ['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.inventory-owner='+owner,
            '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64',
            '--ulimit','core=0:0','--ulimit',f'fsize={CAPS["fileBytes"]}:{CAPS["fileBytes"]}','--tmpfs=/tmp:rw,size=256m',
            '--env','LD_LIBRARY_PATH=/tools/runtime','--mount',f'type=bind,src={root},dst=/work',
            '--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--mount',f'type=bind,src={source},dst=/inputs/source.pbf,readonly',
            *mounts,'--entrypoint=python3',plan['imageId'],'-B','/code/run_osm_inventory_v1.py','/inputs/recipe.json',expected,'/work','--worker']
        created = call(command, capture_output=True, text=True, check=True).stdout.strip()
        require(len(created) == 64 and all(c in '0123456789abcdef' for c in created), 'Inventory owned ID')
        identity = created
        def inspect(): return json.loads(call(['docker','inspect',identity],capture_output=True,text=True,check=True).stdout)[0]
        initial = inspect(); hc = initial['HostConfig']
        limits = {'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{'/tmp':'rw,size=256m'}}
        require(initial['Image'] == plan['imageId'] and all(hc[k] == v for k,v in limits.items()), 'Inventory isolation drift')
        require(all(not m['RW'] for m in initial['Mounts'] if m['Destination'] != '/work'), 'Inventory writable input')
        require({u['Name']:(u['Soft'],u['Hard']) for u in hc['Ulimits']} == {'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])}, 'Inventory file/core limits')
        save(root / 'container-initial.json', {'Image':initial['Image'],'State':initial['State'],'Limits':limits,'Ulimits':hc['Ulimits'],
            'Mounts':[{'destination':m['Destination'],'writable':m['RW']} for m in initial['Mounts']]})
        with (root / 'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                check(); require(tree_bytes(root) <= CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'] and log.tell() <= CAPS['reportBytes'], 'Inventory storage/log cap')
                time.sleep(.25)
            result = child.returncode
        final = inspect()
        save(root / 'container-result.json', {'Image':final['Image'],'State':final['State']})
        require(final['State']['ExitCode'] == result and not final['State']['OOMKilled'], 'Inventory worker/client exit or OOM')
        require(before == stat_key(source), 'Inventory source changed during worker')
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
            require(owned['Config']['Labels'].get('geo-planner.inventory-owner') == owner and owned['Image'] == plan['imageId'], 'Refuse unrelated profile cleanup')
            identity = owned['Id']
            save(root / 'container-before-removal.json', {'State':owned['State'],'scope':'Pre-removal observation; final exit/OOM requires container-result.'})
            removed = cleanup_call(['docker','rm','-f',identity]); require(removed.returncode == 0,'Inventory owned removal')
            absent = cleanup_call(['docker','inspect',identity]); require(absent.returncode != 0 and 'No such' in absent.stderr,'Inventory owned absence')
            save(root / 'cleanup.json',{'ownedContainer':identity,'removed':True,'independentInspectAbsent':True})
        else:
            require('No such' in found.stderr,'Inventory cleanup discovery')
            save(root / 'cleanup.json',{'ownedContainer':None,'ownedNameAbsent':True})
    elapsed = time.monotonic()-began
    require(elapsed < CAPS['hostSeconds'] and tree_bytes(root) <= CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'], 'Inventory final resource cap')
    worker_result = strict_json((root/'result.json').read_bytes()) if (root/'result.json').exists() else {}
    save(root / 'run-summary.json',{'status':'completed_inventory_screen' if success else 'stopped','hostSecondsIncludingHashAndCleanupBeforeSummary':elapsed,
        'workerClientExitCode':result,'networkRequests':0,'wholeSourceNativeEof':worker_result.get('inventory',{}).get('wholeSourceNativeEof',False),'wholeExtractionQualified':False,'modelChanged':False})
    return 0 if success else 2


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output');parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    if args.worker:
        require(digest(args.recipe) == args.sha256,'Inventory worker recipe hash')
        plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
        sys.path.insert(0,'/tools/site')
        raise SystemExit(worker(plan,args.output))
    raise SystemExit(run(args.recipe,args.sha256,args.output))

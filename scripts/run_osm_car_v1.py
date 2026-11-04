"""Bounded road-only static-car cost/encoding qualification; no country build or app change."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time
import unittest
import uuid

from coarse_timing_input import require,start_watchdog
from coarse_osm_car_policy_v1 import POLICY
from coarse_osm_car_graph_v1 import CAPS as DATA_CAPS

IMAGE='sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
OUTPUTS={stage:f'data/coarse-quality/us-osm-car-{stage}-v1' for stage in ('controls','run')}
CAPS={'memoryBytes':2147483648,'tmpBytes':67108864,'fileBytes':134217728,'ownedBytes':268435456,'workerSeconds':600,'hostSeconds':660}
CODE=['coarse_osm_car_policy_v1','coarse_osm_car_codec_v1','coarse_osm_car_graph_v1','coarse_osm_car_payload_v1','coarse_osm_car_v1_test','run_osm_car_v1','coarse_osm_bulk_pbf','run_osm_lineage_v1','coarse_osm_lineage_v1','coarse_osm_lineage_v1_test','coarse_osm_backbone_v1','coarse_osm_backbone_v1_test','coarse_osm_match_v1','coarse_osm_match_v1_test','coarse_osm_attribute_inventory_v1','coarse_osm_attributes_v1','coarse_osm_records','coarse_path_features','coarse_timing_chains','coarse_timing_fragments','coarse_timing_fragments_audit','coarse_timing_compatibility_audit','analyze_timing_cache','analyze_timing_compatibility','coarse_timing_input','coarse_timing_parquet','coarse_backbone_paths','coarse_backbone_codec']
REFERENCES=['import_roads','barrier_policy','import_maneuvers','maneuver_graph','state_graph','anchors','coverage_census']
LINEAGE='data/coarse-quality/us-osm-lineage-run-v1'
SOURCE='data/coarse-quality/us-osm-disk-capture-run-v1/extract/elements.jsonl'
GEOMETRY=['routing/xy.i32','routing/offsets.u32','routing/targets.u32','routing/meters.f64','geometry/xy.i32','geometry/offsets.u32','geometry/nodes.u32','provenance/edges.bin','provenance/vertices.u32','provenance/selected-nodes.u32','provenance/geometry-source-nodes.u32','provenance/alias-edge.i32','provenance/alias-prefix.f64','provenance/alias-suffix.f64']
GEOMETRY += [n+'.gz' for n in GEOMETRY[:7]]
SOURCES={SOURCE:'/inputs/captured.jsonl',**{LINEAGE+'/'+name:'/inputs/lineage/'+name for name in ['report.json','artifacts.json',*GEOMETRY]}}
HOST_CODE=['scripts/run_osm_stream_v1.py','scripts/coarse_osm_full_monitor_v1.py']
TESTS=26



def mounts(stage):
    return {**{'scripts/'+name+'.py':'/code/'+name+'.py' for name in CODE},
            **{'routing/'+name+'.py':'/reference/'+name+'.py' for name in REFERENCES},
            'data/coarse-quality/us-osm-tools-v3/prepare/runtime/libexpat.so.1':'/runtime/libexpat.so.1',**(SOURCES if stage=='run' else {})}


def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(root,name,value):(root/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='native_road_only_car_v1' and plan['image']==IMAGE and plan['output']==OUTPUTS[stage] and plan['caps']==CAPS,'Car exact phase/image/caps')
    require(plan['mounts']==mounts(stage) and set(plan['inputs'])==set(mounts(stage)) and set(plan['hostBindings'])==set(HOST_CODE),'Car exact input scope')
    require(plan['dataCaps']==DATA_CAPS and plan['policy']==POLICY and plan['tests']==TESTS,'Car exact policy/data caps/tests')
    require(plan['sourceSnapshotUtc']=='2026-10-25T21:21:21Z','Car snapshot')
    require(plan['retainedReservationBytes']==64500000000 and plan['overallEnvelopeBytes']==68719476736 and plan['retainedReservationBytes']+CAPS['ownedBytes']+CAPS['tmpBytes']<=plan['overallEnvelopeBytes'],'Car total reserve')
    if stage=='run':require(plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests']==TESTS and plan['lineageAdmission']['qualified'],'Car prior controls/lineage')


def worker(plan):
    from coarse_osm_car_graph_v1 import Graph,load_geometry,read_metadata
    from coarse_osm_car_payload_v1 import Payload,query_native
    root=Path('/work');timer=start_watchdog(CAPS['workerSeconds']);began=time.monotonic();written=0;roster={}
    def check():require(time.monotonic()-began<CAPS['workerSeconds'],'Car worker deadline')
    def emit(name,raw):
        nonlocal written
        check();path=root/name;require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.exists(),'Car fresh bounded artifact path')
        require(len(raw)<=CAPS['fileBytes'] and written+len(raw)<=CAPS['ownedBytes']-1048576,'Car file/owned output cap');path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
        written+=len(raw);roster[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    try:
        for name,path in mounts(plan['stage']).items():
            source=Path(path);limit=DATA_CAPS['inputBytes'] if path=='/inputs/captured.jsonl' else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==plan['inputs'][name],'Car worker input drift/type/size')
        memory=Path('/sys/fs/cgroup');require((memory/'memory.max').read_text().strip()==str(CAPS['memoryBytes']) and (memory/'memory.swap.max').read_text().strip()=='0','Car hard memory/swap')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Car tmp/file guards')
        if plan['stage']=='controls':
            import coarse_osm_car_v1_test as tests
            result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            save(root,'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)})
            require(result.wasSuccessful() and result.testsRun==TESTS and not result.skipped,'Car controls failed')
            raw,compact,geometry,metadata=tests.graphs(tests.fixture());pairs=[{'windowId':'synthetic','sourceNodeIds':[int(metadata['ids'][0]),int(metadata['ids'][-1])]}]
        else:
            from coarse_osm_bulk_pbf import stat_key
            source=Path('/inputs/captured.jsonl');before=stat_key(source);old=json.loads(Path('/inputs/lineage/report.json').read_bytes());artifacts=json.loads(Path('/inputs/lineage/artifacts.json').read_bytes())
            require(old['captureReceipt']['sha256']==plan['inputs'][SOURCE] and len(old['queries'])==41 and len({q['windowId'] for q in old['queries']})==21,'Car original queries/capture')
            geometry=load_geometry('/inputs/lineage',old,artifacts,check)
            with source.open('rb') as stream:metadata=read_metadata(stream,geometry,old['captureReceipt'],plan['sourceSnapshotUtc'],check)
            require(before==stat_key(source),'Car source stat drift');raw=Graph(geometry,metadata,raw=True,check=check);compact=Graph(geometry,metadata,check=check);pairs=old['queries']
        payload_report=compact.serialize(lambda name,data:emit('routing/'+name,data));payload=Payload(lambda name:(root/'routing'/name).read_bytes())
        # Decode every cost and reverse identity; per-pair route checks also use an independent array consumer.
        for i,arc in enumerate(compact.arcs):
            require(payload.cost_ms(i)==((arc['costMs']+124)//125)*125 and payload.reverse_arc(i)==arc['reverse'],'Car independent binary cost/reverse decode')
        mapping={int(identity):i for i,identity in enumerate(metadata['ids'])};queries=[];search_began=time.monotonic()
        for pair in pairs:
            for reverse in (False,True):
                native=list(reversed(pair['sourceNodeIds'])) if reverse else pair['sourceNodeIds'];a,b=(mapping[n] for n in native)
                results={}
                for label,graph,quantized in [('raw',raw,False),('contracted',compact,False),('quantized',compact,True)]:
                    start=time.monotonic();result=graph.query(a,b,quantized=quantized,check=check);results[label]=result|{'searchSeconds':time.monotonic()-start}
                exact=results['contracted'];quant=results['quantized'];binary=query_native(payload,compact,a,b,check)
                require(results['raw']['costMs']==exact['costMs'] and binary==quant['costMs'],'Car directed contraction/binary query mismatch')
                require(exact['costMs'] is None and quant['costMs'] is None or exact['costMs'] is not None and exact['costMs']<=quant['costMs']<=exact['costMs']+124*exact['fragments'],'Car finite cost/error bound')
                queries.append({'windowId':pair['windowId'],'sourceNodeIds':native,'reverseOfOriginal':reverse,'internalEndpoints':int(a not in compact.vertex)+int(b not in compact.vertex),**results,'binaryQuantizedMs':binary})
        report={'format':'native-road-only-car-prototype-v1','policy':POLICY,'captureReceipt':metadata['receipt'],'sourceMetadata':metadata['stats'],
                'selectedWays':len(metadata['ways']),'selectedNativeNodes':compact.nodes,'rawArcs':len(raw.arcs),'contractedArcs':len(compact.arcs),
                'payload':payload_report,'queries':queries,'queryChecksSeconds':time.monotonic()-search_began,
                'allNativePointAliases':sum(a is not None for a in compact.alias),'etaQualified':False,'nationalArtifactBuilt':False,'vercelQualified':False,'modelChanged':False}
        save(root,'report.json',report);save(root,'artifacts.json',roster)
        save(root,'result.json',{'status':'passed_captured_static_car_encoding','stage':plan['stage'],'reportSha256':sha(root/'report.json'),'artifactsSha256':sha(root/'artifacts.json'),'seconds':time.monotonic()-began,'outputBytesMetered':written,'modelChanged':False,'etaQualified':False})
        return 0
    except BaseException as error:
        save(root,'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],'sourceOrModelAdmitted':False});return 2
    finally:
        save(root,'metrics.json',{name:(Path('/sys/fs/cgroup')/name).read_text().strip() for name in ['memory.max','memory.swap.max','memory.peak','memory.events']})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def isolation(observed):
    host=observed['HostConfig'];expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':1000000000,'PidsLimit':32,'Tmpfs':{'/tmp':'rw,size=64m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Car observed isolation')
    require(not host.get('CapAdd') and {x.removeprefix('CAP_') for x in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Car capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Car readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Car file/core limits')


def driver(plan,recipe,pin):
    from run_osm_stream_v1 import cleanup as cleanup_owned
    from coarse_osm_full_monitor_v1 import owned_usage
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUTS[plan['stage']];require(not root.exists(),'Car fresh output required');root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-car-'+owner[:12];began=time.monotonic();identity=child=None;code=2
    save(root,'owner.json',{'label':owner,'name':name,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds']-10,'Car host deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<=CAPS['ownedBytes'],'Car owned allocation cap')
        disk=os.statvfs(root);require(disk.f_bavail*disk.f_frsize>=2147483648,'Car disk headroom')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin_input in (plan['inputs']|plan['hostBindings']).items():
            source=repo/name_input;limit=DATA_CAPS['inputBytes'] if name_input==SOURCE else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==pin_input,'Car host input drift/type/size')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
              '--memory=2g','--memory-swap=2g','--cpus=1','--pids-limit=32','--tmpfs','/tmp:rw,size=64m','--ulimit','core=0:0','--ulimit','fsize=134217728:134217728','--env','PYTHONPATH=/code:/reference','--env','LD_LIBRARY_PATH=/runtime']
        for source,destination in mounts(plan['stage']).items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_car_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed)
        save(root,'container-initial.json',{'Image':observed['Image'],'HostConfig':observed['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in observed['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.25)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Car worker failed/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'seconds':time.monotonic()-began,'networkRequests':0,'pbfOrNativeHelperReads':0,'stage':plan['stage'],'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Car recipe checksum');plan=json.loads(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe,args.sha256))

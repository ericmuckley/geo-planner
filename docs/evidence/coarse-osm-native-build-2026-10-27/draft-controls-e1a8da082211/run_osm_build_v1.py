"""Run one pinned artifact/compile/tiny-ABI stage with no road/sample mounts."""
import argparse
import ctypes
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

from coarse_osm_build_v1 import CAPS, LOCK, LOCK_SHA, GIB, acquire, prepare, load_lock, inventory, sha
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_native_lock_v1 import save
from coarse_osm_records import strict_json
from coarse_timing_input import require, start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import IMAGE, settle_error, cleanup_owned

OUTPUT = 'data/coarse-quality/us-osm-native-build-v1'
COMPILER = '/opt/rh/gcc-toolset-14/root/usr/bin/g++'
FLAGS = ['-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-static-libstdc++','-static-libgcc',
    '-pthread','-I/inputs/libosmium/include','-I/inputs/protozero/include','/work/smoke.cpp',
    '-Wl,-z,defs','-Wl,--exclude-libs,ALL','-lz','-o','/work/smoke.so']
ENV = {'PATH':'/opt/rh/gcc-toolset-14/root/usr/bin:/usr/bin:/bin','HOME':'/work','TMPDIR':'/tmp',
    'LANG':'C','LC_ALL':'C','LD_LIBRARY_PATH':'/opt/rh/gcc-toolset-14/root/usr/lib64:/opt/rh/gcc-toolset-14/root/usr/lib'}


def validate(plan):
    require(plan['phase']=='native_build_closure_v1' and plan['caps']==CAPS,'Build phase/caps drift')
    require(plan['imageId']==IMAGE and plan['imagePull']=='never' and plan['output']==OUTPUT,'Build image/output drift')
    require(plan['lock']=={'path':LOCK,'sha256':LOCK_SHA},'Build lock drift')
    require(plan['phases']=={'controls':'none','acquire':'bridge','prepare':'none','build':'none','abi':'none'},'Build phases drift')
    for name,destination in plan['mounts'].items():
        require(name.startswith('scripts/') and name.endswith(('.py','.cpp')) and '..' not in Path(name).parts or name==LOCK,'No road/sample/source mounts')
        require(destination.startswith(('/code/','/inputs/')) and plan['inputs'][name]==plan['workerFiles'][destination],'Build mount binding')
    require(plan['mounts'].get(LOCK)=='/inputs/lock.json','Build lock mount')
    require(plan['compiler']==COMPILER and plan['flags']==FLAGS and plan['compilerEnvironment']==ENV,'Build command drift')


def enter_builder(root):
    # Clear all capability sets after changing root. Docker also sets no-new-privileges.
    class Header(ctypes.Structure): _fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
    class Data(ctypes.Structure): _fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
    libc=ctypes.CDLL(None,use_errno=True);header=Header(0x20080522,0);data=(Data*2)()
    os.chroot(root);os.chdir('/work')
    require(libc.capset(ctypes.byref(header),ctypes.byref(data))==0,'Clear builder capabilities')
    require(libc.capget(ctypes.byref(header),ctypes.byref(data))==0 and all(not d.effective and not d.permitted and not d.inheritable for d in data),'Builder capabilities remain')


def confined_command(args):
    """Only this subprocess changes root; no outside descriptors, no retained privileges."""
    require(args and args[0] in (COMPILER,'/usr/bin/readelf'),'Unlisted builder executable')
    enter_builder('/builder')
    resource.setrlimit(resource.RLIMIT_FSIZE,(33554432,33554432))
    os.execve(args[0],args,ENV)


def tool(root,name,args,check):
    log=root/(name+'.log')
    with log.open('xb') as stream:
        child=subprocess.Popen([sys.executable,'-B','/code/run_osm_build_v1.py','--confined',*args],stdout=stream,stderr=subprocess.STDOUT)
        began=time.monotonic()
        try:
            while child.poll() is None:
                check(); require(time.monotonic()-began<120 and log.stat().st_size<=1048576,'Compiler time/log cap');time.sleep(.1)
        finally:
            if child.poll() is None: child.kill()
            child.wait(timeout=5)
    require(log.stat().st_size<=1048576 and child.returncode==0,'Pinned compiler/tool refusal: '+name)
    return log.read_text()


def build(root,check):
    root=Path(root);root.chmod(0o777)
    shutil.copyfile('/code/coarse_osm_build_smoke_v1.cpp',root/'smoke.cpp')
    versions=tool(root,'compiler-version',[COMPILER,'--version'],check)
    require('14.' in versions,'Pinned compiler version family')
    tool(root,'compile',[COMPILER,*FLAGS],check)
    artifact=root/'smoke.so';require(artifact.is_file() and artifact.stat().st_size<GIB-CAPS['tmpBytes'],'Build output cap')
    elf=tool(root,'elf',['/usr/bin/readelf','-h','-d','-V','-Ws','/work/smoke.so'],check)
    import re
    needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',elf)
    require(needed and set(needed)<={'libz.so.1','libm.so.6','libc.so.6','libpthread.so.0','libdl.so.2','librt.so.1','ld-linux-aarch64.so.1'},'Unqualified target library dependency')
    require('AArch64' in elf and 'gp_pbf_counts' in elf and 'GLIBCXX_' not in elf,'Artifact machine/export/static runtime')
    save(root/'result.json',{'status':'compiled_target_abi_unqualified','artifactSha256':sha(artifact),'artifactBytes':artifact.stat().st_size,
        'compiler':COMPILER,'flags':FLAGS,'needed':needed,'elfReceiptSha256':sha(root/'elf.log'),
        'scope':'Minimal PBF/C ABI fixture only; no native importer implementation or road data read.'})
    return 0


def qualify(root,check):
    import osmium
    from coarse_osm_native_smoke import fixture_records, write_xml, STATE
    root=Path(root);rows=fixture_records();xml=root/'fixture.osm';pbf=root/'fixture.osm.pbf'
    write_xml(xml,rows)
    header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
    with osmium.SimpleWriter(str(pbf),bufsz=65536,header=header) as writer:
        for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
    artifact=Path('/artifacts/smoke.so')
    prior=strict_json(Path('/artifacts/result.json').read_bytes())
    require(sha(artifact)==prior['artifactSha256'],'Compiled artifact drift')
    library=ctypes.CDLL(str(artifact))
    call=library.gp_pbf_counts;call.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_int64)];call.restype=ctypes.c_int
    values=(ctypes.c_int64*5)();check()
    require(call(os.fsencode(pbf),values)==0 and list(values)==[4,3,2,-10000000,5000000],'Target tiny PBF decode/coordinates')
    negatives={ 'truncated':pbf.read_bytes()[:-1], 'invalid':b'not a PBF', 'empty':b'' }
    for name,body in negatives.items():
        path=root/(name+'.pbf');path.write_bytes(body)
        require(call(os.fsencode(path),values)<0,'Target invalid PBF accepted: '+name)
    require(call(None,values)==-2,'Target null ABI input accepted')
    zlib_versions={}
    for name in ('gp_zlib_runtime','gp_zlib_header'):
        func=getattr(library,name);func.argtypes=[];func.restype=ctypes.c_char_p;zlib_versions[name]=func().decode('ascii')
    save(root/'result.json',{'status':'tiny_compiler_pbf_abi_qualified','artifactSha256':sha(artifact),'fixtureBytes':pbf.stat().st_size,
        'fixtureCounts':[4,3,2],'firstNodeXY':[-10000000,5000000],'negativePbfCases':list(negatives),'nullRejected':True,
        'zlibVersions':zlib_versions,'compilerAbiQualifiedForTinyFixtureOnly':True,'nativeImporterQualified':False,
        'sourceOrSavedSampleReads':0,'fullImportAdmitted':False})
    return 0


def worker(plan,root,phase):
    root=Path(root);watchdog=start_watchdog(CAPS['workSeconds'])
    began=time.monotonic()
    def check():
        require(time.monotonic()-began<CAPS['workSeconds'],'Build worker deadline')
        if phase in ('build','abi'):
            total=sum(p.lstat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())
            require(total<GIB-CAPS['tmpBytes']-16777216,'Build/ABI scratch cap')
    try:
        verify_worker_inputs(plan)
        tmp='/builder/tmp' if phase=='build' else '/tmp'
        disk=os.statvfs(tmp);require(disk.f_blocks*disk.f_frsize==CAPS['tmpBytes'],'Build tmp guard')
        require(resource.getrlimit(resource.RLIMIT_FSIZE)==(GIB,GIB),'Build file guard')
        save(root/'resource-guards.json',{'memory':memory_guard(),'tmpBytes':CAPS['tmpBytes'],'fileBytes':GIB,'phase':phase,
            'sysChrootCapability':phase in ('controls','build'),'watchdogSeconds':CAPS['workSeconds']})
        lock=load_lock('/inputs/lock.json')
        if phase=='controls':
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in ('coarse_osm_native_lock_v1_test','coarse_osm_native_lock_v2_test','coarse_osm_build_v1_test'))
            result=unittest.TextTestRunner().run(suite)
            save(root/'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)})
            return 0 if result.wasSuccessful() and not result.skipped else 2
        if phase=='acquire':return acquire(root,lock)
        if phase=='prepare':return prepare(root,'/downloads',lock,check)
        if phase=='build':return build(root,check)
        return qualify(root,check)
    except Exception as error:
        save(root/'worker-failure.json',{'status':'stopped','phase':phase,'errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
        return 2
    finally:
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def isolation(observed,network,phase):
    expected={'NetworkMode':network,'Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,
        'Tmpfs':{('/builder/tmp' if phase=='build' else '/tmp'):'rw,size=256m'}}
    require(observed['Image']==IMAGE and all(observed['HostConfig'][k]==v for k,v in expected.items()),'Build isolation drift')
    allowed={'/work','/builder/work'} if phase=='build' else {'/work'}
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] not in allowed),'Build writable input')
    require({c.removeprefix('CAP_') for c in observed['HostConfig'].get('CapAdd') or []}==({'SYS_CHROOT'} if phase in ('controls','build') else set()),'Build capabilities drift')
    require({c.removeprefix('CAP_') for c in observed['HostConfig'].get('CapDrop') or []}=={'ALL'},'Build dropped capabilities drift')
    require('no-new-privileges' in observed['HostConfig']['SecurityOpt'],'Build no-new-privileges drift')
    require({u['Name']:(u['Soft'],u['Hard']) for u in observed['HostConfig']['Ulimits']}=={'core':(0,0),'fsize':(GIB,GIB)},'Build ulimits drift')


def driver(recipe,expected,output):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==expected,'Build recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan)
    root=(repo/output).resolve();require(root==repo/OUTPUT and not root.exists(),'Build output must be fresh/exact')
    root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();deadline=began+CAPS['workSeconds'];hard=began+CAPS['hostSeconds'];owner=uuid.uuid4().hex
    save(root/'owner.json',{'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'})
    codes={};success=False;last_scan=0
    def check():
        nonlocal last_scan
        require(time.monotonic()<deadline,'Build shared host deadline')
        require(shutil.disk_usage(root).free>=2147483648,'Build disk headroom')
        # Rootfs writes are bounded by cumulative expanded tar bytes plus reserve in-worker.
        # Phase-boundary inventories measure actual allocation; scratch/logs are monitored.
        if time.monotonic()-last_scan>1:
            for phase in ('controls','build','abi'):
                p=root/phase
                if p.exists():
                    size=sum(x.lstat().st_size for x in p.rglob('*') if x.is_file() and not x.is_symlink())
                    require(size<GIB-CAPS['tmpBytes'],'Build phase storage cap')
            last_scan=time.monotonic()
    def call(args,**kwargs):
        check();return subprocess.run(args,capture_output=True,text=True,timeout=min(15,max(.01,deadline-time.monotonic())),**kwargs)
    def run_phase(phase):
        p=root/phase;p.mkdir();name='geo-planner-native-build-v1-'+phase+'-'+owner[:12];identity=child=None
        save(p/'owner.json',{'name':name,'label':owner});network=plan['phases'][phase]
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network='+network,
            '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64',
            '--ulimit','core=0:0','--ulimit',f'fsize={GIB}:{GIB}','--tmpfs',('/builder/tmp' if phase=='build' else '/tmp')+':rw,size=256m',
            '--env','LD_LIBRARY_PATH=/tools/runtime']
        if phase in ('controls','build'):args+=['--cap-add=SYS_CHROOT']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["site"]},dst=/tools/site,readonly']
        for filename,source in plan['runtime'].items():args+=['--mount',f'type=bind,src={repo/source},dst=/tools/runtime/{filename},readonly']
        if phase=='prepare':args+=['--mount',f'type=bind,src={root/"acquire"},dst=/downloads,readonly']
        if phase=='build':
            args+=['--mount',f'type=bind,src={root/"prepare/rootfs"},dst=/builder,readonly','--mount',f'type=bind,src={p},dst=/builder/work']
            for index,namepart in ((1,'libosmium'),(2,'protozero')):args+=['--mount',f'type=bind,src={root/"prepare"/f"source-{index}"},dst=/builder/inputs/{namepart},readonly']
        if phase=='abi':args+=['--mount',f'type=bind,src={root/"build"},dst=/artifacts,readonly']
        args+=['--mount',f'type=bind,src={p},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_build_v1.py','/inputs/recipe.json',expected,'/work','--worker','--phase',phase]
        try:
            identity=call(args,check=True).stdout.strip();require(len(identity)==64,'Build owned container ID')
            observed=json.loads(call(['docker','inspect',identity],check=True).stdout)[0];isolation(observed,network,phase)
            save(p/'container-initial.json',{'Image':observed['Image'],'HostConfig':observed['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in observed['Mounts']]})
            with (p/'worker.log').open('xb') as log:
                child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    check();require((p/'worker.log').stat().st_size<=CAPS['reportBytes'],'Build worker log cap');time.sleep(.25)
            final=json.loads(call(['docker','inspect',identity],check=True).stdout)[0]
            save(p/'container-result.json',{'State':final['State'],'clientExitCode':child.returncode,'Image':final['Image']})
            require(final['State']['ExitCode']==child.returncode and not final['State']['OOMKilled'],'Build worker exit/OOM')
            return child.returncode
        finally:
            if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
            def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(15,hard-time.monotonic())))
            try:
                if not (p/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,p,child.returncode if child is not None else None)
            finally:cleanup_owned(cleanup_call,identity,name,owner,IMAGE,p)
    try:
        for name,pin in plan['inputs'].items():check();require(sha(repo/name)==pin,'Build input drift: '+name)
        observed=capacity(repo)
        require(observed['hostDiskAvailableBytes']>=16*GIB and observed['hostMemoryBytes']>=8*GIB and observed['dockerMemoryBytes']>=6*GIB,'Build starting capacity')
        save(root/'capacity-at-start.json',observed)
        for phase in ('controls','acquire','prepare','build','abi'):
            codes[phase]=run_phase(phase);require(codes[phase]==0,'Build phase stopped: '+phase)
            if phase in ('acquire','prepare'):
                ceiling=3*GIB if phase=='acquire' else 11*GIB
                measured=inventory(root/phase,check);save(root/(phase+'-storage.json'),measured)
                require(measured['conservativeBytesWithNamespaceReserve']<=ceiling,'Build phase allocation cap')
        success=True
    except (Exception,KeyboardInterrupt) as error:
        save(root/'driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
    require(time.monotonic()-began<CAPS['hostSeconds'],'Build final host deadline')
    save(root/'run-summary.json',{'status':'tiny_compiler_pbf_abi_qualified' if success else 'stopped','phaseClientExitCodes':codes,
        'hostSecondsIncludingInputsStartupAllPhasesStorageAuditsCleanup':time.monotonic()-began,'newDockerImageStoreBytes':0,
        'ownedBuilderImageCreated':False,'roadOrSavedSampleReads':0,'nativeImporterQualified':False,'fullImportAdmitted':False,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--confined':confined_command(sys.argv[2:]);raise SystemExit(2)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output')
    parser.add_argument('--worker',action='store_true');parser.add_argument('--phase',choices=['controls','acquire','prepare','build','abi'])
    args=parser.parse_args()
    if args.worker:
        require(args.phase is not None and sha(args.recipe)==args.sha256,'Build worker recipe hash');plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
        sys.path.insert(0,'/tools/site');raise SystemExit(worker(plan,args.output,args.phase))
    raise SystemExit(driver(args.recipe,args.sha256,args.output))

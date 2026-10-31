import hashlib,json
from pathlib import Path
import subprocess,sys,uuid
repo=Path('/Users/eric/Documents/GitHub/geo-planner');sys.path.insert(0,str(repo/'scripts'))
from prepare_osm_native_lock_v1 import IMAGE, settle_error, cleanup_owned
from run_osm_build_v1 import isolation
from coarse_osm_native_lock_v1 import save
owner=uuid.uuid4().hex;root=Path('/tmp')/('geo-planner-native-build-v1-controls-'+owner[:12]);root.mkdir()
name='geo-planner-native-build-v1-precontrols-'+owner[:12];identity=None
call=lambda args:subprocess.run(args,capture_output=True,text=True,timeout=15)
save(root/'bindings.json',{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for pattern in ('*native_lock_v*.py','*osm*build_v1*.py','coarse_osm_build_smoke_v1.cpp') for p in sorted((repo/'scripts').glob(pattern))})
try:
 args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--cap-add=SYS_CHROOT','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=1073741824:1073741824','--tmpfs=/tmp:rw,size=256m','--mount',f'type=bind,src={repo/"scripts"},dst=/code,readonly','--entrypoint=python3',IMAGE,'-B','-m','unittest','coarse_osm_native_lock_v1_test','coarse_osm_native_lock_v2_test','coarse_osm_build_v1_test']
 # unittest module imports need the read-only code directory on PYTHONPATH.
 args[args.index('--entrypoint=python3'):args.index('--entrypoint=python3')]=['--env','PYTHONPATH=/code']
 created=call(args);created.check_returncode();identity=created.stdout.strip()
 initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,'none','controls')
 save(root/'initial.json',{'Id':identity,'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':initial['Mounts']})
 result=subprocess.run(['docker','start','-a',identity],capture_output=True,text=True,timeout=60)
 (root/'worker.log').write_text(result.stdout+result.stderr)
 final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root/'container-result.json',{'State':final['State'],'clientExitCode':result.returncode})
 assert result.returncode==final['State']['ExitCode']==0 and not final['State']['OOMKilled'],result.stdout+result.stderr
 assert 'Ran 40 tests' in result.stdout+result.stderr and 'OK' in result.stdout+result.stderr and 'skipped' not in result.stdout+result.stderr
finally:
 if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,None)
 cleanup_owned(call,identity,name,owner,IMAGE,root)
 absent=call(['docker','inspect',identity or name]);assert absent.returncode==1 and 'No such' in absent.stderr
 save(root/'independent-absence.json',{'ownedContainer':identity,'exitCode':absent.returncode,'independentInspectAbsent':True})
print(json.dumps({'root':str(root),'tests':40,'successful':True,'noSkips':True,'network':'none','ownedRemovedAndIndependentlyAbsent':True}))

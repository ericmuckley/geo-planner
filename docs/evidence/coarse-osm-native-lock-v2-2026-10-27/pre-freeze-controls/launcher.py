import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

repo=Path('/Users/eric/Documents/GitHub/geo-planner')
sys.path.insert(0,str(repo/'scripts'))
from prepare_osm_native_lock_v1 import IMAGE, check_isolation, settle_error, cleanup_owned
from coarse_osm_native_lock_v1 import save
owner=uuid.uuid4().hex
root=Path('/tmp')/('geo-planner-native-lock-v2-controls-'+owner[:12]); root.mkdir()
name='geo-planner-native-lock-v2-precontrols-'+owner[:12]
identity=None
call=lambda args:subprocess.run(args,capture_output=True,text=True,timeout=15)
save(root/'bindings.json',{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((repo/'scripts').glob('*native_lock_v*.py'))})
try:
    args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--tmpfs=/tmp:rw,size=256m','--mount',f'type=bind,src={repo / "scripts"},dst=/code,readonly','--entrypoint=python3',IMAGE,'-B','-m','unittest','discover','-s','/code','-p','coarse_osm_native_lock_v?_test.py']
    created=call(args); created.check_returncode(); identity=created.stdout.strip()
    initial=json.loads(call(['docker','inspect',identity]).stdout)[0]; check_isolation(initial,'none')
    save(root/'initial.json',{'Id':identity,'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':initial['Mounts']})
    result=subprocess.run(['docker','start','-a',identity],capture_output=True,text=True,timeout=60)
    (root/'worker.log').write_text(result.stdout+result.stderr)
    final=json.loads(call(['docker','inspect',identity]).stdout)[0]
    save(root/'container-result.json',{'State':final['State'],'clientExitCode':result.returncode})
    assert result.returncode==final['State']['ExitCode']==0 and not final['State']['OOMKilled']
    assert 'Ran 27 tests' in (result.stdout+result.stderr) and 'OK' in (result.stdout+result.stderr)
finally:
    if not (root/'container-result.json').exists(): settle_error(call,identity,name,owner,root,None)
    cleanup_owned(call,identity,name,owner,IMAGE,root)
    absent=call(['docker','inspect',identity or name]); assert absent.returncode==1 and 'No such' in absent.stderr
    save(root/'independent-absence.json',{'ownedContainer':identity,'exitCode':absent.returncode,'independentInspectAbsent':True})
print(json.dumps({'root':str(root),'tests':27,'successful':True,'noSkips':True,'network':'none','ownedRemovedAndIndependentlyAbsent':True}))

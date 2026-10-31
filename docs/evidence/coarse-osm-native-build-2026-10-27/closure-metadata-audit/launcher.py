import json,subprocess,sys,uuid
from pathlib import Path
repo=Path('/Users/eric/Documents/GitHub/geo-planner');sys.path[:0]=[str(repo/'scripts'),str(repo/'docs/evidence/coarse-osm-native-build-2026-10-27')]
from prepare_osm_native_lock_v1 import IMAGE,cleanup_owned,settle_error
from run_osm_build_v1 import isolation
from coarse_osm_native_lock_v1 import save
from asset_proof import snapshot
folder=repo/'docs/evidence/coarse-osm-native-build-2026-10-27';root=repo/'data/coarse-quality/us-osm-native-build-v1/prepare/rootfs'
probe=folder/'closure-metadata-audit';probe.mkdir()
portable,metadata=snapshot(root,True)
host=Path('/tmp')/('geo-planner-closed-rootfs-metadata-'+uuid.uuid4().hex+'.json');host.write_text(json.dumps(metadata))
save(probe/'host-portable.json',portable)
owner=uuid.uuid4().hex;name='geo-planner-native-build-metadata-'+owner[:12];identity=None
code='''import json,sys
from pathlib import Path
sys.path.insert(0,"/proof")
from asset_proof import snapshot
value,rows=snapshot("/rootfs",True)
host=json.loads(Path("/host.json").read_text());assert set(host)==set(rows)
differences=[];fields=set()
for path,row in rows.items():
 if row!=host[path]:
  changed=[k for k in row if row[k]!=host[path][k]]
  fields.update(changed)
  assert row["kind"]=="directory" and changed==["size"],(path,row,host[path])
  if len(differences)<8:differences.append({"path":path,"linux":row,"host":host[path]})
print(json.dumps({"portable":value,"differentFields":sorted(fields),"differenceSamples":differences,"allDifferencesAreDirectorySizeOnly":True}))'''
(probe/'code.txt').write_text(code)
call=lambda args:subprocess.run(args,capture_output=True,text=True,timeout=15)
try:
 args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=1073741824:1073741824','--tmpfs=/tmp:rw,size=256m','--mount',f'type=bind,src={root},dst=/rootfs,readonly','--mount',f'type=bind,src={folder/"asset_proof.py"},dst=/proof/asset_proof.py,readonly','--mount',f'type=bind,src={host},dst=/host.json,readonly','--entrypoint=python3',IMAGE,'-B','-c',code]
 created=call(args);created.check_returncode();identity=created.stdout.strip()
 initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,'none','prepare')
 save(probe/'initial.json',{'Id':identity,'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':initial['Mounts']})
 result=subprocess.run(['docker','start','-a',identity],capture_output=True,text=True,timeout=90)
 (probe/'stdout.json').write_text(result.stdout);(probe/'stderr.log').write_text(result.stderr)
 final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(probe/'container-result.json',{'State':final['State'],'clientExitCode':result.returncode})
 assert result.returncode==final['State']['ExitCode']==0 and not final['State']['OOMKilled'],result.stderr
 observed=json.loads(result.stdout);assert observed['portable']==portable
 save(probe/'comparison.json',{'portableHostAndLinuxEqual':True,'allDifferencesAreDirectorySizeOnly':True,'portable':portable})
finally:
 if not (probe/'container-result.json').exists():settle_error(call,identity,name,owner,probe,None)
 cleanup_owned(call,identity,name,owner,IMAGE,probe)
 absent=call(['docker','inspect',identity or name]);assert absent.returncode==1 and 'No such' in absent.stderr
 save(probe/'independent-absence.json',{'ownedContainer':identity,'exitCode':absent.returncode,'independentInspectAbsent':True})
print(json.dumps({'portableHostLinuxEqual':True,'differentFields':observed['differentFields'],'samples':observed['differenceSamples']}))

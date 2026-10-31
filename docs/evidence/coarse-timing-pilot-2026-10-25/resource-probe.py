"""Prove memory enforcement with cached, network-free disposable containers."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

root = Path(__file__).resolve().parent
plan = json.loads((root / 'resource-plan.json').read_text())
assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == plan['scriptSha256']
image = plan['containerImageId']
records = []
for size in ['64m', '1g']:
    name = 'geo-planner-timing-probe-' + uuid.uuid4().hex[:12]
    code = '''import json,pathlib,subprocess,sys
p=pathlib.Path('/sys/fs/cgroup')
r={'memoryMaxBytes':int((p/'memory.max').read_text()),'swapMaxBytes':int((p/'memory.swap.max').read_text())}
print(json.dumps(r),flush=True)
if sys.argv[1]=='64m':
 child=subprocess.run([sys.executable,'-B','-c','x=bytearray(128*1024**2)'])
 r.update(childReturnCode=child.returncode,memoryEvents=(p/'memory.events').read_text())
 print(json.dumps(r),flush=True)
'''
    identity = None
    try:
        created = subprocess.run(['docker','create','--pull=never','--init','--network=none','--name',name,
            '--label','geo-planner.timing-resource-probe=true','--read-only','--cap-drop=ALL',
            '--security-opt=no-new-privileges','--memory='+size,'--memory-swap='+size,'--pids-limit=32',
            '--entrypoint=python3',image,'-B','-c',code,size],capture_output=True,text=True,check=True,timeout=20)
        identity = created.stdout.strip()
        assert len(identity)==64
        ran = subprocess.run(['docker','start','-a',identity],capture_output=True,text=True,timeout=20)
        inspected = json.loads(subprocess.run(['docker','inspect',identity],capture_output=True,text=True,check=True,timeout=20).stdout)[0]
        lines = [json.loads(line) for line in ran.stdout.splitlines() if line.startswith('{')]
        assert lines and lines[0]['swapMaxBytes']==0
        expected = 64*1024**2 if size=='64m' else 1024**3
        assert lines[0]['memoryMaxBytes']==expected
        if size=='64m':
            events = dict(line.split() for line in lines[-1].get('memoryEvents','').splitlines())
            assert inspected['State']['OOMKilled'] or (lines[-1].get('childReturnCode')==-9 and int(events.get('oom_kill',0))>=1)
        else:
            assert ran.returncode==0
        records.append({'size':size,'workerReturnCode':ran.returncode,'kernel':lines,
                        'oomKilled':inspected['State']['OOMKilled'],
                        'networkMode':inspected['HostConfig']['NetworkMode'],
                        'memory':inspected['HostConfig']['Memory'],'memorySwap':inspected['HostConfig']['MemorySwap']})
    finally:
        if identity:
            subprocess.run(['docker','rm','-f',identity],capture_output=True,timeout=20)
result={'containerImageId':image,'hardMemoryGuardProven':True,'records':records,
        'sourceOrToolDownloads':0,'network':'none','scope':'Kernel memory/swap enforcement only, not application/cloud memory or routing performance.'}
with (root/'resource-proof.json').open('x') as stream:
    stream.write(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

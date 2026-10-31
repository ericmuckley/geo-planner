"""Saved prefix controls and preserved missing-mount stop; no native/large inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
REPORT=Path(__file__).resolve().parent


def load(path):return json.loads(path.read_bytes())


def closed(stage,version):
    record=load(REPORT/f'prefix-closed-{stage}-{version}.json')
    mirror=REPORT/f'prefix-raw/{stage}-{version}'
    assert {str(p.relative_to(mirror)) for p in mirror.rglob('*') if p.is_file()}==set(record['roster'])
    for name,pin in record['roster'].items():
        raw=(mirror/name).read_bytes();assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256']
    absence=load(REPORT/f'prefix-cleanup-{stage}-{version}.json')
    assert absence['independentlyAbsent'] and absence['queryReturnCode']==0 and absence['containerIds']==[]
    freeze=load(REPORT/f'prefix-freeze-{stage}-{version}.json');plan=load(REPORT/f'prefix-plan-{stage}-{version}.json')
    assert hashlib.sha256((ROOT/freeze['recipe']).read_bytes()).hexdigest()==freeze['sha256']
    assert (mirror/'execution-plan.json').read_bytes()==(ROOT/freeze['recipe']).read_bytes()
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','docs/evidence/')):assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==pin,name
    initial=load(mirror/'container-initial.json');host=initial['HostConfig']
    assert host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==4294967296
    assert host['ReadonlyRootfs'] and host['PidsLimit']==64 and host['NanoCpus']==2000000000
    assert all(not m['RW'] for m in initial['Mounts'] if m['Destination']!='/work')
    assert not any(m['Destination'] in ('/source.pbf','/fine-index') for m in initial['Mounts'])
    assert load(mirror/'cleanup.json')['removed']
    return plan,mirror


def main():
    subprocess.run([sys.executable,'-B',str(REPORT/'verify_qualification_v13.py')],check=True,stdout=subprocess.DEVNULL)
    _,failed=closed('controls','v1')
    assert 'ModuleNotFoundError' in (failed/'worker.log').read_text() and 'coarse_osm_full_monitor_v1' in (failed/'worker.log').read_text()
    assert not (failed/'result.json').exists()
    plan,good=closed('controls','v2')
    result=load(good/'result.json');tests=load(good/'controls.json');part=load(good/'part-0000.json')
    assert tests=={'tests':8,'successful':True,'skips':0}
    assert result['status']=='passed_prefix_conversion' and result['inputUnchanged']
    assert (result['totals']['rows'],result['totals']['blocks'],result['totals']['oldBytes'],result['totals']['newBytes'])==(4,1,83,86)
    assert result['codecRows']==8 and result['codecCalls']==2
    assert part['oldSha256']=='7ceff1f5ce2668398f3848e9e7f9094bafbb5d2653eb0eaea9f0ab38cd89d86e'
    assert part['convertedSha256']=='324f4f26161b2647d85dc5bc5af94365b32337c6c434d89de874fc443611634d'
    assert part['everyIdAndCellNativeRoundtrip'] and plan['retainedBytes']==55406628967
    state=load(good/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    assert not result['nationalSourceRead'] and not result['fullFineIndexRead'] and not result['completeBankCapacityQualified'] and not result['modelChanged']
    print(json.dumps({'prefixControllerQualified':True,'linuxTests':8,'skips':0,'preservedV1MountFailure':True,'tinyConversionExact':True,'workersAbsent':True}))


if __name__=='__main__':main()

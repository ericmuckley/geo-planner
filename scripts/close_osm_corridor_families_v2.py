"""Close the saved candidate-topology diagnostic without rerunning it."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from coarse_osm_full_monitor_v1 import owned_usage
from coarse_osm_bulk_pbf import stat_key
from coarse_timing_input import require


def main():
    repo=Path(__file__).resolve().parents[1];report=repo/'docs/evidence/coarse-osm-extraction-2026-10-30';root=repo/'data/coarse-quality/us-osm-corridor-families-v1';mirror=report/'corridor-family-raw-v2'
    closed=report/'corridor-family-closed-v2.json';absence=report/'corridor-family-cleanup-v2.json';require(not any(p.exists() for p in (mirror,closed,absence)),'Fresh topology closure')
    load=lambda p:json.loads(p.read_bytes());plan=report/'corridor-family-plan-v1.json';pin=hashlib.sha256(plan.read_bytes()).hexdigest()
    state=load(root/'state.json');result=load(root/'container-result.json');require(state['status']=='diagnostic_complete_source_incomplete' and result['State']['ExitCode']==0 and not result['State']['OOMKilled'] and load(root/'cleanup.json')['removed'],'Terminal topology result/owned cleanup')
    query=subprocess.run(['docker','ps','-aq','--filter','label=geo-planner.offline-plan='+pin],capture_output=True,text=True,check=True,timeout=15);require(not query.stdout.strip(),'Topology worker remains')
    mirror.mkdir();roster={}
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        before=stat_key(path);size=path.stat().st_size;name=str(path.relative_to(root))
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        require(before==stat_key(path),'Topology output drift');ignored=size>1048576;roster[name]={'bytes':size,'sha256':digest,'ignoredLargeAsset':ignored}
        if not ignored:
            dest=mirror/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    record={'root':str(root.relative_to(repo)),'roster':roster,'files':len(roster),'bytes':sum(r['bytes'] for r in roster.values()),'usage':owned_usage(root),'closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for path,value in [(closed,record),(absence,{'recipeSha256':pin,'independentlyAbsent':True,'queryReturnCode':query.returncode,'containerIds':[]})]:
        with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({k:record[k] for k in ('files','bytes','usage')}|{'workerAbsent':True}))


if __name__=='__main__':main()

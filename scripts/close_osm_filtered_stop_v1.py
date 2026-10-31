"""Close the selected-element cap stop without promoting incomplete data."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_timing_input import require
from run_osm_filtered_capture_v1 import OUTPUTS,REPORT


def main():
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUTS['run'];report=repo/REPORT
    closed=report/'filtered-capture-closed-run-v1.json';absence=report/'filtered-capture-cleanup-run-v1.json';mirror=report/'filtered-capture-raw/run-v1'
    require(not closed.exists() and not absence.exists() and not mirror.exists(),'Census new closure required')
    load=lambda name:json.loads((root/name).read_bytes())
    require(load('run-summary.json')['status']=='stopped','Capture stopped host result required')
    failure=load('worker-failure.json')
    require(failure['error']=='Full extraction stopped: Selected unique element cap' and not failure['rawAcquiredFileCaptureComplete'],'Capture exact cap stop required')
    require(not (root/'result.json').exists() and not failure['lastNativeReceipt']['nativeEof'],'Capture incomplete result required')
    state=load('container-result.json');require(state['State']['ExitCode']==state['clientExitCode']==2 and not state['State']['OOMKilled'],'Capture clean failed exit required')
    require(load('cleanup.json')['removed'] and load('cleanup.json')['independentInspectAbsent'],'Census owned cleanup required')
    owner=load('owner.json')
    query=subprocess.run(['docker','ps','-aq','--filter','label=geo-planner.stream-owner='+owner['label']],capture_output=True,text=True,check=True,timeout=15)
    require(not query.stdout.strip(),'Census owned worker still present')
    usage=owned_usage(root);mirror.mkdir(parents=True);roster={}
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        before=stat_key(path);name=str(path.relative_to(root))
        with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        require(stat_key(path)==before,'Census closed file drift')
        ignored=path.suffix=='.bin' and path.stem.isdigit()
        roster[name]={'bytes':path.stat().st_size,'sha256':pin,'ignoredPart':ignored}
        if not ignored:
            dest=mirror/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
            with dest.open('rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==pin,'Census mirror drift')
    record={'root':OUTPUTS['run'],'roster':roster,'usage':usage,'files':len(roster),'bytes':sum(r['bytes'] for r in roster.values()),
            'closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with closed.open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
    with absence.open('x') as stream:json.dump({'owner':owner,'queryReturnCode':query.returncode,'containerIds':[],'independentlyAbsent':True},stream,indent=2);stream.write('\n')
    print(json.dumps({'files':len(roster),'bytes':record['bytes'],'ignoredParts':sum(r['ignoredPart'] for r in roster.values()),'workerAbsent':True}))


if __name__=='__main__':main()

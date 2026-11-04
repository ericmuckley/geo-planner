"""Close the national disk capture, retaining SQLite journals without duplicate copies."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_timing_input import require
from run_osm_disk_capture_v1 import OUTPUTS,REPORT


def close(stage):
    require(stage=='run','National capture closure only')
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUTS[stage];report=repo/REPORT
    mirror=report/('disk-capture-raw/'+stage+'-v1');closed=report/('disk-capture-closed-'+stage+'-v1.json');absence=report/('disk-capture-cleanup-'+stage+'-v1.json')
    require(not mirror.exists() and not closed.exists() and not absence.exists(),'Fresh disk capture closure')
    load=lambda name:json.loads((root/name).read_bytes())
    require(load('run-summary.json')['status'] in ('passed_full_road_capture','stopped'),'Terminal capture summary')
    require(load('cleanup.json')['removed'] and load('cleanup.json')['independentInspectAbsent'],'Disk capture owned cleanup')
    owner=load('owner.json');query=subprocess.run(['docker','ps','-aq','--filter','label=geo-planner.stream-owner='+owner['label']],capture_output=True,text=True,check=True,timeout=15)
    require(not query.stdout.strip(),'Disk capture owned worker remains')
    usage=owned_usage(root);mirror.mkdir(parents=True);roster={}
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        before=stat_key(path);name=str(path.relative_to(root))
        with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        require(before==stat_key(path),'Disk capture closed file drift')
        ignored=stage=='run' and ((path.suffix=='.bin' and path.stem.isdigit()) or path.name.startswith(('primary-selected.sqlite','audit-selected.sqlite')) or path.name=='elements.jsonl')
        roster[name]={'bytes':path.stat().st_size,'sha256':pin,'ignoredLargeAsset':ignored}
        if not ignored:
            dest=mirror/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    def save(path,value):
        with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    record={'root':OUTPUTS[stage],'roster':roster,'usage':usage,'files':len(roster),'bytes':sum(row['bytes'] for row in roster.values()),'closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save(closed,record);save(absence,{'owner':owner,'independentlyAbsent':True,'queryReturnCode':query.returncode,'containerIds':[]})
    print(json.dumps({'files':record['files'],'bytes':record['bytes'],'usage':usage,'workerAbsent':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['run']);close(parser.parse_args().stage)

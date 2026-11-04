"""Close one native geometry matcher stage without rerunning it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_timing_input import require
from run_osm_continuous_match_v1 import OUTPUTS
REPORT='docs/evidence/coarse-osm-extraction-2026-10-30'


def close(stage):
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUTS[stage];report=repo/REPORT
    mirror=report/('continuous-match-raw/'+stage+'-v1');closed=report/('continuous-match-closed-'+stage+'-v1.json');absence=report/('continuous-match-cleanup-'+stage+'-v1.json')
    require(not mirror.exists() and not closed.exists() and not absence.exists(),'Fresh opportunity closure')
    load=lambda name:json.loads((root/name).read_bytes())
    require(load('run-summary.json')['exitCode'] in (0,2),'Terminal capture summary')
    require(load('cleanup.json')['removed'] and load('cleanup.json')['independentInspectAbsent'],'Opportunity owned cleanup')
    owner=load('owner.json');query=subprocess.run(['docker','ps','-aq','--filter','label=geo-planner.stream-owner='+owner['label']],capture_output=True,text=True,check=True,timeout=15)
    require(not query.stdout.strip(),'Opportunity owned worker remains')
    usage=owned_usage(root);mirror.mkdir(parents=True);roster={}
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        before=stat_key(path);name=str(path.relative_to(root))
        with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        require(before==stat_key(path),'Opportunity closed file drift')
        ignored=path.stat().st_size>1048576
        roster[name]={'bytes':path.stat().st_size,'sha256':pin,'ignoredLargeAsset':ignored}
        if not ignored:
            dest=mirror/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    def save(path,value):
        with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    record={'root':OUTPUTS[stage],'roster':roster,'usage':usage,'files':len(roster),'bytes':sum(row['bytes'] for row in roster.values()),'closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save(closed,record);save(absence,{'owner':owner,'independentlyAbsent':True,'queryReturnCode':query.returncode,'containerIds':[]})
    print(json.dumps({'files':record['files'],'bytes':record['bytes'],'usage':usage,'workerAbsent':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['controls','run']);close(parser.parse_args().stage)

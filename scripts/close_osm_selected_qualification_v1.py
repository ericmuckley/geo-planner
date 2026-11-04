"""Close a selected-state qualification attempt without replaying its producer."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_timing_input import require


def close(version):
    require(version in ('v14','v15'),'Selected qualification version')
    repo=Path(__file__).resolve().parents[1];report=repo/'docs/evidence/coarse-osm-extraction-2026-10-30'
    root=repo/('data/coarse-quality/us-osm-country-controls-'+version)
    mirror=report/('qualification-raw/'+version);closed=report/('qualification-closed-'+version+'.json');absence=report/('cleanup-audit-'+version+'.json')
    require(not mirror.exists() and not closed.exists() and not absence.exists(),'Fresh qualification closure required')
    summary=json.loads((root/'run-summary.json').read_bytes());require(summary['status'] in ('stopped','country_screen_synthetic_qualified'),'Qualification terminal summary')
    phases=json.loads((root/'execution-plan.json').read_bytes())['phases'];audits={}
    for phase in phases:
        path=root/phase
        if not path.exists():continue
        cleanup=json.loads((path/'cleanup.json').read_bytes());require(cleanup['removed'] and cleanup['independentInspectAbsent'],'Qualification cleanup')
        owner=json.loads((path/'owner.json').read_bytes())
        query=subprocess.run(['docker','ps','-aq','--filter','label=geo-planner.stream-owner='+owner['label']],capture_output=True,text=True,check=True,timeout=15)
        require(not query.stdout.strip(),'Qualification worker remains')
        audits[phase]={'owner':owner,'independentAbsent':True,'queryReturnCode':query.returncode,'containerIds':[]}
    usage=owned_usage(root);roster={};mirror.mkdir(parents=True)
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        before=stat_key(path);name=str(path.relative_to(root));ignored=path.name=='country-screen.so' or path.name in ('two-million.pbf','two-million-fields.jsonl.gz')
        with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        require(before==stat_key(path),'Qualification closed file drift')
        roster[name]={'bytes':path.stat().st_size,'sha256':pin,'ignoredLargeAsset':ignored}
        if not ignored:
            dest=mirror/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    def save(path,value):
        with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    record={'root':str(root.relative_to(repo)),'roster':roster,'usage':usage,'files':len(roster),'bytes':sum(row['bytes'] for row in roster.values()),'closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save(closed,record);save(absence,audits)
    print(json.dumps({'files':record['files'],'bytes':record['bytes'],'conservativeAllocatedBytes':usage['conservativeAllocatedBytes'],'workersAbsent':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('version',choices=['v14','v15']);close(parser.parse_args().version)

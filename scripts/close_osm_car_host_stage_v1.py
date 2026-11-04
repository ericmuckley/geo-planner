"""Seal a terminal host-only storage/profile stage without replaying it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_full_monitor_v1 import owned_usage

STAGES={
    'spatial-profile':('us-osm-car-spatial-country-profile-v1','spatial-country-profile'),
    'wire-codec':('us-osm-car-wire-codec-v1','wire-codec'),
}


def close(stage):
    repo=Path(__file__).resolve().parents[1];name,prefix=STAGES[stage]
    root=repo/'data/coarse-quality'/name;report=repo/'docs/evidence/coarse-osm-car-capacity-2026-11-01'
    destination=report/(prefix+'-closed-v1.json');mirror=report/(prefix+'-raw-v1')
    assert not destination.exists() and not mirror.exists()
    terminal='report.json' if (root/'report.json').exists() else 'failure.json'
    result=json.loads((root/terminal).read_bytes());assert terminal=='failure.json' or not (root/'failure.json').exists()
    roster={};mirror.mkdir()
    for path in sorted(root.rglob('*')):
        if path.is_dir():continue
        assert path.is_file() and not path.is_symlink()
        before=stat_key(path);size=path.stat().st_size
        with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        assert before==stat_key(path)
        relative=str(path.relative_to(root));ignored=path.suffix!='.json' or size>1048576
        roster[relative]={'bytes':size,'sha256':pin,'ignoredLargeAsset':ignored}
        if not ignored:
            copy=mirror/relative;copy.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,copy)
    record={'root':str(root.relative_to(repo)),'roster':roster,'usage':owned_usage(root),'terminalRecord':terminal,
            'terminalStatus':result.get('status',result.get('error')),
            'scope':'Closed terminal host-only functional stage; no Docker/independent container-absence or app admission claim.',
            'closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with destination.open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
    print(json.dumps({'files':len(roster),'usage':record['usage'],'terminal':terminal}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=STAGES);close(parser.parse_args().stage)

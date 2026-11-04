"""Close the terminal access-only host profile without recomputation."""
from pathlib import Path
import hashlib
import json
import shutil
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_full_monitor_v1 import owned_usage

def close_candidate():
    repo=Path(__file__).resolve().parents[1];root=repo/'data/coarse-quality/us-osm-car-access-candidate-evaluation-v1'
    evidence=repo/'docs/evidence/coarse-osm-car-capacity-2026-11-01';mirror=evidence/'access-candidate-evaluation-raw-v1';mirror.mkdir()
    terminal='report.json' if (root/'report.json').exists() else 'failure.json';result=json.loads((root/terminal).read_bytes());roster={}
    for path in sorted(root.rglob('*')):
        if path.is_dir():continue
        assert path.is_file() and not path.is_symlink();before=stat_key(path);size=path.stat().st_size
        with path.open('rb') as f:pin=hashlib.file_digest(f,'sha256').hexdigest()
        assert before==stat_key(path);name=str(path.relative_to(root));ignored=path.suffix!='.json' or size>1048576
        roster[name]={'bytes':size,'sha256':pin,'ignoredLargeAsset':ignored}
        if not ignored:destination=mirror/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
    record={'root':str(root.relative_to(repo)),'roster':roster,'usage':owned_usage(root),'terminalRecord':terminal,'terminalStatus':result.get('status',result.get('error')),'scope':'Closed terminal host-only access component, not routing or full app admission.','closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with (evidence/'access-candidate-evaluation-closed-v1.json').open('x') as f:json.dump(record,f,indent=2);f.write('\n')
    print(json.dumps({'files':len(roster),'usage':record['usage'],'terminal':terminal}))

if __name__=='__main__':close_candidate()
